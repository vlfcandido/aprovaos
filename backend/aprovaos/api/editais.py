"""Rotas HTML de edital: `/editais/subir` (upload → DNA → concurso), `/editais` e `/concurso/{id}`.

O que é: o router da fatia V2 — `POST /editais/subir` roda o pipeline inteiro (validar PDF →
extrair texto → parser do conteúdo programático → `gerar_dna` por IA ou regras → gravar PDF →
persistir → commit) e redireciona para a página do concurso; erros esperados voltam na mesma
página com mensagem e status 200 (premissa N). `processar_conteudo_pdf` é o miolo do pipeline
extraído para bytes já em mãos — reaproveitado por `api/radar.py::analisar_edital_do_radar`
(fatia 1b, "Analisar este edital": o PDF vem da URL do detalhe da Cebraspe, não de upload).
Quando ler: ao mexer no upload, na página do concurso ou na lista "Meus editais".
"""

import hashlib
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from aprovaos.agentes.analista_de_edital import AnalistaDeEdital, criar_analista_adk, gerar_dna
from aprovaos.api.db import obter_db
from aprovaos.api.sessao import exigir_usuario
from aprovaos.api.templates import renderizar, responder_redirecionamento
from aprovaos.config import Configuracoes
from aprovaos.dados.arquivos import guardar_pdf
from aprovaos.dados.base import agora_utc
from aprovaos.dados.modelos import Concurso, Usuario
from aprovaos.dados.repositorio_assinatura import tier_do_usuario
from aprovaos.dados.repositorio_aula import aula_publicada_do_topico_com_origem
from aprovaos.dados.repositorio_edital import (
    STATUS_NAO_VISTO,
    DadosDocumento,
    MateriaVerticalizada,
    TopicoVerticalizado,
    buscar_concurso,
    contagem_editais_com_dna,
    dna_atual,
    edital_atual,
    listar_concursos_do_tenant,
    registrar_edital,
    verticalizado,
)
from aprovaos.dados.repositorio_fio_memoria import estatisticas_topicos_vistos
from aprovaos.dados.repositorio_questao import contagem_por_topico, topicos_vistos
from aprovaos.dados.repositorio_traco import registrar_traco
from aprovaos.dominio.assinatura import pode_criar_edital
from aprovaos.dominio.dna import DnaConcurso
from aprovaos.dominio.edital import (
    DESCONHECIDO,
    extrair_conteudo_programatico,
    normalizar_materia,
    slug_materia,
)
from aprovaos.dominio.erros import ArquivoInvalido, ConteudoProgramaticoNaoEncontrado, PdfSemTexto
from aprovaos.dominio.pdf import LIMITE_BYTES, contar_paginas, extrair_texto, validar_pdf
from aprovaos.dominio.trilha import TopicoParaTrilha, montar_trilha
from aprovaos.motor.dossie import topicos_de_maior_peso
from aprovaos.roteador.custo import ChamadaLlm
from aprovaos.roteador.teto import TetoDiario

router = APIRouter(include_in_schema=False)

MOTIVO_SEM_CHAVE = "sem GOOGLE_API_KEY"
MOTIVO_TETO = "teto diário atingido"
TEXTO_PESO_UNIFORME = (
    "Sem provas anteriores desta banca na base, o peso por tópico é uniforme dentro da matéria."
)
TIPO_ITEM_TEXTO = {
    "multipla_escolha": "múltipla escolha",
    "certo_errado": "certo ou errado",
    DESCONHECIDO: "desconhecido",
}


@router.get("/editais/subir")
def subir(request: Request, usuario: Annotated[Usuario, Depends(exigir_usuario)]) -> Response:
    """Formulário de subir edital em PDF.

    Args:
        request: a requisição atual.
        usuario: o usuário logado (sem login, `exigir_usuario` redireciona para `/entrar`).

    Returns:
        O HTML de `editais/subir.html` sem erros.
    """
    return renderizar(request, "editais/subir.html", {"erros": []}, usuario)


