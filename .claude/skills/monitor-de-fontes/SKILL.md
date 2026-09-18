---
name: monitor-de-fontes
description: Use quando for adicionar, mapear ou consertar uma fonte do `coletor` do Motor de Conhecimento — banca, diário oficial, tribunal, Planalto, LexML, RSS, API ou página HTML — inclusive "avisar quando sair edital/prova", "detecção de novidade", "fontes.yaml", ou quando uma fonte para de detectar itens novos ou detecta tudo de novo a cada rodada.
---

# Monitor de fontes
> O que é: o protocolo para uma fonte entrar no `coletor` com URL verificada, política de coleta escrita e teste de novidade que prova o que promete. Quando ler: antes de propor qualquer fonte nova; ao revisar uma classe `FonteColetavel`.

## Princípio
**Fonte sem mapeamento real não entra.** Mapear é abrir a URL de verdade (WebFetch/navegador), ler `robots.txt` e termos de uso, e salvar o que a página respondeu como fixture. Só depois vem código. Detectar novidade é comparar **identidades de itens** entre duas rodadas — não é ver se a página mudou.

## Passo 1 — Ficha da fonte (obrigatória antes de código)
Preencher e gravar em `knowledge/fontes.yaml` (uma entrada por fonte). Campo sem resposta = `desconhecido` e a fonte entra com `status: pendente_mapeamento` — a tarefa para aqui e vira pendência.
```yaml
- id: unioeste-cogeps
  nome: Fundação de Apoio à Unioeste — COGEPS
  url_lista: https://…            # aberta de verdade; anotar o que respondeu
  formato: api_json | rss | html   # o que a URL devolve
  o_que_publica: [edital, prova, gabarito, resultado]
  identidade_do_item: url_canonica | id_na_api | guid_rss   # o que torna um item único entre rodadas
  robots_txt: permite | proíbe | inexistente   # URL/robots.txt lida em <data>
  termos_de_uso: url + resumo | não localizados   # cláusula anti-automação? (RISCOS R-02)
  politica_coleta: {frequencia: 6h, user_agent: "AprovaOS-coletor/0.1 (+contato: <e-mail do dono>)", sem_login: true, cache: etag}
  verificado_em: 2026-09-17
  evidencia: knowledge/fixtures/fontes/unioeste-cogeps/snapshot-2026-09-17.html   # resposta REAL salva
  status: ativa | pendente_mapeamento | vetada
```
Regras da ficha: `url_lista` e `evidencia` só existem se a página foi aberta nesta tarefa e o conteúdo salvo; `user_agent` usa o contato real do dono, nunca um domínio inventado; `termos_de_uso` com cláusula anti-automação → `status: vetada` até decisão registrada em `docs/DECISOES.md` (caso FGV, P-13).

## Passo 2 — Classe da fonte (contrato `FonteColetavel`)
- Um arquivo por fonte em `backend/aprovaos/motor/fontes/<id>.py`; `listar_novidades(vistos: set[str]) -> list[Novidade]` e `baixar(novidade) -> Documento`.
- **Sem I/O em import**: cliente HTTP, config e leitura de env entram por parâmetro do construtor ou de uma fábrica.
- `Novidade.id` = `identidade_do_item` da ficha (URL canônica normalizada, id da API, guid). Nunca hash de título, nunca posição na lista.
- Novidade = item cujo `id` **não está em `vistos`**. ETag/Last-Modified só evitam baixar de novo; não decidem novidade.
- Classificação de tipo (`edital`/`prova`/`gabarito`) vem de campo da API/RSS ou de regra escrita na ficha; se for por palavra-chave no HTML, o item recebe `tipo: desconhecido` quando nenhuma regra casa — sem "confiança 0,6" inventada.
- Dependência nova (ex.: `beautifulsoup4`) precisa de veredito em `docs/DECISOES.md` (CLAUDE.md regra 8).

## Passo 3 — Teste de novidade (red-first)
Dois snapshots em `knowledge/fixtures/fontes/<id>/`: `v1` = resposta real salva; `v2` = v1 com **um item a mais** (inserido à mão, documentado no cabeçalho do arquivo). Testes mínimos:
1. `v1` com `vistos = ∅` → N novidades, N = itens reais do snapshot (contar no arquivo, não "≥ 3").
2. `v1` com `vistos = ids(v1)` → `[]`.
3. `v2` com `vistos = ids(v1)` → **exatamente 1** novidade, com o `id` do item inserido.
4. Página fora do ar / 5xx → exceção tipada, não `[]` (senão "sem novidade" esconde falha).
5. Termos/robots proíbem → o construtor recusa (`FonteVetada`).

## Verificação antes de entregar
- A ficha tem `verificado_em` de hoje e `evidencia` apontando para um arquivo que existe e veio da rede.
- Nenhuma URL no código que não esteja na ficha.
- O teste 3 existe e passa; o teste "primeira execução detecta ≥ 3 links" sozinho **não** é teste de novidade.

## Erros que este protocolo existe para evitar
- URL da fonte escrita de memória (`/portal/cogeps/correntes`) sem abrir a página.
- Fixture HTML inventado pelo próprio autor — o teste passa em qualquer parser.
- "ETag não mudou → sem novidade": página muda por banner e dispara falso positivo; item novo em página com ETag fraco passa despercebido.
- `User-Agent: AprovaOS/1.0 (+https://aprovaos.education)` — domínio que não existe.
- Confiança numérica (0,95/0,6) atribuída por palavra-chave sem medição.
