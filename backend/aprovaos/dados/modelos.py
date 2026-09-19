"""Modelos ORM: tabelas base da V1, de edital/DNA da V2 e de questões/eventos da V3.

O que é: as quinze tabelas do AprovaOS até a V3 (modelo de dados §2, §3 e §4). Quando ler: ao
consultar ou estender essas tabelas; nomes de tabela e coluna são os de
`docs/04-modelo-de-dados.md` — não renomeie. `dna_concurso` guarda o JSON inteiro do DNA em
`conteudo` (plano V2, premissa B) e `topico_edital.ordem` dá a posição do tópico no edital.
`questao` guarda o que o curador da V3 produz (`dominio/questao.py::QuestaoCurada`): `origem`
e `regra_prova` são o JSON dos modelos Pydantic homônimos; `topico_id` é nullable (item sem
tópico casado fica na base, mas nunca publicável); `publicavel` é o veredito do curador,
`publicada` é o que a consulta da tela decide servir. `evento_estudo` é append-only (sem
`atualizado_em`, sem `ON UPDATE` — a camada de dados nunca expõe update/delete nela).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aprovaos.dados.base import Base, Carimbos, ChaveUuid, DataHoraUtc, agora_utc


class Tenant(ChaveUuid, Carimbos, Base):
    """Dono dos dados: pessoa física (`pf`, criado no cadastro) ou organização (`org`)."""

    __tablename__ = "tenant"
    __table_args__ = (CheckConstraint("tipo IN ('pf','org')", name="tipo"),)

    tipo: Mapped[str] = mapped_column(String(8), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)


class Usuario(ChaveUuid, Carimbos, Base):
    """Conta de acesso por e-mail+senha (argon2); `excluido_em` marca pedido de exclusão."""

    __tablename__ = "usuario"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    excluido_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)

    tenant: Mapped[Tenant] = relationship()


class Sessao(ChaveUuid, Carimbos, Base):
    """Sessão de login server-side (ADR-0026): guarda só o SHA-256 do token do cookie."""

    __tablename__ = "sessao"

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    revogada_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)

    usuario: Mapped[Usuario] = relationship()


class Traco(ChaveUuid, Base):
    """Traço de execução de agente (ADR-0024): fonte de custos; sem escrita na V1."""

    __tablename__ = "traco"

    criado_em: Mapped[datetime] = mapped_column(DataHoraUtc, default=agora_utc, nullable=False)
    iniciado_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    duracao_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    usuario_id: Mapped[UUID | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    agente: Mapped[str] = mapped_column(String(64), nullable=False)
    modelo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custo_brl: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    tier: Mapped[str | None] = mapped_column(String(8), nullable=True)
    resultado: Mapped[str] = mapped_column(String(16), nullable=False)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    span_pai_id: Mapped[UUID | None] = mapped_column(ForeignKey("traco.id"), nullable=True)


class Concurso(ChaveUuid, Carimbos, Base):
    """Concurso de um tenant (`tenant_id` `NULL` = catálogo futuro, fatia 1b).

    `banca` recebe `"desconhecido"` quando o edital não a declara — nunca `NULL`, para o DNA
    e a página terem um único jeito de dizer "não sei".
    """

    __tablename__ = "concurso"

    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant.id"), index=True, nullable=True
    )
    orgao: Mapped[str] = mapped_column(String(200), nullable=False)
    cargo: Mapped[str] = mapped_column(String(200), nullable=False)
    banca: Mapped[str] = mapped_column(String(200), nullable=False)
    data_prova: Mapped[date | None] = mapped_column(Date, nullable=True)

    tenant: Mapped[Tenant | None] = relationship()


class Documento(ChaveUuid, Carimbos, Base):
    """Arquivo bruto guardado em disco (edital subido, prova, gabarito…), endereçado pelo hash."""

    __tablename__ = "documento"
    __table_args__ = (
        CheckConstraint("tipo IN ('prova','gabarito','edital','lei','informativo')", name="tipo"),
    )

    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    caminho: Mapped[str] = mapped_column(String(255), nullable=False)
    baixado_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    metadados: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Edital(ChaveUuid, Carimbos, Base):
    """Versão de edital de um concurso (`versao` 1 na V2; retificações viram versão 2, P-24)."""

    __tablename__ = "edital"
    __table_args__ = (UniqueConstraint("concurso_id", "versao"),)

    concurso_id: Mapped[UUID] = mapped_column(ForeignKey("concurso.id"), index=True, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    documento_id: Mapped[UUID] = mapped_column(ForeignKey("documento.id"), nullable=False)

    concurso: Mapped[Concurso] = relationship()
    documento: Mapped[Documento] = relationship()


class Topico(ChaveUuid, Carimbos, Base):
    """Vocabulário global de tópicos por `slug` (get-or-create; compartilhado entre editais)."""

    __tablename__ = "topico"

    materia: Mapped[str] = mapped_column(String(120), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class TopicoEdital(ChaveUuid, Carimbos, Base):
    """Tópico como aparece num edital: texto original, posição (`ordem`) e peso uniforme.

    `grupo` é o cabeçalho agrupador acima da matéria no edital (ex.: `CONHECIMENTOS
    ESPECÍFICOS`), ou `None` quando a matéria aparece solta (P-26: o parser já devolvia
    `MateriaExtraida.grupo`, mas ele não era persistido).
    """

    __tablename__ = "topico_edital"
    __table_args__ = (UniqueConstraint("edital_id", "topico_id"),)

    edital_id: Mapped[UUID] = mapped_column(ForeignKey("edital.id"), index=True, nullable=False)
    topico_id: Mapped[UUID] = mapped_column(ForeignKey("topico.id"), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    peso_edital: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    texto_original: Mapped[str] = mapped_column(Text, nullable=False)
    grupo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    edital: Mapped[Edital] = relationship()
    topico: Mapped[Topico] = relationship()


class DnaConcursoRegistro(ChaveUuid, Carimbos, Base):
    """Linha de `dna_concurso`: o JSON inteiro do `DnaConcurso` em `conteudo` + origem/versão.

    O nome Python evita colidir com o modelo Pydantic `DnaConcurso` de `dominio/dna.py`.
    """

    __tablename__ = "dna_concurso"
    __table_args__ = (
        UniqueConstraint("concurso_id", "versao"),
        CheckConstraint("origem IN ('ia','regras')", name="origem"),
    )

    concurso_id: Mapped[UUID] = mapped_column(ForeignKey("concurso.id"), index=True, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    origem: Mapped[str] = mapped_column(String(8), nullable=False)
    modelo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    motivo_fallback: Mapped[str | None] = mapped_column(Text, nullable=True)
    conteudo: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    concurso: Mapped[Concurso] = relationship()


class Fonte(ChaveUuid, Carimbos, Base):
    """Uma fonte de conteúdo do coletor, espelho da ficha em `knowledge/fontes.yaml`.

    `id_externo` é o `id` da ficha (ex.: `"cebraspe"`); `politica` guarda a `politica_coleta`
    inteira (frequência, user-agent, sem-login) quando disponível.
    """

    __tablename__ = "fonte"
    __table_args__ = (
        CheckConstraint("status IN ('ativa','vetada','pendente_mapeamento')", name="status"),
    )

    id_externo: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    url_lista: Mapped[str] = mapped_column(String(500), nullable=False)
    politica: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    ultima_varredura: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    proxima: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)


class Questao(ChaveUuid, Carimbos, Base):
    """Uma questão (original ou inédita), no formato que o curador da V3 produz e o gate publica.

    Espelha `dominio.questao.QuestaoCurada` quase campo a campo: `regra_prova` e `origem`
    guardam os modelos Pydantic homônimos como JSON (`RegraProva`/`Origem`); `topico_slug` vira
    `topico_id` (FK, nullable — item sem correspondência fica na base, mas nunca publicável);
    `topico_confianca`/`topico_evidencia` registram por que o classificador decidiu o que
    decidiu. `origem` é nullable porque uma questão inédita (`inedita=True`, fatia 5) não tem
    procedência de prova; `documento_id` (FK) é a fonte de verdade da relação com `documento` —
    `origem["documento_id"]` é só um espelho histórico do mesmo valor, gravado junto por
    comodidade de quem lê o JSON inteiro sem dar join; nunca o inverso. `publicavel` é o veredito
    determinístico do gate (`dominio.questao.decidir_publicacao`) e é o que toda consulta da
    tela hoje filtra (`repositorio_questao.proxima_questao`/`contagem_por_topico`,
    `api/questoes.py`). `publicada`/`despublicada_em` **não são lidas nem escritas por ninguém
    nesta fatia** — estão reservadas para o calibrador (fatia 8, despublicação por reporte
    confirmado); quando ele existir, a consulta da tela **terá de passar a filtrar também**
    `publicada`, ou uma questão despublicada continuaria aparecendo para o aluno (P-34,
    `docs/PENDENCIAS.md`). `dificuldade_est`/`discriminacao_est` ficam para a calibração (fatia
    futura).
    """

    __tablename__ = "questao"
    __table_args__ = (
        CheckConstraint(
            "gabarito_status IN ('definitivo','preliminar','anulado','alterado','sem_gabarito')",
            name="gabarito_status",
        ),
        CheckConstraint("gabarito IS NULL OR gabarito IN ('A','B','C','D','E')", name="gabarito"),
        CheckConstraint(
            "gabarito_preliminar IS NULL OR gabarito_preliminar IN ('A','B','C','D','E')",
            name="gabarito_preliminar",
        ),
        CheckConstraint("topico_confianca IN ('alta','media','baixa')", name="topico_confianca"),
    )

    adapter: Mapped[str] = mapped_column(String(32), nullable=False)
    banca: Mapped[str] = mapped_column(String(64), nullable=False)
    tipo_item: Mapped[str] = mapped_column(String(32), nullable=False)
    comando: Mapped[str | None] = mapped_column(Text, nullable=True)
    texto_apoio: Mapped[str | None] = mapped_column(Text, nullable=True)
    texto_apoio_itens: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    gabarito_preliminar: Mapped[str | None] = mapped_column(String(1), nullable=True)
    gabarito: Mapped[str | None] = mapped_column(String(1), nullable=True)
    gabarito_status: Mapped[str] = mapped_column(String(16), nullable=False)
    publicavel: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publicada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    despublicada_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    motivo_nao_publicavel: Mapped[str | None] = mapped_column(Text, nullable=True)
    regra_prova: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    topico_id: Mapped[UUID | None] = mapped_column(ForeignKey("topico.id"), nullable=True)
    topico_confianca: Mapped[str] = mapped_column(String(8), nullable=False)
    topico_evidencia: Mapped[str] = mapped_column(Text, nullable=False)
    origem: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    inedita: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    documento_id: Mapped[UUID | None] = mapped_column(ForeignKey("documento.id"), nullable=True)
    hash_dedup: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    dificuldade_est: Mapped[float | None] = mapped_column(Float, nullable=True)
    discriminacao_est: Mapped[float | None] = mapped_column(Float, nullable=True)
    validada_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    validador_versao: Mapped[str | None] = mapped_column(String(64), nullable=True)
    justificativa_certo: Mapped[str | None] = mapped_column(Text, nullable=True)
    justificativa_errado: Mapped[str | None] = mapped_column(Text, nullable=True)

    topico: Mapped[Topico | None] = relationship()
    documento: Mapped[Documento | None] = relationship()


class Alternativa(ChaveUuid, Carimbos, Base):
    """Uma alternativa (A–E) de uma `Questao` de múltipla escolha (`tipo_item="multipla_escolha"`).

    Criada vazia na migração 0003 (fora do escopo da V3, só C/E); passa a ser gravada pelo
    `repositorio_questao.salvar_questoes` a partir do passo 2 da fatia V3b. `justificativa`
    nasce sempre `None` — quem a preenche é o gerador de inéditas com validador (fatia 5), nunca
    o curador (mesmo princípio de `Questao.justificativa_certo`/`justificativa_errado`).
    """

    __tablename__ = "alternativa"
    __table_args__ = (UniqueConstraint("questao_id", "letra"),)

    questao_id: Mapped[UUID] = mapped_column(ForeignKey("questao.id"), index=True, nullable=False)
    letra: Mapped[str] = mapped_column(String(1), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    correta: Mapped[bool] = mapped_column(Boolean, nullable=False)
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)

    questao: Mapped[Questao] = relationship()


class EventoEstudo(ChaveUuid, Base):
    """Fato imutável do estudo: uma resposta, um check-in, um bloco pulado.

    Append-only por contrato (modelo de dados §2): nunca é atualizado nem apagado, por isso não
    herda `Carimbos` (sem `atualizado_em`, sem `ON UPDATE`) — a camada de dados não expõe
    update/delete nesta tabela. O `CheckConstraint` de `tipo` já traz os dez valores do modelo
    de dados; esta fatia só produz `resposta` e `reporte`, os demais entram sem migração nova.
    """

    __tablename__ = "evento_estudo"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ("
            "'resposta','checkin','bloco_iniciado','bloco_concluido','bloco_pulado',"
            "'discordou','distracao','revisao_cartao','aula_lida','resumo_aberto','reporte'"
            ")",
            name="tipo",
        ),
        CheckConstraint(
            "confianca_declarada IS NULL OR confianca_declarada IN ('certeza','duvida')",
            name="confianca_declarada",
        ),
        Index("ix_evento_estudo_usuario_ocorrido", "usuario_id", "ocorrido_em"),
        Index("ix_evento_estudo_questao_ocorrido", "questao_id", "ocorrido_em"),
    )

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    ocorrido_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    questao_id: Mapped[UUID | None] = mapped_column(ForeignKey("questao.id"), nullable=True)
    acertou: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    resposta: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tempo_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confianca_declarada: Mapped[str | None] = mapped_column(String(8), nullable=True)

    usuario: Mapped[Usuario] = relationship()
    questao: Mapped[Questao | None] = relationship()


class ReporteErro(ChaveUuid, Carimbos, Base):
    """Reporte de um aluno sobre um conteúdo (`questao` nesta fatia): fila do calibrador.

    `conteudo_id` não é uma FK — `conteudo_tipo` decide a tabela (`aula`/`questao`/`dossie`),
    igual à convenção polimórfica de `anotacao`/`citacao` no modelo de dados. Uma questão
    reportada some de `proxima_questao` só para quem reportou (premissa H, passo 11).
    """

    __tablename__ = "reporte_erro"
    __table_args__ = (
        CheckConstraint("conteudo_tipo IN ('aula','questao','dossie')", name="conteudo_tipo"),
        CheckConstraint("status IN ('aberto','analise','corrigido','improcedente')", name="status"),
    )

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), index=True, nullable=False)
    conteudo_tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    conteudo_id: Mapped[UUID] = mapped_column(nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="aberto", nullable=False)
    resolvido_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)

    usuario: Mapped[Usuario] = relationship()
