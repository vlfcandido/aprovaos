// Fase 1 do AprovaOS — pesquisa de FATOS do produto (bancas, fontes, mercado, mobile, SEO, concorrentes, regulatório) + GAPS do ramo de estudos via o script leve da fábrica (workflow filho, ADR-0006).
// Quando ler: para rodar/retomar a Fase 1. args = { gaps_prontos: [gaps dos pilotos pf-estudos, nicho_id 'est-piloto'], script_fabrica: caminho absoluto do script leve, so_fatos: bool, so_gaps: bool, angulos: [ids] }.
export const meta = {
  name: 'aprovaos-fase1-pesquisa',
  description: 'Fase 1 AprovaOS: fatos por ângulo (Sonnet, ≤10 buscas/≤12 aberturas) → verificação cética dos ângulos que decidem (Sonnet) → síntese (Opus); em paralelo, gaps do ramo de estudos pelo script leve da fábrica (6 ângulos, 3 etapas, Chrome sequencial)',
  phases: [
    { title: 'Fatos', detail: '1 agente por ângulo: bancas, fontes de provas, fontes de conhecimento, mercado, mobile, SEO, concorrentes BR/global, regulatório', model: 'sonnet' },
    { title: 'Verificação', detail: 'cético abre cada URL dos ângulos que decidem exame e fontes (Sonnet)', model: 'sonnet' },
    { title: 'Síntese', detail: 'recomendação numérica de exame inicial + prioridade do mapa de fontes (Opus)' },
    { title: 'Gaps', detail: 'workflow filho da fábrica (est-*), compartilha orçamento' },
  ],
}

// ---------- schemas ----------
const EVID = { type: 'object', properties: {
  url: { type: 'string' }, tipo: { type: 'string', enum: ['oficial', 'imprensa', 'review', 'forum', 'reddit', 'loja_app', 'pagina_produto', 'academico', 'outro'] },
  trecho: { type: 'string' }, data: { type: 'string' }, secundaria: { type: 'boolean' }, contexto: { type: 'string' } }, required: ['url', 'tipo', 'trecho', 'secundaria'] }
const FATO = { type: 'object', properties: {
  id: { type: 'string' }, afirmacao: { type: 'string' }, valor: { type: 'string' }, unidade_ou_periodo: { type: 'string' },
  evidencias: { type: 'array', items: EVID }, confianca: { type: 'string', enum: ['alta', 'media', 'baixa'] }, observacao: { type: 'string' } },
  required: ['id', 'afirmacao', 'valor', 'evidencias', 'confianca'] }
const FONTE_MOTOR = { type: 'object', properties: {
  nome: { type: 'string' }, url: { type: 'string' },
  tipo: { type: 'string', enum: ['banca', 'edital_diario_oficial', 'legislacao', 'jurisprudencia', 'enem_inep', 'oab', 'conhecimento_aberto', 'agregador_terceiro', 'outro'] },
  formato: { type: 'string', enum: ['pdf', 'html', 'rss', 'api', 'sitemap', 'misto', 'desconhecido'] },
  frequencia_estimada: { type: 'string' }, deteccao_novidade: { type: 'string', enum: ['rss', 'sitemap', 'diff', 'api', 'desconhecido'] },
  termos_de_uso: { type: 'string' }, url_termos: { type: 'string' }, licenca_ou_risco: { type: 'string' }, volume_estimado: { type: 'string' },
  evidencias: { type: 'array', items: EVID } }, required: ['nome', 'url', 'tipo', 'formato', 'deteccao_novidade', 'licenca_ou_risco', 'evidencias'] }
const CONCORRENTE = { type: 'object', properties: {
  nome: { type: 'string' }, url: { type: 'string' }, publico: { type: 'string' }, planos_e_precos: { type: 'string' }, url_precos: { type: 'string' },
  funcionalidades_ia: { type: 'string' }, o_que_promete: { type: 'string' }, onde_ia_e_rasa: { type: 'string' }, reclamacoes_recorrentes: { type: 'string' },
  evidencias: { type: 'array', items: EVID } }, required: ['nome', 'url', 'publico', 'planos_e_precos', 'funcionalidades_ia', 'evidencias'] }
