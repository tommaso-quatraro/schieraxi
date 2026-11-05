# Web e iPhone uguali

Scritto il 2/11/2026 dopo un confronto su telefono: la stessa giornata era «Giornata 10» in testa alla web, «Giornata 7» in
Oggi e «Giornata 7 di lega (Serie A 10)» sull'iPhone. Chi usa le due app non deve mai chiedersi quale numero è giusto.

## La regola
1. **La web app è il riferimento.** Testi, numeri, forme e stati dell'iPhone sono quelli della web (`fanta/web/testi.js`).
2. Si prende la forma dell'iPhone solo dove è chiaramente migliore. In quel caso si cambia anche la web, e la scelta si scrive
   qui nel vocabolario.
3. **Ogni modifica a una schermata vale per tutte e due.** Una PR che cambia un testo, un numero o uno stato su un lato
   aggiorna anche l'altro. Se non può, perché l'altro lato è di un altro agente o di un'altra PR, apre un'issue «coerenza:
   …» con il testo esatto e la cita nella PR.
4. I numeri arrivano dal server e non si ricalcolano sul client: fantavoto atteso, «gioca N%», punti attesi e fascia.
5. Il widget dell'iPhone e Android seguono lo stesso vocabolario.

## Vocabolario comune
| Cosa | Forma giusta | Mai |
|---|---|---|
| Numero della giornata | «Giornata 7»: il numero della **lega** (`giornata_lega`; se manca, `giornata`). Vale in testata, Oggi, Formazione, Diario, avvisi, widget, testo e immagine da condividere. | «Giornata 7 di lega (Serie A 10)»; il numero di Serie A da solo dove si parla della tua formazione |
| Numero di Serie A | Solo dove si parla del calendario di Serie A: il calendario, il grafico dei voti e lo stato dei dati. Si scrive «Serie A, giornata 10», oppure «G10» sotto un titolo che dice Serie A. | «Giornata 10» senza dire che è di Serie A |
| Probabilità di giocare | «gioca 92%», l'unica percentuale sul giocare. Sul campo, sotto il 70%, «⚠ gioca 45%» in una pillola arancio. A partita iniziata non si mostra più. Partita rinviata: sulla pedina «Rinviata» al posto di «gioca N%», prima e dopo la scadenza. | «92%» da solo, «Titolare 85%», «Dubbio (55%)», «⚠ gioca 50%» per una partita rinviata |
| Avversario sul campo | «vs PAR» in casa, «@ UDI» in trasferta, con la sigla nei colori sociali | «PAR (f)», «UDI fuori» |
| Partita in una riga | «ATA vs PAR · oggi 20:45» (in casa), «INT @ MIL · sab 31 20:45» (in trasferta). Prima la squadra del giocatore. | «INT – MIL fuori», «GEN – COM casa», «GENOA vs COMO» |
| Partita nella scheda | «Giornata 7 · in casa contro Como · sab 31 20:45», «… · in trasferta contro Milan · …» | «fuori contro» |
| Partite del turno (Oggi) | «MIL vs INT», con la squadra di casa prima e le sigle. Uguale nella carta delle partite rinviate: «UDI vs MIL» | «Milan – Inter», «UDI–MIL» |
| Sigle delle squadre | Tre lettere maiuscole, dalla tabella `SIGLE` (web) = `ColoriSquadra.sigle` (iOS): devono restare uguali. Il nome intero («Como») solo in frase: scheda, VoiceOver, lettori di schermo. | Nome intero in maiuscolo («GENOA»); nome intero in una riga di elenco |
| Titolarità (prima della scadenza) | Probabile titolare · In ballottaggio · Probabile panchina · Improbabile · Fuori; dubbio: «In dubbio · gioca 55%». Sempre l'`etichetta` del server, la stessa in Formazione, campo, scheda, Oggi («Da controllare»), scelta del confronto e widget. «In dubbio» solo se lo dicono le probabili; in una frase la stessa parola in minuscolo («Lerri: improbabile, gioca 2%.») | numeri dentro l'etichetta; «In dubbio» per chi gioca al 2% senza dubbio delle probabili |
| Posto in formazione (Confronto, scelta del confronto, sostituzione) | «Titolare», «Panchina 2», «Non schierato» (fuori dai titolari e dalla panchina) | «Probabile titolare», «Fuori»: sono parole della titolarità |
| Stato della partita (dopo la scadenza) | Da giocare · Partita in corso · Ha giocato (o il fantavoto) · Voto in arrivo · Senza voto · Rinviata. Stesse parole in Oggi, Formazione e scheda. | «In campo», «in campo ora», «Aspetta il voto», «partita rinviata» |
| Stato della scelta (Formazione) | Le frasi di `formazione.stato_*` di `testi.js`: «Stai vedendo la consigliata: non hai salvato una tua formazione.», «La tua formazione è salvata (oggi alle 13:09)», «Modifiche non salvate · salvata …», «Modifica a mano non ancora salvata», «La formazione salvata non è più valida: …» | frasi diverse per lo stesso stato |
| Formazione chiusa | Formazione in sola lettura. Per la tua squadra una frase sola, nella riga dello stato della scelta: «Giornata iniziata: la formazione è chiusa», con «· vale quella che hai salvato» se hai salvato una scelta (`formazione.stato_chiusa`, `formazione.stato_chiusa_tua`). La fascia «La formazione di questa giornata è chiusa: le partite sono cominciate.» (`formazione.chiusa`) solo per la formazione di un'altra squadra, che non ha la riga di stato. Se la scadenza passa mentre salvi: «La giornata è già iniziata: la formazione non si può più cambiare.» (`err.formazione_chiusa`). | fascia e riga di stato insieme per la tua squadra (due frasi per lo stesso stato); nessuna fascia |
| Stato della giornata (Oggi) | Prima: conto alla rovescia («2 giorni 3 h», «3 h 20 min», «12 min») e sotto «La formazione si chiude sab 31 14:50 (10 min prima della prima partita)». Dopo la scadenza: «**Chiusa**» e «La formazione della giornata 7 si è chiusa sab 31 14:50». Finita: «Giornata 7 finita». Senza data: «Data da definire». | «In corso» al posto di «Chiusa» |
| Fantavoto atteso | Numero **neutro** (colore del testo), una cifra decimale, uguale in campo, elenchi, scheda e widget. Sul campo sta in una pillola scura con il numero bianco. | colorato in base al valore (pallino rosso, blu, verde) |
| Voti veri (giornata in corso) | Numero neutro, come sopra | verde da 7, rosso sotto 6 |
| Colori | Solo per gli esiti: bonus e malus, «+» verde e «−» rosso, avvisi arancio (`docs/DESIGN.md`, «Colori semantici») | colore come unica informazione |
| Numeri | Virgola italiana; punti con un decimale; «+1,2» e «−0,4» con il meno tipografico; 0,0 senza segno; «–» se manca | «-0,4» con il trattino |
| Plurali | «1 tuo titolare / 3 tuoi titolari», «1 giocatore deve ancora giocare», «1 credito» | «1 giocatori», «(i)» |
| Date e ore | Ora italiana. «oggi 20:45», «ieri 20:45», «domani 18:30»; entro la settimana «sab 31 20:45»; oltre, con il mese. Salvataggi: «oggi alle 13:09», «sab 31 alle 13:09». In una frase del server (motivi, «perché»): «mer 18 nov», sempre con il mese, perché la frase resta in memoria e «domani» invecchierebbe. | «sab 8 nov, 18:30» per le partite della settimana; «18/11» |
| Nomi dei giocatori | Negli elenchi come li manda il server («Rossi L.»). **Sul campo** solo il cognome, senza l'iniziale, come sull'iPhone («Rossi»): lo spazio è poco. Il cognome è sempre intero e va a capo, con il trattino dove l'italiano lo mette, e il carattere non si rimpicciolisce mai (al minimo 12 pt sull'iPhone, 12 px sulla web); anche «⚠ gioca N%» e «vs MON» vanno a capo invece di rimpicciolirsi. | «Carlos Au…» tagliato per colpa dell'iniziale, «Zosaba Nd…» |
| Sezioni e menu | Nomi e ordine di `VOCI_LEGA` (`fanta/web/app.js`). Squadra: Squadre e rose, Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario, Aggiorna le rose. Altro: Scambi, Diario delle giornate, Regole, Movimenti e storico, Crediti delle squadre, Nuova stagione, Novità. | voci in un altro ordine, voci in più su un lato solo |
| Giocatori seguiti | Un solo nome: «**Seguiti**» (menu, scheda del mercato, avvisi). Nella scheda il pulsante «☆ Segui», che diventa «★ Seguito»; «Lo segui: ti avviso se cambia qualcosa», «Non lo segui più». In inglese «Following» / «☆ Follow». | «Osservati», «☆ Osserva», «Osservato», «Watched» |