def _escolher_analista(
    db: Session, config: Configuracoes, usuario: Usuario
) -> tuple[AnalistaDeEdital | None, str | None]:
    """Decide se a IA entra: sem chave ou sem teto → `None` com o motivo; senão o analista ADK.

    O callback entregue à fábrica grava cada `ChamadaLlm` em `traco` na sessão do request
    (premissa G); o `commit` fica com a rota.
    """
    if config.google_api_key is None:
        return None, MOTIVO_SEM_CHAVE
    if not TetoDiario(config.teto_diario_brl).pode_chamar(db, agora_utc()):
        return None, MOTIVO_TETO

    def registrar(chamada: ChamadaLlm) -> None:
        registrar_traco(db, chamada, usuario_id=usuario.id)

    return criar_analista_adk(config, registrar), None


async def processar_conteudo_pdf(
    request: Request,
    db: Session,
    usuario: Usuario,
    conteudo: bytes,
    nome_original: str,
) -> Concurso:
    """Roda o pipeline do edital (validar → DNA → persistir) sobre bytes já em mãos.

    Extraído de `processar_edital` para ser compartilhado com `POST
    /radar/{evento_url}/analisar` (fatia 1b): lá o PDF chega pela URL do detalhe da Cebraspe, não
    por upload multipart, mas o resto do pipeline é idêntico. Não faz `commit` nem redireciona —
    quem chama decide o que fazer com o `Concurso` devolvido (e propaga as exceções de domínio
    para decidir a mensagem certa na tela de origem).

    Args:
        request: a requisição atual (`app.state.config`, `app.state.uploads_dir`).
        db: sessão de banco do request.
        usuario: o usuário logado.
        conteudo: bytes do PDF, já confirmados como vindos de uma fonte que promete ser PDF.
        nome_original: nome de exibição do arquivo (o do upload, ou o `nomeArquivo` da API).

    Returns:
        O `Concurso` já persistido (`add`/`flush`, sem `commit`).

    Raises:
        ArquivoInvalido: não é PDF, passa de 10 MB, ou está corrompido.
        PdfSemTexto: PDF sem texto extraível.
        ConteudoProgramaticoNaoEncontrado: sem conteúdo programático reconhecível.
    """
    config: Configuracoes = request.app.state.config
    validar_pdf(conteudo, "application/pdf")
    texto = extrair_texto(conteudo)
    materias = extrair_conteudo_programatico(texto)

    analista, motivo = _escolher_analista(db, config, usuario)
    resultado = await gerar_dna(texto, materias, analista, motivo)

    hash_pdf = hashlib.sha256(conteudo).hexdigest()
    caminho = guardar_pdf(request.app.state.uploads_dir, hash_pdf, conteudo)
    documento = DadosDocumento(
        hash=hash_pdf,
        caminho_relativo=caminho.name,
        nome_original=nome_original,
        tamanho=len(conteudo),
        paginas=contar_paginas(conteudo),
    )
    modelo = config.modelo_dna if resultado.origem == "ia" else None
    return registrar_edital(db, usuario.tenant_id, resultado, materias, documento, modelo)


