# Fixtures jurídicas — medição de fontes primárias
> O que é: evidência bruta (HTML/PDF, vindos da rede) das quatro fontes que a skill `deep-research-topico` lista para norma/súmula, coletada para a tarefa de fundação "explicação ancorada". Quando ler: antes de desenhar o pipeline `dispositivo_legal`/`citacao`, ou para auditar de onde veio cada trecho literal citado no relatório `fontes-juridicas-report.md`.

Coleta em **2026-09-19**, desta máquina, via `curl`/WebFetch (sem navegador). Nenhum arquivo aqui foi editado — é o download cru. **Correção feita na mesma tarefa**: a primeira rodada testou o Planalto sem `User-Agent` de navegador e concluiu (errado) que o site estava fora do ar; uma segunda rodada, com UA de navegador, provou que ele responde normalmente — ver `planalto_falha_evidencia.txt` para a evidência completa da correção.

| arquivo | origem (URL) | o que é | tamanho | status HTTP |
|---|---|---|---|---|
| `constituicao_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm` | Constituição Federal de 1988, texto compilado oficial (**Rota A** da skill, principal) — baixado com `curl -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"`; sem UA de navegador, a mesma URL devolve 0 bytes | 1,84 MB | 200 (só com UA de navegador; sem UA: `000`/0 bytes) |
| `lei14133_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm` | Lei 14.133/2021, texto compilado oficial (Rota A) — mesmo UA de navegador necessário | 650 KB | 200 (idem) |
| `constituicao_camara_normaatualizada.html` | `https://www2.camara.leg.br/legin/fed/consti/1988/constituicao-1988-5-outubro-1988-322142-normaatualizada-pl.html` | Constituição Federal de 1988 pela Câmara (**Rota B**, agora alternativa) — sem exigência de UA especial | 1,7 MB | 200 |
| `lei14133_camara_normaatualizada.pdf` | `https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-normaatualizada-pl.pdf` | Lei 14.133/2021 pela Câmara (Rota B) — o `.html` equivalente devolveu **504 Gateway Timeout** em 3 tentativas; o `.pdf` (e um `.doc`, não guardado aqui) responderam normalmente | 412 KB (88 páginas) | 200 |
| `lei14133_camara_norma_original.html` | `https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-norma-pl.html` | Lei 14.133/2021, texto **original** de 2021 (sem anotação de alterações posteriores) — guardado como alternativa mais leve, não usado para citar por não indicar vigência | 61 KB | 200 |
| `stf_indice_sumulas.html` | `https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=30&sumula=3345y` | Índice de todas as Súmulas comuns do STF — cada item é um link `sumariosumulas.asp?base=30&sumula=<id-interno>`; o `<id-interno>` **não é o número da súmula** e precisa ser resolvido aqui antes de abrir a súmula individual | 140 KB | 200 (só com UA de navegador; sem UA: 403) |
| `stf_indice_sumulas_vinculantes.html` | `https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=26` | Índice de todas as Súmulas Vinculantes, mesmo mecanismo de `<id-interno>` | 62 KB | 200 (idem) |
| `stf_sumula_vinculante_1.html` | `https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=26&sumula=1185` | Súmula Vinculante nº 1, texto integral + precedente representativo + teses de repercussão geral | 71 KB | 200 |
| `stf_sumula_473.html` | `https://portal.stf.jus.br/jurisprudencia/sumariosumulas.asp?base=30&sumula=1602` | Súmula 473 (STF pode anular/revogar seus próprios atos), texto integral + tese de repercussão geral | 62 KB | 200 |
| `stj_sumulas_verbetes.pdf` | `https://scon.stj.jus.br/docs_internet/jurisprudencia/tematica/download/SU/Verbetes/VerbetesSTJ.pdf` | Enunciados de todas as Súmulas do STJ (nº 676 a 1), texto integral + órgão julgador + data do julgado/DJe | 418 KB (10 páginas) | 200 (sem UA especial) |
| `lexml_verificacao_seguranca.xml` | `https://www.lexml.gov.br/busca/SRU?operation=searchRetrieve&query=...` | Evidência de que a Rota C (LexML) **continua bloqueada mesmo com UA de navegador** — devolve a página HTML "Verificação de segurança — Senado Federal" (JS challenge), não um erro de UA | 9 KB | 200 (mas é a página de bloqueio, não o conteúdo pedido) |
| `planalto_falha_evidencia.txt` | `https://www.planalto.gov.br/...` (3 URLs testadas, 2 rodadas: sem UA e com UA) | Log da correção: primeira rodada (sem UA) registrou, errado, "falha de rede"; segunda rodada (com UA de navegador) provou que era filtro de User-Agent. Mantém o texto original riscado, por rastreabilidade | 4,4 KB (texto) | ver detalhe no arquivo |

