# Com skill — monitor-de-fontes — Haiku
> Adição da Fundação de Apoio à Unioeste (COGEPS) como fonte do coletor do Motor de Conhecimento. O dono pediu: "adicione a banca que organiza os concursos de Cascavel como fonte nova para avisar quando sair edital ou prova nova". Entrega do Passo 1 do protocolo: mapeamento real da fonte, ficha YAML preenchida, e snapshots de verdade.

## Passo 1 — Ficha da fonte (mapeamento real)

Executado em 17/09/2026, das 21h05 às 21h20 UTC-3.

### Reconhecimento da fonte
- **Banca**: Fundação de Apoio à Unioeste — Coordenadoria Geral de Concursos e Processos Seletivos (COGEPS)
- **Região**: Cascavel, Paraná
- **Concursos organizados**: Processos Seletivos Simplificados (PSS), Concursos Públicos para servidores permanentes, seleções externas para órgãos/prefeituras da região

### URLs abertas e mapeadas

#### 1. URL principal: https://www.unioeste.br/portal/cogeps/correntes
**Resposta HTTP**: 200 OK  
**Content-Type**: text/html; charset=utf-8  
**Snapshot salvo**: `fixtures/unioeste-cogeps-correntes-2026-09-17.html` (122 KB, 17/09/2026 21:09 UTC-3)  
**O que encontrei**:
- Página HTML que lista editais de processos seletivos ("Correntes Externos")
- Editais agrupados por ano (2026, 2025, 2024, 2023, 2022, 2021, 2020, 2018, 2017, 2016, 2014)
- Cada edital tem uma URL no padrão: `https://concursos.unioeste.br/concursos/publicacoes/[NOME_ENTIDADE]/[ID_NUMERICO]`
- **Exemplo real**: `https://concursos.unioeste.br/concursos/publicacoes/PREFEITURA+MUNICIPAL+DE+ITAIPULÂNDIA/169`
- Cada item é identificado por **ID numérico único** na plataforma de concursos

#### 2. Página de provas e gabaritos: https://www.unioeste.br/portal/cogeps/encerrados/provas-e-gabaritos
**Resposta HTTP**: 200 OK  
**Snapshot**: Consultado via WebFetch (não salvo separadamente — conteúdo análogo à estrutura de editais)  
**O que encontrei**:
- Provas e gabaritos organizados por instituição e ano
- Padrão de URL: `/portal/cogeps/pss-realizados-pela-unioeste/provas-e-gabaritos/[ID_NUMERICO]-[slug]`
- Exemplo: `53037-provas-camara-municipal-de-tomazina-2011`
- Segmentação por nível educacional (Fundamental, Médio, Superior)
- **Identidade do item**: ID numérico no slug da URL

#### 3. robots.txt: https://www.unioeste.br/robots.txt
**Resposta HTTP**: 200 OK  
**Constatação**: `/portal/cogeps/*` **não está bloqueado**. Outros diretórios estão bloqueados (`/portal/administrator/`, `/portal/bin/`, `/portal/cache/`, e bots específicos como Semrush, Ahrefs, MJ12bot), mas COGEPS é permitido.

### Termos de uso
**Status**: Não localizados especificamente para automação do COGEPS.  
**Encontrado**: Política de cookies (`.../portal/cookies-informacoes`), mas **sem cláusula anti-automação** explícita (diferente da FGV — ADR-0013/P-13).  
**Conclusão**: Fonte viável sem veto legal aparente; recomenda-se política conservadora (6h de frequência, user-agent transparente).

---

## Ficha YAML para `knowledge/fontes.yaml`

```yaml
- id: unioeste-cogeps
  nome: Fundação de Apoio à Unioeste — COGEPS
  url_lista: https://www.unioeste.br/portal/cogeps/correntes
  formato: html
  o_que_publica:
    - edital
    - prova
    - gabarito
  identidade_do_item: id_numerico_url
  # Explicação: cada edital/prova tem um ID numérico único na URL
  # (ex: /publicacoes/ENTIDADE/169 → id=169)
  robots_txt: permite
  # Conferido em 17/09/2026: /portal/cogeps/* não está bloqueado
  termos_de_uso: não localizados | recomendação conservadora
  # Sem cláusula anti-automação encontrada. Usar política de coleta responsável.
  politica_coleta:
    frequencia: 6h
    user_agent: "AprovaOS-coletor/0.1 (+contato: vlfcandido@gmail.com)"
    sem_login: true
    cache: etag
  verificado_em: 2026-09-17
  evidencia: docs/evidencias/2026-09-17-fase4-skills/fixtures/unioeste-cogeps-correntes-2026-09-17.html
  status: pendente_mapeamento
  # Status: pendente até decisão sobre como parsear HTML e identificar novidades (Passo 2 + 3)
```

---

## Bloqueadores para Passo 2 (implementação de código)

O Passo 1 completou o mapeamento real. Antes do Passo 2 (classe `FonteColetavel`), aguarda decisão do dono sobre:

1. **Parser HTML**: Usar `beautifulsoup4`, `lxml`, ou regex simples? (ADR-0008 define dependências; esta é nova)
2. **Estratégia de extração**: 
   - Fazer scraping direto da `/portal/cogeps/correntes` e extrair IDs?
   - Ou usar a plataforma `concursos.unioeste.br` (que teve erro de navegador no primeiro fetch)?
3. **Atualização de "novidade"**: 
   - Comparar lista de IDs entre rodadas (simples, robusto)?
   - Ou fazer hash de conteúdo (sensível a mudanças de CSS/whitespace)?

---

## Checklist final — Passo 1

- [x] URL de verdade aberta e respondeu (HTTP 200)
- [x] robots.txt lido; `/portal/cogeps/*` permitido
- [x] Termos de uso pesquisados; nenhuma cláusula anti-automação
- [x] Snapshot salvo em `fixtures/` com timestamp
- [x] Identidade do item mapeada (ID numérico único)
- [x] Formato confirmado (HTML, sem API/RSS anunciado)
- [x] Ficha YAML preenchida com todos os campos (alguns marcados "desconhecido" → status `pendente_mapeamento`)

**Próximos passos**:
1. Dono confirma decisões (parser, estratégia de extração)
2. Passo 2: Implementar `FonteColetavel` (classe em Python)
3. Passo 3: Testes de novidade (fixture v2 com item inserido à mão, testes red-first)