const RESULT_ANGULO = { type: 'object', properties: {
  fatos: { type: 'array', items: FATO }, fontes_motor: { type: 'array', items: FONTE_MOTOR }, concorrentes: { type: 'array', items: CONCORRENTE },
  palavras_chave: { type: 'array', items: { type: 'object', properties: { termo: { type: 'string' }, intencao: { type: 'string' }, volume: { type: 'string' }, volume_medido: { type: 'boolean' }, fonte_volume: { type: 'string' }, dificuldade: { type: 'string' }, quem_ranqueia: { type: 'string' } }, required: ['termo', 'intencao', 'volume', 'volume_medido', 'dificuldade'] } },
  lacunas: { type: 'array', items: { type: 'string' } }, buscas_feitas: { type: 'array', items: { type: 'string' } } },
  required: ['fatos', 'lacunas', 'buscas_feitas'] }
const VER = { type: 'object', properties: { vereditos: { type: 'array', items: { type: 'object', properties: {
  id: { type: 'string' },
  evidencias: { type: 'array', items: { type: 'object', properties: { url: { type: 'string' }, abre: { type: 'boolean' }, trecho_confere: { type: 'boolean' }, observacao: { type: 'string' } }, required: ['url', 'abre', 'trecho_confere'] } },
  sustentado: { type: 'boolean' }, correcao: { type: 'string' } }, required: ['id', 'evidencias', 'sustentado'] } } }, required: ['vereditos'] }
const SINTESE = { type: 'object', properties: {
  exame_recomendado: { type: 'string' }, justificativa_numerica: { type: 'string' },
  comparacao: { type: 'array', items: { type: 'object', properties: { exame: { type: 'string' }, publico_anual: { type: 'string' }, provas_publicas: { type: 'string' }, padrao_banca: { type: 'string' }, sazonalidade: { type: 'string' }, fontes_abertas: { type: 'string' }, pontos_contra: { type: 'string' } }, required: ['exame', 'publico_anual', 'provas_publicas', 'padrao_banca', 'sazonalidade', 'pontos_contra'] } },
  mapa_fontes_prioridade: { type: 'array', items: { type: 'object', properties: { nome: { type: 'string' }, por_que_primeiro: { type: 'string' }, risco: { type: 'string' } }, required: ['nome', 'por_que_primeiro', 'risco'] } },
  mobile_recomendacao: { type: 'string' }, mobile_justificativa: { type: 'string' },
  fatos_nao_sustentados_que_pesam: { type: 'array', items: { type: 'string' } },
  lacunas_para_pendencias: { type: 'array', items: { type: 'string' } } },
  required: ['exame_recomendado', 'justificativa_numerica', 'comparacao', 'mapa_fontes_prioridade', 'mobile_recomendacao', 'mobile_justificativa', 'lacunas_para_pendencias'] }