## O que isso mudou em relação à primeira coleta desta tarefa
- **Planalto (Rota A) volta a ser a fonte primária principal**, como a skill manda — não estava
  fora do ar, o `curl` sem `-A` é que apanhava num filtro de borda por assinatura de User-Agent.
- Um **User-Agent identificado no formato `Mozilla/5.0 (compatible; AprovaOS-coletor/0.1;
  +contato: vlfcandido@gmail.com)`** passa no mesmo filtro (testado e confirmado byte-a-byte
  igual ao UA de navegador puro) — é a forma de nos identificarmos sem mentir sobre quem somos.
  Um UA identificado **sem** o prefixo `Mozilla/5.0` (ex.: `AprovaOS-coletor/0.1 (+contato: ...)`)
  continua sendo recusado. Essa escolha de UA fica registrada como decisão pendente do dono no
  relatório-mãe.
- A Câmara (Rota B) deixa de ser "a única que funciona" e volta a ser **a alternativa** prevista
  pela skill — continua útil porque a versão `.html` "normaatualizada" da Lei 14.133 no Planalto
  funcionou (não testamos se ela também cairia como no `.html` da Câmara, mas o Planalto respondeu
  de primeira; a Câmara fica como plano B se o Planalto cair para uma norma específica).

## O que falta aqui (não veio da rede, não existe fixture)
- LexML (Rota C) — testado de novo com UA de navegador nesta correção: **continua bloqueado**,
  mesma página "Verificação de segurança — Senado Federal". Isso não é filtro de UA, é desafio de
  JavaScript de verdade — precisaria de navegador real (Playwright/Chrome).
- Julgados do STF/STJ (ementas de ADI/RE/REsp) — fora do escopo desta medição (só normas e
  súmulas foram pedidas).
- WebFetch (a ferramenta interna usada nesta tarefa, sem controle de UA por quem chama) não foi
  reconfirmada com UA de navegador — ela reportou `ECONNRESET` na primeira rodada; não sabemos se
  ela também seria aceita pelo Planalto porque não há como definir o UA que ela envia por dentro
  desta tarefa. Registrado como lacuna no relatório-mãe.

## Disciplina
Toda evidência acima foi baixada nesta tarefa, com URL registrada. Nenhum trecho citado no relatório-mãe (`.superpowers/sdd/V3b-multipla-escolha/fontes-juridicas-report.md`) vem de fonte que não esteja num destes arquivos.

## Ampliação do catálogo (2026-09-19, rodada 2) — as 6 normas mais citadas pela base real

Medidas em `motor/ancorar.py` sobre as 250 questões reais do `dev.db` (`normas_fora_do_catalogo`
antes desta rodada). Baixadas com o mesmo UA híbrido da ADR-0037
(`Mozilla/5.0 (compatible; AprovaOS-coletor/0.1; +contato: vlfcandido@gmail.com)`), via `curl -A`.

| arquivo | origem (URL) | norma | nº questões que citam | tamanho | sha1 (12) | status HTTP |
|---|---|---|---|---|---|---|
| `clt_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm` | CLT (Decreto-Lei 5.452/1943) | 11 | 3 531 201 bytes | `7330528e2d1a` | 200 |
| `lei8429_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/leis/l8429.htm` | Lei 8.429/1992 (Improbidade) | 5 | 210 250 bytes | `5f858a024f78` | 200 |
| `lei6404_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/leis/l6404compilada.htm` | Lei 6.404/1976 (S/A) | 3 | 554 245 bytes | `9eccbbdd671b` | 200 |
| `lei11101_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11101.htm` | Lei 11.101/2005 (Recuperação/Falência) | 3 | 633 110 bytes | `32154fb7072c` | 200 |
| `lei11340_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm` | Lei 11.340/2006 (Maria da Penha) | 3 | 264 515 bytes | `b510057d7ace` | 200 |
| `lei6830_planalto_compilada.htm` | `https://www.planalto.gov.br/ccivil_03/leis/l6830.htm` | Lei 6.830/1980 (Execução Fiscal) | 2 | 50 924 bytes | `455756e7c989` | 200 |

Cada arquivo entrou em `motor.fontes.planalto.CATALOGO` (id estável, mesmo produzido por
`dominio.citacao._norma_id`) e em `motor.ancorar._FIXTURES_OFFLINE`.

