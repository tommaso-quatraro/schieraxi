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
| Numero della giornata | **Tutti e due i numeri, come su Leghe** (dal 5/11/2026, #299): «**Giornata 8 · 11ª di Serie A**» = giornata 8 della lega (`giornata_lega`) e 11ª di Serie A (`giornata`). Forme e frasi esatte nella sezione «Giornata: le forme» qui sotto. | «Giornata 8» da sola dove c'è spazio; «Giornata 7 di lega (Serie A 10)»; «Giornata 11» per un numero di Serie A |
| Numero di Serie A | Dove si parla solo della Serie A (calendario, grafico dei voti, stato dei dati, prova del modello) e quando la lega non c'è (stagioni passate, prima che la lega parta): «11ª giornata di Serie A». Nelle colonne strette «G11» sotto un titolo, con «11ª giornata di Serie A» per i lettori di schermo. | «Giornata 11» senza dire che è di Serie A |
| Probabilità di giocare | «gioca 92%», l'unica percentuale sul giocare. Sul campo, sotto il 70%, «⚠ gioca 45%» in una pillola arancio. A partita iniziata non si mostra più. Partita rinviata: sulla pedina «Rinviata» al posto di «gioca N%», prima e dopo la scadenza. | «92%» da solo, «Titolare 85%», «Dubbio (55%)», «⚠ gioca 50%» per una partita rinviata |
| Avversario sul campo | «vs PAR» in casa, «@ UDI» in trasferta, con la sigla del club (sulla web scritta in bianco con la lineetta nel colore sociale davanti, sull'iPhone nei colori sociali: «Differenze ammesse») | «PAR (f)», «UDI fuori» |
| Partita in una riga | «ATA vs PAR · oggi 20:45» (in casa), «INT @ MIL · sab 31 20:45» (in trasferta). Prima la squadra del giocatore. | «INT – MIL fuori», «GEN – COM casa», «GENOA vs COMO» |
| Partita nella scheda | «Giornata 7 · 10ª di Serie A · in casa contro Como · sab 31 20:45», «… · in trasferta contro Milan · …» | «fuori contro» |
| Partite del turno (Oggi) | «MIL vs INT», con la squadra di casa prima e le sigle. Uguale nella carta delle partite rinviate («UDI vs MIL») e nel riepilogo della giornata finita («Manca il recupero di ATA vs PAR») | «Milan – Inter», «UDI–MIL» |
| Sigle delle squadre | Tre lettere maiuscole, dalla tabella `SIGLE` (web) = `ColoriSquadra.sigle` (iOS): devono restare uguali. Il nome intero («Como») solo in frase: scheda, VoiceOver, lettori di schermo. | Nome intero in maiuscolo («GENOA»); nome intero in una riga di elenco |
| Titolarità (prima della scadenza) | Probabile titolare · In ballottaggio · Probabile panchina · Improbabile · Fuori; dubbio: «In dubbio · gioca 55%». Sempre l'`etichetta` del server, la stessa in Formazione, campo, scheda, Oggi («Da controllare»), scelta del confronto e widget. «In dubbio» solo se lo dicono le probabili; in una frase la stessa parola in minuscolo («Lerri: improbabile, gioca 2%.») | numeri dentro l'etichetta; «In dubbio» per chi gioca al 2% senza dubbio delle probabili |
| Posto in formazione (Confronto, scelta del confronto, sostituzione) | «Titolare», «Panchina 2», «Non schierato» (fuori dai titolari e dalla panchina) | «Probabile titolare», «Fuori»: sono parole della titolarità |
| Stato della partita (dopo la scadenza) | Da giocare · Partita in corso · Ha giocato (o il fantavoto) · Voto in arrivo · Senza voto · Rinviata. Stesse parole in Oggi, Formazione e scheda. | «In campo», «in campo ora», «Aspetta il voto», «partita rinviata» |
| Stato della scelta (Formazione) | Le frasi di `formazione.stato_*` di `testi.js`: «Stai vedendo la consigliata: non hai salvato una tua formazione.», «La tua formazione è salvata (oggi alle 13:09)», «Modifiche non salvate · salvata …», «Modifica a mano non ancora salvata», «La formazione salvata non è più valida: …» | frasi diverse per lo stesso stato |
| Da fare (Oggi) | Le frasi e i pulsanti sono il `testo` e l'`azione` del server, uguali sui due lati (la web traduce da `frase.*`). Hai salvato la consigliata e poi è cambiata: una riga sola, «La consigliata è cambiata da quando l'hai salvata: rivedila. Ora schiera Y al posto di X.» (oltre 3 cambi «… Cambiano N titolari.»; se esce un titolare fuori, «X è infortunato e la consigliata è cambiata…», urgente), pulsante «Apri la formazione», icona della formazione sull'iPhone (tipo `formazione`, #333). Con la consigliata salvata e ancora uguale nessun «Meglio…» né «Sostituisci». | frasi riscritte su un lato; «Sostituisci» su una consigliata appena salvata |
| Formazione chiusa | Formazione in sola lettura. Per la tua squadra una frase sola, nella riga dello stato della scelta: «Giornata iniziata: la formazione è chiusa», con «· vale quella che hai salvato» se hai salvato una scelta (`formazione.stato_chiusa`, `formazione.stato_chiusa_tua`); se la scelta salvata non si può più schierare (`stato_scelta: "non_valida"` di `GET /api/formazione`, o `formazione_non_valida` rileggendola) «Giornata iniziata: la formazione è chiusa · vale la consigliata, la tua non è più valida» (`formazione.stato_chiusa_non_valida`) e si vede la consigliata, come in Oggi (#319). La fascia «La formazione di questa giornata è chiusa: le partite sono cominciate.» (`formazione.chiusa`) solo per la formazione di un'altra squadra, che non ha la riga di stato. Se la scadenza passa mentre salvi: «La giornata è già iniziata: la formazione non si può più cambiare.» (`err.formazione_chiusa`). | fascia e riga di stato insieme per la tua squadra (due frasi per lo stesso stato); nessuna fascia |
| Anticipo già cominciato (Formazione aperta, #373) | I giocatori in `bloccati` di `GET /api/formazione` in «Modifica a mano» non si sostituiscono e non entrano dalla rosa (al posto del pulsante per sostituire c'è ⇄); sotto i titolari «Chi gioca in una partita già cominciata non si può più spostare.» (`formazione.bloccati`). Salvataggio rifiutato dal server: la sua frase, «Rossi gioca in una partita già cominciata: non si può più spostare.» (`err.giocatore_bloccato`) | lucchetti o pillole nuove; una frase diversa per lo stesso rifiuto |
| Nota sotto il campo (Formazione) | Il perché delle scelte che sembrano storte (#356): una riga per titolare, «**Nome** · riga», con il testo del server (`perche_scelta` del modulo sullo schermo, chiavi `scelta.*`), per esempio «Preferito a Gallo: con lui la formazione fa più punti attesi (64,1 contro 63,9).» o «Titolare anche se incerto (gioca 35%): se non gioca entra Gallo dalla panchina, e insieme valgono di più.». Solo per la proposta del server: niente righe dopo «Modifica a mano» né a giornata iniziata. | frasi scritte dal client; righe per i titolari che non sembrano storti; la nota anche sulla formazione modificata a mano |
| Stato della giornata (Oggi) | Prima: conto alla rovescia («2 giorni 3 h», «3 h 20 min», «12 min») e sotto «La formazione si chiude sab 31 14:50 (10 min prima della prima partita)». Dopo la scadenza: «**Chiusa**» e «La formazione si è chiusa sab 31 14:50» (la giornata è scritta subito sopra il conto, non si ripete). Finita: «Giornata 7 · 10ª di Serie A: finita». Senza data: «Data da definire». | «In corso» al posto di «Chiusa» |
| Fantavoto atteso | Numero **neutro** (colore del testo), una cifra decimale, uguale in campo, elenchi, scheda e widget. Sul campo della web è il numero nel disco bianco della pedina, sull'iPhone sta in una pillola scura sotto il volto («Differenze ammesse»). | colorato in base al valore (pallino rosso, blu, verde) |
| Voti veri (giornata in corso) | Numero neutro, come sopra | verde da 7, rosso sotto 6 |
| Colori | Solo per gli esiti: bonus e malus, «+» verde e «−» rosso, avvisi arancio (`docs/DESIGN.md`, «Colori semantici») | colore come unica informazione |
| Numeri | Virgola italiana; punti con un decimale; «+1,2» e «−0,4» con il meno tipografico; 0,0 senza segno; «–» se manca | «-0,4» con il trattino |
| Plurali | «1 tuo titolare / 3 tuoi titolari», «1 giocatore deve ancora giocare», «1 credito» | «1 giocatori», «(i)» |
| Date e ore | Ora italiana. «oggi 20:45», «ieri 20:45», «domani 18:30»; entro la settimana «sab 31 20:45»; oltre, con il mese. Salvataggi: «oggi alle 13:09», «sab 31 alle 13:09». In una frase del server (motivi, «perché»): «mer 18 nov», sempre con il mese, perché la frase resta in memoria e «domani» invecchierebbe. | «sab 8 nov, 18:30» per le partite della settimana; «18/11» |
| Nomi dei giocatori | Negli elenchi come li manda il server («Rossi L.»). **Sul campo** solo il cognome, senza l'iniziale, come sull'iPhone («Rossi»): lo spazio è poco. Il cognome è sempre intero e va a capo, con il trattino dove l'italiano lo mette, e il carattere non si rimpicciolisce mai (al minimo 12 pt sull'iPhone, 12 px sulla web); anche «⚠ gioca N%» e «vs MON» vanno a capo invece di rimpicciolirsi. | «Carlos Au…» tagliato per colpa dell'iniziale, «Zosaba Nd…» |
| Sezioni e menu | Nomi e ordine di `VOCI_LEGA` (`fanta/web/app.js`). Squadra: Squadre e rose, Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario, Aggiorna le rose. Altro: Scambi, Diario delle giornate, Regole, Movimenti e storico, Crediti delle squadre, Nuova stagione, Novità. | voci in un altro ordine, voci in più su un lato solo |
| Giocatori seguiti | Un solo nome: «**Seguiti**» (menu, scheda del mercato, avvisi). Nella scheda il pulsante «☆ Segui», che diventa «★ Seguito»; «Lo segui: ti avviso se cambia qualcosa», «Non lo segui più». In inglese «Following» / «☆ Follow». | «Osservati», «☆ Osserva», «Osservato», «Watched» |

## Giornata: le forme (#299, dal 5/11/2026)
Decisione del proprietario: come su Leghe Fantacalcio si mostrano **tutti e due i numeri**, quello della lega e quello di Serie A.
I due numeri arrivano dal server in ogni risposta che parla di una giornata: `giornata` (Serie A) e `giornata_lega` (lega; `null`
per le stagioni passate e prima che la lega parta). Il testo lo costruisce **una sola funzione per piattaforma**, mai a mano:
web `nomeGiornata(lega, serieA)` in `fanta/web/app.js`; server `frasi.nome_giornata(serie_a, lega)` in `fanta/frasi.py`
(avvisi, Da fare, testo per i Comandi); iPhone `NomeGiornata` in `ios/Sources/Domain/TempiLega.swift` (app e widget), con le stesse forme.

| Forma | Quando | Italiano | Inglese |
|---|---|---|---|
| Intera | dove c'è spazio: testata, Oggi, Formazione, Diario, scheda, Confronto, avvisi, Da fare, testo e immagine da condividere | «Giornata 8 · 11ª di Serie A» | «Matchday 8 · Serie A matchday 11» |
| Corta | dove lo spazio è poco (widget piccoli, righe strette, cerchi della schermata di blocco) | «Giornata 8» e sotto, più piccolo, «11ª di Serie A»; solo «Giornata 8» come ultimo ripiego. Mai «G8» (nei widget: `ParoleWidget.formeGiornata`) | «Matchday 8» e sotto «Serie A matchday 11» |
| Solo Serie A | `giornata_lega` nullo (stagioni passate, prima che la lega parta) e dove si parla solo di Serie A | «11ª giornata di Serie A» | «Serie A matchday 11» |
| Colonna stretta | colonne del calendario e del grafico «Attesi e fatti» dei widget, sotto un titolo | «G11» | «G11» |

- VoiceOver e lettori di schermo leggono **sempre la forma intera** (o «11ª giornata di Serie A» per la colonna «G11»).
- Lega partita con la Serie A (`prima_giornata_lega` = 1): si scrivono tutti e due anche se uguali, «Giornata 8 · 8ª di Serie A».
- «ª» è il carattere dell'ordinale femminile (U+00AA), non una «a» piccola.
- Davanti all'8ª e all'11ª (ottava, undicesima) l'articolo perde la vocale: «l'11ª giornata di Serie A», «dall'8ª all'11ª»,
  «per l'11ª»; «la 1ª» e «la Giornata 8» restano. Una funzione per lato: web `elidiOrdinali`, server `frasi.elidi_ordinali`, iPhone `TempiLega.elidiOrdinali`.
- **In una frase** la forma intera va in testa, seguita dai due punti: «Giornata 8 · 11ª di Serie A: la formazione si chiude sab 31 14:50.»
  Così la frase resta grammaticale in ogni lingua e non nasce una terza forma.
- Se manca anche `giornata` (server vecchio) si scrive «Giornata 8»; se mancano tutti e due, niente.

Frasi esatte, schermata per schermata (italiano; l'inglese è in `fanta/web/testi.js` con le stesse chiavi):

| Dove | Testo |
|---|---|
| Testata (web) | «Giornata 8 · 11ª di Serie A» |
| Oggi, sopra il conto alla rovescia | «Giornata 8 · 11ª di Serie A»; dopo la scadenza sotto «Chiusa» c'è «La formazione si è chiusa sab 31 14:50» (senza numero: è scritto sopra) |
| Oggi, giornata finita (titolo del riepilogo) | «Giornata 7 · 10ª di Serie A: finita» |
| Oggi, prossima giornata | «Giornata 9 · 12ª di Serie A: la formazione si chiude sab 7 14:50.» |
| Formazione, intestazione | «Giornata 8 · 11ª di Serie A · modulo consigliato» (o «la tua scelta», «modulo scelto») |
| Formazione, giornata saltata | «Giornata 8 · 11ª di Serie A: è già iniziata. Questa è la formazione per la Giornata 9 · 12ª di Serie A.» |
| Testo da condividere, prima riga | «Giornata 8 · 11ª di Serie A · 3-4-3» (uguale nel testo per i Comandi, `GET /api/formazione/testo`) |
| Immagine da condividere | titolo «Giornata 8 · 11ª di Serie A · 3-4-3» (il carattere si rimpicciolisce se non ci sta); titolo della condivisione «Formazione · Giornata 8 · 11ª di Serie A» |
| Scheda del giocatore, prossima partita | «Giornata 8 · 11ª di Serie A · in casa contro Como · sab 31 20:45» |
| Confronto, titolo | «Chi schierare? Giornata 8 · 11ª di Serie A» |
| Diario, titolo di ogni giornata | «Giornata 8 · 11ª di Serie A»; stagione passata «11ª giornata di Serie A» (con la stagione accanto) |
| Diario, correggi | «Giornata 8 · 11ª di Serie A: tocca i giocatori che hai schierato. Servono 11 titolari.» |
| Diario, «Quando hai scelto diversamente» | «Giornata 8 · 11ª di Serie A: Rossi, Bianchi invece di Verdi, Neri» |
| Diario, «Quanto ci abbiamo preso» | righe «Giornata 8 · 11ª di Serie A · …»; «Calcolato su 5 giornate, dalla Giornata 4 · 7ª di Serie A alla Giornata 8 · 11ª di Serie A.»; sotto le barre del grafico solo il numero della lega |
| Da fare (testo del server) | «Giornata 7 · 10ª di Serie A: è finita, dimmi se hai schierato la consigliata.»; «È il momento di aste e scambi nella lega: se le rose sono cambiate, aggiornale prima della Giornata 12 · 15ª di Serie A.» |
| Widget (iPhone) | forma corta; nel widget piccolo solo «Giornata 8»; etichetta di VoiceOver con la forma intera |
| Calendario di Serie A | colonne «G11», lettori di schermo «11ª giornata di Serie A» |
| Scheda, grafico dei voti | al passaggio sul punto «11ª giornata di Serie A: 6,5» |
| Stato dei dati, probabili | «11ª giornata di Serie A» |
| Stato dei dati, registro delle giornate (giornate perse) | «9ª giornata di Serie A · 2026-27» (`sd.reg_giornata`) |
| Prova del modello (Diario) | «dalla 5ª alla 10ª giornata di Serie A» |

Avvisi sul telefono (testi del server, `fanta/frasi_avvisi.py`): i titoli non hanno più il numero, la forma intera sta in testa al testo.
- Cambi nelle probabili: titolo «SchieraXI · cambi nelle probabili», prima riga del testo «Giornata 8 · 11ª di Serie A».
- Un'ora prima: «Giornata 8 · 11ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 14:50).»
- Ultimi minuti: «Giornata 8 · 11ª di Serie A: la formazione si chiude alle 14:50. L'hai inserita su Leghe?»
- Titolare a rischio: «Hai già schierato, ma Rossi non è più sicuro come titolare. Giornata 8 · 11ª di Serie A: la formazione si chiude alle 14:50, controlla.»
- Riepilogo: titolo «SchieraXI · riepilogo della giornata»; testo «Giornata 7 · 10ª di Serie A: la formazione consigliata ha fatto circa 70,5 punti …» e «Prossima: Giornata 8 · 11ª di Serie A. La formazione si chiude 08/11 alle 14:50.»
- Formazione pronta: «Giornata 8 · 11ª di Serie A: la formazione è pronta. Apri l'app e controlla le probabili.»

Scelte già prese con la forma dell'iPhone (da portare sulla web): «INT @ MIL» nelle righe, «in trasferta contro», il
cognome senza iniziale sul campo, «Ho schierato la consigliata» nel Diario.

## Differenze ammesse
Differenze volute: testi uguali, cambia solo dove o come si mostrano. Una riga per differenza, con il motivo.
- **Aggiorna le rose, «Rose salvate»**: sulla web è un avviso che passa; sull'iPhone è la prima riga dell'esito. Motivo: l'iPhone non ha avvisi che passano, e così la conferma resta scritta (anche per VoiceOver) finché non si riprova.
- **Aggiorna le rose, posto dell'esito**: sulla web l'esito prende il posto dell'anteprima, in fondo alla scheda; sull'iPhone sta in cima alla lista. Motivo: dopo «Conferma e salva» l'anteprima si chiude e la lista riparte dall'alto, quindi in cima l'esito si vede subito, senza scorrere sotto il file e il testo incollato.
- **Colore delle azioni nel tema chiaro** (pulsanti pieni, link, linea della scheda attiva): verde bosco `#0B6B3A` sulla web, oliva `#526600` sull'iPhone; nel tema scuro è lo stesso verde. Motivo: scelta 1b del proprietario nella spec della grafica B (5/11/2026): cambia l'aspetto della web, l'iPhone resta com'è. Testi e funzioni uguali.
- **Schede in alto sul PC** (web da 900 px): le quattro schede stanno nella testata ferma in alto, con la ricerca sempre aperta; il tasto Indietro del browser torna alla schermata di prima. Sull'iPhone e sulla web più stretta restano nella barra in basso. Motivo: con il mouse la barra in alto si raggiunge meglio; le schede e i loro nomi sono gli stessi.
- **Etichette dei giocatori** («Probabile titolare», «In ballottaggio · gioca 55%», «Improbabile»): sulla web sono testo colorato, senza fondo, e due vicine si separano con « · »; sull'iPhone restano pillole. Motivo: grafica B della web (spec del 5/11/2026, §8.9), meno riquadri sulla pagina. Parole e toni (verde, arancio, rosso, grigio) sono gli stessi, perché vengono dal server.
- **Sigla della squadra nelle righe dei giocatori** (Formazione, Oggi, Rosa, Seguiti, Elenco): sulla web davanti alla sigla c'è una lineetta di 3 px in uno dei colori sociali del club (quello che si vede sul fondo del tema), decorativa; sull'iPhone la riga è solo testo (`RigaGiocatore`, nessun colore del club). Motivo: grafica B della web (spec del 5/11/2026, §8.4), il colore del club in un segno piccolo accanto alla sigla. Il testo è lo stesso e grigio sui due lati («NAP vs LAZ · sab 31 20:45»).
- **Indice sul volto nelle righe**: sulla web è un numero piccolo nell'angolo del volto, nei colori del testo, senza anello colorato; sull'iPhone c'è l'anello colorato con il numero. Motivo: grafica B della web (§8.4), meno segni per riga. Il numero è lo stesso, e la frase sotto la Formazione è la stessa sui due lati («Negli elenchi il numero sul volto è l'indice: 100 = il migliore del suo ruolo questa giornata.»): la prova è `FraseIndiceComeLaWebTests`, che la confronta con `formazione.numero_sulla_maglia` di `testi.js`.
- **Pedina sul campo** (Formazione): sulla web la pedina è il numero nel disco, senza volto: un disco bianco da 44 px con il fantavoto atteso, sotto il cognome, «gioca 85%» (o lo stato a partita iniziata, «Rinviata») e «vs NAP» / «@ NAP» con la lineetta del colore sociale; sotto il 70% un anello arancio attorno al disco e «⚠ gioca 57%» nella pillola arancio. Sull'iPhone la pedina ha il volto, con il fantavoto nella pillola scura e la sigla nei colori sociali. Il contenuto è uguale: fantavoto, cognome, «gioca N%» o stato, avversario, e la frase per i lettori di schermo. Motivo: scelta 2 del proprietario nella spec della grafica B (5/11/2026, §8.10): sulla web il numero è la pedina e i volti stanno negli elenchi e nella scheda. La legenda della web sta sotto il campo e si riapre con «Cosa vuol dire» (sull'iPhone la prima volta è una scheda sopra il campo, poi «Cosa vuol dire» sotto); testi uguali.
- **Formazione sul PC** (web da 768 px; da 900 px 5:7): il campo resta fermo a sinistra accanto all'elenco, a destra cifre, stato della scelta, modulo, stile, titolari, panchina e fuori; con modifiche da salvare la riga dello stato con «Salva» resta in vista mentre si scorre, e **Ctrl+S** (⌘+S sul Mac) salva. Sotto Stile una riga di nota: la descrizione dello stile si apre con «Come si legge». Sull'iPhone una colonna sola (stato della scelta, stile e modulo, campo, titolari), con la descrizione dello stile scritta per intero. Motivo: grafica B della web (spec §5, C3, C6 e C9), comodità con mouse e tastiera. Testi, numeri e pulsanti sono gli stessi.
- **Scheda del giocatore sul PC** (web da 1200 px): scheda, confronto, scelta per il confronto, sostituzione di un titolare, «Perché questo numero» e risultati della ricerca si aprono in un pannello a destra, accanto alla pagina che resta attiva (un clic su un altro giocatore cambia il pannello); la ricerca si scrive nel campo della testata. Sull'iPhone e sull'iPad la scheda è un foglio di sistema, e sulla web più stretta il foglio di sempre. Nella scheda il fantavoto atteso è il numero grande con accanto «gioca N%», separati da un filo, e nel «Perché questo numero» l'effetto di ogni motivo sta a destra, in colonna (sull'iPhone a sinistra: «+1,1 · Segna più della media del ruolo»). Motivo: grafica B della web (spec del 5/11/2026, §5 C5, §8.11 e §9), comodità con il mouse. Testi e numeri sono gli stessi.
- **Squadra e Altro sul PC** (web da 1100 px): le voci restano a sinistra e la voce scelta si apre a destra, comprese Cambi consigliati, Seguiti, Elenco dei giocatori e Calendario (sotto i 1100 px sono pagine con le quattro sezioni in alto, come prima); la rosa di una squadra ha il menu accanto. Nell'Elenco dei giocatori e nella rosa i nomi delle colonne restano fermi in alto mentre si scorre. Sull'iPad è lo stesso schema (elenco a sinistra e pagina a destra, `LegaView`), sull'iPhone una pagina alla volta. Motivo: grafica B della web (spec del 5/11/2026, §5 C7 e C10), da una voce all'altra con un clic. Nomi e ordine delle voci sono quelli di `VOCI_LEGA`, uguali sui due lati.
- **«gioca N%» nelle righe sotto il 70%**: sulla web arancio e in grassetto (accanto c'è l'etichetta a parole), sull'iPhone grigio come gli altri. Motivo: grafica B della web (§8.4). Parole e numero uguali.
- **Pagina strettissima** (web sotto i 320 px utili: zoom del browser al 200% sul telefono, o testo «Molto grande» su un telefono piccolo): la testata scorre via, la barra in basso mostra solo le icone, le righe dei giocatori mettono il nome sotto il volto e il campo ha due pedine per fila. Motivo: l'iPhone non ha lo zoom della pagina; il suo testo grande lo gestiscono la barra di sistema e `RigaGiocatore`. Testi e numeri restano gli stessi.
- **Oggi, aspetto**: sulla web la maglia accanto al conto alla rovescia è piccola e dritta (72 px; sull'iPhone 56 pt); le cifre della formazione (modulo | punti attesi) sono separate da un filo; le azioni di Da fare sono testo nel colore delle azioni, a destra nella riga, e il loro numero è grigio accanto al titolo (sull'iPhone pulsanti con il bordo); le righe di Da controllare, Indisponibili e Diffidati hanno la lettera grigia del ruolo e l'etichetta scritta nel colore del tono (sull'iPhone il quadratino del ruolo e la pillola); sul PC due colonne 5:7. Motivo: grafica B della web (spec del 5/11/2026, §9), un solo pulsante pieno e meno riquadri. Testi e numeri sono gli stessi. La testa della schermata e la posizione delle sezioni non sono aspetto: riga 48 di «Differenze di oggi».

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
| 18 | Oggi, banner delle novità | «Novità della versione X» (dal 2/11/2026, senza ✨ né «tocca per vedere»: `STILE-SENZA-AI.md`) | «Novità nell'app (versione X): tocca per vedere» con le stelline | web | fatto sull'iPhone (#416, `TestiOggi.novita` confrontato con `testi.js`) |
| 19 | Oggi in corso, stati | «senza voto», «voto in arrivo», «in campo ora», «partita rinviata», «da giocare» | «Senza voto», «Aspetta il voto», «In campo», «Rinviata», «dom 20:45» | vocabolario (Senza voto, Voto in arrivo, Partita in corso, Rinviata, Da giocare) | web: fatto sulla web (pacchetto 1); iPhone: da fare (I-fasi) |
| 20 | Oggi in corso, squadra e voti | «GEN», voto neutro | «Genoa», voto verde o rosso | «GEN», voto neutro | da fare (I-fasi) |
| 21 | Segno negativo | «−0,4» | «-0,4» | «−0,4» | da fare (I-formati) |
| 22 | Date | «sab 31 20:45», «oggi 20:45» | «sab 31 ott, 20:45» | web | da fare (I-formati) |
| 23 | Scheda giocatore, numero grande | neutro | verde | neutro | #27 (da chiedere) |
| 24 | Diario, pulsante | «Ho schierato questa» | «Ho schierato la consigliata» (#21) | iPhone | fatto sulla web (pacchetto 1) |
| 25 | Scambi | «Costruisci uno scambio», «Valuta lo scambio», «Giocatori in rosa dopo lo scambio», «Formazione migliore (prossime N giornate)» | «Analizza», «Valuta l'offerta», «Rose dopo lo scambio», «Tua formazione migliore» | web | da fare (I-Scambi, dopo #14) |
| 26 | Menu Squadra e Altro, pagina Calendario | «Aggiorna le rose» per ultima, «Calendario» con l'elenco dei giocatori, «Nuova stagione» sempre, riga sotto ogni voce; Calendario «Calendario e difficoltà» | «Aggiorna le rose» per prima, niente «Calendario» né «Nuova stagione», senza righe sotto; «Difficoltà delle prossime partite» | web | fatto con #304 (test contro `VOCI_LEGA` e `testi.js`) |
| 27 | Menu Altro | niente asta | «Asta e riparazione» | da decidere | decisione dell'utente |
| 28 | Confronto, titolo | – | «Giornata 10» (Serie A) | «Giornata 7» | da fare (I-menu, dopo #29) |
| 29 | Avvisi, Impostazioni, Account, Regole, Novità, Squadre e rose | – | – | da confrontare | da fare (I-confronto) |
| 30 | Pillole dei giocatori, colore | quattro toni del server: «Probabile titolare», «Ha giocato», «Partita in corso» verdi | le stesse grigie (tre gravità, positivo come neutro) | web (`docs/DESIGN.md`, «Colori semantici») | fatto con #242 |
| 31 | Pulsanti pieni, tema scuro | testo verde quasi nero sul verde chiaro (`--azione-testo`) | testo bianco sul verde chiaro, 1,8:1 | web (stessi due colori) | fatto con #248 |
| 32 | Scelta del confronto, posto | «Titolare», «Panchina 2», «Non schierato» e l'etichetta del server | «Titolare», «Panchina 2», «Fuori» | web | fatto sull'iPhone (#295) |
| 33 | Confronto, numeri negativi nelle barre | «−1,12» | «-1,12» (`Formato.decimali`) | web | fatto sull'iPhone (#295) |
| 34 | Campo, partita rinviata e partita iniziata | «Rinviata»; a partita iniziata il fantavoto preso o lo stato («Partita in corso») | «gioca 50%», anche a partita iniziata | web (`esitoPedina`) | fatto sull'iPhone (#295, #283): `EsitoPedina` |
| 35 | Oggi, carta del rinvio | «UDI vs MIL» | «UDI–MIL» | web | fatto sull'iPhone (#295) |
| 36 | Widget, «Da controllare» | `etichetta` di `/api/widget` («Improbabile») | «In dubbio · gioca 2%» dal `tipo` | server | fatto sull'iPhone (#295) |
| 37 | Formazione chiusa con la scelta salvata non più valida | «Giornata iniziata: la formazione è chiusa · vale la consigliata, la tua non è più valida» e la consigliata | uguale alla web | server (`stato_scelta` di `GET /api/formazione`) | web fatto (#319); iPhone fatto (#296, PR #318) |
| 38 | Stato dei dati, registro delle giornate | carta «Registro delle giornate» dopo l'affidabilità: tre misure con media, soglia e «regge» / «non regge» / «servono ancora N giornate», poi «Giornate perse» con il motivo (`cartaRegistro`, testi `sd.reg_*`) | uguale; le giornate perse in una sezione loro della lista | web | fatto con #344 (test contro `testi.js` e sulla stessa risposta del server) |
| 39 | Formazione, nota sotto il campo | righe del perché della scelta (prima solo gli incerti) | mancava (nemmeno gli incerti) | server (`perche_scelta` di `GET /api/formazione`) | web e iPhone fatti nella stessa PR (#356) |
| 40 | Confronto, «Tutti i numeri» | «Atteso ponderato (con la probabilità di giocare)», «Quando gioca» a parole, «vs COM», «Normale» | «Punti attesi», «Parte titolare 75%», «COM casa», «Media» | web (`apriConfronto`) | fatto sull'iPhone (#293) |
| 41 | Oggi, giornata finita, recuperi | «Manca il recupero di ATA–PAR» | uguale | «ATA vs PAR», come la carta del rinvio | fatto sulla web e sull'iPhone (#310): stessa funzione della carta del rinvio (`partitaVs`, `TestiRinvio.partita`) |
| 42 | Confronto, in cima ai due nomi | posto sotto il nome («Titolare», «Panchina 2», «Non schierato») | niente posto | web | fatto sull'iPhone (#311): pillola verde per «Titolare», grigia per gli altri, letta da VoiceOver; la partita «INT vs ROM» è la #302 |
| 43 | Righe giocatore a partita iniziata (Formazione, Seguiti, Oggi, Rosa di una squadra) | a partita finita con il voto il fantavoto preso con sotto «fantavoto», altrimenti «–» (lo stato è nella pillola); niente «Perché questo numero». Partita rinviata come prima della partita | fantavoto atteso e «gioca 72%» anche dopo il voto | web (`voceGiocatore`, `valoreRosa`, `esitoPartita`) | fatto sull'iPhone (#313, #367): `EsitoPartita`, `RigaGiocatore`, `RigaRosa`. VoiceOver dice le stesse cose: «fantavoto 3,5» a partita finita, niente a partita in corso (il «–» non si legge), e le etichette sempre |
| 44 | Numero della giornata, ovunque (anche widget e avvisi) | «Giornata 8 · 11ª di Serie A» (`nomeGiornata`) | «Giornata 8» | sezione «Giornata: le forme» | web e server fatto (#299, PR #306); iPhone fatto (#312) |
| 45 | Stato dei dati, consiglio di formazione | carta «Consiglio di formazione» dopo il registro: quattro indicatori a parole (niente sigle C1-C4) con media, soglia e «regge» / «non regge» / «servono ancora N giornate» del server (`cartaConsiglio`, testi `sd.cons_*`) | uguale, sezione dopo il registro (`ConsiglioFormazioneSezione`, `ParoleConsiglio`) | web | fatto con #366 (test contro `testi.js` e sulla stessa risposta del server) |
| 46 | Stato dei dati, gol attesi nostri (senza Understat) | carta «Gol attesi nostri (senza Understat)» dopo il registro: «Le tre misure insieme» «reggono» / «non reggono» / «servono ancora N giornate» (`regge_tutto` del server), poi tre misure a parole (niente sigla I4) con media, soglia e «regge» / «non regge», e «Giornata per giornata» ripiegata (`cartaNostri`, testi `sd.nos_*`) | uguale, sezione dopo il registro (`GolAttesiNostriSezione`, `ParoleNostri`), giornate in un gruppo che si apre | web | fatto con #401 (test contro `testi.js` e sulla stessa risposta del server) |
| 46 | Formazione aperta con un anticipo già cominciato | in «Modifica a mano» i `bloccati` non si sostituiscono né entrano, riga `formazione.bloccati`; rifiuto del server con la sua frase | uguale alla web | server (`bloccati`, 400 `giocatore_bloccato`) | fatto con #373 (web e iPhone nella stessa PR; test contro `testi.js`) |
| 47 | Diario, «Quanto ci abbiamo preso», riga su tutta la Serie A | riga sotto i quattro numeri, testo del server | uguale, stesso testo | server (`precisione.serie_a.testo` di `GET /api/diario`) | web e iPhone fatti nella stessa PR (#374) |
| 48 | Oggi, testa e ordine delle sezioni | parte dal titolo «Oggi», senza nome e slogan (il nome disegnato sta nella testata da 900 px); sotto il conto alla rovescia le cifre della formazione con «Apri la formazione» e le probabili, poi Partita rinviata, Da fare, novità; poi I tuoi migliori, Da controllare, Indisponibili, Diffidati, Partite del turno | uguale: niente nome né slogan, stesso ordine anche a giornata in corso (punti, chi va a punteggio, cambi dalla panchina) e finita (riepilogo, prossima formazione, poi Indisponibili e Diffidati); «Mancano le probabili» sotto «Apri la formazione»; Partite del turno sempre, anche con «Risultati in diretta» spenta (allora senza punteggio né minuto in diretta, decisione del 6/11/2026); titoli e frasi di `testi.js` («La tua formazione», la riga sotto Da controllare); punti attesi scritti subito giusti, senza salire da 0 | web (grafica B, spec del 5/11/2026, §9: l'azione principale nel primo schermo) | web fatto (PR #415); iPhone fatto (#416): l'ordine sta in `SezioneOggi.ordine`, `OggiComeLaWebTests` lo confronta con `mostraOggi` e i testi con `testi.js` |

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