// ---------- regras ----------
const BLOQUEADOS = 'reclameaqui.com.br, workana.com, 99freelas.com.br, reddit.com, catho.com.br, indeed.com, g2.com, freelancer.com, glassdoor.com'
const REGRAS = `
REGRAS (valem para todo agente desta pesquisa):
- Carregue as ferramentas com ToolSearch usando a query "select:WebSearch,WebFetch" antes de qualquer busca.
- Português do Brasil. Nenhuma URL inventada: toda URL foi ABERTA por você com WebFetch e o trecho é LITERAL (≤ 60 palavras). Sem trecho, não inclua. O snippet do WebSearch NÃO é evidência.
- Fonte PRIMÁRIA sempre que possível (site da banca, INEP, Planalto, STF/STJ, página de preços do produto, loja de app). Imprensa citando órgão oficial é aceita SÓ quando o dado primário não abrir: marque secundaria=true e confianca="baixa" ou "media".
- "não medido" é melhor que número inventado. Registre em "lacunas" o que procurou e não achou (site + termos).
- ECONOMIA DE CONTEXTO: no máximo 10 chamadas de WebSearch e 12 aberturas com WebFetch. Em TODO WebFetch passe um prompt curto pedindo SOMENTE os trechos literais que respondem à pergunta (números, datas, termos de uso, preços), ≤ 60 palavras cada — nunca resumo da página inteira. Não repita buscas parecidas. Ao terminar, escreva o resultado imediatamente.
- Sites que bloqueiam o WebFetch (não gaste abertura): ${BLOQUEADOS}. Use alternativas (site oficial, play.google.com, apps.apple.com, capterra.com.br, imprensa especializada como Folha Dirigida, JC Concursos, g1).
- Neutralidade: o produto tem uma HIPÓTESE (concursos Cebraspe+FGV). Não a favoreça: reporte números de ENEM e OAB com a mesma honestidade quando pedido.
- ids dos fatos: "<angulo>-01", "<angulo>-02"...
`

