"""Roteador de chamadas de LLM: custo estimado em R$, teto diário e o registro de cada chamada.

O que é: pacote `roteador/` (arquitetura §8) — `custo.py` (preços, `ChamadaLlm`,
`estimar_custo_brl`) e `teto.py` (`TetoDiario`). Quando ler: antes de qualquer agente chamar um
modelo; toda chamada passa por aqui e vira uma linha em `traco`.
"""
