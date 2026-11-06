## Etichette pronte dal server?
Il server potrebbe mandare il testo già scritto, così i due client non possono divergere. Serve davvero in un caso solo.

**Fatto (2/11/2026):** il server manda `etichetta` (PR #83) e la web la mostra in Formazione, campo, scheda, Rosa, Seguiti, Oggi in corso e avvisi di Oggi (testo e colore dal `tono`); le parole composte in JS restano solo come ripiego quando `etichetta` manca (Cambi consigliati, server vecchio). L'iPhone deve fare lo stesso.

**Sì: l'etichetta di stato del giocatore.** Oggi la stessa scelta (titolarità prima della scadenza, stato della partita dopo,
«Fuori» se infortunato o squalificato, dubbio) si rifà in quattro punti: `pillTitolarita` e `valoreLive` della web,
`Giocatore.etichette` e `TestiFase` dell'iPhone. Ci sono già tre vocabolari diversi (righe 11, 17 e 19). Proposta: un campo
facoltativo `etichetta` = `{testo, frase, gravita}` per ogni giocatore di `/api/formazione`, `/api/oggi` e della scheda,
costruito con le `Frase` di `fanta/frasi.py`. La web lo traduce con `traduciFrase`, l'iPhone mostra `testo`.
- Pro: una regola sola e parole uguali per forza; l'inglese della web resta. I client vecchi ignorano il campo.
- Contro: un campo in più per giocatore (circa 30 per risposta, pochi byte); una voce nuova in `CATALOGO` e in `testi.js`; i
  client devono comunque disegnare la pillola (colore da `gravita`).

**No, basta il vocabolario:**
- **Numero della giornata**: sono due numeri, non un testo. Il server manda `giornata_lega` accanto a `giornata` in ogni
  risposta e ogni client costruisce il testo con la sua funzione unica (sezione «Giornata: le forme»). Le frasi del server
  (avvisi, Da fare) usano `frasi.nome_giornata`, che dà le stesse forme.
  Un'etichetta pronta non impedirebbe a un client di leggere il campo sbagliato. Lo impedisce un test (vedi sotto).
- **«vs PAR» / «@ PAR»**: due caratteri, e i client devono comunque disegnare la sigla nei colori sociali.
- **Date e conto alla rovescia**: «oggi», «ieri» e i minuti cambiano con l'orologio del telefono. Restano sul client.

## Controlli automatici (proposti)
- Web (pytest su `fanta/web/app.js`): ogni numero di giornata passa da `nomeGiornata` (`tests/test_giornate_lega_serie_a.py`); nessuna chiave
  `giocatore.casa` o `giocatore.fuori` dopo una sigla.
- iPhone (Swift Testing): la funzione unica della giornata dà «Giornata 8 · 11ª di Serie A», «11ª giornata di Serie A» con la lega nulla e la forma corta; `Formato.conSegno(-0.4)` vale «−0,4»; la tabella delle sigle è
  uguale a quella della web (un file di prova con le 26 sigle, letto da tutti e due i test).

## Prima di unire una PR che tocca una schermata
- Ho cambiato testi o stati? Cerco la stessa frase sull'altro lato (`testi.js` oppure `ios/Sources`) e la allineo, o apro
  l'issue «coerenza: …».
- Numero della giornata, «gioca N%», partita, sigle, date e segni seguono il vocabolario qui sopra.
- Una foto per lato della schermata toccata, con gli stessi dati (web locale o foto della CI dell'iPhone).