// ---------- ângulos de fatos ----------
const ANGULOS = [
  { id: 'bancas', verificar: true, prompt: `VOCÊ LEVANTA FATOS SOBRE BANCAS DE CONCURSO no Brasil, para decidir o exame inicial de um produto de estudo.
A FUNDO — Cebraspe (cebraspe.org.br) e FGV Conhecimento (fgv.br/fgvconhecimento ou conhecimento.fgv.br): (a) onde ficam provas e gabaritos anteriores no site oficial (URL da seção, formato PDF/HTML, se há busca por concurso/ano), (b) quantos concursos organizou nos últimos 12–24 meses (número com fonte), (c) formato das questões (certo/errado, múltipla escolha A–E, discursiva; penalização por erro), (d) concursos previstos/autorizados nos próximos 12 meses (calendário com fonte: banca ou imprensa especializada), (e) padrões notórios da banca citados por professores/aprovados (só com URL e trecho).
DE PASSAGEM (1–2 fatos cada, só para comparar): FCC, Vunesp, Cesgranrio, Instituto AOCP — volume aproximado e formato.
Entregue 8–15 fatos com evidência. Cada fato = um número ou característica verificável.` },
  { id: 'fontes-provas', verificar: true, prompt: `VOCÊ MAPEIA FONTES DE PROVAS E GABARITOS para um Motor de Conhecimento que vai coletar automaticamente.
Para CADA fonte preencha "fontes_motor": URL exata da seção de provas, formato (PDF/HTML/RSS/API), como detectar novidade (RSS? sitemap? só diff de página?), frequência estimada de novidade, TERMOS DE USO (abra a página de termos/política do site e copie o trecho sobre reprodução/uso automatizado/robôs; se não houver, diga "sem termos localizados"), licença ou risco (prova de concurso público é documento público? há aviso de copyright?), volume estimado (quantas provas/anos).
Fontes obrigatórias: Cebraspe (provas anteriores), FGV Conhecimento (provas anteriores), INEP (provas e gabaritos do ENEM: gov.br/inep), OAB/FGV (exame de ordem: provas anteriores em oab.fgv.br ou examedeordem.oab.org.br), Diário Oficial da União (in.gov.br — editais; existe API ou RSS?), 2 portais agregadores de editais (ex.: pciconcursos.com.br, concursosnobrasil.com.br) com seus termos de uso.
Também: 2 agregadores de questões (Qconcursos, Tec Concursos) — o que os termos de uso deles dizem sobre extração (só para registrar risco; não é fonte do Motor).
Entregue as fontes em "fontes_motor" e 4–8 fatos-resumo em "fatos" (ex.: "INEP publica provas do ENEM desde 1998 em PDF").` },
  { id: 'fontes-conhecimento', verificar: true, prompt: `VOCÊ MAPEIA FONTES ABERTAS DE CONHECIMENTO e BIBLIOGRAFIA para as matérias mais cobradas por Cebraspe e FGV em concursos (Língua Portuguesa, Direito Constitucional, Direito Administrativo, Raciocínio Lógico-Matemático, Informática/Noções de TI, Administração Pública/AFO, Direito Penal/Processual quando couber).
Para CADA fonte preencha "fontes_motor": Planalto legislação consolidada (planalto.gov.br/ccivil_03 — formato, existe RSS/API? como detectar alteração de lei?), LexML (lexml.gov.br — API?), STF (portal.stf.jus.br: informativos, súmulas, teses de repercussão geral — RSS? API?), STJ (stj.jus.br: informativos, súmulas, repetitivos — RSS?), Senado/Câmara (dados abertos de normas), cartilhas/manuais oficiais (ex.: Manual de Redação da Presidência, cartilhas do TCU/CGU), SciELO e repositórios abertos (licença CC?), Wikisource/domínio público.
Bibliografia: quais autores/obras os editais e programas citam ou os aprovados recomendam por matéria (3–5 por matéria, com URL de onde achou — só como REFERÊNCIA, nunca conteúdo).
Termos de uso e licença de cada fonte com trecho literal. Entregue "fontes_motor" + 5–10 fatos (ex.: "STF publica Informativo semanal em HTML e PDF, com RSS em ...").` },
  { id: 'mercado', verificar: true, prompt: `VOCÊ DIMENSIONA O MERCADO BRASILEIRO DE ESTUDO PARA PROVAS, por módulo, com fonte.
Para cada módulo, números anuais mais recentes: (1) CONCURSOS — candidatos inscritos por ano (estimativas de mercado; inscritos no CNU/"Enem dos concursos" 2024–2026 é dado oficial do MGI), número de concursos/vagas por ano, gasto médio com cursinho/assinatura; receita ou número de alunos de Gran, Estratégia, Qconcursos (imprensa, marcar secundária); (2) ENEM — inscritos e presentes (INEP, gov.br); (3) OAB — inscritos por exame (FGV/OAB); (4) RESIDÊNCIA MÉDICA — inscritos no ENARE e maiores processos; (5) VESTIBULARES grandes (Fuvest, Unicamp) — inscritos.
Também: preço de assinatura dos 3 maiores (Qconcursos, Gran, Estratégia) lido na página de preços.
Entregue 10–15 fatos, cada um com URL aberta e trecho com o número. Dado primário não abriu → imprensa citando o órgão, secundaria=true.` },
  { id: 'mobile', verificar: true, prompt: `VOCÊ LEVANTA EVIDÊNCIA SOBRE ESTUDO NO CELULAR vs. WEB para decidir web/PWA/app.
(1) Apps de concurso e ENEM no Google Play e App Store: Qconcursos, Gran Cursos, Estratégia, Tec Concursos, Aprova Concursos, Descomplica, Me Salva, Anki (AnkiDroid) — downloads ("mais de X mil"), nota, número de avaliações, e 2–3 reclamações recorrentes de 1–2 estrelas (trecho literal, data). play.google.com e apps.apple.com abrem no WebFetch.
(2) Pesquisas sobre hábito de estudo no celular no Brasil (TIC Domicílios/Cetic.br — acesso à internet só pelo celular; pesquisas de plataformas de ensino), com URL e número.
(3) O que só o app entrega vs. PWA: push (iOS suporta web push desde qual versão? fonte Apple/WebKit), offline, modo foco — fatos com fonte oficial.
Entregue 8–12 fatos com evidência.` },
  { id: 'seo', verificar: false, prompt: `VOCÊ LEVANTA PALAVRAS-CHAVE de SEO para um produto de estudo para concursos (e, para comparar, ENEM e OAB), SEM ferramentas com login.
Método: (a) Google autocompletar e "pesquisas relacionadas" via WebSearch para cabeças como "como estudar para concurso", "plano de estudos concurso", "questões cebraspe", "como a FGV cobra", "edital verticalizado", "cronograma de estudos", "simulado enem", "como passar na OAB"; (b) Ahrefs Free Keyword Generator (ahrefs.com/keyword-generator) para volume e KD quando abrir; (c) quem ranqueia no top 3 hoje (portal grande, cursinho, blog, fórum) para 10–15 termos.
Entregue em "palavras_chave" 25–40 termos com intenção (informacional/transacional), volume (número se medido; senão "não medido" e volume_medido=false), dificuldade estimada e quem ranqueia. Em "fatos", 3–5 observações (ex.: "termos 'como a banca X cobra Y' têm páginas de cursinho no top 3"). Registre em "lacunas" que o volume real será medido no Keyword Planner pelo dono.` },
  { id: 'concorrentes-br', verificar: false, prompt: `VOCÊ MAPEIA CONCORRENTES BRASILEIROS de estudo para concursos com foco em IA: Qconcursos, Gran Cursos Online, Estratégia Concursos, Tec Concursos, Concursa AI, EstudaIA, GoConcursos, Clipping Concursos, Mister Concursos, Aprova Concursos (e 1–2 que descobrir).
Para cada um preencha "concorrentes": público, planos e preços LIDOS na página de preços (URL), funcionalidades de IA declaradas (assistente, correção, plano de estudos, geração de questões — cite a página), o que promete, onde a IA parece rasa (só se houver evidência: review, post, demo; senão "não medido"), reclamações recorrentes (Google Play/App Store 1–2★, Capterra; Reclame Aqui bloqueia o WebFetch — não gaste).
Entregue 8–12 concorrentes + 3–5 fatos transversais (ex.: faixa de preço mediana).` },
  { id: 'concorrentes-global', verificar: false, prompt: `VOCÊ MAPEIA CONCORRENTES GLOBAIS de "agente de estudo com IA" e preparação para provas: produtos que fazem plano diário adaptativo, tutor proativo, previsão de nota — ex.: Quizlet (Q-Chat), Magoosh, UWorld, Khanmigo, Speak, Duolingo Max, Brainly, StudyFetch, Turbolearn, Knowunity, Kaplan/Princeton Review com IA, e agentes de estudo lançados em 2025–2026.
Para cada um: público, preço (página oficial), o que a IA faz de verdade (proativo ou só responde?), o que promete, evidência de resultado (se houver), reclamações recorrentes (App Store/Play, Trustpilot). Marque quem tem "plano diário que se reajusta" e "previsão de nota".
Entregue 8–12 concorrentes + 3–5 fatos (ex.: preços em US$/mês, quem é proativo).` },
  { id: 'regulatorio', verificar: true, prompt: `VOCÊ LEVANTA O QUADRO JURÍDICO do uso de provas e conteúdo, com fonte primária.
(1) Provas de concurso público e do ENEM são documentos públicos? Base: Lei 9.610/1998 art. 8º (o que não é protegido) e art. 46; Lei de Acesso à Informação; há decisões judiciais ou pareceres sobre reprodução de questões de concurso por cursinhos/sites (busque STJ/TJ, "reprodução de questões de concurso direito autoral")? Copie os trechos literais dos dispositivos no Planalto.
(2) Termos de uso de Cebraspe, FGV, INEP sobre reprodução (se não achou no ângulo anterior, tente aqui: página "termos" ou rodapé).
(3) LGPD: dados de humor/energia/rotina são "dado sensível" (art. 5º, II)? Copie o dispositivo. O que muda para o regime de pequeno porte (Resolução ANPD CD/ANPD nº 2/2022 — trecho).
(4) Uso de LLM para gerar questões "no estilo" de uma banca: há vedação? (marca registrada da banca — INPI; concorrência desleal; use fontes oficiais ou artigos jurídicos com URL).
Entregue 8–12 fatos, cada um com trecho literal e URL do Planalto/tribunal/ANPD.` },
]

