"""Agentes do AprovaOS (ADK): cada papel com prompt versionado em `prompts/<papel>.md`.

O que é: pacote `agentes/` (arquitetura §4–§6) — na V2, só `analista_de_edital`. Quando ler: ao
criar um agente novo; toda chamada de modelo passa pelo `roteador` e vira linha em `traco`, e
nenhum módulo daqui importa `google.*` em nível de módulo (só dentro das fábricas).
"""