@router.post("/editais/subir")
async def processar_edital(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    arquivo: Annotated[UploadFile, File()],
) -> Response:
    """Roda o pipeline do edital e redireciona para `/concurso/{id}`.

    Args:
        request: a requisição atual (`app.state.config`, `app.state.uploads_dir`).
        db: sessão de banco do request (o commit é feito aqui, uma vez, no fim).
        usuario: o usuário logado.
        arquivo: campo `arquivo` do formulário multipart.

    Returns:
        Redirecionamento (`HX-Redirect` ou 303) no sucesso; a página com a mensagem (200) para
        arquivo que não é PDF, maior que 10 MB, sem texto ou sem conteúdo programático, ou para
        o limite do Free (ADR-0015: DNA de 1 concurso — `dominio.assinatura.pode_criar_edital`,
        conferido **antes** de gastar o pipeline de PDF/DNA num upload que não vai ser aceito).
    """
    tier = tier_do_usuario(db, usuario.id, agora_utc().date())
    veredito = pode_criar_edital(tier, contagem_editais_com_dna(db, usuario.tenant_id))
    if not veredito.permitido:
        contexto = {"erros": [f"{veredito.motivo} {veredito.convite}"]}
        return renderizar(request, "editais/subir.html", contexto, usuario)

    conteudo = await arquivo.read(LIMITE_BYTES + 1)
    try:
        validar_pdf(conteudo, arquivo.content_type or "")
        concurso = await processar_conteudo_pdf(
            request, db, usuario, conteudo, arquivo.filename or "edital.pdf"
        )
    except (ArquivoInvalido, PdfSemTexto, ConteudoProgramaticoNaoEncontrado) as erro:
        return renderizar(request, "editais/subir.html", {"erros": [str(erro)]}, usuario)
    db.commit()
    return responder_redirecionamento(request, f"/concurso/{concurso.id}")


def _nome_exibicao(nome: str) -> str:
    """`LÍNGUA PORTUGUESA` → `Língua Portuguesa` (nomes vêm em caixa alta do edital).

    Usa `dominio.edital.normalizar_materia`, a **mesma** regra que o banco aplica em
    `topico.materia`. Antes usava `str.title()`, que capitaliza toda palavra e produzia
    "Noções De Informática" e "Matemática/raciocínio Lógico" na tabela de pesos. Eram duas
    implementações da mesma ideia — uma foi corrigida quando a matéria duplicou no painel e a
    outra ficou para trás. Uma regra só, num lugar só.
    """
    return normalizar_materia(nome)


def _materias_de_prova(
    dna: DnaConcurso, materias: list[MateriaVerticalizada]
) -> list[dict[str, Any]]:
    """Linhas da tabela de pesos: `pesos.materia` + nome de exibição vindo do verticalizado.

    O nome é o da matéria do conteúdo programático cujo slug bate com a chave; quando a chave é
    o **grupo** (ex.: `conhecimentos-especificos`, quando o DNA só sabe o peso do bloco inteiro,
    não de cada matéria dentro dele), o nome vem de `topico_edital.grupo` — com acento, nunca do
    slug em Title Case (P-26). Só na ausência de ambos é que o slug vira o nome, último recurso.
    """
    nome_por_slug = {m.slug: _nome_exibicao(m.nome) for m in materias}
    for m in materias:
        if m.grupo:
            nome_por_slug.setdefault(slug_materia(m.grupo), _nome_exibicao(m.grupo))
    linhas: list[dict[str, Any]] = []
    for slug, peso in dna.pesos.materia.items():
        linha = peso.model_dump(mode="json")
        linha["slug"] = slug
        linha["nome"] = nome_por_slug.get(slug, slug.replace("-", " ").title())
        linha["pct_barra"] = 0 if isinstance(peso.pct_pontos, str) else peso.pct_pontos
        linhas.append(linha)
    return linhas


def _topico_verticalizado(
    topico: TopicoVerticalizado, contagem: dict[UUID, int], vistos: set[UUID]
) -> dict[str, Any]:
    """Um tópico do verticalizado pronto para o template: contagem de questões e status por aluno.

    `verticalizado()` não sabe de `questao` nem de usuário (é só o edital); é aqui, na rota, que
    a contagem publicável (`contagem_por_topico`) e o "já respondeu" (`topicos_vistos`) — os dois
    do repositório de questões — se juntam ao tópico pelo `id` (passo 14 da V3).

    Args:
        topico: o tópico como `verticalizado()` devolveu, com `status` sempre `não visto`.
        contagem: `{topico_id: questões publicáveis}`, de `contagem_por_topico`.
        vistos: `topico_id` com pelo menos uma resposta deste aluno, de `topicos_vistos`.

    Returns:
        Dicionário para o template, com `questoes` (contagem) e `status` (`visto`/`não visto`).
    """
    return {
        "slug": topico.slug,
        "texto_original": topico.texto_original,
        "status": "visto" if topico.id in vistos else STATUS_NAO_VISTO,
        "questoes": contagem.get(topico.id, 0),
    }