function promptAngulo(a) {
  return `${REGRAS}
ÂNGULO "${a.id}". ${a.prompt}
Formato: preencha "fatos" (obrigatório), "fontes_motor"/"concorrentes"/"palavras_chave" quando o ângulo pedir, "lacunas" e "buscas_feitas" (todas as queries usadas).`
}

function promptVerif(a, r) {
  const itens = (r.fatos || []).map(f => ({ id: f.id, afirmacao: f.afirmacao, valor: f.valor, evidencias: f.evidencias }))
    .concat((r.fontes_motor || []).map((f, i) => ({ id: `${a.id}-fonte-${String(i + 1).padStart(2, '0')}`, afirmacao: `${f.nome}: ${f.url} — ${f.licenca_ou_risco}`, valor: f.termos_de_uso || '', evidencias: f.evidencias })))
  return `VOCÊ É UM VERIFICADOR CÉTICO. Para cada item abaixo, abra CADA URL em "evidencias" com WebFetch (carregue com ToolSearch "select:WebFetch,WebSearch"). ECONOMIA DE CONTEXTO: no prompt do WebFetch pergunte apenas "a página contém este trecho ou o mesmo sentido com os mesmos números: <trecho>? responda SIM/NÃO e copie a frase mais próxima (≤ 40 palavras)". Máximo 14 aberturas no total: se houver mais URLs, priorize as que carregam número ou termos de uso e marque as demais com abre=false e observacao="não verificada (teto)".
Responda por item: abre (não 404/403/paywall/vazia), trecho_confere (o trecho ou seu sentido exato, mesmos números, está na página), observacao (se a página diz outra coisa, o quê). sustentado = pelo menos 1 evidência abre E confere E sustenta a afirmação; se a única evidência for secundária (imprensa), sustentado só se a imprensa cita o órgão nominalmente. Em dúvida, false. Sem memória: só o que a página mostra. Se um site bloquear (403), tente UMA vez com WebSearch pelo trecho; se não confirmar, abre=false.
ITENS (${itens.length}):
${JSON.stringify(itens, null, 1)}`
}

