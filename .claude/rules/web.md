---
paths:
  - "fanta/web/**"
  - "fanta/testi/**"
  - "sito/**"
  - "prove/foto_web/**"
---
# Web app e sito (`fanta/web/`, `sito/`)

- **Niente librerie né compilazione**: HTML, CSS e JavaScript così come sono. Il job `rilascia` alza `VERSIONE` in
  `fanta/web/sw.js`; in `sito/sw.js` la alzi tu a ogni modifica del sito.
- **Testi.** Ogni testo dell'interfaccia sta nel catalogo `fanta/testi/<prefisso>.json` (italiano e inglese); dopo una
  modifica `python script/testi.py --scrivi`, che rigenera il blocco dei dati di `fanta/web/testi.js` e i file Swift del
  catalogo. Nel codice solo `t("chiave")`. Le frasi che cambiano con i dati arrivano dal server già scritte.
- **Aspetto.** Prima di toccare stile o testi visibili: `docs/DESIGN.md` e `docs/STILE-SENZA-AI.md` (skill `ui-schieraxi`).
  Un dato principale per riga, grande; il resto piccolo. Il colore si usa solo se vuol dire qualcosa.
- **Prova.** Una modifica visibile si guarda davvero: 390, 768, 1024 e 1440 px, chiaro e scuro, con dati verosimili (non la
  lega vuota). Foto senza finestra: `prove/foto_web/foto.py` (skill `collaudo`). Nella descrizione della pull request la
  riga `Aspetto:` con le scene che cambiano, oppure `nessuno`.
- **Test.** Si prova il comportamento (cosa compare e cosa succede a un tocco), non il testo del sorgente: un test che
  cerca una stringa in `app.js` si rompe a ogni riordino senza trovare difetti. I test Python che devono leggere il codice
  della web passano da `tests/codice_web.py`.
- **Sicurezza.** Niente `innerHTML` con dati scritti dall'utente. Nel sito niente script né stili dentro l'HTML (la
  Content-Security-Policy non li ammette).
- **iPhone.** La web è il riferimento: se cambi testi, numeri o stati di una schermata, l'iPhone va allineato nello stesso
  lavoro oppure apri un'issue «coerenza: …». La tabella `docs/COERENZA-WEB-IPHONE.md` è generata: si cambiano i dati in
  `docs/coerenza/`, poi `python script/coerenza.py --scrivi`.
- Se cambi una schermata, aggiorna `docs/GUIDA-UTENTE.md` nella stessa pull request.
