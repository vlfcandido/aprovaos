"""O comando de coleta: prova + gabarito de Direito de um evento da Cebraspe.

O que é: `arquivos_do_cargo` (filtra pelo cargo pedido, só o caderno de conhecimentos
específicos), `cargo_de_direito` (acha esse cargo no `eventoCargos` do detalhe — o número varia
por concurso, nunca é fixo, e o cargo jurídico nem sempre diz "Direito": nos tribunais costuma
ser "Analista Judiciário — Área Judiciária"), `parear` (casa prova com gabarito) e `coletar_par`
(baixa, grava em disco e persiste os dois `Documento`, com dedup por hash). `main()` é o
`argparse` que roda tudo isso para um evento: `--evento`, `--cargo` (opcional; descoberto sozinho
quando omitido) e `--listar` (só mostra, não baixa). Passo 5 do plano
`docs/fatias/V3-questoes-cebraspe.md`.

Nenhuma execução acontece em import: `main()` só roda sob `if __name__ == "__main__"`, e é quem
abre a fonte (`criar_fonte_cebraspe`, com `with` — fecha o cliente HTTP ao sair) e o engine do
banco — o dono desse ciclo de vida é este módulo.

Quando ler: antes de rodar a coleta de um concurso novo, ou ao investigar por que um cargo de
Direito não foi encontrado.
"""

import argparse
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aprovaos.config import Configuracoes, obter_configuracoes
from aprovaos.dados.base import agora_utc
from aprovaos.dados.conexao import criar_engine, criar_fabrica_sessao
from aprovaos.dados.modelos import Documento
from aprovaos.motor.fontes.base import FonteColetavel, Novidade
from aprovaos.motor.fontes.cebraspe import CargoEvento, FonteCebraspe, criar_fonte_cebraspe

_ARQUIVOS_DO_CARGO_TIPOS = ("prova", "gabarito")
_PADRAO_NUMERO_DO_CARGO = re.compile(r"CARGO\s+(\d+)", re.IGNORECASE)
_RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]

# Léxico do cargo de Direito: nos tribunais o cargo jurídico costuma se chamar "Analista
# Judiciário — Área Judiciária", sem a palavra "Direito" — por isso o léxico não é só "DIREITO"
# (regra corrigida na rodada 1 de revisão do passo 5). Comparação sempre sem acento/maiúsculas
# (`_normalizar`), porque a API mistura os dois estilos entre eventos.
_TERMOS_CARGO_DE_DIREITO = ("DIREITO", "JUDICIARIA", "JURIDICA", "JURIDICO")
_TERMOS_NIVEL_SUPERIOR = ("ANALISTA", "PROCURADOR")
_TERMO_ESPECIFICOS = "ESPECIFICOS"


class ParDeProva(BaseModel):
    """Prova e gabarito definitivo do mesmo cargo, no mesmo evento.

    Attributes:
        prova: a novidade de tipo `"prova"`.
        gabarito: a novidade de tipo `"gabarito"`, do mesmo evento.
    """

    prova: Novidade
    gabarito: Novidade


class ProvaSemGabarito(RuntimeError):
    """Um evento tem prova sem gabarito (ou gabarito sem prova) para o cargo pedido.

    A V3 nunca substitui o par por outro cargo nem inventa o arquivo que falta — o evento é
    pulado e o motivo vai para o relatório (decisão do dono, passo 5).
    """


def resolver_documentos_dir(config: Configuracoes) -> Path:
    """Resolve a pasta onde os PDFs de prova/gabarito são gravados.

    Args:
        config: configurações do backend.

    Returns:
        `config.documentos_dir` quando definido; senão `knowledge/provas` na raiz do
        repositório (`config.documentos_dir` é `None` por padrão).
    """
    if config.documentos_dir is not None:
        return config.documentos_dir
    return _RAIZ_DO_REPOSITORIO / "knowledge" / "provas"


def _numero_do_cargo(area: str) -> int:
    """Extrai o número de `"CARGO 9: ..."` → `9`.

    Args:
        area: o texto de `CargoEvento.area`.

    Returns:
        O número do cargo.

    Raises:
        ValueError: `area` não começa com o padrão `"CARGO <número>"`.
    """
    encontrado = _PADRAO_NUMERO_DO_CARGO.search(area)
    if encontrado is None:
        raise ValueError(f"área sem número de cargo reconhecível: {area!r}")
    return int(encontrado.group(1))