### Achado 1 (corrigido nesta rodada): Lei 11.340/2006 vem em UTF-16LE, não `cp1252`
Único arquivo desta leva com BOM `b"\xff\xfe"` (UTF-16LE) — as outras cinco normas, como a CF e
a Lei 14.133 antes delas, são `cp1252`. Decodificar com `cp1252` sem checar o BOM produz um
caractere por byte (`"< h t m l >"`) e **zero** ocorrências de `"Art."` — não era estrutura não
tratada, era a codificação errada aplicada a bytes corretos. `decodificar_html`
(`motor/fontes/planalto.py`) passou a detectar o BOM (UTF-16LE/BE) antes de cair no padrão
`cp1252`; teste `test_decodificar_html_reconhece_bom_utf16_le_da_lei_11340`
(`tests/test_fonte_planalto.py`), contra este arquivo real.

### Achado 2 (registrado, não remendado): CLT art. 477 — anotação "Vigência\nencerrada"
`extrair_artigo(html, "477")` levanta `EstruturaNaoTratada` no trecho:
```
Vigência 
encerrada
```
(duas palavras, sem parênteses, dentro de um `<a href="…/adc-113-mpv955.htm">`, depois de um
inciso incluído pela MPV 905/2019 e revogado pela MPV 955/2020). O extrator já remove a
anotação `"Vigência"` sozinha sem parênteses (achado da rodada anterior, Lei 14.133 art. 6º
XXII) — aqui o texto tem uma segunda palavra ("encerrada") que sobra depois da remoção e não
casa com nenhum padrão de caput/inciso/parágrafo/alínea. **Efeito na ancoragem**: as 3 questões
que citam "art. 477 da CLT" ficam em `catalogada_nao_resolvida` (a norma está no catálogo, mas
o trecho específico não resolve) — não travam o comando (`_resolver_trecho` engole a exceção).

### Achado 3 (registrado, não remendado): títulos de Seção/Capítulo em Title Case
`dominio.legislacao._eh_titulo_estrutural` só reconhece título estrutural em **CAIXA ALTA sem
nenhuma letra minúscula** (medido nos HTMLs da CF/Lei 14.133, ex.: `"CAPÍTULO IV"`). Duas normas
desta leva intercalam títulos em Title Case (mistura maiúscula/minúscula) entre artigos:
- Lei 8.429/1992, entre os arts. 9º e 10 (`extrair_artigo(html, "9")` até `extrair_artigo(html,
  "12")` levantam `EstruturaNaoTratada`):
  ```
  Seção II
  Dos Atos de Improbidade Administrativa que Causam Prejuízo ao Erário
  ```
  e, mais adiante, `"CAPÍTULO III Das Penas"`, `"CAPÍTULO IV Da Declaração de Bens"` (este
  título é 100 % CAIXA ALTA no rótulo do capítulo, mas o subtítulo que o acompanha na mesma
  linha não é — o `<p>` inteiro falha o teste de "sem nenhuma letra minúscula").
- Lei 11.340/2006, entre os arts. 23 e 24 (`extrair_artigo(html, "24")` levanta
  `EstruturaNaoTratada`): `"Seção IV"` sozinho (sem subtítulo na mesma linha, mas ainda assim
  com letras minúsculas em "Seção").
- Lei 6.404/1976: rubricas marginais de uma palavra/frase entre artigos, mesmo padrão —
  `"Objeto Social"` entre os arts. 1º e 2º (`extrair_artigo(html, "1")` funciona porque a
  rubrica vem **depois** do fim do art. 1º, mas `extrair_artigo(html, "116")` falha por um
  motivo relacionado: alíneas listadas direto sob o caput, sem inciso/parágrafo antecedente —
  `EstruturaNaoTratada: "Alínea sem inciso/parágrafo anterior a que pertencer: 'a) é titular…'"`.
- Lei 11.101/2005, art. 6º: parágrafo com sufixo de letra (`"§ 4º-A."`) não casa com
  `_PADRAO_PARAGRAFO` (que só reconhece `§ N[ºo]?\.?`, sem o `-A`).

**Nenhum desses quatro achados foi corrigido nesta rodada** (instrução explícita: registrar o
trecho literal e não remendar). Ficam como estrutura não tratada — o comando de ancoragem já
trata isso sem travar (`_resolver_trecho` devolve `None`); o `dossie_topico` da Lei 8.429/1992
(ver relatório da tarefa) só usa os artigos que o extrator lê de fato (1º e 2º) e declara os
demais como lacuna, nunca preenchidos de memória.