Scelte già prese con la forma dell'iPhone (da portare sulla web): «INT @ MIL» nelle righe, «in trasferta contro», il
cognome senza iniziale sul campo, «Ho schierato la consigliata» nel Diario.

## Differenze ammesse
Differenze volute: testi uguali, cambia solo dove o come si mostrano. Una riga per differenza, con il motivo.
- **Aggiorna le rose, «Rose salvate»**: sulla web è un avviso che passa; sull'iPhone è la prima riga dell'esito. Motivo: l'iPhone non ha avvisi che passano, e così la conferma resta scritta (anche per VoiceOver) finché non si riprova.
- **Aggiorna le rose, posto dell'esito**: sulla web l'esito prende il posto dell'anteprima, in fondo alla scheda; sull'iPhone sta in cima alla lista. Motivo: dopo «Conferma e salva» l'anteprima si chiude e la lista riparte dall'alto, quindi in cima l'esito si vede subito, senza scorrere sotto il file e il testo incollato.
- **Pagina strettissima** (web sotto i 320 px utili: zoom del browser al 200% sul telefono, o testo «Molto grande» su un telefono piccolo): la testata scorre via, la barra in basso mostra solo le icone, le righe dei giocatori mettono il nome sotto il volto e il campo ha due pedine per fila. Motivo: l'iPhone non ha lo zoom della pagina; il suo testo grande lo gestiscono la barra di sistema e `RigaGiocatore`. Testi e numeri restano gli stessi.

