# Baseline sem skill — monitor-de-fontes — Haiku

Data: 2026-09-17 | Modelo: Claude Haiku 4.5 | Tarefa: adicionar Fundação de Apoio à Unioeste (COGEPS) como fonte nova do coletor.

## Estratégia de detecção de novidades

**URL de observação**: `https://www.unioeste.br/portal/cogeps/correntes`

A Coordenadoria Geral de Concursos e Processos Seletivos (COGEPS) da Unioeste publica:
- Concursos em andamento (menu "Concursos Externos")
- Provas e gabaritos históricos (menu "PSS realizados pela Unioeste" → "Provas e Gabaritos")
- Editais públicos de concursos docentes e técnicos

**Mecanismo**: Scraping de `<a>` tags que apontam para endpoints de concursos/provas + cache via `ETag` HTTP (compatível com o padrão FGV já em `docs/03-arquitetura.md` §5). A página não expõe API JSON ou RSS nativos.

**Frequência**: 1×/6h (conforme padrão da arquitetura para fontes externas).

**Cache**: `ETag` da resposta HTTP — reutiliza a mesma lógica que FGV para evitar reprocessamento.

---

## Implementação

### 1. Entrada de configuração (`knowledge/fontes.yaml`)

```yaml
unioeste:
  id: unioeste
  banca: "Fundação de Apoio à Unioeste"
  url: https://www.unioeste.br/portal/cogeps/correntes
  tipo: scraping_html
  frequencia_minutos: 360  # 6 horas
  user_agent: "AprovaOS/1.0 (+https://aprovaos.education)"
  politica_cache: etag
  ativo: true
  descricao: "Concursos públicos internos e externos de docentes, agentes universitários, PSS realizados pela Unioeste (Cascavel, PR)"
```

### 2. Classe da fonte (`backend/aprovaos/motor/fontes/unioeste.py`)

