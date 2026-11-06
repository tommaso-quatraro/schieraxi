# Widget di SchieraXI: quali, in che misure, con quali dati

Tutti leggono UNA chiamata compatta, `GET /api/widget` (token `fw_` a scopo limitato, sempre `If-None-Match`; 304 = dati uguali, 202 = il server sta calcolando e il widget tiene quelli di prima). La lega non usa il capitano e non ha una classifica della lega nei dati: niente widget per quelle due cose.

| Widget | piccolo | medio | grande | extra large (iPad) | cerchio | rettangolo | riga | Motivo |
|---|---|---|---|---|---|---|---|---|
| Prossima giornata | si | si | no | no | si | si | si | conto alla rovescia come la web («6 h 44 min», «2 giorni 3 h»: una voce della timeline per ogni minuto in cui cambia, per l'ora che viene, senza ricaricare) e scadenza «oggi 05:30» / «ven 6 03:32»; grande ed extra large non aggiungerebbero dati |
| Formazione consigliata | si | si (campo mini) | si (campo con cognomi) | si (campo + lista) | si | si | si | i volti sul campo sono il dato |
| Da controllare | no | si | si | no | no | si | no | servono almeno 2-3 nomi per avere senso. Le parole sono l'`etichetta` degli avvisi del server, come Oggi e la Formazione («Improbabile», «Probabile panchina», «In dubbio · gioca 55%»); senza, quelle calcolate dal `tipo` |
| Chi gioca (orari) | no | si | si | si (2 colonne) | no | si | si | serve un nome, un orario e un avversario. Riga (`RigaChiGioca`): a destra quando gioca, una volta sola e con il giorno come la web («oggi 18:30», «domani 18:30»; se non c'è posto, oggi «18:30»); sotto l'avversario e le parole («Diffidato», «Rigorista», «In dubbio · gioca 70%»), in arancione solo se c'è da guardare |
| Crediti e svincolo | si | si | no | no | si | si | si | un numero e un suggerimento: grande sarebbe vuoto |
| Stato dei dati | si | no | no | no | si | si | si | un'informazione sola (per la diagnosi) |
| Cruscotto | no | no | si | si (2 colonne) | si | si | si | tutto prima di una giornata: scadenza viva, formazione, dubbi, scambio, svincolo, attesi e fatti, crediti; ogni blocco apre la sua schermata |
| Punti attesi e fatti | si | si (grafico) | si (grafico e tabella) | no | si | si | si | dal diario: quanto hai fatto contro il previsto; serve a fidarsi delle previsioni |
| Partite live | no | si | si | no | no | si | si | punteggio e minuto delle partite in corso con i tuoi titolari (volto e cognome); senza partite in gioco mostra le prossime. Aggiornamento ogni 2 minuti nelle finestre di gioco (iOS puo rimandare); dal campo `live` di /api/widget |
| Giocatore seguito (scelta nelle impostazioni del widget) | si | si | no | no | si | si | si | un giocatore a tua scelta tra seguiti, rosa e titolari; «gioca N%» da `p_voto` come l'app (mai la percentuale delle probabili); se il server ha tolto i seguiti per il peso (`mancano`), «Apri l'app per vederli» |
| Miglior scambio | si | si | si | no | no | si | si | solo se il server lo ha gia' in cache (apri Scambi nell'app); altrimenti dice di aprire l'app |

Da fare: niente di fisso. Stile e modulo: il server non li mette in `/api/widget`.

## Fasi della giornata

Campi facoltativi `fase`, `in_corso`, `riepilogo` (gli stessi di `GET /api/oggi`, contratto «fasi della giornata» nel repository del server), letti da `RiassuntoWidget.faseGiornata` e portati in `RiassuntoOggi` (`fase`, `puntiFatti`, `puntiFine`, `ancoraDaGiocare`, `giornataChiusa`; test in `WidgetFasiTests`).
- `in_corso`: niente «Da controllare» (anche Formazione e Cruscotto non mostrano i dubbi); Prossima giornata mostra i punti fatti grandi, «circa X a fine giornata», gli attesi di prima e quanti devono ancora giocare; il tocco apre Oggi. Dopo la scadenza la giornata è **«Chiusa»** come sulla web (`oggi.chiusa`), mai «In corso»: conto alla rovescia, Prossima giornata, Da controllare («La formazione della giornata 8 si è chiusa oggi 14:50. I punti fatti sono in Oggi.»). «In corso» resta solo per le partite («Partite in corso»).
- `finita`: riepilogo della giornata chiusa (fatti contro attesi) e conto alla rovescia della prossima (`giornata` e `scadenza` sono già quelle della prossima); niente «Da controllare»: quel widget dice «Giornata 8 finita» (`oggi.giornata_finita` della web) e in testata la giornata finita, non la prossima.
- Senza `fase` (server che non la manda): come prima. Con la fase ma senza i numeri (`in_corso: null`): conto alla rovescia di sempre, ma senza «Da controllare».
- Foto: galleria con `-DATI in_corso` / `-DATI finita` (`LegaDemo.widget(fase:)`), giri `iphone_fasi` e `ipad_fasi` di `scripts/screenshot_widget.sh`.

## Dati delle foto: la stessa lega dell'app

La galleria dei widget (`AnteprimaWidget`) e la demo dell'app (`DatiDemo.swift`) leggono la stessa lega inventata,
`Sources/Support/LegaDemo.swift` (compilato anche nella galleria, vedi `project.yml`): stessi nomi con gli accenti, stessa
percentuale di chi è in dubbio, stessa scadenza, stessi orari, Diario, seguiti, scambio e svincolo (`DemoWidgetComeAppTests`).
Dati possibili: prima della scadenza nessuna partita è in corso (le partite in diretta ci sono solo a giornata in corso: per questo
il widget Live, con `-DATI pieni`, si fotografa a giornata in corso). Il widget senza collegamento non mostra testi tecnici: la
diagnostica sta nell'app (Impostazioni > Avanzate > Diagnostica widget).

## Testi che non entrano

Un widget ha misure fisse: con il testo grande, su iPad o sulla schermata di blocco un testo può non entrare. Mai tagliarlo a metà
parola («4 da contr…»): ogni testo ha più forme, dalla più lunga alla più corta, scritte in `ParoleWidget` (`Sources/Support/WidgetRiassunto.swift`,
provate in `TestiCortiWidgetTests`), e la vista mostra la prima che entra (`TestoCheEntra`, `PrimaCheEntra`, cioè `ViewThatFits`).
Esempi: «4 da controllare» → «4»; «In dubbio · gioca 70%» → prima senza volti, poi «gioca 70%»; «Giornata 7» → «G7»; tabella dei punti:
«G7» al posto di «Giornata 7», poi via la fascia; elenchi di nomi: «Sorvani e altri 2». VoiceOver legge sempre la forma intera.
Lo stesso vale per i blocchi interi (#249). Il Cruscotto grande è alto da circa 270 punti (iPad mini, iPhone SE) a 350 (iPhone
grandi) e tiene la prima prova che entra (`DisposizioneWidget.proveCruscotto`, provate in `DisposizioneWidgetTests`): prima della
scadenza va via la prossima partita, poi la forma compatta (senza fascia e senza la squadra dello scambio, «Scambio +2,4»), poi il
grafico (i crediti restano su una riga), infine un dubbio solo; durante le partite il blocco delle partite resta sempre. Extra large:
a sinistra il campo più grande che entra, a destra le stesse prove. Miglior scambio medio: prima la colonna di sinistra più stretta,
poi senza volti, poi chi dai e chi ricevi su due righe di testo (mai «Vlase…»). Le partite da giocare hanno il giorno e l'ora come
la web («oggi 20:45», «domani 11:23», «mar 3 18:30»): una regola sola per tutti i widget, `PartitaLive.orari`. Dove lo spazio non
basta una partita di oggi ripiega sulla sola ora («20:45»); gli altri giorni tengono sempre il giorno. VoiceOver legge sempre la forma
intera. La usano Partite live e Cruscotto (`PartitaLive.formeEtichetta`), Giocatore seguito e Chi gioca
(`GiocatoreWidget.formeQuandoGioca`, `formePartita`, #267); le righe sulla schermata di blocco con `RigaInLinea`. A mezzanotte la
voce della timeline (`VociTimeline.istanti`) cambia «domani 11:23» in «oggi 11:23».
Una partita senza punteggio si scrive come le partite del turno dell'app e della web, «NAP vs ATA · oggi 18:00», mai con il
trattino tra le sigle; dove non entra nemmeno «NAP vs ATA · 18:00» (o «… · domani 12:30») restano le sole squadre «NAP vs ATA».
Con il punteggio il tabellone «INT 2–1 ROM 63'» (`PartitaLive.formeRiga`, `traLeSigle`, #391); VoiceOver legge il punteggio solo
se ci sono tutti e due i gol.
Widget Formazione (tutte le misure): la giornata è «Giornata 8 · 11ª di Serie A» o «Giornata 8», mai «G8» né «G11» (#299; la
sigla resta solo dove si parla del calendario). Una funzione sola, `ParoleWidget.giornataFormazione`. Grande: accanto al modulo i
punti attesi e sotto la fascia con la giornata (`TestataFormazioneGrande`); se «Giornata 8» non entra accanto alla fascia scende
sulla riga sotto (`postiGiornata`). Piccolo: il titolo con la giornata sulla riga sotto; se in altezza non c'è posto, il simbolo
con la giornata accanto (si perde il titolo, non la giornata). Rettangolo della schermata di blocco: «Giornata 8», al più
rimpicciolita. VoiceOver legge sempre «Giornata 8, 11ª di Serie A».
I widget rotondi della schermata di blocco stanno in `CerchioWidget` (contenuto sempre al centro). Crediti: simbolo «C» nel cerchio
(`ParoleWidget.simboloCrediti`, come l'app), mai l'euro.

## Collegamento automatico (Apple ID gratuito + SideStore)

L'utente non compila niente: l'app passa al widget l'indirizzo e il token `fw_` da sola. Come firma SideStore (sorgenti, ramo `develop`, novembre 2026):
- [verificato nel codice] registra il gruppo `group.it.schieraxi.app` come `group.it.schieraxi.app.<SQUADRA>`, uguale per app e widget (`FetchProvisioningProfilesOperation.adjustedGroupIdentifier`), e aggiunge la squadra al bundle id (`it.schieraxi.app.<SQUADRA>`).
- [verificato nel codice] dal commit 7866508 (15/9/2026) NON scrive più `ALTAppGroups` in Info.plist (prima sì; AltStore sì). Il nome vero si legge dal profilo `embedded.mobileprovision` di ogni pacchetto (`ProfiloFirma`), poi si prova con `containerURL(forSecurityApplicationGroupIdentifier:)`. Era il motivo per cui il widget restava da collegare.
- [verificato nel codice] firma con i permessi del profilo, solo quelli che l'app dichiara (ldid in `ipa.yml`); per `keychain-access-groups` tiene i gruppi dell'app e cambia il prefisso (prima del primo punto) con la squadra (`ALTSigner.swift` di AltSign). Da qui il ripiego: Keychain condiviso `<SQUADRA>.it.schieraxi.app.condiviso` (`PortachiaviCondiviso`). Il token della sessione resta nel gruppo privato dell'app.
- [da verificare sul telefono] che il profilo gratuito contenga davvero gruppo e `keychain-access-groups` e che widget e app vedano gli stessi dati. La riga Impostazioni > App lo dice: «Widget collegato automaticamente» o «Widget: tocca per collegare»; i dettagli in Avanzate > Diagnostica widget («gruppo sì/no · portachiavi sì/no»).

Ordine per indirizzo e token (`CodiceWidget.destinazione`, provato nei test): App Group con token > Keychain condiviso con token > codice incollato > indirizzo dell'app senza token > server pubblico (`ServerPubblico.indirizzo`). Il widget non chiede più l'indirizzo.

Ultimo ripiego (se né gruppo né Keychain funzionano):
- Widget non collegato (il server risponde 401 o non c'è niente): dice **«Tocca per collegare»** e il tocco apre `schieraxi://widget/collega`.
- L'app (foglio «Collega il widget», `Presentation/Lega/CollegaWidgetView.swift`, anche dal passo Widget della guida e dalla riga delle Impostazioni) chiede il token `fw_` se manca e riprova l'automatico; solo se non va crea il codice (`CodiceWidget`, prefisso `schieraxi1.`) e lo mette negli appunti di questo telefono per 5 minuti (niente Appunti universali).
- L'utente tiene premuto il widget > «Modifica widget» > attiva «Collegamento manuale» > incolla in «Codice di collegamento» (il campo compare solo con l'interruttore acceso, `parameterSummary` con `When`).
- Il server tiene UN token per utente: quando l'app lo rinnova (a 7 giorni dalla scadenza dei 90) o si esce dall'account, il codice incollato smette di valere (con il collegamento automatico invece il token nuovo arriva da solo). Il widget mostra la copia vecchia con **«Tocca per ricollegare»** e lo stesso tocco.

Tocchi (indirizzi `schieraxi://`): widget da collegare -> `widget/collega`, scadenza -> `oggi`, modulo e punti -> `formazione`, volti e righe dei giocatori -> `giocatore/<id>`, scambio -> `scambi`, svincolo e crediti -> `mercato`, grafico attesi e fatti -> `lega`.

Anteprime: il target `AnteprimaWidget` (solo CI, non entra nell IPA) mostra i widget con dati finti in tutte le misure; il workflow `Screenshot` (`screenshot.yml`, insieme alle foto dell app) li fotografa su iPhone e iPad (chiaro, scuro, dati parziali o assenti) e carica l artifact `screenshot-widget`.