def _texto_anula(valor: bool | str) -> str:
    """Frase pt-BR para `regra_correcao.anula_por_erro`."""
    if isinstance(valor, str):
        return DESCONHECIDO
    return "uma resposta errada anula uma certa" if valor else "sem desconto por resposta errada"


@router.get("/concurso/{concurso_id}")
def concurso(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    concurso_id: UUID,
) -> Response:
    """Página do concurso: DNA reduzido e edital verticalizado (só o dono do tenant).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado.
        concurso_id: chave do concurso (inválida → 422 JSON pelo tratador da V1).

    Returns:
        O HTML de `editais/concurso.html`.

    Raises:
        HTTPException: 404 se não existir (ou não tiver edital/DNA); 403 se for de outro tenant.
    """
    achado = buscar_concurso(db, concurso_id)
    if achado is None:
        raise HTTPException(status_code=404, detail="Concurso não encontrado.")
    if achado.tenant_id != usuario.tenant_id:
        raise HTTPException(status_code=403, detail="Este concurso pertence a outra conta.")
    edital = edital_atual(db, achado.id)
    registro = dna_atual(db, achado.id)
    if edital is None or registro is None:
        raise HTTPException(status_code=404, detail="Este concurso ainda não tem edital.")

    dna = DnaConcurso.model_validate(registro.conteudo)
    materias = verticalizado(db, edital.id)
    contagem = contagem_por_topico(db, edital.id)
    vistos = topicos_vistos(db, usuario.id, edital.id)
    regra = dna.regra_correcao
    contexto: dict[str, Any] = {
        "concurso": {
            "id": str(achado.id),
            "orgao": achado.orgao,
            "cargo": achado.cargo,
            "banca": achado.banca,
            "data_prova": achado.data_prova.strftime("%d/%m/%Y") if achado.data_prova else None,
            "edital": dna.concurso.edital,
            "fonte": dna.concurso.fonte,
        },
        "origem": {
            "tipo": registro.origem,
            "modelo": registro.modelo,
            "motivo": registro.motivo_fallback,
        },
        "materias_prova": _materias_de_prova(dna, materias),
        "regra": {
            "tipo_item": TIPO_ITEM_TEXTO.get(regra.tipo_item, regra.tipo_item),
            "alternativas": regra.alternativas,
            "anula": _texto_anula(regra.anula_por_erro),
            "minimo_global": regra.minimo_global,
            "minimo_por_materia": regra.minimo_por_materia,
            "fonte": regra.fonte,
        },
        "etapas": [etapa.model_dump(mode="json") for etapa in dna.etapas],
        "lacunas": dna.lacunas,
        "peso_uniforme": any(t.metodo == "uniforme_no_edital" for t in dna.pesos.topico.values()),
        "texto_peso_uniforme": TEXTO_PESO_UNIFORME,
        "materias": [
            {
                "nome": m.nome,
                "slug": m.slug,
                "grupo": m.grupo,
                "nome_exibicao": _nome_exibicao(m.nome),
                "topicos": [_topico_verticalizado(t, contagem, vistos) for t in m.topicos],
            }
            for m in materias
        ],
        "total_topicos": sum(len(m.topicos) for m in materias),
        "topicos_vistos": len(vistos),
    }
    return renderizar(request, "editais/concurso.html", contexto, usuario)


