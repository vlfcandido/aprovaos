"""Modelos ORM: tabelas base da V1, de edital/DNA da V2 e de questões/eventos da V3.

O que é: as quinze tabelas do AprovaOS até a V3 (modelo de dados §2, §3 e §4). Quando ler: ao
consultar ou estender essas tabelas; nomes de tabela e coluna são os de
`docs/04-modelo-de-dados.md` — não renomeie. `dna_concurso` guarda o JSON inteiro do DNA em
`conteudo` (plano V2, premissa B) e `topico_edital.ordem` dá a posição do tópico no edital.
`questao` guarda o que o curador da V3 produz (`dominio/questao.py::QuestaoCurada`): `origem`
e `regra_prova` são o JSON dos modelos Pydantic homônimos; `topico_id` é nullable (item sem
tópico casado fica na base, mas nunca publicável); `publicavel` é o veredito do curador,
`publicada` é o que a consulta da tela decide servir. `evento_estudo` é append-only (sem
`atualizado_em`, sem `ON UPDATE` — a camada de dados nunca expõe update/delete nela); a V4
acrescenta a coluna `cartao_id` (nullable) para o tipo `revisao_cartao`. `cartao` (V4, F4.3)
guarda o estado do `fsrs.Card` — ver o docstring da classe `Cartao` para o adendo à ADR-0022. A V5
acrescenta `evento_estudo.dados` (JSON, nullable) — o campo que `docs/04-modelo-de-dados.md` §2
já previa desde a Fase 3 e nenhuma fatia anterior tinha precisado criar; o fio da memória o usa
para marcar `bloco_topico_id` (e, quando o item é intercalado, `fio_motivo`/
`fio_origem_topico_id`) sem inventar coluna nova. A fatia 7 acrescenta `usuario.
consentimento_dados_rotina*` (três colunas para o campo lógico único do modelo de dados — ver o
docstring de `Usuario`) e a tabela `perfil_estudo` (rotina + concurso principal, P-23); o
diagnóstico adaptativo da mesma fatia não ganha tabela nova — ele lê `evento_estudo` marcado com
`dados={"diagnostico": True}`, o mesmo padrão de `bloco_topico_id`. A fatia 8 acrescenta
`plano_dia`/`bloco` (plano do dia, job noturno, check-in — ver os docstrings das duas classes) e
os cinco tipos de `evento_estudo` que ainda não tinham produtor (`checkin`, `bloco_iniciado`,
`bloco_concluido`, `bloco_pulado`, `discordou`, `distracao` — seis, na verdade; o `CheckConstraint`
de `tipo` já os continha desde a V3). A fatia 11 acrescenta a tabela `Calibracao` (ver o docstring
da classe) e fecha a P-34 (`docs/PENDENCIAS.md`): `Questao.publicada` continua sem consumidor
direto (bookkeeping do calibrador), mas `Questao.despublicada_em` passa a ser o que toda consulta
de servir conteúdo filtra além de `publicavel` — uma questão despublicada some da tela na hora,
sem precisar reescrever `publicavel` (o veredito estrutural do curador, que o calibrador nunca
toca). A fatia 5 acrescenta `veredito_questao` (histórico append-only das tentativas de validação
de uma inédita — ver o docstring da classe `VereditoQuestao`); nenhuma coluna de `Questao` muda,
já que `origem`/`inedita`/`validada_em`/`validador_versao`/`justificativa_certo`/
`justificativa_errado` já existiam desde a V3/fundação jurídica para este caso.
"""