def _normalizar(texto: str) -> str:
    """Maiúsculas e sem acento.

    Para comparar termos que a API escreve de formas diferentes entre eventos (`"Área:
    Judiciária"` num, `"ÁREA: JUDICIÁRIA"` noutro).
    """
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.upper()


def _cargos_pelo_lexico(cargos: list[CargoEvento]) -> list[CargoEvento]:
    """Cargos cuja `area` casa o léxico de Direito (`_TERMOS_CARGO_DE_DIREITO`), na ordem da API."""
    return [
        cargo
        for cargo in cargos
        if any(termo in _normalizar(cargo.area) for termo in _TERMOS_CARGO_DE_DIREITO)
    ]


def cargo_de_direito(cargos: list[CargoEvento]) -> list[tuple[int, str]]:
    """Acha, entre os cargos do evento, o(s) cargo(s) de Direito.

    Casa `area` (sem acento, maiúsculas) contra o léxico "DIREITO", "JUDICIÁRIA", "JURÍDICA",
    "JURÍDICO" — nos tribunais o cargo jurídico costuma se chamar "Analista Judiciário — Área
    Judiciária", sem a palavra "Direito". Mais de um cargo casando o léxico prefere os de nível
    superior ("Analista"/"Procurador"); persistindo o empate (dois de nível superior, ou nenhum),
    devolve todos — mais barato coletar demais do que arriscar excluir o cargo certo.

    Args:
        cargos: os cargos do evento (`FonteCebraspe.cargos_do_evento`).

    Returns:
        `[(número do cargo, texto da área), ...]`, na ordem da API — vazia quando nenhum cargo
        casa o léxico (nunca um palpite).
    """
    achados = _cargos_pelo_lexico(cargos)
    if len(achados) > 1:
        nivel_superior = [
            cargo
            for cargo in achados
            if any(termo in _normalizar(cargo.area) for termo in _TERMOS_NIVEL_SUPERIOR)
        ]
        if nivel_superior:
            achados = nivel_superior
    return [(_numero_do_cargo(cargo.area), cargo.area) for cargo in achados]


def _termina_no_cargo(titulo: str, cargo_numero: int) -> bool:
    """`True` quando `titulo` termina exatamente em `"CARGO <cargo_numero>"`.

    A âncora de fim de string é o que exclui os cadernos de "conhecimentos gerais para os
    cargos 1, 2, 6, 8, 9, 18 e 22" mesmo quando citam o número pedido no meio da lista — e evita
    que `cargo_numero=1` capture `"CARGO 11"`.
    """
    return re.search(rf"CARGO\s+{cargo_numero}\s*$", titulo.strip()) is not None


def arquivos_do_cargo(novidades: list[Novidade], cargo_numero: int) -> list[Novidade]:
    """Filtra os arquivos de prova/gabarito de conhecimentos específicos de um cargo.

    Args:
        novidades: arquivos do evento (`FonteCebraspe.arquivos_do_evento`).
        cargo_numero: o número do cargo (achado por `cargo_de_direito` ou passado por `--cargo`).

    Returns:
        Os arquivos `tipo in ("prova", "gabarito")` cujo título termina em `"CARGO
        <cargo_numero>"` **e** contém "ESPECÍFICOS" — nunca os cadernos de conhecimentos gerais
        (mesmo que citem o cargo) nem os de "conhecimentos básicos para o cargo N" (achado real
        no STJ_24: o cargo 19 tem um caderno básico e um específico, os dois terminando em
        "CARGO 19"; só o específico é o que a V3 quer).
    """
    return [
        novidade
        for novidade in novidades
        if novidade.tipo in _ARQUIVOS_DO_CARGO_TIPOS
        and _termina_no_cargo(novidade.titulo, cargo_numero)
        and _TERMO_ESPECIFICOS in _normalizar(novidade.titulo)
    ]


