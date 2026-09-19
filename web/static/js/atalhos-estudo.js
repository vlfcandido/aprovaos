// O que é: ilha de JS vanilla isolada com os atalhos de teclado da tela de resolver questão
// (ADR-0019): C escolhe "Certo", E escolhe "Errado", → avança para a próxima questão. Degrada
// sem quebrar — se este arquivo não carregar, os botões e o link continuam clicáveis
// normalmente; nenhuma regra de negócio depende de JS (o "required" dos rádios de
// certeza/dúvida já é validado pelo navegador antes do envio, e de novo pela rota no servidor).
// O ouvinte fica no `document` (delegação), então continua funcionando depois de o HTMX trocar
// o conteúdo de `#questao` — não há elemento fixo para perder a referência.
// Quando ler: ao mudar os atalhos de teclado das telas de estudo.
document.addEventListener("keydown", function atalhosDeEstudo(evento) {
  var alvo = evento.target;
  var digitandoEmCampo =
    alvo instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName);
  if (digitandoEmCampo || evento.altKey || evento.ctrlKey || evento.metaKey) {
    return;
  }

  var seletorDoAlvo = null;
  if (evento.key === "c" || evento.key === "C") {
    seletorDoAlvo = "[data-atalho='certo']";
  } else if (evento.key === "e" || evento.key === "E") {
    seletorDoAlvo = "[data-atalho='errado']";
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