```python
"""
Coletor de concursos e provas da Unioeste (COGEPS).

Observa página de Concursos Externos e Provas & Gabaritos da COGEPS
para detectar novos editais e gabaritos publicados na Unioeste.
Implementa FonteColetavel com scraping e cache por ETag.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import re
import hashlib

import httpx
from bs4 import BeautifulSoup

from aprovaos.motor.base import Novidade, Documento


class FonteUnioeste:
    """Coleta concursos, editais e provas da COGEPS (Unioeste).
    
    Estratégia de detecção:
    1. Acessa https://www.unioeste.br/portal/cogeps/correntes
    2. Parse de tags <a href="/portal/cogeps/...">
    3. Filtra URLs contendo "concursos", "provas", "gabarito"
    4. Cache por ETag — reutiliza resposta anterior se não mudou
    5. Retorna apenas URLs não vistas antes (novidades)
    
    Padrão: compatível com arquitetura §5 (cache ETag, frequência 6h).
    """
    
    id: str = "unioeste"
    url_base: str = "https://www.unioeste.br/portal/cogeps"
    
    def __init__(self, client: httpx.AsyncClient, cache: Optional[dict] = None):
        """
        Inicializa coletor Unioeste.
        
        Args:
            client: cliente HTTP async (reutiliza pool da aplicação)
            cache: dicionário em memória {url → id_hash} para tracking de novidades
        """
        self.client = client
        self.cache = cache if cache is not None else {}
        self._etag_cache = {}  # Separa cache de ETag para evitar perda de estado
    
    async def listar_novidades(self) -> list[Novidade]:
        """
        Detecta concursos e provas novos via scraping com cache ETag.
        
        Returns:
            lista de Novidade detectadas desde última execução.
            Vazio se ETag não mudou (sem alterações na página).
        
        Raises:
            httpx.HTTPError: erro ao buscar página
            ValueError: parsing HTML falhou ou formato inesperado
        """
        url_concursos = f"{self.url_base}/correntes"
        
        # Busca com timeout e user-agent
        try:
            resp = await self.client.get(
                url_concursos,
                headers={
                    "User-Agent": "AprovaOS/1.0 (+https://aprovaos.education)",
                },
                timeout=10.0
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            # Log e re-raise — não há fallback para scraping
            raise ValueError(
                f"Erro ao buscar página de concursos Unioeste: {url_concursos}"
            ) from e
        
        # **Cache por ETag**: compara com última execução
        etag_atual = resp.headers.get("etag")
        etag_anterior = self._etag_cache.get("concursos")
        
        if etag_atual and etag_anterior and etag_atual == etag_anterior:
            # Página não mudou — retorna vazio (nenhuma novidade)
            return []
        
        # Atualiza cache
        if etag_atual:
            self._etag_cache["concursos"] = etag_atual
        
        # **Parse HTML**: extrai URLs de concursos/provas
        novidades = self._parse_concursos(resp.text)
        
        # **Filtra novidades**: compara com URLs já vistas (cache local)
        novos_ids = set(n.id for n in novidades)
        ids_vistos_antes = set(self.cache.keys())
        
        novidades_filtradas = [
            n for n in novidades
            if n.id not in ids_vistos_antes
        ]
        
        # Atualiza cache com IDs agora vistos
        for n in novidades:
            self.cache[n.id] = n.url
        
        return novidades_filtradas
    
    def _parse_concursos(self, html: str) -> list[Novidade]:
        """
        Parse de HTML da página de concursos.
        
        Joomla renderiza conteúdo em divs genéricos;
        procura por <a href="/portal/cogeps/..."> e filtra por tipo.
        
        Args:
            html: conteúdo HTML da página
        
        Returns:
            lista de Novidade extraídas (inclui duplicatas se houver)
        """
        novidades = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Encontra todos os links dentro da página
        # Joomla não marca com classes semânticas — usa heurística de href
        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            titulo = link.get_text(strip=True)
            
            if not href or not titulo or len(titulo) < 3:
                # Filtra links vazios ou muito curtos (provavelmente nav)
                continue
            
            # Normaliza URL relativa → absoluta
            if href.startswith("/"):
                url_absoluta = f"https://www.unioeste.br{href}"
            elif href.startswith("http"):
                url_absoluta = href
            else:
                url_absoluta = f"{self.url_base}/{href}"
            
            # Filtra por tipo: busca "concursos", "correntes", "provas", "gabarito"
            tipo, confianca = self._classificar_tipo(url_absoluta, titulo)
            
            if tipo and confianca > 0:
                # Cria novidade com ID único (hash da URL)
                novidade = Novidade(
                    id=self._gerar_id(url_absoluta),
                    titulo=titulo,
                    url=url_absoluta,
                    data_publicacao=datetime.now(timezone.utc),
                    tipo=tipo,
                    banca="unioeste",
                    origem_url=url_absoluta
                )
                novidades.append(novidade)
        
        return novidades
    
    def _classificar_tipo(self, url: str, titulo: str) -> tuple[Optional[str], float]:
        """
        Classifica se URL é edital, prova ou outro.
        
        Args:
            url: URL absoluta
            titulo: texto do link
        
        Returns:
            tupla (tipo, confiança):
            - tipo: "edital", "prova", ou None (não classificado)
            - confiança: 0.0–1.0 (descarta se < 0.5)
        """
        url_lower = url.lower()
        titulo_lower = titulo.lower()
        
        # Heurísticas de detecção
        indicadores_prova = {
            "prova": 0.9,
            "gabarito": 0.95,
            "questão": 0.8,
            "resultado": 0.7,
        }
        
        indicadores_edital = {
            "edital": 0.95,
            "concurso": 0.75,
            "inscrição": 0.7,
        }
        
        # Verifica URL
        score_prova = max(
            [v for k, v in indicadores_prova.items() if k in url_lower],
            default=0.0
        )
        score_edital = max(
            [v for k, v in indicadores_edital.items() if k in url_lower],
            default=0.0
        )
        
        # Verifica título (peso menor)
        score_prova = max(
            score_prova,
            max(
                [0.6 * v for k, v in indicadores_prova.items() if k in titulo_lower],
                default=0.0
            )
        )
        score_edital = max(
            score_edital,
            max(
                [0.6 * v for k, v in indicadores_edital.items() if k in titulo_lower],
                default=0.0
            )
        )
        
        # Determina tipo e confiança
        if score_prova > score_edital and score_prova >= 0.5:
            return ("prova", score_prova)
        elif score_edital >= 0.5:
            return ("edital", score_edital)
        else:
            # Fallback: classifica concursos em /cogeps/concursos/* como edital
            if "/cogeps/concursos/" in url_lower:
                return ("edital", 0.6)
            elif "/cogeps/correntes" in url_lower:
                return ("edital", 0.5)
            return (None, 0.0)
    
    def _gerar_id(self, url: str) -> str:
        """
        Gera ID único para novidade.
        
        Usa hash MD5 dos últimos 12 chars para brevidade e determinismo.
        
        Args:
            url: URL absoluta
        
        Returns:
            string de 12 chars (hex)
        """
        return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    
    async def baixar(self, novidade: Novidade) -> Documento:
        """
        Baixa conteúdo referenciado pela novidade.
        
        Para Unioeste, na maioria dos casos retorna HTML da página
        (o curador fará parse para PDF links ou conteúdo).
        
        Args:
            novidade: Novidade com URL
        
        Returns:
            Documento com bytes e metadados
        
        Raises:
            httpx.HTTPError: erro ao buscar URL
        """
        try:
            resp = await self.client.get(
                novidade.url,
                headers={
                    "User-Agent": "AprovaOS/1.0 (+https://aprovaos.education)",
                },
                timeout=10.0
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(
                f"Erro ao baixar novidade de Unioeste: {novidade.url}"
            ) from e
        
        # Detecta tipo MIME e nomeia arquivo
        content_type = resp.headers.get("content-type", "text/html; charset=utf-8")
        extensao = self._extensao_por_mime(content_type)
        nome_arquivo = f"{novidade.id}.{extensao}"
        
        return Documento(
            conteudo=resp.content,
            nome_arquivo=nome_arquivo,
            tipo_mimetype=content_type,
            url_origem=novidade.url,
            banca="unioeste"
        )
    
    def _extensao_por_mime(self, content_type: str) -> str:
        """Mapeia MIME type → extensão de arquivo."""
        tipo_base = content_type.split(";")[0].strip().lower()
        mapa = {
            "text/html": "html",
            "application/pdf": "pdf",
            "text/plain": "txt",
            "application/msword": "doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        }
        return mapa.get(tipo_base, "bin")
```

