// O que é: ilha de JS vanilla (ADR-0019) do modo foco — a sessão de estudo sem navegação, sem
// rodapé e sem nada que não seja o conteúdo. Quando ler: ao mexer no modo foco ou ao investigar
// por que a barra lateral sumiu.
//
// Por que existe: a aluna estuda 2 a 6 horas, muitas vezes cansada, à noite. Toda porta aberta
// na tela é um convite a sair da questão que ela está resolvendo. O modo foco tira as portas e
// deixa uma só saída, sempre visível e sempre no mesmo lugar.
//
// Decisões que valem a pena saber antes de mexer:
// - O estado vive em `sessionStorage`, não em `localStorage`: modo foco vale para a sessão de
//   estudo de agora, não para sempre. Quem fecha o navegador volta com a navegação no lugar.
// - É aplicado antes da primeira pintura (o `<script>` do shell não tem `defer`), como o tema —
//   senão a barra lateral aparece e some, que é pior que nunca ter sumido.
// - Degrada sem quebrar: sem JS os dois botões continuam escondidos e a página é a de sempre.
// - `Esc` sai. Não há tecla para entrar: as telas de estudo já usam A–E e C/E
//   (`atalhos-estudo.js`), e roubar mais uma letra é criar conflito.
(function () {
  var CHAVE = "aprovaos:foco";

  function ligado() {
    try {
      return window.sessionStorage.getItem(CHAVE) === "1";
    } catch (erro) {
      return false;
    }
  }

  function aplicar(ativo) {
    if (ativo) {
      document.documentElement.setAttribute("data-foco", "1");
    } else {
      document.documentElement.removeAttribute("data-foco");
    }
  }

  function guardar(ativo) {
    try {
      if (ativo) {
        window.sessionStorage.setItem(CHAVE, "1");
      } else {
        window.sessionStorage.removeItem(CHAVE);
      }
    } catch (erro) {
      /* sem persistência: o modo foco vale só nesta página, e tudo bem */
    }
  }

  aplicar(ligado());

  document.addEventListener("DOMContentLoaded", function () {
    var entrar = document.querySelector("[data-modo-foco]");
    var sair = document.querySelector("[data-sair-do-foco]");
    if (!entrar || !sair) {
      return;
    }
    entrar.hidden = false;
    sair.hidden = false;

    // Só sincroniza o estado. **Não mexe no foco do teclado**: chamada na carga da página, ela
    // roubaria o foco para o botão da lateral em toda navegação — foi o que aconteceu na
    // primeira versão, e aparecia como um retângulo de foco em volta de "Modo foco" em toda
    // captura de tela.
    function sincronizar(ativo) {
      guardar(ativo);
      aplicar(ativo);
      entrar.setAttribute("aria-pressed", ativo ? "true" : "false");
    }

    // Mover o foco é resposta a um clique da pessoa, nunca efeito de carga: quem entrou no modo
    // vai para a saída; quem saiu volta para o botão que o trouxe de volta — senão o foco fica
    // num elemento que acabou de ser escondido e o próximo Tab recomeça do topo.
    function focar(elemento) {
      if (typeof elemento.focus === "function") {
        elemento.focus();
      }
    }

    sincronizar(ligado());
    entrar.addEventListener("click", function () {
      sincronizar(true);
      focar(sair);
    });
    sair.addEventListener("click", function () {
      sincronizar(false);
      focar(entrar);
    });
    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && ligado()) {
        sincronizar(false);
        focar(entrar);
      }
    });
  });
})();
