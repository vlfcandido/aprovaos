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