from datetime import date, datetime, time
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
    Time,
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
    """Conta de acesso por e-mail+senha (argon2); `excluido_em` marca pedido de exclusão.

    `consentimento_dados_rotina*` (fatia 7) são as três colunas que
    `docs/04-modelo-de-dados.md` §2 nomeia como um único campo lógico ("bool, data, versão do
    texto") — energia/sono é dado sensível por cautela (RISCOS R-01) e `perfil_estudo.
    energia_tipica` só pode ser gravado depois do aceite. `_em`/`_versao` ficam `None` até o
    primeiro aceite; um novo aceite (a cada `POST /rotina`, decisão do plano §7) sobrescreve os
    três, nunca acumula histórico à parte — quem quer saber "quando ela aceitou pela primeira
    vez" o fará quando essa necessidade aparecer, não antes.

    `google_sub` (fatia 1b, RF-20, Ruling 42, migração 0018) é o `sub` do perfil OpenID do
    Google; `None` para conta e-mail+senha. `senha_hash` passa a ser opcional na mesma migração:
    uma conta nascida por Google não tem senha nenhuma (`criar_ou_ligar_conta_google` grava
    `None`); `POST /entrar` para essa conta responde a mesma mensagem genérica de credenciais
    inválidas, sem revelar que o caminho de senha nunca existiu para aquele e-mail (mesma
    cautela da P-22).
    """

    __tablename__ = "usuario"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    senha_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    excluido_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    consentimento_dados_rotina: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consentimento_dados_rotina_em: Mapped[datetime | None] = mapped_column(
        DataHoraUtc, nullable=True
    )
    consentimento_dados_rotina_versao: Mapped[str | None] = mapped_column(String(16), nullable=True)

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

    `origem` (P-62, migração 0017) separa concurso **real** de concurso de **fixture de teste**.
    Antes dela nada no banco fazia essa distinção, e o edital fictício da Fase 4 convivia com o
    edital real do TJ-PR como iguais — o que fazia as páginas públicas das famílias C e D
    (`dados/repositorio_publico.py`) gerarem conteúdo a partir de número que um modelo inventou,
    apresentado como medido. Regra: **`"fixture"` nunca é publicável**. O valor nasce `"real"`;
    quem processa um PDF de `knowledge/fixtures/` passa `origem="fixture"` a `registrar_edital`.
    """

    __tablename__ = "concurso"
    __table_args__ = (CheckConstraint("origem IN ('real','fixture')", name="origem"),)

    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant.id"), index=True, nullable=True
    )
    orgao: Mapped[str] = mapped_column(String(200), nullable=False)
    cargo: Mapped[str] = mapped_column(String(200), nullable=False)
    banca: Mapped[str] = mapped_column(String(200), nullable=False)
    data_prova: Mapped[date | None] = mapped_column(Date, nullable=True)
    origem: Mapped[str] = mapped_column(String(16), default="real", nullable=False)

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


class TopicoRelacao(ChaveUuid, Carimbos, Base):
    """Aresta do grafo de tópicos (modelo de dados §3): liga dois `topico_id` entre si.

    Existe para o caso descoberto na correção estrutural de 19/09/2026 (ADR-0041, fecha a
    P-52): `topico` é vocabulário **por edital** — dois editais que cobram o mesmo assunto (ex.:
    improbidade administrativa, Lei nº 8.429/1992) geram dois `Topico.slug` distintos, e
    conteúdo caro (`dossie_topico`, `aula`) fica pendurado no slug de um único edital. Em vez de
    migrar `dossie_topico`/`aula` para um "conceito canônico" novo (mais invasivo, quebraria o
    versionamento por `topico_id` já testado), a ponte é esta aresta: quem lê dossiê/aula/citação
    por tópico passa a olhar também os tópicos ligados a ele por `origem="equivalencia_curada"`
    antes de desistir.

    `origem` guarda os dois valores que `docs/04-modelo-de-dados.md` §3 já previa
    (`edital`/`dossie` — nenhum implementado ainda; `coocorrencia` idem) mais os dois que a
    correção estrutural de 19/09/2026 acrescentou: `equivalencia_curada` (ADR-0041, peso sempre
    `1.000` — o mesmo assunto, visto por dois editais, nunca uma força parcial) e
    `subconjunto_curado` (I1 de uma revisão independente no mesmo dia, peso sempre `< 1.000` —
    um dossiê/aula cobre só um subconjunto do item do outro edital; ex.: um dossiê que detalha
    apelação/agravo/embargos para o item genérico "Dos recursos" do TJ-PR **não** é a mesma
    coisa que o item inteiro, mesmo citando a mesma lei). As duas são decididas à mão, com
    evidência textual literal (a mesma lei/expressão citada nos dois lados, ou o que fica de
    fora quando é subconjunto), nunca inferidas por similaridade automática (ADR-0036 — "na
    dúvida, não relacione"). `evidencia` é a extensão desta ADR ao mínimo do modelo de dados
    (mesmo padrão de `dna_concurso`/`questao`/`aula` — coluna além do que a Fase 3 documentava):
    sem ela, a relação seria "parecem iguais" sem rastro, o que a tarefa que originou esta tabela
    proíbe explicitamente. A relação é **simétrica na leitura** (`de_id`/`para_id` não importam
    quem é quem — `topicos_equivalentes`/`topicos_subconjunto` buscam nas duas direções) ainda
    que gravada como aresta direcionada; `criar_relacao_equivalente`/`criar_relacao_subconjunto`
    são idempotentes nas duas direções, então nunca existem duas linhas para o mesmo par na
    mesma origem.
    """

    __tablename__ = "topico_relacao"
    __table_args__ = (
        UniqueConstraint("de_id", "para_id", "origem"),
        CheckConstraint("de_id <> para_id", name="de_id_diferente_de_para_id"),
        CheckConstraint(
            "origem IN ('edital','dossie','coocorrencia','equivalencia_curada',"
            "'subconjunto_curado')",
            name="origem",
        ),
    )

    de_id: Mapped[UUID] = mapped_column(ForeignKey("topico.id"), index=True, nullable=False)
    para_id: Mapped[UUID] = mapped_column(ForeignKey("topico.id"), index=True, nullable=False)
    peso: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    origem: Mapped[str] = mapped_column(String(24), nullable=False)
    evidencia: Mapped[str] = mapped_column(Text, nullable=False)

    de: Mapped[Topico] = relationship(foreign_keys=[de_id])
    para: Mapped[Topico] = relationship(foreign_keys=[para_id])


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


class ConcursoRadar(ChaveUuid, Base):
    """Um concurso do catálogo público do radar (fatia 1b, F1.1) — global, nunca por tenant.

    Espelha `dominio.radar.ConcursoDoRadar`, mais o que só a persistência precisa: `fonte_id`
    (de qual fonte veio), `url_evento` (o endpoint de detalhe, único link honesto que a API
    garante — não há página humana medida para o evento), `primeiro_visto_em`/`ultimo_visto_em`
    (o comando `motor.radar.varrer` carimba os dois a cada rodada; um concurso que sai do
    catálogo **nunca é apagado**, só para de ter `ultimo_visto_em` avançado) e `bruto` (o
    `ConcursoDoRadar.model_dump()` da última leitura, para auditoria sem precisar reprocessar a
    API). Não herda `Carimbos`: os dois carimbos de visto substituem `criado_em`/`atualizado_em`
    (mesmo motivo de `PerfilEstudo`/`EventoEstudo`).

    `UniqueConstraint(fonte_id, evento_url)` é a identidade do catálogo: duas fontes poderiam,
    em tese, usar o mesmo `eventoURL` sem colidir.
    """

    __tablename__ = "concurso_radar"
    __table_args__ = (
        UniqueConstraint("fonte_id", "evento_url"),
        CheckConstraint(
            "fase IN ('novos','inscricoes_abertas','em_andamento','encerrado')", name="fase"
        ),
    )

    fonte_id: Mapped[UUID] = mapped_column(ForeignKey("fonte.id"), index=True, nullable=False)
    evento_url: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fase: Mapped[str] = mapped_column(String(24), nullable=False)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    vagas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salario_max_brl: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    periodo_inscricao_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    inscricao_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    inscricao_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    lacunas: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    url_evento: Mapped[str] = mapped_column(String(500), nullable=False)
    primeiro_visto_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    ultimo_visto_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    bruto: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    fonte: Mapped[Fonte] = relationship()


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
    `api/questoes.py`). **Fatia 11 (fecha a P-34, `docs/PENDENCIAS.md`):** o calibrador
    (`dados.repositorio_calibracao.gravar_calibracao`) grava `despublicada_em` (carimbo) e
    `publicada=False` quando decide despublicar uma questão; toda consulta que serve conteúdo
    (`repositorio_questao.proxima_questao`/`contagem_por_topico`/`questoes_publicaveis_do_topico`,
    `api/questoes.py::questao_valida_para_responder`, `api/diagnostico.py`, `motor/dossie.py`,
    `motor/ligar_por_topico.py`) passa a exigir `despublicada_em IS NULL` além de
    `publicavel=True` — `publicavel` continua sendo só o veredito estrutural do curador,
    nunca reescrito pelo calibrador. `dificuldade_est`/`discriminacao_est` agora têm produtor
    (`dominio.calibracao.avaliar_questao`, regras R-4/R-5/R-6/R-7), gravados pelo mesmo
    repositório.
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
    de dados; a V3 produziu `resposta` e `reporte`, a V4 acrescenta `revisao_cartao` (com
    `cartao_id` preenchido) — a fatia 8 produz os seis tipos que faltavam
    (`checkin`/`bloco_iniciado`/`bloco_concluido`/`bloco_pulado`/`discordou`/`distracao`).
    `dados` (V5) é o JSON livre que o modelo de dados já nomeava: o fio da memória grava
    `bloco_topico_id` nele (e, quando o item é intercalado, `fio_motivo`/`fio_origem_topico_id`);
    qualquer chave futura entra sem migração nova. `bloco_id`/`energia` (fatia 8) passam a ser
    colunas reais — o modelo de dados §2 já as nomeava desde a Fase 3 ("questao_id?, bloco_id?,
    cartao_id?, ..., energia?, hora_local"), mas nenhuma fatia anterior tinha `bloco` para
    apontar; `hora_local` continua sem coluna própria (exigiria o fuso do usuário, P-44, ainda
    não resolvido).
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
    bloco_id: Mapped[UUID | None] = mapped_column(ForeignKey("bloco.id"), nullable=True)
    cartao_id: Mapped[UUID | None] = mapped_column(ForeignKey("cartao.id"), nullable=True)
    acertou: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    resposta: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tempo_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confianca_declarada: Mapped[str | None] = mapped_column(String(8), nullable=True)
    energia: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dados: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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


class DispositivoLegal(ChaveUuid, Carimbos, Base):
    """Um dispositivo de norma (caput, inciso ou parágrafo) com o texto literal vigente.

    Espelha `dominio.legislacao.TrechoDispositivo`: uma linha por trecho citável — hoje só o
    nível que a coluna `citacao_canonica` (`docs/04-modelo-de-dados.md` §3) prevê (`artigo`,
    `inciso`, `paragrafo`); alínea ainda não tem coluna própria (nota de escopo em
    `dominio/legislacao.py`). `atualizado_em` (mixin `Carimbos`) é a data da coleta/atualização
    do texto, como o modelo de dados documenta para esta tabela; `fonte_url` é sempre a URL de
    onde o texto foi coletado (Planalto, hoje). `citacao_canonica` é única — recoletar o mesmo
    dispositivo atualiza a linha existente, nunca duplica.
    """

    __tablename__ = "dispositivo_legal"
    __table_args__ = (UniqueConstraint("citacao_canonica"),)

    citacao_canonica: Mapped[str] = mapped_column(String(120), nullable=False)
    norma: Mapped[str] = mapped_column(String(120), nullable=False)
    artigo: Mapped[str] = mapped_column(String(16), nullable=False)
    inciso: Mapped[str | None] = mapped_column(String(16), nullable=True)
    paragrafo: Mapped[str | None] = mapped_column(String(16), nullable=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fonte_url: Mapped[str] = mapped_column(String(500), nullable=False)


class Citacao(ChaveUuid, Carimbos, Base):
    """Liga um `DispositivoLegal` a um conteúdo (`questao` nesta rodada; `aula`/`dossie` depois).

    `conteudo_id` não é FK — mesma convenção polimórfica de `ReporteErro` (`conteudo_tipo` decide
    a tabela). `posicao` é a ordem da citação dentro do conteúdo (ex.: 1ª, 2ª citação de uma
    aula), para reconstruir a ordem de exibição sem depender de `criado_em`.
    """

    __tablename__ = "citacao"
    __table_args__ = (
        CheckConstraint("conteudo_tipo IN ('questao','aula','dossie')", name="conteudo_tipo"),
    )

    conteudo_tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    conteudo_id: Mapped[UUID] = mapped_column(nullable=False)
    dispositivo_id: Mapped[UUID] = mapped_column(
        ForeignKey("dispositivo_legal.id"), index=True, nullable=False
    )
    posicao: Mapped[int] = mapped_column(Integer, nullable=False)

    dispositivo: Mapped[DispositivoLegal] = relationship()


class Cartao(ChaveUuid, Carimbos, Base):
    """Cartão de revisão espaçada (modelo de dados §2, F4.3): estado do `fsrs.Card` serializado.

    `stability, difficulty, due, reps, lapses, last_review` são os seis campos nomeados no
    modelo de dados; `estado_fsrs`/`passo_fsrs` são o adendo à ADR-0022 (`docs/DECISOES.md`,
    detalhado em `docs/fatias/V4-revisao-espacada.md` §2) — sem eles, reconstruir o `fsrs.Card`
    perde a fase de aprendizado e recalcula um `due` errado. `UniqueConstraint(usuario_id,
    questao_id)` é o que cumpre "não regenere o que já existe": errar a mesma questão duas vezes
    nunca cria um segundo cartão (`questao_id IS NULL`, dos cartões manuais da fatia futura, não
    entra nessa unicidade — SQL trata `NULL` como distinto de `NULL`). `mnemonico_id` não tem FK
    ainda porque `mnemonico` não existe (F4.5, fatia futura); nenhuma linha o preenche nesta
    fatia.
    """

    __tablename__ = "cartao"
    __table_args__ = (
        CheckConstraint("origem IN ('auto_erro','manual')", name="origem"),
        UniqueConstraint("usuario_id", "questao_id"),
        Index("ix_cartao_usuario_due", "usuario_id", "due"),
    )

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), index=True, nullable=False)
    questao_id: Mapped[UUID | None] = mapped_column(ForeignKey("questao.id"), nullable=True)
    topico_id: Mapped[UUID] = mapped_column(ForeignKey("topico.id"), nullable=False)
    frente: Mapped[str] = mapped_column(Text, nullable=False)
    verso: Mapped[str] = mapped_column(Text, nullable=False)
    mnemonico_id: Mapped[UUID | None] = mapped_column(nullable=True)
    origem: Mapped[str] = mapped_column(String(16), nullable=False)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    due: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False)
    last_review: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    estado_fsrs: Mapped[int] = mapped_column(Integer, nullable=False)
    passo_fsrs: Mapped[int | None] = mapped_column(Integer, nullable=True)

    usuario: Mapped[Usuario] = relationship()
    questao: Mapped[Questao | None] = relationship()
    topico: Mapped[Topico] = relationship()


class DossieTopico(ChaveUuid, Carimbos, Base):
    """O dossiê de um tópico (modelo de dados §3).

    Dispositivos com trecho e URL, log de buscas e lacunas declaradas — a fonte única que a
    aula e as questões inéditas desse tópico usam. Versionado por `topico_id`: uma mudança de
    lei gera versão nova e marca a antiga em
    `substituido_por` (o dependente, quando reprocessado, sabe de onde veio). Espelha
    `dominio.dossie.ConteudoDossie`: `fontes` guarda a lista de
    `dominio.dossie.FonteDossie.model_dump()` (inclui `norma`/`artigo`/`inciso`/`paragrafo`/
    `citacao_canonica`, não só URL+trecho — mais rico que a tabela de exibição da skill
    `deep-research-topico`, porque é o que liga o dossiê a `dispositivo_legal`/`citacao` na
    fatia "ligar por tópico"); `log_buscas`, a lista de `dominio.dossie.EntradaLogBusca.
    model_dump()`. `validado_em` fica `None` até um humano/validador revisar (fora do escopo
    desta rodada, que é 100 % determinística).
    """

    __tablename__ = "dossie_topico"
    __table_args__ = (UniqueConstraint("topico_id", "versao"),)

    topico_id: Mapped[UUID] = mapped_column(ForeignKey("topico.id"), index=True, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    fontes: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    bibliografia: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    log_buscas: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    validado_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    substituido_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("dossie_topico.id"), nullable=True
    )

    topico: Mapped[Topico] = relationship()


class Aula(ChaveUuid, Carimbos, Base):
    """A aula de um tópico (modelo de dados §3, fatia 6): o dossiê reorganizado para aprender.

    Espelha `dominio.aula.ConteudoAula`: `citacoes` guarda
    `dominio.aula.CitacaoAula.model_dump()` (canônica, `F-n` do dossiê, trecho literal já
    embutido — a tela de aula não precisa juntar com `dispositivo_legal`/`citacao` para o
    popover, o mesmo princípio de `dossie_topico.fontes`); `relacionados`, a lista de
    `dominio.aula.RelacionadoAula.model_dump()` (fio da memória (a)); `como_a_banca_cobra` e
    `lacunas_declaradas` são a extensão desta fatia ao mínimo do modelo de dados (mesmo padrão de
    `dna_concurso`/`questao` — coluna JSON além do que `docs/04-modelo-de-dados.md` já
    documentava, decisão registrada em `docs/fatias/6-trilha-e-aulas.md` §1); `mnemonico` é
    `dominio.aula.MnemonicoAula.model_dump()` ou `None` (linha 6 do PRD, §5 do plano — gerado
    junto com a aula, mesmo rigor de citação). `audio_url` fica sempre `None` nesta fatia (linha
    6 do PRD exclui áudio até o piloto mostrar uso). `validado_em`/`publicada` só existem depois
    de `dominio.aula.verificar_aula` aprovar — reprovada não grava linha nenhuma
    (`dados.repositorio_aula.salvar_aula` só é chamado pelo comando depois do veredito).
    """

    __tablename__ = "aula"
    __table_args__ = (UniqueConstraint("topico_id", "versao"),)

    dossie_id: Mapped[UUID] = mapped_column(ForeignKey("dossie_topico.id"), nullable=False)
    dossie_versao: Mapped[int] = mapped_column(Integer, nullable=False)
    topico_id: Mapped[UUID] = mapped_column(ForeignKey("topico.id"), index=True, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    texto_denso: Mapped[str] = mapped_column(Text, nullable=False)
    texto_leigo: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    citacoes: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    relacionados: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    como_a_banca_cobra: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    lacunas_declaradas: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    mnemonico: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validado_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    publicada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    dossie: Mapped[DossieTopico] = relationship()
    topico: Mapped[Topico] = relationship()


class PerfilEstudo(ChaveUuid, Base):
    """Rotina do aluno (fatia 7, F2.2): horas por dia, horário, energia, data-alvo e o principal.

    Append-only por `versao` (modelo de dados §2) — por isso não herda `Carimbos`: não há
    `atualizado_em`/`ON UPDATE` porque uma mudança de rotina nunca atualiza a linha anterior, cria
    uma nova (mesmo motivo de `EventoEstudo` não usar o mixin). `dados/repositorio_perfil.py` lê
    sempre a de maior `versao`. `concurso_principal_id` resolve a P-23 (`docs/PENDENCIAS.md`): a
    escolha explícita da aluna, que `repositorio_edital.concurso_principal` passa a preferir à
    heurística "o último edital subido". `concursos_acompanhados` nasce sempre `[]` nesta fatia —
    a UI de "principal + acompanhando" é F1.3, fatia 1b; a coluna só evita uma migração nova
    quando essa fatia chegar.
    """

    __tablename__ = "perfil_estudo"
    __table_args__ = (
        UniqueConstraint("usuario_id", "versao"),
        CheckConstraint("energia_tipica IN ('alta','media','baixa')", name="energia_tipica"),
    )

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), index=True, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    horas_por_dia_semana: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    horario_preferido: Mapped[str] = mapped_column(String(16), nullable=False)
    energia_tipica: Mapped[str] = mapped_column(String(8), nullable=False)
    data_alvo: Mapped[date | None] = mapped_column(Date, nullable=True)
    concurso_principal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("concurso.id"), nullable=True
    )
    concursos_acompanhados: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DataHoraUtc, default=agora_utc, nullable=False)

    usuario: Mapped[Usuario] = relationship()
    concurso_principal: Mapped[Concurso | None] = relationship()


class PlanoDia(ChaveUuid, Base):
    """O plano de um dia de uma usuária — nasce à noite (`versao=1`), reescrito pelo check-in.

    Não herda `Carimbos`: `gerado_em` já é o carimbo de criação e não há `atualizado_em` — uma
    reescrita (check-in, F3.2) nunca faz `UPDATE` nesta linha, cria uma nova com `versao` maior
    para o mesmo `(usuario_id, data)` (a versão é o histórico, mesmo espírito de `PerfilEstudo`
    e `EventoEstudo` não terem o mixin). `energia`/`sono_h` são `None` na `versao=1` (a geração
    noturna não tem check-in ainda); o check-in os preenche com os valores reais.

    Attributes:
        usuario_id: dona do plano.
        data: o dia planejado (data local da aluna — sem fuso próprio nesta fatia, P-44 já
            registrada na V4 para `Cartao.due`).
        versao: `1` = gerada pelo job noturno; `2+` = reescrita por check-in.
        gerado_em: instante em que esta versão foi montada.
        energia: `1`–`5` declarada no check-in; `None` na `versao=1`.
        sono_h: horas de sono declaradas no check-in; `None` na `versao=1`.
        tempo_min: minutos disponíveis usados para montar este plano.
        modo: `"normal"`/`"descanso"`/`"semana_prova"` (só os dois primeiros têm comportamento
            nesta fatia — `dominio.plano.montar_plano` nunca produz `"semana_prova"`).
        porque_geral: a explicação final do dia inteiro (`dominio.plano.motivo_geral_do_plano`)
            — nunca vazia, mesmo sem bloco nenhum.
    """

    __tablename__ = "plano_dia"
    __table_args__ = (
        UniqueConstraint("usuario_id", "data", "versao"),
        CheckConstraint("modo IN ('normal','descanso','semana_prova')", name="modo"),
    )

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuario.id"), index=True, nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DataHoraUtc, default=agora_utc, nullable=False)
    energia: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sono_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    tempo_min: Mapped[int] = mapped_column(Integer, nullable=False)
    modo: Mapped[str] = mapped_column(String(16), nullable=False)
    porque_geral: Mapped[str] = mapped_column(Text, nullable=False)

    usuario: Mapped[Usuario] = relationship()
    blocos: Mapped[list["Bloco"]] = relationship(
        order_by="Bloco.ordem", cascade="all, delete-orphan"
    )


class Bloco(ChaveUuid, Base):
    """Um bloco do dia — aula, questões, revisão ou descanso — sempre com o porquê visível.

    Não herda `Carimbos`: `status`/`iniciado_em`/`concluido_em` mudam por ação da aluna (iniciar,
    concluir, pular, discordar), cada mudança já vira um `EventoEstudo` próprio (o registro
    append-only); o `Bloco` guarda só o estado atual, não o histórico de mudanças dele. Quando a
    aluna discorda (F3.3/F3.4), o bloco antigo vira `status="trocado"` e um `Bloco` novo nasce na
    mesma `ordem` — nunca um `UPDATE` no lugar do tipo/tópico antigo, para o porquê original
    continuar auditável junto do evento `discordou`.

    Attributes:
        plano_dia_id: o `PlanoDia` (uma versão específica) dono deste bloco.
        ordem: posição no dia, a partir de 1.
        tipo: `"aula"`/`"questoes"`/`"revisao"`/`"resumo"`/`"descanso"` — só os três primeiros têm
            produtor nesta fatia (`"resumo"` é F4.7, `"descanso"` como bloco explícito não nasce
            aqui — ver `dominio.plano.montar_plano`).
        topico_id: tópico do bloco; `None` em `"revisao"` (abrange vários tópicos).
        aula_id: `None` nesta fatia — a tela de bloco de aula resolve a aula pelo `topico_id` via
            `aula_publicada_do_topico`, mesmo caminho de `/topico/{slug}/aula`; a coluna existe
            porque o modelo de dados a nomeia, para quando fixar a aula exata valer a pena.
        duracao_min: duração estimada.
        hora_sugerida: relógio sugerido (`dominio.plano._atribuir_ordem_e_hora`).
        porque: a explicação deste bloco — `NOT NULL` por contrato (F3.3 CA).
        status: `"pendente"`/`"iniciado"`/`"concluido"`/`"pulado"`/`"trocado"`.
        iniciado_em: quando a aluna apertou "Iniciar"; `None` até lá.
        concluido_em: quando marcou "Concluí"; `None` até lá (inclusive quando `status="pulado"`
            ou `"trocado"`).
    """

    __tablename__ = "bloco"
    __table_args__ = (
        CheckConstraint("tipo IN ('aula','questoes','revisao','resumo','descanso')", name="tipo"),
        CheckConstraint(
            "status IN ('pendente','iniciado','concluido','pulado','trocado')", name="status"
        ),
    )

    plano_dia_id: Mapped[UUID] = mapped_column(
        ForeignKey("plano_dia.id"), index=True, nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    topico_id: Mapped[UUID | None] = mapped_column(ForeignKey("topico.id"), nullable=True)
    aula_id: Mapped[UUID | None] = mapped_column(ForeignKey("aula.id"), nullable=True)
    duracao_min: Mapped[int] = mapped_column(Integer, nullable=False)
    hora_sugerida: Mapped[time | None] = mapped_column(Time, nullable=True)
    porque: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pendente", nullable=False)
    iniciado_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)
    concluido_em: Mapped[datetime | None] = mapped_column(DataHoraUtc, nullable=True)

    topico: Mapped[Topico | None] = relationship()
    aula: Mapped[Aula | None] = relationship()


class Calibracao(ChaveUuid, Base):
    """Uma linha do relatório diário do calibrador (fatia 11) para uma questão.

    Espelha `dominio.calibracao.AjusteCalibracao`: uma linha por questão avaliada, por dia de
    execução — histórico, nunca sobrescrito (`data` + `questao_id` não é único de propósito: rodar
    o calibrador todo dia acumula uma série temporal de `dificuldade_real`/`discriminacao`/`acao`
    por questão, o que o painel de curva/previsão da fatia 10 pode reaproveitar depois).
    `discriminacao` é `NULL` quando `AjusteCalibracao.discriminacao == "desconhecido"` — nunca um
    número fabricado para caber na coluna `Float`. **Nota de escopo:** `docs/04-modelo-de-dados.md`
    §6 lista `acao` com três valores (`manter`/`sinalizar`/`despublicar`); a skill
    `calibracao-de-questoes` (fase 4, posterior a esse rascunho) define quatro
    (`manter`/`ajustar`/`sinalizar`/`despublicar`) — `ajustar` é o que atualiza
    `questao.dificuldade_est`/`discriminacao_est` sem sinalizar nem despublicar (R-4/R-6/R-7).
    Esta tabela segue a skill (fonte de verdade do contrato, CLAUDE.md "Contratos vêm das
    skills"); documentado aqui em vez de reescrever o modelo de dados nesta fatia.
    """

    __tablename__ = "calibracao"
    __table_args__ = (
        CheckConstraint("acao IN ('manter','ajustar','sinalizar','despublicar')", name="acao"),
        Index("ix_calibracao_questao_data", "questao_id", "data"),
    )

    questao_id: Mapped[UUID] = mapped_column(ForeignKey("questao.id"), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    dificuldade_real: Mapped[float] = mapped_column(Float, nullable=False)
    discriminacao: Mapped[float | None] = mapped_column(Float, nullable=True)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    acao: Mapped[str] = mapped_column(String(16), nullable=False)

    questao: Mapped[Questao] = relationship()


class VereditoQuestao(ChaveUuid, Base):
    """O histórico de tentativas de validação de uma inédita (fatia 5, RF-28).

    Append-only, como `EventoEstudo`: uma linha por chamada a `dominio.validacao_questao.julgar`
    para uma dada `Questao` — nunca atualizada nem apagada (por isso não herda `Carimbos`, sem
    `atualizado_em`). Existe porque `questao.validada_em`/`questao.validador_versao` sozinhos só
    guardam o **último** veredito; a fatia 5 precisa do histórico completo, inclusive das
    tentativas reprovadas, para RF-28 ("rejeição registrada com motivo", nunca descartada em
    silêncio) — uma inédita reprovada continua na tabela `questao` com `publicavel=False`, e
    cada tentativa de validação dela (aprovada ou não) fica aqui, com o motivo.

    Attributes:
        questao_id: a questão avaliada (FK — a `Questao` já existe antes do primeiro veredito,
            gravada pelo comando assim que o gerador devolve o item).
        aprovado: o `Veredito.aprovado` desta tentativa.
        motivos: `Veredito.motivos` desta tentativa (JSON — lista de strings; vazia quando
            aprovado).
        validador_versao: `Veredito.validador_versao` desta tentativa.
        criado_em: quando esta tentativa de validação rodou.
    """

    __tablename__ = "veredito_questao"

    questao_id: Mapped[UUID] = mapped_column(ForeignKey("questao.id"), index=True, nullable=False)
    aprovado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    motivos: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    validador_versao: Mapped[str] = mapped_column(String(64), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DataHoraUtc, default=agora_utc, nullable=False)

    questao: Mapped[Questao] = relationship()