## Differenze di oggi
Confronto fatto sul codice di `main` del 2/11/2026, sulle PR aperte e sulle foto del telefono e della CI. Le schermate segnate
«da confrontare» non le ho guardate riga per riga.

| # | Schermata | Web | iPhone | Forma giusta | Chi la sistema |
|---|---|---|---|---|---|
| 1 | Testata (web) | «Giornata 10» (`prossima_giornata`, Serie A) | – | «Giornata 7» | fatto sulla web (pacchetto 1) |
| 2 | Formazione, intestazione, testo e immagine da condividere | «Giornata 10 · la tua scelta» (`f.giornata`) | «Giornata 7 di lega (Serie A 10)» | «Giornata 7» | web: fatto sulla web (pacchetto 1); iPhone: da fare (I-formati) |
| 3 | Oggi, card della giornata | «Giornata 7» | «Giornata 7 di lega (Serie A 10)» | «Giornata 7» | da fare (I-formati) |
| 4 | Scheda giocatore, prossima partita | «Giornata 11 · fuori contro …» (Serie A) | «Giornata 11 · in trasferta contro …» | «Giornata 8 · in trasferta contro …» | da fare (S, W, #27) |
| 5 | Diario | «Giornata 7» | «Giornata 10» (Serie A) | «Giornata 7» | #21 |
| 6 | Campo | «gioca 92%» e «vs PAR / @ UDI» | «92% · PAR (f)» | web | fatto con #22 (build 256): aggiornare l'app sul telefono |
| 7 | Campo, fantavoto atteso | pillola scura | pallino colorato per valore | pillola scura | fatto con #22 |
| 8 | Campo, nome | «Rossi L.», tagliato se lungo | «Rossi» | iPhone | fatto sulla web (pacchetto 1) |
| 9 | Formazione chiusa | fascia «chiusa», sola lettura | niente fascia, si può ancora salvare | web | fatto con #69 (sola lettura) e #290 (stessa frase) |
| 10 | Formazione, stato «salvata» | sempre visibile | mancava | web | fatto con #22 |
| 11 | Formazione, etichette | a parole | «Titolare 85%» | web | #69 (campo e Formazione), #27 (elenco e scheda) |
| 12 | Righe giocatore (Formazione, Rosa, Seguiti, Elenco) | «INT – MIL fuori · sab 31 20:45» | «INTER @ MILAN» (nome intero maiuscolo), senza data | «INT @ MIL · sab 31 20:45» | web: fatto sulla web (pacchetto 1); iPhone: I-Oggi per `RigaGiocatore.swift`, #27 per l'elenco |
| 13 | Righe giocatore, etichette | pillole | testo colorato in fila | pillole | da fare (I-Oggi) |
| 14 | Calendario e prossime partite (celle) | «MIL» con sotto «fuori» | uguale («MIL» e «fuori») | «@ MIL» / «vs MIL» | web: fatto sulla web (pacchetto 1); iPhone in #27 o dopo, `ComponentiScheda.swift` |
| 15 | Oggi, partite del turno | «MIL vs INT» | «Milan – Inter» (anche in #17) | web | #17 (da chiedere) |
| 16 | Oggi, giornata chiusa | «Chiusa» e «… si è chiusa sab 31 14:50» | «In corso» (anche in #17) | web | #17 (da chiedere) |
| 17 | Oggi, dubbio | «In dubbio · gioca 55%» | «Dubbio (55%)» in #17 | web | #17 (da chiedere) |
| 18 | Oggi, banner delle novità | «Novità della versione X» (dal 2/11/2026, senza ✨ né «tocca per vedere»: `STILE-SENZA-AI.md`) | «Novità di SchieraXI» in #17 | web | iPhone da allineare |
| 19 | Oggi in corso, stati | «senza voto», «voto in arrivo», «in campo ora», «partita rinviata», «da giocare» | «Senza voto», «Aspetta il voto», «In campo», «Rinviata», «dom 20:45» | vocabolario (Senza voto, Voto in arrivo, Partita in corso, Rinviata, Da giocare) | web: fatto sulla web (pacchetto 1); iPhone: da fare (I-fasi) |
| 20 | Oggi in corso, squadra e voti | «GEN», voto neutro | «Genoa», voto verde o rosso | «GEN», voto neutro | da fare (I-fasi) |
| 21 | Segno negativo | «−0,4» | «-0,4» | «−0,4» | da fare (I-formati) |
| 22 | Date | «sab 31 20:45», «oggi 20:45» | «sab 31 ott, 20:45» | web | da fare (I-formati) |
| 23 | Scheda giocatore, numero grande | neutro | verde | neutro | #27 (da chiedere) |
| 24 | Diario, pulsante | «Ho schierato questa» | «Ho schierato la consigliata» (#21) | iPhone | fatto sulla web (pacchetto 1) |
| 25 | Scambi | «Costruisci uno scambio», «Valuta lo scambio», «Giocatori in rosa dopo lo scambio», «Formazione migliore (prossime N giornate)» | «Analizza», «Valuta l'offerta», «Rose dopo lo scambio», «Tua formazione migliore» | web | da fare (I-Scambi, dopo #14) |
| 26 | Menu Squadra | «Aggiorna le rose» per ultima | «Aggiorna le rose» per prima | web | da fare (I-menu, dopo #29) |
| 27 | Menu Altro | niente asta | «Asta e riparazione» | da decidere | decisione dell'utente |
| 28 | Confronto, titolo | – | «Giornata 10» (Serie A) | «Giornata 7» | da fare (I-menu, dopo #29) |
| 29 | Avvisi, Impostazioni, Account, Regole, Novità, Squadre e rose | – | – | da confrontare | da fare (I-confronto) |
| 30 | Pillole dei giocatori, colore | quattro toni del server: «Probabile titolare», «Ha giocato», «Partita in corso» verdi | le stesse grigie (tre gravità, positivo come neutro) | web (`docs/DESIGN.md`, «Colori semantici») | fatto con #242 |
| 31 | Pulsanti pieni, tema scuro | testo verde quasi nero sul verde chiaro (`--azione-testo`) | testo bianco sul verde chiaro, 1,8:1 | web (stessi due colori) | fatto con #248 |
| 32 | Scelta del confronto, posto | «Titolare», «Panchina 2», «Non schierato» e l'etichetta del server | «Titolare», «Panchina 2», «Fuori» | web | iPhone da fare (#281): `ConfrontoViewModel.posto` |
| 33 | Confronto, numeri negativi nelle barre | «−1,12» | «-1,12» (`Formato.decimali`) | web | iPhone da fare (#281): `ConfrontoView.valore` |
| 34 | Campo, partita rinviata | «Rinviata» | «gioca 50%» | web | iPhone da fare (#284): `PedinaCampo` |
| 35 | Oggi, carta del rinvio | «UDI vs MIL» | «UDI–MIL» | web | iPhone da fare (#284): `PartiteRinviate.partita` |
| 36 | Widget, «Da controllare» | `etichetta` di `/api/widget` («Improbabile») | «In dubbio · gioca 2%» dal `tipo` | server | iPhone da fare (#282): `GiocatoreWidget.descrizioneStato` |

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
- **Numero della giornata**: è un numero, non un testo. Serve che il server mandi `giornata_lega` accanto a `giornata` in ogni
  risposta (oggi manca nella scheda del giocatore e nel confronto), e che i client usino `giornata_lega ?? giornata`.
  Un'etichetta pronta non impedirebbe a un client di leggere il campo sbagliato. Lo impedisce un test (vedi sotto).
- **«vs PAR» / «@ PAR»**: due caratteri, e i client devono comunque disegnare la sigla nei colori sociali.
- **Date e conto alla rovescia**: «oggi», «ieri» e i minuti cambiano con l'orologio del telefono. Restano sul client.

## Controlli automatici (proposti)
- Web (pytest su `fanta/web/app.js`): nessun `t("testata.giornata", { n: <x>.giornata })` senza `_lega`; nessuna chiave
  `giocatore.casa` o `giocatore.fuori` dopo una sigla.
- iPhone (XCTest): `TempiLega.etichetta` non contiene «Serie A»; `Formato.conSegno(-0.4)` vale «−0,4»; la tabella delle sigle è
  uguale a quella della web (un file di prova con le 26 sigle, letto da tutti e due i test).

## Prima di unire una PR che tocca una schermata
- Ho cambiato testi o stati? Cerco la stessa frase sull'altro lato (`testi.js` oppure `ios/Sources`) e la allineo, o apro
  l'issue «coerenza: …».
- Numero della giornata, «gioca N%», partita, sigle, date e segni seguono il vocabolario qui sopra.
- Una foto per lato della schermata toccata, con gli stessi dati (web locale o foto della CI dell'iPhone).
