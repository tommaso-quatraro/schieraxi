# 0010. I testi di web e iPhone nascono da un catalogo solo

Data: 8/11/2026. Stato: accettata (il catalogo unico l'ha deciso l'utente il 6/11; la forma qui sotto è una scelta del piano).

## Contesto e problema
I testi della web stanno in `fanta/web/testi.js` (italiano e inglese); l'iPhone li riscrive nel suo codice e una trentina di test
iOS li confrontano con `testi.js` leggendolo riga per riga sul Mac. Una parola cambiata su un lato si scopre solo dopo una corsa
iOS, e intanto web e iPhone mostrano frasi diverse. Piano: `docs/superpowers/plans/2026-11-08-ondata-2.md`, lavoro (a).

## Fattori della decisione
- Una sola fonte (decisione 0003: la web è il riferimento).
- Un errore si deve vedere su Linux in pochi secondi, non sul Mac dopo 20 minuti.
- Pochi conflitti fra pull request che aggiungono testi in parti diverse dell'app.
- Nessuna libreria nuova e nessuna compilazione per la web.

## Opzioni considerate
- Tenere `testi.js` come fonte e generare da lì i testi dell'iPhone.
- Un catalogo JSON, un file per prefisso della chiave, da cui si generano `testi.js` e i testi dell'iPhone.
- I testi solo sul server, chiesti dalle app all'avvio.

## Decisione
Scelta: il catalogo JSON in `fanta/testi/<prefisso>.json` (`it`, `en`, `nota`). `python script/testi.py --scrivi` genera la parte dei
dati di `fanta/web/testi.js` e, per le sole chiavi che l'iPhone dichiara in `ios/testi/<prefisso>.txt`, i file Swift di
`ios/Sources/Support/Catalogo/`. I programmi leggono JSON senza indovinare il JavaScript, un file per prefisso divide i conflitti,
e l'iPhone riceve solo le chiavi che usa, così una PR della web tocca `ios/` solo quando cambia un testo che l'iPhone mostra.
I testi solo sul server sono scartati: la web dovrebbe aspettare una risposta prima di scrivere qualsiasi cosa.

## Conseguenze
- Bene: un testo cambiato arriva a web e iPhone nella stessa pull request, per costruzione; i test iOS che confrontano con
  `testi.js` si tolgono man mano.
- Male (il prezzo): un passo in più per chi scrive un testo (catalogo, poi `--scrivi`); una volta sola, l'ordine delle righe di
  `testi.js` cambia.
- Controlli: `python script/testi.py --controlla` e `tests/test_catalogo_testi.py` (file generati uguali al catalogo, chiavi dell'iPhone
  presenti, segnaposto uguali nelle due lingue); `tests/test_testi.py` e `tests/test_frasi.py` continuano a leggere `testi.js` generato.
