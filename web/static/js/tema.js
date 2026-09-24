// O que é: ilha de JS vanilla (ADR-0019) do alternador de tema — claro, escuro ou o do sistema.
// O protótipo validado com a piloto tem esse controle, e o produto seguia só a preferência do
// sistema operacional: quem valida o produto no macOS em modo escuro nunca via o tema claro, que
// é justamente o que foi validado com ela. Os tokens já suportavam `data-theme="claro|escuro"`
// desde a V1 (`web/static/css/tokens.css`) — faltava quem os ligasse.
// Degrada sem quebrar: sem JS, o tema do sistema continua valendo e o botão não aparece.
// Quando ler: ao mexer no tema ou ao investigar um "flash" de cor na carga da página.
(function () {
  var CHAVE = "aprovaos:tema";
  // A ordem do ciclo é a da luz: sistema → claro → sépia (papel, para leitura longa) → escuro.
  // O sépia entrou em 23/09/2026 com o sistema de design: quem estuda 2 a 6 horas seguidas lê
  // texto longo, e branco puro cansa.
  var CICLO = ["sistema", "claro", "sepia", "escuro"];
  var ROTULO = {
    sistema: "Tema: do sistema",
    claro: "Tema: claro",
    sepia: "Tema: sépia",
    escuro: "Tema: escuro",
  };

  function lerPreferencia() {
    // `localStorage` pode lançar (janela anônima, cookies bloqueados) — o tema do sistema é um
    // padrão perfeitamente bom, então a falha nunca sobe.
    try {
      var salvo = window.localStorage.getItem(CHAVE);
      return CICLO.indexOf(salvo) === -1 ? "sistema" : salvo;
    } catch (erro) {
      return "sistema";
    }
  }

  function aplicar(tema) {
    if (tema === "sistema") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", tema);
    }
  }

  function guardar(tema) {
    try {
      window.localStorage.setItem(CHAVE, tema);
    } catch (erro) {
      /* sem persistência: o tema vale só nesta página, e tudo bem */
    }
  }

  aplicar(lerPreferencia());

  document.addEventListener("DOMContentLoaded", function () {
    var botao = document.querySelector("[data-alternar-tema]");
    if (!botao) {
      return;
    }
    botao.hidden = false;

    function pintarBotao() {
      var atual = lerPreferencia();
      botao.textContent = ROTULO[atual];
      botao.setAttribute("aria-label", ROTULO[atual] + " — trocar");
    }

    pintarBotao();
    botao.addEventListener("click", function () {
      var proximo = CICLO[(CICLO.indexOf(lerPreferencia()) + 1) % CICLO.length];
      guardar(proximo);
      aplicar(proximo);
      pintarBotao();
    });
  });
})();