def parear(arquivos: list[Novidade]) -> list[ParDeProva]:
    """Casa prova com gabarito, agrupando por evento.

    Args:
        arquivos: arquivos já filtrados por `arquivos_do_cargo` (um cargo, um ou mais eventos).

    Returns:
        Um `ParDeProva` por evento presente em `arquivos`.

    Raises:
        ProvaSemGabarito: algum evento tem só prova ou só gabarito.
    """
    por_evento: dict[str, dict[str, Novidade]] = {}
    for arquivo in arquivos:
        por_evento.setdefault(arquivo.evento, {})[arquivo.tipo] = arquivo

    pares: list[ParDeProva] = []
    for evento, achados in por_evento.items():
        prova = achados.get("prova")
        gabarito = achados.get("gabarito")
        if prova is None or gabarito is None:
            faltando = "prova" if prova is None else "gabarito"
            raise ProvaSemGabarito(f"evento {evento}: falta {faltando} para este cargo")
        pares.append(ParDeProva(prova=prova, gabarito=gabarito))
    return pares


def _nome_do_arquivo(novidade: Novidade) -> str:
    """`"{evento}/{nomeArquivo}"` (a identidade da novidade) → `"{nomeArquivo}"`."""
    return novidade.id.split("/", 1)[1]


def _coletar_um(
    db: Session, config: Configuracoes, fonte: FonteColetavel, novidade: Novidade
) -> Documento:
    """Baixa uma novidade, grava o arquivo em disco e persiste (ou reaproveita) o `Documento`."""
    arquivo = fonte.baixar(novidade)

    existente = db.scalars(select(Documento).where(Documento.hash == arquivo.hash)).first()
    if existente is not None:
        return existente

    nome_arquivo = _nome_do_arquivo(novidade)
    pasta_evento = resolver_documentos_dir(config) / novidade.evento
    pasta_evento.mkdir(parents=True, exist_ok=True)
    caminho_absoluto = pasta_evento / nome_arquivo
    if not caminho_absoluto.exists():
        caminho_absoluto.write_bytes(arquivo.conteudo)

    documento = Documento(
        tipo=novidade.tipo,
        hash=arquivo.hash,
        caminho=f"{novidade.evento}/{nome_arquivo}",
        baixado_em=agora_utc(),
        metadados={
            "descricao": novidade.titulo,
            "evento": novidade.evento,
            "url_origem": novidade.url,
        },
    )
    db.add(documento)
    db.flush()
    return documento


def coletar_par(
    db: Session, config: Configuracoes, fonte: FonteColetavel, par: ParDeProva
) -> tuple[Documento, Documento]:
    """Baixa e persiste prova e gabarito de um `ParDeProva`.

    Idempotente por hash: rodar duas vezes para o mesmo par não cria `Documento` duplicado — a
    segunda chamada devolve a linha já existente.

    Args:
        db: sessão de banco (o `commit` é de quem chama; esta função só `add`/`flush`).
        config: configurações do backend (usa `documentos_dir`).
        fonte: a fonte de onde baixar (`FonteCebraspe` real ou falsa, em teste).
        par: a prova e o gabarito a coletar.

    Returns:
        `(documento_prova, documento_gabarito)`.
    """
    return (
        _coletar_um(db, config, fonte, par.prova),
        _coletar_um(db, config, fonte, par.gabarito),
    )


def _analisar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    """Define e interpreta os argumentos de `main()`."""
    parser = argparse.ArgumentParser(
        description=(
            "Coleta a prova objetiva e o gabarito definitivo do cargo de Direito de um evento "
            "encerrado da Cebraspe."
        )
    )
    parser.add_argument("--evento", required=True, help="eventoURL (ex.: TJ_PA_25_SERVIDOR)")
    parser.add_argument(
        "--cargo",
        type=int,
        default=None,
        help="número do cargo; se omitido, descoberto pelo eventoCargos (área com 'DIREITO')",
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="só lista os arquivos encontrados (tipo, título, URL), sem baixar",
    )
    return parser.parse_args(argv)


