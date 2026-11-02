// Va caricato nell'<head>, prima del resto della pagina: applica subito il tema scelto (niente lampo di colore)
// e segna che c'è JavaScript. Sta in un file a parte perché la Content-Security-Policy non ammette script dentro la pagina.
(function (d) {
  d.classList.add('js');
  try {
    var t = localStorage.getItem('tema');
    if (t === 'chiaro' || t === 'scuro') d.dataset.tema = t;
  } catch (e) {}
  // rete di sicurezza: se dopo 3 secondi il resto dello script non ha rivelato la pagina, mostra tutto
  setTimeout(function () {
    if (!d.classList.contains('pronto')) d.classList.add('rivela-tutto');
  }, 3000);
})(document.documentElement);