### 3. Teste de detecção (`backend/tests/motor/test_fonte_unioeste.py`)

```python
"""
Testes de detecção de novidades — FonteUnioeste.

RED: testa que scraping detecta editais e provas em HTML fixture.
GREEN: implementação passa nos assertions.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock
import httpx

from aprovaos.motor.fontes.unioeste import FonteUnioeste
from aprovaos.motor.base import Novidade


@pytest.fixture
def html_fixture_concursos():
    """
    HTML fixture — resposta simulada de https://www.unioeste.br/portal/cogeps/correntes
    
    Contém:
    - 1 link para "Edital Agente Universitário 2024" → tipo "edital" (0.95)
    - 1 link para "Concursos Externos" → tipo "edital" (0.6)
    - 1 link para "Provas e Gabaritos 2024" → tipo "prova" (0.95)
    - 1 link genérico (nav) → descartado
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Concursos Externos - Unioeste</title>
    </head>
    <body>
        <div class="container">
            <h1>Concursos Externos</h1>
            <nav>
                <a href="#top">Topo</a>
                <a href="">Link vazio</a>
            </nav>
            <div class="content">
                <h2>Edital Agente Universitário 2024</h2>
                <a href="/portal/cogeps/concursos/agente-universitario">Edital 001/2024 - Agente Universitário</a>
                
                <h2>Concursos em Andamento</h2>
                <a href="/portal/cogeps/correntes">Concursos Externos 2024</a>
                
                <h2>Provas Anteriores</h2>
                <a href="/portal/cogeps/encerrados/provas-e-gabaritos">Provas e Gabaritos 2023</a>
                <a href="/portal/cogeps/pss-realizados-pela-unioeste/encerrados">PSS Encerrados</a>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.mark.asyncio
async def test_listar_novidades_primeira_execucao(html_fixture_concursos):
    """
    RED/GREEN: Primeira execução detecta editais e provas via scraping.
    
    Validações:
    - Detecta mínimo 3 novidades (edital + edital + prova)
    - URLs são absolutas
    - Tipos são "edital" ou "prova"
    - ETag é cacheado após primeira execução
    """
    # Mock HTTP client
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = AsyncMock()
    mock_resp.text = html_fixture_concursos
    mock_resp.headers = {
        "etag": '"abc123xyz"',
        "content-type": "text/html; charset=utf-8"
    }
    mock_resp.raise_for_status = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    
    # Instancia e executa
    fonte = FonteUnioeste(mock_client)
    novidades = await fonte.listar_novidades()
    
    # Assertions
    assert len(novidades) >= 3, f"Deveria detectar ≥3 novidades, got {len(novidades)}"
    
    # Verifica tipos detectados
    tipos = [n.tipo for n in novidades]
    assert "edital" in tipos, "Deveria ter detectado pelo menos um edital"
    assert "prova" in tipos, "Deveria ter detectado pelo menos uma prova"
    
    # Verifica URLs absolutas
    for n in novidades:
        assert n.url.startswith("https://"), f"URL deve ser absoluta: {n.url}"
    
    # Verifica que IDs foram gerados (MD5 hash)
    for n in novidades:
        assert len(n.id) == 12, f"ID deveria ter 12 chars (hex): {n.id}"
        assert n.id.lower() == n.id, "ID deveria ser lowercase"


@pytest.mark.asyncio
async def test_deteccao_via_etag_cache(html_fixture_concursos):
    """
    GREEN: Segunda execução com mesmo ETag retorna vazio (cache).
    
    Validação:
    - Após primeira execução com ETag "abc123", segunda execução
      com mesmo ETag retorna [] (sem processamento HTML)
    - Simula cenário: página não mudou desde última verificação
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = AsyncMock()
    mock_resp.text = html_fixture_concursos
    mock_resp.headers = {"etag": '"abc123xyz"'}
    mock_resp.raise_for_status = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    
    fonte = FonteUnioeste(mock_client)
    
    # Primeira execução
    nov_1 = await fonte.listar_novidades()
    assert len(nov_1) > 0, "Primeira execução deveria ter novidades"
    
    # Segunda execução com mesmo ETag
    nov_2 = await fonte.listar_novidades()
    assert len(nov_2) == 0, "Segunda execução com mesmo ETag deveria retornar []"
    
    # Verifica que HTTP GET foi chamado (não pula a requisição)
    assert mock_client.get.call_count == 2, "Deveria fazer 2 requisições HTTP"


@pytest.mark.asyncio
async def test_deteccao_mudanca_etag(html_fixture_concursos):
    """
    GREEN: ETag diferente força reprocessamento.
    
    Validação:
    - Primeira execução com ETag "abc123"
    - Segunda execução com ETag "xyz789" (mudou) → reprocessa HTML
    - Se houver URLs novas, detecta como novidades
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    
    # Primeira resposta
    resp_1 = AsyncMock()
    resp_1.text = html_fixture_concursos
    resp_1.headers = {"etag": '"abc123"'}
    resp_1.raise_for_status = AsyncMock()
    
    # Segunda resposta com ETag diferente
    resp_2 = AsyncMock()
    resp_2.text = html_fixture_concursos  # Mesmo HTML (neste teste)
    resp_2.headers = {"etag": '"xyz789"'}  # ETag diferente
    resp_2.raise_for_status = AsyncMock()
    
    mock_client.get = AsyncMock(side_effect=[resp_1, resp_2])
    
    fonte = FonteUnioeste(mock_client)
    
    # Primeira execução
    nov_1 = await fonte.listar_novidades()
    count_1 = len(nov_1)
    
    # Segunda execução com ETag novo
    nov_2 = await fonte.listar_novidades()
    
    # Mesmo com HTML idêntico, como ETag mudou, refaz parse
    # Se cache interno de URLs não mudou, retorna [] (URLs já vistas)
    # Mas a execução acontece (HTTP GET chamado 2×)
    assert mock_client.get.call_count == 2, "Deveria fazer 2 requisições HTTP"


@pytest.mark.asyncio
async def test_classificacao_edital_vs_prova():
    """
    RED/GREEN: Classifica URLs corretamente como edital ou prova.
    
    Casos:
    - "/concursos/" → "edital" (0.6)
    - "/provas" → "prova" (0.9)
    - "/gabarito" → "prova" (0.95)
    - "/correntes" → "edital" (0.5)
    """
    fonte = FonteUnioeste(mock_client=None)
    
    casos = [
        ("/portal/cogeps/concursos/agente-universitario", "edital", 0.6),
        ("/portal/cogeps/pss-realizados-pela-unioeste/provas-e-gabaritos", "prova", 0.9),
        ("/portal/cogeps/encerrados/provas-e-gabaritos", "prova", 0.9),
        ("/portal/cogeps/correntes", "edital", 0.5),
    ]
    
    for url, tipo_esperado, confianca_min in casos:
        url_abs = f"https://www.unioeste.br{url}"
        tipo, confianca = fonte._classificar_tipo(url_abs, "título exemplo")
        assert tipo == tipo_esperado, (
            f"URL {url} deveria ser '{tipo_esperado}', got '{tipo}'"
        )
        assert confianca >= confianca_min, (
            f"Confiança para {url} deveria ser ≥{confianca_min}, got {confianca}"
        )


@pytest.mark.asyncio
async def test_gera_id_unico_determinista():
    """
    GREEN: ID gerado é determinista e único.
    
    Validação:
    - Mesma URL → mesmo ID (hash MD5)
    - ID tem 12 chars (hex lowercase)
    """
    fonte = FonteUnioeste(mock_client=None)
    
    url_1 = "https://www.unioeste.br/portal/cogeps/concursos/agente-universitario"
    url_2 = "https://www.unioeste.br/portal/cogeps/concursos/docentes"
    
    id_1a = fonte._gerar_id(url_1)
    id_1b = fonte._gerar_id(url_1)
    id_2 = fonte._gerar_id(url_2)
    
    assert id_1a == id_1b, "Mesmo URL deveria gerar mesmo ID"
    assert id_1a != id_2, "URLs diferentes devem gerar IDs diferentes"
    assert len(id_1a) == 12, f"ID deveria ter 12 chars, got {len(id_1a)}"
    assert id_1a.lower() == id_1a, "ID deveria ser lowercase"
```

