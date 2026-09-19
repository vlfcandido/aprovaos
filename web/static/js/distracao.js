// O que é: ilha de JS vanilla isolada do aviso discreto de distração (fatia 8, F3.6/S-05,
// ADR-0019) — na tela "Hoje", cada bloco com `status="iniciado"` carrega `data-bloco-iniciado`
// (o instante em que a aluna apertou "Iniciar"). A cada 15 s, e sempre que a aba volta a ficar
// visível (`visibilitychange`), o script confere se algum bloco em andamento já passou de
// LIMIAR_MS: se sim, mostra o aviso discreto já presente no HTML (`[data-distracao-aviso]`,
// nasce `hidden`) e registra `EventoEstudo(tipo="distracao")` via `POST /api/distracao` — uma
// vez por bloco, nunca repete. "Discreto, sem culpa": nunca bloqueia a tela, nunca desabilita
// botão, nunca usa `alert`/`confirm`; a pessoa continua livre para ignorar o aviso e seguir
// estudando. Degrada sem quebrar: se este arquivo não carregar, ou o `fetch` falhar (rede,
// sessão expirada), os botões Iniciar/Concluir/Pular continuam funcionando normalmente — o
// evento de distração é só um registro a mais, nunca uma condição para o resto da tela.
// Quando ler: ao mudar o limiar do aviso, o texto mostrado, ou o que é gravado.
(function () {
  "use strict";

  // "você está há 4 min neste item" — a frase pedida pela usuária-piloto na entrevista.
  var LIMIAR_MS = 4 * 60 * 1000;
  var INTERVALO_VERIFICACAO_MS = 15000;

  // Blocos já avisados nesta carga de página — reiniciado a cada troca de conteúdo pelo htmx
  // (`htmx:afterSwap`), porque um bloco concluído/pulado some e outro pode assumir o lugar.
  var avisados = {};

  function millisSemAviso(isoInicio) {
    var inicio = new Date(isoInicio).getTime();
    if (isNaN(inicio)) {
      return 0;
    }
    return Date.now() - inicio;
  }

  function registrarNoServidor(blocoId) {
    if (typeof fetch !== "function") {
      return; // navegador sem fetch: o aviso na tela ainda aparece, só não é gravado
    }
    fetch("/api/distracao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bloco_id: blocoId }),
      keepalive: true,
    }).catch(function () {
      // Best-effort: sem sessão, sem rede, ou erro do servidor — o aviso já apareceu na tela;
      // o registro é só telemetria, nunca bloqueia a experiência (princípio S-05).
    });
  }

  function mostrarAviso(elemento) {
    var aviso = elemento.querySelector("[data-distracao-aviso]");
    if (aviso) {
      aviso.hidden = false;
    }
  }

  function verificarBlocos() {
    var elementos = document.querySelectorAll("[data-bloco-iniciado]");
    for (var i = 0; i < elementos.length; i += 1) {
      var elemento = elementos[i];
      var blocoId = elemento.getAttribute("data-bloco-id");
      var iniciadoEm = elemento.getAttribute("data-bloco-iniciado");
      if (!blocoId || !iniciadoEm || avisados[blocoId]) {
        continue;
      }
      if (millisSemAviso(iniciadoEm) >= LIMIAR_MS) {
        avisados[blocoId] = true;
        mostrarAviso(elemento);
        registrarNoServidor(blocoId);
      }
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      verificarBlocos(); // voltou pra aba: confere se passou do limiar enquanto ela estava fora
    }
  });

  document.addEventListener("htmx:afterSwap", function () {
    avisados = {};
    verificarBlocos();
  });

  setInterval(verificarBlocos, INTERVALO_VERIFICACAO_MS);
  verificarBlocos();
})();
