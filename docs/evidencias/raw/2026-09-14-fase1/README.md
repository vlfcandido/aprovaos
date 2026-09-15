# Raw da rodada de pesquisa da Fase 1 (`wf_09928095-f09`, 14/09/2026)
> O que é: o journal completo do workflow e um JSON por agente (66 resultados), extraídos depois que o reboot matou a sessão da fábrica. Quando ler: para conferir uma URL ou trecho citado em `docs/01-pesquisa-mercado.md` (os `[ids]` de lá apontam para `fato__<ângulo>.json`), ou para relançar a consolidação cruzada dos gaps (P-16).

- `journal.jsonl` — eventos `started`/`result` do run; o agente `consolida:cross-nicho` (a889c32f8a070cb7c) começou e não terminou.
- `fato__<ângulo>.json` — resultado do agente de fatos (schema `RESULT_ANGULO` do script).
- `verifica__<ângulo>.json` — vereditos do verificador cético (6 ângulos).
- `busca__/abre__/monta__/consolida__est-*.json` — etapas do script leve da fábrica por nicho; `consolida__est-piloto.json` é a consolidação dos pilotos.
- Script que gerou tudo: `../2026-09-14-pesquisa-fase1.workflow.js`.