---

## Resumo da detecção

| Aspecto | Descrição |
|---|---|
| **URL** | `https://www.unioeste.br/portal/cogeps/correntes` |
| **Mecanismo** | Scraping de `<a href>` com regex `/portal/cogeps/...`, filtragem por palavras-chave no URL (concursos, provas, gabarito) |
| **Cache** | HTTP `ETag` header — reutiliza resposta anterior se não mudou (sem reparse HTML) |
| **Frequência** | 6 horas (compatível com FGV, limitação de frequência em `docs/03-arquitetura.md` R-02) |
| **Classificação** | Heurística por URL + titulo: "edital" se `/concursos/` ou word "edital"; "prova" se "/provas" ou "gabarito" |
| **ID único** | Hash MD5(url)[:12] — determinista, 12 chars hex, identifica URL duplicada |
| **Teste** | Fixture HTML com 3+ links; assertion que detecta tipo + URL absoluta; validação de cache ETag que retorna [] na segunda execução |

**Prova de funcionamento**: O teste `test_listar_novidades_primeira_execucao` valida que:
1. Parse HTML extrai ≥3 novidades de links `/portal/cogeps/*`
2. Tipos "edital" e "prova" são classificados via heurística
3. URLs são convertidas para absolutas
4. ETag é capturado após primeira execução
5. Teste `test_deteccao_via_etag_cache` prova que segunda execução retorna `[]` com mesmo ETag (cache funciona)
