// O que é: ilha de JS vanilla isolada (ADR-0019) que desabilita de verdade os botões de resposta
// (as alternativas A–E ou os dois botões Certo/Errado) do formulário #form-resposta enquanto a
// aluna não marcar "Tenho certeza"/"Estou em dúvida" — reforço visual do defeito nº 1 do porte
// visual (fatia 14 §2.1: clicar numa alternativa sem marcar confiança antes não podia mais ficar
// em silêncio). Degrada sem quebrar: sem este arquivo, os botões continuam clicáveis e é a rota
// quem garante que nada é gravado e que a tela nunca fica muda (`api/questoes.py::
// responder_questao`/`responder_revisao` devolvem 200 reexibindo a questão com o aviso, nunca um
// 4xx que o htmx engoliria). A linha `[data-aviso-confianca]` já vem visível no HTML por padrão
// (para quem não tem JS, ela é só um lembrete permanente); aqui ela também é escondida assim que
// a confiança é marcada, para não sobrar um aviso óbvio depois de resolvido.
// Quando ler: ao mexer no bloqueio de confiança da tela de questão ou de revisão.
function _confiancaAplicarBloqueio(form) {
  var marcada = form.querySelector("input[name='confianca']:checked") !== null;
  var grupoDeResposta = form.querySelector(".alternativas, .respostas");
  if (grupoDeResposta) {
    var botoes = grupoDeResposta.querySelectorAll("button[type='submit']");
    for (var i = 0; i < botoes.length; i++) {
      botoes[i].disabled = !marcada;
    }
  }
  var aviso = form.querySelector("[data-aviso-confianca]");
  if (aviso) {
    aviso.hidden = marcada;
  }
}

function _confiancaInicializarEm(raiz) {
  if (!raiz || typeof raiz.querySelector !== "function") {
    return;
  }
  var form = raiz.querySelector("#form-resposta");
  if (form) {
    _confiancaAplicarBloqueio(form);
  }
}

document.addEventListener("DOMContentLoaded", function () {
  _confiancaInicializarEm(document);
});

// O htmx dispara `htmx:afterSwap` no elemento que recebeu o novo conteúdo (`#questao`) — é assim
// que o bloqueio volta a valer depois de cada resposta, sem precisar reatar nada manualmente.
document.addEventListener("htmx:afterSwap", function (evento) {
  _confiancaInicializarEm(evento.target);
});

document.addEventListener("change", function (evento) {
  var alvo = evento.target;
  if (alvo instanceof HTMLInputElement && alvo.name === "confianca") {
    var form = alvo.closest("#form-resposta");
    if (form) {
      _confiancaAplicarBloqueio(form);
    }
  }
});