// ---------- parâmetros ----------
const A = args || {}
const selecionados = A.angulos && A.angulos.length ? ANGULOS.filter(a => A.angulos.includes(a.id)) : ANGULOS
const NAO_VERIFICADOS = selecionados.filter(a => !a.verificar).map(a => a.id)
log(`Ângulos de fatos: ${selecionados.map(a => a.id).join(', ')}; sem verificação cética (custo): ${NAO_VERIFICADOS.join(', ') || 'nenhum'}; gaps prontos: ${(A.gaps_prontos || []).length}; so_fatos=${!!A.so_fatos}; so_gaps=${!!A.so_gaps}`)

// ---------- Fatos → Verificação (pipeline por ângulo) ----------
async function fatos() {
  if (A.so_gaps) return []
  phase('Fatos')
  return pipeline(
    selecionados,
    (a) => agent(promptAngulo(a), { label: `fato:${a.id}`, phase: 'Fatos', schema: RESULT_ANGULO, model: 'sonnet', effort: 'medium' }),
    async (r, a) => {
      if (!r) { log(`${a.id}: agente falhou`); return { angulo: a.id, resultado: null, verificacao: null } }
      log(`${a.id}: ${r.fatos.length} fatos, ${(r.fontes_motor || []).length} fontes, ${(r.concorrentes || []).length} concorrentes, ${(r.palavras_chave || []).length} termos, ${r.lacunas.length} lacunas`)
      if (!a.verificar) return { angulo: a.id, resultado: r, verificacao: null }
      const v = await agent(promptVerif(a, r), { label: `verifica:${a.id}`, phase: 'Verificação', schema: VER, model: 'sonnet', effort: 'medium' })
      const n = v ? v.vereditos.filter(x => x.sustentado).length : 0
      log(`${a.id}: verificação ${v ? `${n}/${v.vereditos.length} sustentados` : 'falhou'}`)
      return { angulo: a.id, resultado: r, verificacao: v }
    },
  )
}

