// Pagine Privacy e Termini: stesso tema (chiaro/scuro) scelto nell'app.
try { const t = localStorage.getItem("tema"); if (t === "chiaro" || t === "scuro") document.documentElement.dataset.tema = t; } catch (e) { /* niente memoria: tema del sistema */ }
