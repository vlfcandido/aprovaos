#!/usr/bin/env bash
# O que é: captura as telas do produto em três larguras (monitor, tablet, telefone) com o Chrome
# do sistema, para revisar layout sem abrir doze abas na mão.
# Quando ler: antes de dizer que uma tela está pronta, e ao revisar uma passada visual.
#
# Uso:  bash scripts/capturar.sh [URL_BASE] [PASTA_SAIDA]
#       URL_BASE  padrão http://127.0.0.1:8000  (suba o servidor antes)
#       PASTA     padrão /tmp/aprovaos-telas
#
# Limite honesto: o Chrome sobe com perfil limpo, então **só captura tela pública**. As telas de
# aluna (/hoje, /painel, /diagnostico, /editais, /rotina) exigem sessão e continuam sendo
# conferidas com o navegador de verdade. O que estas capturas pegam é a classe de defeito que
# mais apareceu em 23/09/2026: shell, largura, espaçamento e os componentes compartilhados.
set -euo pipefail

URL_BASE="${1:-http://127.0.0.1:8000}"
SAIDA="${2:-/tmp/aprovaos-telas}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [ ! -x "$CHROME" ]; then
  echo "Chrome não encontrado em $CHROME — instale ou ajuste a variável CHROME no script." >&2
  exit 1
fi

if ! curl -fsS -o /dev/null "$URL_BASE/saude"; then
  echo "Servidor não responde em $URL_BASE — suba antes (veja docs/HANDOFF.md §2)." >&2
  exit 1
fi

# tela:caminho — só as públicas, pelo motivo no cabeçalho.
TELAS=("inicio:/" "radar:/radar" "entrar:/entrar" "cadastro:/cadastro" "biblioteca:/estilo")
# nome:largura,altura — monitor, tablet da piloto, telefone.
# O macOS não deixa a janela do Chrome descer abaixo de ~600px: pedir 400 renderiza a 614 e
# **corta** a imagem, o que parece estouro de layout e não é (levei um susto assim em
# 23/09/2026). 640px é a quebra real do nosso CSS e é o menor tamanho que esta máquina mede de
# verdade; abaixo disso, confira no aparelho ou nas ferramentas de dispositivo do navegador.
TAMANHOS=("monitor:1920,1080" "tablet:834,1112" "estreito:640,900")

mkdir -p "$SAIDA"
rm -f "$SAIDA"/*.png

for tela in "${TELAS[@]}"; do
  nome="${tela%%:*}"; caminho="${tela##*:}"
  for tamanho in "${TAMANHOS[@]}"; do
    rotulo="${tamanho%%:*}"; medidas="${tamanho##*:}"
    arquivo="$SAIDA/${nome}-${rotulo}.png"
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
      --virtual-time-budget=2000 --window-size="$medidas" \
      --screenshot="$arquivo" "$URL_BASE$caminho" >/dev/null 2>&1
    [ -f "$arquivo" ] && echo "  $nome · $rotulo" || echo "  FALHOU: $nome · $rotulo" >&2
  done
done

echo
echo "capturas em $SAIDA — abra com: open $SAIDA"
echo "confira, em cada uma: sobrou faixa vazia? o texto passa de ~80 caracteres?"
echo "tem rolagem horizontal? o âmbar aparece mais de uma vez na mesma região?"
