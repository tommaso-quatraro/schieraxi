// Va caricato nell'<head>, prima del resto della pagina: applica subito il tema scelto (niente lampo di colore).
// Sta in un file a parte perché la Content-Security-Policy non ammette script dentro la pagina.
(function (d) {
  try {
    var t = localStorage.getItem('tema');
    if (t === 'chiaro' || t === 'scuro') d.dataset.tema = t;
  } catch (e) {}
})(document.documentElement);
