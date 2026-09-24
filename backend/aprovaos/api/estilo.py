"""A página de amostra da biblioteca de componentes — `GET /estilo`, só em desenvolvimento.

O que é: o espelho do sistema visual (fatia 14) e a documentação viva dele. Mostra cada
componente de `web/static/css/componentes.css` uma vez, nos três temas, e a **tabela de
contraste medida** a partir do próprio `tokens.css` — o número na tela vem do arquivo, então
não existe a hipótese de a documentação dizer um valor e o produto usar outro. Quando ler: ao
acrescentar um componente à biblioteca — a amostra dele entra em
`web/templates/estilo/pagina.html` no mesmo commit.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from aprovaos.api.templates import renderizar
from aprovaos.config import Configuracoes
from aprovaos.dominio.contraste import MedidaDeContraste, ler_temas, medir_pares

router = APIRouter()

#: Rótulo de cada tema para a tabela — o nome que aparece na tela, não a chave do CSS.
ROTULO_DE_TEMA = {"claro": "Claro", "escuro": "Escuro", "sepia": "Sépia"}


def medir_contraste_dos_tokens(web_dir: Path) -> list[MedidaDeContraste]:
    """Mede o contraste de todos os pares do contrato, em todos os temas, lendo `tokens.css`.

    Lê o disco a cada chamada de propósito: em desenvolvimento a folha muda a cada salvamento, e
    uma tabela em cache mostraria a cor de dois minutos atrás.

    Args:
        web_dir: a pasta `web/` (o mesmo caminho que serve `/static`).

    Returns:
        As medidas na ordem dos temas e dos pares; lista vazia se a folha não existir — a
        amostra perde a tabela, não a página.
    """
    tokens = web_dir / "static" / "css" / "tokens.css"
    try:
        css = tokens.read_text(encoding="utf-8")
    except OSError:
        return []
    return medir_pares(ler_temas(css))


@router.get("/estilo")
def estilo(request: Request) -> HTMLResponse:
    """Mostra a amostra da biblioteca; 404 fora de `AMBIENTE=dev`.

    Não é tela de produto: é ferramenta de quem constrói. Fica fora do ar em produção para não
    virar uma página pública que ninguém mantém.

    Args:
        request: a requisição atual (`app.state.config`).

    Returns:
        O HTML de `estilo/pagina.html`, com as medidas de contraste agrupadas por tema.

    Raises:
        HTTPException: 404 quando `AMBIENTE` não é `dev`.
    """
    config: Configuracoes = request.app.state.config
    if config.ambiente != "dev":
        raise HTTPException(status_code=404)
    medidas = medir_contraste_dos_tokens(request.app.state.web_dir)
    contraste = [
        (ROTULO_DE_TEMA.get(tema, tema), [m for m in medidas if m.tema == tema])
        for tema in ROTULO_DE_TEMA
    ]
    return renderizar(request, "estilo/pagina.html", {"contraste": contraste})