// ---------- Gaps (workflow filho da fábrica) ----------
async function gaps() {
  if (A.so_fatos || !A.script_fabrica) { log('Gaps: pulado (so_fatos ou sem script_fabrica)'); return null }
  try {
    return await workflow({ scriptPath: A.script_fabrica }, {
      nichos: ['est-concursos', 'est-vestibular', 'est-faculdade', 'est-idiomas-certificacoes', 'est-memorizacao', 'est-quem-ensina'],
      etapas: true, gaps_prontos: A.gaps_prontos || [],
    })
  } catch (e) { log(`Gaps: workflow filho falhou — ${e && e.message}`); return { erro: String(e && e.message) } }
}

const [fatosPorAngulo, gapsResultado] = await parallel([() => fatos(), () => gaps()])

// ---------- Síntese (Opus) ----------
phase('Síntese')
const compacto = (fatosPorAngulo || []).filter(Boolean).map(x => {
  const porId = new Map((((x.verificacao || {}).vereditos) || []).map(v => [v.id, v]))
  const r = x.resultado || { fatos: [], lacunas: ['agente falhou'] }
  return {
    angulo: x.angulo, verificado: !!x.verificacao,
    fatos: r.fatos.map(f => ({ id: f.id, afirmacao: f.afirmacao, valor: f.valor, confianca: f.confianca, secundaria: f.evidencias.some(e => e.secundaria), sustentado: porId.has(f.id) ? porId.get(f.id).sustentado : 'não verificado', urls: f.evidencias.map(e => e.url) })),
    fontes_motor: (r.fontes_motor || []).map(f => ({ nome: f.nome, url: f.url, tipo: f.tipo, formato: f.formato, deteccao: f.deteccao_novidade, licenca_ou_risco: f.licenca_ou_risco, termos: (f.termos_de_uso || '').slice(0, 200) })),
    concorrentes: (r.concorrentes || []).map(c => ({ nome: c.nome, precos: c.planos_e_precos, ia: c.funcionalidades_ia, rasa: c.onde_ia_e_rasa })),
    lacunas: r.lacunas,
  }
})
const sintese = compacto.length ? await agent(`Você é o SINTETIZADOR da Fase 1 do AprovaOS (agente de IA que assume a aprovação do candidato; MVP = lado A, um exame; hipótese do dono: concursos Cebraspe+FGV — NÃO a favoreça: decida pelos números).
Abaixo estão os fatos levantados por ângulo, com o veredito do verificador quando houve ("sustentado": true/false/"não verificado"). Use SOMENTE fatos sustentados ou não verificados de confiança alta/média; liste em "fatos_nao_sustentados_que_pesam" os que mudariam a conclusão se fossem verdadeiros.
Entregue: (1) exame_recomendado + justificativa_numerica (público anual, provas públicas disponíveis, padrão de banca, sazonalidade, fontes abertas, custo de cobrir a base) comparando concursos Cebraspe+FGV, ENEM e OAB em "comparacao"; (2) mapa_fontes_prioridade: as 6–10 fontes que o Motor de Conhecimento deve integrar primeiro, por quê e o risco (termos de uso/licença); (3) mobile_recomendacao ("web só" | "PWA com push" | "app") com justificativa pelos fatos; (4) lacunas_para_pendencias: o que faltou medir, com a busca ou fonte sugerida. Não pesquise; só sintetize. Português do Brasil, ≤ 600 palavras no total dos campos de texto.

FATOS POR ÂNGULO:
${JSON.stringify(compacto, null, 1)}`, { label: 'sintese', phase: 'Síntese', schema: SINTESE, effort: 'high' }) : null

return {
  fatos_por_angulo: fatosPorAngulo,
  sintese,
  gaps: gapsResultado,
  nao_verificados: NAO_VERIFICADOS,
}
