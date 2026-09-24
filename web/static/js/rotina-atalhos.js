// O que é: ilha de JS vanilla (ADR-0019) dos atalhos de tempo da tela `/rotina`. Quando ler: ao
// mexer nos atalhos de horas ou no total da semana.
//
// Por que existe: a tela pedia sete números digitados, e o dono resumiu ("tá péssima pra ficar
// digitando os dados ali"). O caminho principal virou um toque por grupo de dias. Esta ilha faz
// três coisas, todas dispensáveis:
//   1. escreve o valor do atalho nos campos dia a dia (para o que está na tela ser o que será
//      salvo, sem surpresa no servidor);
//   2. marca o grupo como "Dia a dia" assim que a pessoa digita num campo — digitar é a
//      declaração de que ela quer precisão, e o atalho não pode apagar isso;
//   3. atualiza o total da semana enquanto ela escolhe (devolutiva imediata, sem pontuação,
//      sem meta e sem cor de alerta — ADR-0051).
//
// **Sem JS a tela funciona inteira**: o atalho é um `<input type="radio">` de verdade e quem
// decide a precedência é `dominio/rotina.py` no servidor; o total da semana já vem renderizado
// e o `<details>` abre no clique, como manda o HTML.
(function () {
  var DIAS = { uteis: ["seg", "ter", "qua", "qui", "sex"], fds: ["sab", "dom"] };
  var MANUAL = "manual";

  function campo(dia) {
    return document.querySelector("[data-hora-dia='" + dia + "']");
  }

  function numero(texto) {
    var valor = parseFloat(String(texto).replace(",", "."));
    return isNaN(valor) ? 0 : valor;
  }

  function texto(valor) {
    // pt-BR: 2,5 — nunca 2.5. `toFixed` só quando há fração, para não mostrar "14,0".
    return (Math.round(valor * 10) / 10).toString().replace(".", ",");
  }

  function escolhaDoGrupo(grupo) {
    var marcado = document.querySelector(
      "[data-atalho-tempo='" + grupo + "']:checked"
    );
    return marcado ? marcado.value : "";
  }

  function atualizarTotal() {
    var alvo = document.querySelector("[data-total-semanal]");
    if (!alvo) {
      return;
    }
    var total = 0;
    Object.keys(DIAS).forEach(function (grupo) {
      DIAS[grupo].forEach(function (dia) {
        var entrada = campo(dia);
        if (entrada) {
          total += numero(entrada.value);
        }
      });
    });
    alvo.textContent = texto(total);

    var aviso = document.querySelector("[data-aviso-preset]");
    if (aviso) {
      aviso.hidden = escolhaDoGrupo("uteis") !== "4" && escolhaDoGrupo("fds") !== "4";
    }
  }

  function aplicarAtalho(grupo, valor) {
    var detalhe = document.querySelector(".ajuste-fino");
    if (valor === MANUAL) {
      if (detalhe) {
        detalhe.open = true;
      }
      var primeiro = campo(DIAS[grupo][0]);
      if (primeiro && typeof primeiro.focus === "function") {
        primeiro.focus();
        primeiro.select();
      }
      return;
    }
    DIAS[grupo].forEach(function (dia) {
      var entrada = campo(dia);
      if (entrada) {
        entrada.value = texto(numero(valor));
      }
    });
  }

  function grupoDoDia(dia) {
    return DIAS.uteis.indexOf(dia) === -1 ? "fds" : "uteis";
  }

  document.addEventListener("change", function (evento) {
    var alvo = evento.target;
    if (!(alvo instanceof HTMLInputElement)) {
      return;
    }
    if (alvo.hasAttribute("data-atalho-tempo")) {
      aplicarAtalho(alvo.getAttribute("data-atalho-tempo"), alvo.value);
      atualizarTotal();
    }
  });

  document.addEventListener("input", function (evento) {
    var alvo = evento.target;
    if (!(alvo instanceof HTMLInputElement) || !alvo.hasAttribute("data-hora-dia")) {
      return;
    }
    // Digitou num dia: o grupo dele passa a ser "Dia a dia", senão o atalho marcado venceria no
    // servidor e o que ela acabou de escrever iria para o lixo sem aviso.
    var grupo = grupoDoDia(alvo.getAttribute("data-hora-dia"));
    var manual = document.querySelector(
      "[data-atalho-tempo='" + grupo + "'][value='" + MANUAL + "']"
    );
    if (manual && !manual.checked) {
      manual.checked = true;
    }
    atualizarTotal();
  });

  document.addEventListener("DOMContentLoaded", atualizarTotal);
})();
