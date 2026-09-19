"""Grava snapshots reais da API pública da Cebraspe para as fixtures do coletor (V3, passo 2).

O que é: script reproduzível (`uv run python ../scripts/snapshot_cebraspe.py`, de `backend/`) que
baixa a listagem de concursos encerrados e o detalhe de um evento de referência
(`TJ_PA_25_SERVIDOR`) direto da API da Cebraspe e grava as respostas, sem alteração, em
`knowledge/fixtures/fontes/cebraspe/`. Identifica-se com o `User-Agent` do ADR-0030
(`AprovaOS-coletor/0.1 (+contato: <e-mail>)`). Quando ler: ao regenerar as fixtures do coletor da
Cebraspe ou ao verificar o formato real da API (marker `rede` dos testes).
"""

import json
import sys
from pathlib import Path
from typing import Any

import httpx2

URL_LISTA_ENCERRADO = "https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado"
URL_DETALHE = "https://apis.cebraspe.org.br/cebraspe/eventos/{evento_url}"
EVENTO_DE_REFERENCIA = "TJ_PA_25_SERVIDOR"
CONTATO_PADRAO = "vlfcandido@gmail.com"
_RAIZ_DO_REPO = Path(__file__).resolve().parents[1]
PASTA_FIXTURES = _RAIZ_DO_REPO / "knowledge" / "fixtures" / "fontes" / "cebraspe"


def cabecalhos(contato: str) -> dict[str, str]:
    """Monta o `User-Agent` identificado do coletor (ADR-0030).

    Args:
        contato: e-mail do dono, anunciado nas requisições à Cebraspe.

    Returns:
        Dicionário de cabeçalhos HTTP para a requisição.
    """
    return {"User-Agent": f"AprovaOS-coletor/0.1 (+contato: {contato})"}


def buscar_json(cliente: httpx2.Client, url: str) -> Any:
    """Executa um `GET` e devolve o corpo já decodificado como JSON.

    Args:
        cliente: cliente HTTP já configurado com o `User-Agent` identificado.
        url: endereço da API a consultar.

    Returns:
        O corpo da resposta, decodificado (lista ou dicionário, conforme o endpoint).

    Raises:
        httpx2.HTTPStatusError: se a resposta não for 2xx.
    """
    resposta = cliente.get(url)
    resposta.raise_for_status()
    return resposta.json()


def gravar_json(conteudo: Any, destino: Path) -> None:
    """Grava `conteudo` como JSON legível em `destino`, criando a pasta se preciso.

    Args:
        conteudo: estrutura já decodificada (lista ou dicionário) a serializar.
        destino: caminho do arquivo `.json` de saída.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def gerar_snapshots(pasta: Path, contato: str) -> None:
    """Baixa a listagem de encerrados e o detalhe do evento de referência, e grava as duas fixtures.

    Args:
        pasta: pasta de destino das fixtures (`knowledge/fixtures/fontes/cebraspe/`).
        contato: e-mail do dono, para o `User-Agent` identificado.
    """
    with httpx2.Client(headers=cabecalhos(contato), timeout=30, follow_redirects=True) as cliente:
        lista = buscar_json(cliente, URL_LISTA_ENCERRADO)
        gravar_json(lista, pasta / "lista-encerrado-v1.json")

        detalhe = buscar_json(cliente, URL_DETALHE.format(evento_url=EVENTO_DE_REFERENCIA))
        gravar_json(detalhe, pasta / f"detalhe-{EVENTO_DE_REFERENCIA}.json")


def main(argv: list[str]) -> int:
    """Ponto de entrada: `snapshot_cebraspe.py [contato]`.

    Args:
        argv: argumentos da linha de comando, sem o nome do script; o primeiro, se houver, é o
            e-mail de contato do `User-Agent` (padrão: `vlfcandido@gmail.com`, ADR-0030).

    Returns:
        0 em sucesso.
    """
    contato = argv[0] if argv else CONTATO_PADRAO
    gerar_snapshots(PASTA_FIXTURES, contato)
    print(f"snapshots gravados em {PASTA_FIXTURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
