// O que é: ilha de JS vanilla isolada com os atalhos de teclado das telas de resolver questão
// (ADR-0019): em "certo_errado", C escolhe "Certo" e E escolhe "Errado"; em "multipla_escolha"
// (passo 3 da V3b), A–E escolhem a alternativa correspondente — as letras C/E aceitam as duas
// leituras (`[data-atalho='resposta-c'], [data-atalho='certo']`) porque só uma delas existe no
// DOM por vez, nunca as duas juntas. → avança para a próxima questão nos dois casos. Degrada sem
// quebrar — se este arquivo não carregar, os botões e o link continuam clicáveis normalmente;
// nenhuma regra de negócio depende de JS (o "required" dos rádios de certeza/dúvida já é
// validado pelo navegador antes do envio, e de novo pela rota no servidor). O ouvinte fica no
// `document` (delegação), então continua funcionando depois de o HTMX trocar o conteúdo de
// `#questao` — não há elemento fixo para perder a referência.
// Quando ler: ao mudar os atalhos de teclado das telas de estudo.
var SELETOR_POR_TECLA = {
  a: "[data-atalho='resposta-a']",
  b: "[data-atalho='resposta-b']",
  c: "[data-atalho='resposta-c'], [data-atalho='certo']",
  d: "[data-atalho='resposta-d']",
  e: "[data-atalho='resposta-e'], [data-atalho='errado']",
};

document.addEventListener("keydown", function atalhosDeEstudo(evento) {
  var alvo = evento.target;
  var digitandoEmCampo =
    alvo instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName);
  if (digitandoEmCampo || evento.altKey || evento.ctrlKey || evento.metaKey) {
    return;
  }

  var tecla = evento.key.toLowerCase();
  var seletorDoAlvo = null;
  if (Object.prototype.hasOwnProperty.call(SELETOR_POR_TECLA, tecla)) {
    seletorDoAlvo = SELETOR_POR_TECLA[tecla];
  } else if (evento.key === "ArrowRight") {
    seletorDoAlvo = "[data-atalho='proxima']";
  }
  if (seletorDoAlvo === null) {
    return;
  }

  var elemento = document.querySelector(seletorDoAlvo);
  if (elemento instanceof HTMLElement) {
    evento.preventDefault();
    elemento.click();
  }
});