@router.get("/concurso/{concurso_id}/trilha")
def trilha_do_concurso(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
    concurso_id: UUID,
) -> Response:
    """A trilha de estudo do concurso (fatia 6): tópicos ordenados por peso medido e histórico.

    A aula de cada item usa `repositorio_aula.aula_publicada_do_topico_com_origem` (corrigido em
    19/09/2026, I2) — a mesma leitura de `GET /topico/{slug}/aula`, que atravessa
    `topico_relacao` (equivalência plena e cobertura parcial) antes de dizer "sem aula". Quando a
    origem é `subconjunto_curado`, o item mostra "cobre parte" (I1: a página não pode servir uma
    aula de outro edital calada sobre ser cobertura parcial).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado.
        concurso_id: chave do concurso.

    Returns:
        O HTML de `editais/trilha.html`.

    Raises:
        HTTPException: 404 se não existir (ou não tiver edital); 403 se for de outro tenant.
    """
    achado = buscar_concurso(db, concurso_id)
    if achado is None:
        raise HTTPException(status_code=404, detail="Concurso não encontrado.")
    if achado.tenant_id != usuario.tenant_id:
        raise HTTPException(status_code=403, detail="Este concurso pertence a outra conta.")
    edital = edital_atual(db, achado.id)
    if edital is None:
        raise HTTPException(status_code=404, detail="Este concurso ainda não tem edital.")

    topicos_com_peso = topicos_de_maior_peso(db, edital.id, limite=10_000)
    vistos = {
        estatistica.topico_id: estatistica
        for estatistica in estatisticas_topicos_vistos(db, usuario.id, edital.id)
    }
    trilha = montar_trilha(
        [
            TopicoParaTrilha(
                topico_id=t.topico_id,
                slug=t.slug,
                nome=t.nome,
                materia=t.materia,
                questoes_publicaveis=t.questoes_publicaveis,
            )
            for t in topicos_com_peso
        ],
        vistos,
    )
    # Corrigido em 19/09/2026 (I2): antes, esta busca consultava `Aula` só pelo `topico_id`
    # direto — um tópico sem aula própria, mas ligado por `topico_relacao` (equivalência plena
    # ou cobertura parcial, ADR-0041/I1) a outro que tem, nunca mostrava "Ver aula" aqui, mesmo
    # com `GET /topico/{slug}/aula` servindo a aula normalmente (a mesma leitura que essa rota
    # usa). Agora as duas passam pela mesma função — e, quando a origem é `subconjunto_curado`,
    # a trilha avisa que a aula cobre só parte do item, em vez de servi-la calada.
    origem_por_topico = {
        item.topico_id: origem
        for item in trilha
        if (encontrada := aula_publicada_do_topico_com_origem(db, item.topico_id)) is not None
        for origem in (encontrada[1],)
    }
    contexto: dict[str, Any] = {
        "concurso": {"id": str(achado.id), "cargo": achado.cargo, "orgao": achado.orgao},
        "trilha": [
            {
                "slug": item.slug,
                "nome": item.nome,
                "status": item.status,
                "motivo": item.motivo,
                "tem_aula": item.topico_id in origem_por_topico,
                "cobertura_parcial": origem_por_topico.get(item.topico_id) == "subconjunto_curado",
            }
            for item in trilha
        ],
    }
    return renderizar(request, "editais/trilha.html", contexto, usuario)


@router.get("/editais")
def meus_editais(
    request: Request,
    db: Annotated[Session, Depends(obter_db)],
    usuario: Annotated[Usuario, Depends(exigir_usuario)],
) -> Response:
    """Lista "Meus editais": os concursos do tenant, o mais recente primeiro e marcado principal.

    Concurso principal = o último subido (premissa A da V2; `perfil_estudo` é da fatia 7, P-23).

    Args:
        request: a requisição atual.
        db: sessão de banco do request (só leitura).
        usuario: o usuário logado.

    Returns:
        O HTML de `editais/lista.html`.
    """
    concursos = [
        {
            "id": str(c.id),
            "orgao": c.orgao,
            "cargo": c.cargo,
            "banca": c.banca,
            "criado_em": c.criado_em.strftime("%d/%m/%Y"),
            "principal": posicao == 0,
        }
        for posicao, c in enumerate(listar_concursos_do_tenant(db, usuario.tenant_id))
    ]
    return renderizar(request, "editais/lista.html", {"concursos": concursos}, usuario)
