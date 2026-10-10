"use strict";

// Small local interaction; no CDN or remote runtime dependency.
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-language-toggle]");
  const panel = document.querySelector("[data-english-panel]");
  if (!toggle || !panel) return;
  toggle.addEventListener("click", () => {
    const showing = panel.hidden;
    panel.hidden = !showing;
    toggle.setAttribute("aria-expanded", String(showing));
    toggle.textContent = showing ? "EN / FA" : "FA / EN";
  });
});