def _candidatos_de_cargo(
    fonte: FonteCebraspe, argumentos: argparse.Namespace
) -> tuple[list[tuple[int, str | None]], str | None]:
    """Resolve os cargos a coletar (`--cargo` explícito ou descoberta por `cargo_de_direito`).

    Args:
        fonte: a fonte já aberta.
        argumentos: os argumentos de `main()` (usa `--evento`/`--cargo`).

    Returns:
        `(candidatos, mensagem)`. `candidatos` é `[(número, área ou None)]` — `área` é `None`
        quando o número veio de `--cargo` (escolha explícita, nada a registrar). `mensagem` é a
        linha de log da descoberta (ou do motivo de pular); `candidatos` vazio + `mensagem`
        preenchida significa "nenhum cargo de Direito neste evento — pule-o".
    """
    if argumentos.cargo is not None:
        return [(argumentos.cargo, None)], None

    cargos = fonte.cargos_do_evento(argumentos.evento)
    brutos = _cargos_pelo_lexico(cargos)
    if not brutos:
        return [], f"{argumentos.evento}: nenhum cargo de Direito em eventoCargos — pulado"

    escolhidos = cargo_de_direito(cargos)
    descricao = ", ".join(f"{numero} ({area})" for numero, area in escolhidos)
    if len(escolhidos) == 1:
        mensagem = f"{argumentos.evento}: cargo de Direito = {descricao}"
    elif len(escolhidos) < len(brutos):
        mensagem = (
            f"{argumentos.evento}: {len(brutos)} cargos casaram o léxico de Direito; "
            f"nível superior escolhido: {descricao}"
        )
    else:
        mensagem = (
            f"{argumentos.evento}: {len(escolhidos)} cargos de Direito empatados em nível "
            f"— coletando todos: {descricao}"
        )
    return [(numero, area) for numero, area in escolhidos], mensagem


def _coletar(fonte: FonteCebraspe, config: Configuracoes, argumentos: argparse.Namespace) -> int:
    """O corpo do comando com a fonte já aberta.

    Chamado por `main()`; testável isoladamente (com `fonte` falsa) sem precisar simular o
    gerenciador de contexto do cliente HTTP.

    Args:
        fonte: a fonte já aberta (real ou falsa, em teste).
        config: configurações do backend.
        argumentos: os argumentos de `main()`.

    Returns:
        `0` sempre que o comando roda até o fim — inclusive quando pula um evento/cargo sem par
        completo (pular com registro não é erro; decisão do dono, passo 5).
    """
    candidatos, mensagem = _candidatos_de_cargo(fonte, argumentos)
    if mensagem:
        print(mensagem)
    if not candidatos:
        return 0

    todos = fonte.arquivos_do_evento(argumentos.evento)
    pares: list[ParDeProva] = []
    for numero, _area in candidatos:
        arquivos = arquivos_do_cargo(todos, numero)
        if argumentos.listar:
            for arquivo in arquivos:
                print(f"{arquivo.tipo}\t{arquivo.titulo}\t{arquivo.url}")
            continue
        try:
            pares.extend(parear(arquivos))
        except ProvaSemGabarito as erro:
            print(f"{argumentos.evento} (cargo {numero}): {erro} — pulado")

    if argumentos.listar or not pares:
        return 0

    engine = criar_engine(config.database_url)
    fabrica_sessao = criar_fabrica_sessao(engine)
    with fabrica_sessao() as db:
        for par in pares:
            documento_prova, documento_gabarito = coletar_par(db, config, fonte, par)
            print(f"gravado: {documento_prova.caminho} + {documento_gabarito.caminho}")
        db.commit()
    return 0


def main(
    argv: list[str] | None = None,
    config: Configuracoes | None = None,
    fonte: FonteCebraspe | None = None,
) -> int:
    """Ponto de entrada do comando de coleta.

    Abre a fonte (`criar_fonte_cebraspe(config)`, dentro de um `with` — fecha o cliente HTTP ao
    sair) e o engine do banco com `with`/bloco explícito, fechando-o ao sair — nenhum dos dois
    fica sem dono. Sem cargo de Direito no evento (`eventoCargos`), ou sem par prova+gabarito
    completo desse cargo, o evento é pulado com uma mensagem — nunca adivinhado.

    Args:
        argv: argumentos da linha de comando; `None` usa `sys.argv` (padrão do `argparse`).
        config: configurações explícitas (testes); `None` lê do ambiente/.env.
        fonte: fonte já aberta (testes, com cliente HTTP falso); `None` abre
            `criar_fonte_cebraspe(config)` num `with`, exercitando o fechamento de verdade.

    Returns:
        `0` sempre que o comando roda até o fim (inclusive ao pular um evento/cargo).
    """
    argumentos = _analisar_argumentos(argv)
    config = config or obter_configuracoes()

    if fonte is not None:
        return _coletar(fonte, config, argumentos)
    with criar_fonte_cebraspe(config) as fonte_aberta:
        return _coletar(fonte_aberta, config, argumentos)


if __name__ == "__main__":
    raise SystemExit(main())
