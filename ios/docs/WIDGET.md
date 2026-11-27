# Widget di SchieraXI: quali, in che misure, con quali dati

I widget sono **tre**: Prossima giornata, Formazione consigliata, Da controllare. Gli altri otto (Chi gioca, Crediti e svincolo,
Stato dei dati, Cruscotto, Punti attesi e fatti, Partite live, Giocatore seguito, Miglior scambio) non erano nel pacchetto e sono stati
tolti il 12/11/2026 con le loro foto (#634). Più sotto le regole che parlano di loro descrivono testi e conti che restano in
`Sources/Support/WidgetRiassunto.swift` (e nei suoi test) senza più un widget che li mostri: si tolgono in un lavoro a parte.

Tutti leggono UNA chiamata compatta, `GET /api/widget` (token `fw_` a scopo limitato, sempre `If-None-Match`; 304 = dati uguali, 202 = il server sta calcolando e il widget tiene quelli di prima). La lega non usa il capitano e non ha una classifica della lega nei dati: niente widget per quelle due cose.

| Widget | piccolo | medio | grande | extra large (iPad) | cerchio | rettangolo | riga | Motivo |
|---|---|---|---|---|---|---|---|---|
| Prossima giornata | si | si | no | no | si | si | si | conto alla rovescia come la web («6 h 44 min», «2 giorni 3 h»: una voce della timeline per ogni minuto in cui cambia, per l'ora che viene, senza ricaricare) e scadenza «oggi 05:30» / «ven 6 03:32»; grande ed extra large non aggiungerebbero dati. Sulla schermata di blocco il conto c'è in tutte e tre le forme (#871: cerchio e riga mostravano modulo e punti, come la Formazione): nel cerchio la giornata e il conto, lo stesso cerchio di chi è entrato a giornata iniziata; nel rettangolo la giornata, il conto e la formazione; nella riga «Giornata 8: 17 h 50 min» e, dove non entra, il solo conto (`RiassuntoOggi.formeRigaInLineaConto`; senza scadenza resta la formazione), con VoiceOver che legge il conto a parole intere |
| Formazione consigliata | si | si (campo mini) | si (campo con cognomi) | si (campo + lista) | si | si | si | i volti sul campo sono il dato |
| Da controllare | no | si | si | no | no | si | no | servono almeno 2-3 nomi per avere senso. Le parole sono l'`etichetta` degli avvisi del server, come Oggi e la Formazione («Improbabile», «Probabile panchina», «In dubbio · gioca 55%»); senza, quelle calcolate dal `tipo`. Il numero («4 da controllare», «e altri 2») è quello del server (`da_controllare` di `/api/widget`, dal 26/11/2026, `RiassuntoWidget.contoDaControllare`): `avvisi` porta al più 6 giocatori, prima i titolari, e il widget non li conta più da sé; con un server di prima conta i titolari arrivati. Lo stesso numero in Prossima giornata e Formazione consigliata. Test in `ContoDaControllareWidgetTests` |

Da fare: niente di fisso. Stile e modulo: il server non li mette in `/api/widget`.

## Fasi della giornata

Campi facoltativi `fase`, `in_corso`, `riepilogo` (gli stessi di `GET /api/oggi`, contratto «fasi della giornata» nel repository del server), letti da `RiassuntoWidget.faseGiornata` e portati in `RiassuntoOggi` (`fase`, `puntiFatti`, `puntiFine`, `ancoraDaGiocare`, `giornataChiusa`; test in `WidgetFasiTests`).
- `in_corso`: niente «Da controllare» (anche Formazione non mostra i dubbi); Prossima giornata mostra i punti fatti grandi con «punti finora», «circa 75 a fine giornata» senza decimali, gli attesi di prima e sotto la frase del server su cosa manca (`in_corso.situazione`, #900: «3 giocatori devono ancora giocare», «Hanno giocato tutti tranne Bapepe, che aspetta il recupero.»; nel medio, al posto della riga con i nomi di chi aspetta il recupero, la breve scritta apposta dal server, che sta intera senza rimpicciolirsi (`in_corso.situazione_breve` di `/api/widget`, #911: «3 giocatori aspettano il recupero; mancano i voti ufficiali.», `RiassuntoOggi.fraseDelMedio`, test in `WidgetFraseBreveTests`; VoiceOver legge la riga intera); senza la breve (server di prima, dati di `/api/oggi`) la riga intera nella colonna di destra se ci sta intera, se no a tutta larghezza sotto le due colonne; con il testo grande, prima di rimpicciolire, le stesse due con tutto il widget alla misura del testo normale (#911: la frase non esce mai più piccola che con il testo normale); ultima scelta, sempre alla misura del testo normale, la frase rimpicciolita nella colonna di destra fino a 5 righe: si misura con `ViewThatFits` e non si taglia mai con «…»; nelle foto `*_recupero` dei widget, dati `in_corso_recupero` della galleria, la frase con tre nomi e la sua breve; con un server di prima `oggi.ancora_da_giocare` e `oggi.tutti_giocato`), con le parole e i numeri della testa della Formazione (`formazione.punti_finora`, `formazione.circa_fine`, #774; per questo l'estensione compila `Catalogo+Oggi.swift` e `Catalogo+Formazione.swift`; test in `WidgetInCorsoComeLAppTests`). Nel medio la frase è divisa in «A fine giornata» e «circa 75», nel cerchio solo «fatti» («Differenze ammesse» della coerenza). Il tocco apre Oggi. Dopo la scadenza la giornata è **«Chiusa»** come sulla web (`oggi.chiusa`), mai «In corso»: conto alla rovescia, Prossima giornata, Da controllare (nel medio e nel grande «Chiusa» in testata con la giornata a destra, al posto di «Da controllare» che non aveva più niente sotto, e sotto «La formazione si è chiusa oggi 14:50.» e «I punti fatti sono nella Formazione.»: `RiassuntoOggi.testataDubbi` e `corpoFaseDubbi`, #819, test in `TestataDaControllareTests`). «In corso» resta solo per le partite («Partite in corso»).
- `finita`: riepilogo della giornata chiusa (fatti contro attesi) e conto alla rovescia della prossima (`giornata` e `scadenza` sono già quelle della prossima); niente «Da controllare»: nel medio e nel grande la testata è la giornata finita, non la prossima, con la frase della web «Giornata 8 · 11ª di Serie A: finita» (`oggi.giornata_finita`, poi «Giornata 8: finita») e niente giornata a destra, che la ripeteva; sotto «Si ricomincia con la prossima giornata.» (#819). Nel rettangolo «Giornata 8: finita» (la stessa forma corta di Da controllare: prima «Giornata 8 finita», #871) e la prossima.
- Campionato finito (`campionato_finito` = `{testo, frase}`, #656, #727): nessuna giornata; `RiassuntoWidget.campionatoFinito` porta il `testo` del server in `RiassuntoOggi.campionatoFinito` (prima `comeRiassuntoOggi` voleva una giornata e i widget dicevano «Nessun dato · Apri SchieraXI per aggiornare i dati» con il simbolo del Wi-Fi). Tutti e tre mostrano la frase con la bandiera a scacchi (`CampionatoFinitoWidget`), anche nelle 48 ore in cui il server manda ancora il riepilogo dell'ultima giornata (lo mostra l'app); dove la frase intera non entra la sua prima parte, fino ai due punti («Il campionato è finito», `ParoleWidget.formeCampionatoFinito`), nella riga in linea anche solo il simbolo. Foto: `-DATI campionato_finito` (`LegaDemo.widgetCampionatoFinito`), giri `iphone_campionato_finito` di `scripts/screenshot_widget.sh`; test in `WidgetCampionatoFinitoTests`.
- Entrato a giornata già iniziata senza una formazione (`senza_formazione` con `fase: "in_corso"`, #651, #687): niente `in_corso` e c'è `prossima`, la giornata da preparare; `giornata`, `scadenza` e `formazione` restano della giornata già iniziata. `RiassuntoWidget.faseGiornata` li porta in `RiassuntoOggi.senzaFormazione` e `prossimaDaPreparare` (giornata, numero della lega, scadenza). Prossima giornata non mostra la consigliata di quella giornata («Chiusa · 3-4-3 71,5 punti attesi») ma, come la web, la giornata già iniziata con «Questa giornata è già iniziata», «Prepara la prossima» (`oggi.gia_iniziata`, `oggi.prepara_prossima`) e il conto alla rovescia alla scadenza della prossima (`scadenzaDelConto`, anche per le voci della timeline); nel medio a destra la prossima giornata con «alla scadenza, …». Il tocco apre la Formazione, che è già quella della prossima. Dal #752 lo stesso vale per Formazione consigliata e Da controllare, in ogni misura (nel grande e nell'extra large tutto in alto e raggruppato: la giornata già iniziata, «Prepara la prossima» e subito sotto la prossima con il conto alla rovescia; lo spazio libero resta sotto): prima Formazione consigliata mostrava la consigliata della giornata già iniziata (che `formazione` di `/api/widget` porta ancora) e Da controllare «Chiusa · … I punti fatti sono nella Formazione.». La vista è una sola (`SenzaFormazioneWidget`), il caso lo sceglie `CasoWidget` (campionato finito prima di tutto, poi questo, poi il widget di sempre); anche il tocco su Da controllare apre la Formazione. La consigliata della prossima nel widget non c'è: con il token del widget il server legge solo la cache, e quella consigliata ci sta solo dopo che l'app ha aperto la Formazione (sparisce a ogni aggiornamento dei dati), quindi il widget passerebbe da una cosa all'altra. Foto: `-DATI senza_formazione`, giri `iphone_senza_formazione` e `ipad_fasi` di `scripts/screenshot_widget.sh`; test in `WidgetSenzaFormazioneTests` e `WidgetAltriSenzaFormazioneTests` (dati `widget-senza-formazione` e `widget-in-corso`).
- Senza `fase` (server che non la manda): come prima. Con la fase ma senza i numeri (`in_corso: null`): conto alla rovescia di sempre, ma senza «Da controllare».
- Foto: galleria con `-DATI in_corso` / `-DATI finita` (`LegaDemo.widget(fase:)`), giri `iphone_fasi` e `ipad_fasi` di `scripts/screenshot_widget.sh`.

## Dati delle foto: la stessa lega dell'app

La galleria dei widget (`AnteprimaWidget`) e la demo dell'app (`DatiDemo.swift`) leggono la stessa lega inventata,
`Sources/Support/LegaDemo.swift` (compilato anche nella galleria, vedi `project.yml`): stessi nomi con gli accenti, stessa
percentuale di chi è in dubbio, stessa scadenza, stessi orari, Diario (`DemoWidgetComeAppTests`).
Dati possibili: prima della scadenza nessuna partita è in corso. Il widget senza collegamento non mostra testi tecnici: la
diagnostica sta nell'app (Impostazioni > Avanzate > Diagnostica widget).

## Testi che non entrano

Un widget ha misure fisse: con il testo grande, su iPad o sulla schermata di blocco un testo può non entrare. Mai tagliarlo a metà
parola («4 da contr…»): ogni testo ha più forme, dalla più lunga alla più corta, scritte in `ParoleWidget` (`Sources/Support/WidgetRiassunto.swift`,
provate in `TestiCortiWidgetTests`), e la vista mostra la prima che entra (`TestoCheEntra`, `PrimaCheEntra`, cioè `ViewThatFits`).
Esempi: «4 da controllare» → «4 da vedere» (`oggi.da_vedere` del catalogo, #848) → «4»; «In dubbio · gioca 70%» → prima senza volti, poi «gioca 70%»; «Giornata 7 · 10ª di Serie A» →
«Giornata 7»; tabella dei punti: prima via «10ª di Serie A», poi via la fascia; elenchi di nomi: «Sorvani e altri 2». VoiceOver
legge sempre la forma intera.
Un testo che può andare a capo non si spezza a metà di una data o del conto alla rovescia (#871: «alla scadenza, lun / 23 20:35»):
giorno, numero e ora restano uniti con lo spazio che non va a capo (`ParoleWidget.unito`), e si va a capo prima, dopo la virgola
(«alla scadenza,» e sotto «lun 23 20:35», `ParoleWidget.allaScadenza`, l'unica che i widget usano: lo prova un test sui sorgenti).
«Prossima: 4 giorni 1 h» è un testo solo (`ParoleWidget.prossima`, vista `ProssimaConto`): prima erano due testi che si
rimpicciolivano ciascuno per conto suo e con il testo molto grande il conto usciva più piccolo di «Prossima:». Nei piccoli va a capo
con il conto intero sulla riga sotto; nei rettangoli resta su una riga e, se serve, si rimpicciolisce tutto insieme. Nel piccolo di
chi è entrato a giornata iniziata, dove con il testo grande non entra tutto, prima cede la parola «Prossima:» (resta il conto su una
riga, sotto «Prepara la prossima») e per ultima la riga «Questa giornata è già iniziata», che dice perché non c'è una formazione
(`DisposizioneWidget.proveColonnaSenzaFormazione`).
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
Giornata, in tutti i widget (#299): «Giornata 8 · 11ª di Serie A» o «Giornata 8», mai «G8» né «G11». Una funzione sola,
`ParoleWidget.formeGiornata` (e `giornataNelCerchio` per i cerchi della schermata di blocco, dove «Giornata 8» si rimpicciolisce).
Testate con titolo (`IntestazioneWidget`, Attesi e fatti): la prima disposizione di `ParoleWidget.testata` che entra intera, il
titolo con la giornata intera, poi con «Giornata 8», poi il solo simbolo: si perde il titolo, mai la giornata. Righe delle fasi
(Prossima giornata, Da controllare): «Giornata 8 · Chiusa», «Giornata 8: finita», e in linea «Giornata 8: 41,5 punti finora»
che perde parole fino a «Giornata 8: 41,5». Attesi e fatti di una stagione passata (agosto, «38ª di Serie A»): nel rettangolo
la stagione sta sulla riga sotto («2025-26 · attesi 70,0 · +1,0»); la riga in linea la perde per ultima («38ª di Serie A: 71,0»),
VoiceOver la dice sempre. Le ultime forme hanno un tetto di lunghezza provato dai test (`GiornataInteraWidgetTests`); senza il
numero della lega le testate piccole si rimpiccioliscono invece di tagliarsi. La sigla resta solo nelle colonne strette sotto un titolo, come le colonne del
calendario: le colonne del grafico «Attesi e fatti» («G4 G5 G6 G7»), con VoiceOver che legge la giornata intera.
Widget Formazione: grande ed extra large, accanto al modulo i
punti attesi e sotto la fascia con la giornata (`TestataFormazioneGrande`); se «Giornata 8» non entra accanto alla fascia scende
sulla riga sotto (`postiGiornata`); sotto il campo «2 da controllare» a sinistra e «7 in panchina» a destra. L'extra large non li
aveva (#871); è alto quanto il grande e il campo con i volti da 48 punti lo riempiva già, quindi la sua colonna di sinistra tiene la
prima prova che entra in altezza (`DisposizioneWidget.proveCampoExtraLarge`): volti da 48, 40, 32 punti, per ultimi via i cognomi
sotto i volti, che l'elenco dei titolari accanto dice già. Testata, giornata e righe sotto il campo non cedono. Piccolo: il titolo
con la giornata sulla riga sotto; se in altezza non c'è posto, il simbolo con la giornata accanto (si perde il titolo, non la
giornata). Medio: la giornata non c'è (comportamento accettato nel collaudo del 25/11, #871): la colonna di sinistra è larga 120
punti e il resto è del campo; la giornata la dicono piccolo, grande, extra large e schermata di blocco. Rettangolo della schermata
di blocco: «Giornata 8» sulla prima riga, come il rettangolo di Prossima giornata, poi «Formazione 3-4-3», i punti attesi e «2 da
controllare» (#871: con giocatori da controllare la giornata spariva); dove le quattro righe non entrano (testo grande, iPhone
piccoli) la giornata sale accanto al modulo, che perde «Formazione» (`DisposizioneWidget.proveRettangoloFormazione`). Né la giornata
né «da controllare» cedono; la giornata al più si rimpicciolisce. VoiceOver legge sempre «Giornata 8, 11ª di Serie A».
I widget rotondi della schermata di blocco stanno in `CerchioWidget` (contenuto sempre al centro). Crediti: simbolo «C» nel cerchio
(`ParoleWidget.simboloCrediti`, come l'app), mai l'euro.
Copia salvata (server che non risponde o rete assente, #834): una riga sola per tutti i widget, `RigaCopia`. Di oggi la sola ora,
«dati delle 18:30»; di un altro giorno anche il giorno, come `Quando.relativa`: «dati di ieri 18:30», «dati di mar 17 21:05»,
oltre la settimana «dati di dom 8 nov 18:30»; dove non entra perde l'ora («dati di ieri»), poi «dati di» (la sola data accanto al
simbolo, «ieri», di oggi «18:30»: con il testo molto grande sta su una riga anche nel medio), mai «…» (`ParoleWidget.datiSalvati`,
ora italiana, contata dall'istante della voce: a mezzanotte «dati delle 23:30» diventa «dati di ieri 23:30»). La stessa riga c'è
anche con i dati arrivati bene ma vecchi, perché iOS ha rimandato le ricariche: oltre 15 minuti con una partita in gioco o che sta
per iniziare, oltre un'ora negli altri momenti, con l'orologio al posto della nuvola sbarrata (`EtaDatiWidget`, `Voce.oraDeiDati`;
la timeline ha una voce in più quando passa ogni soglia). Prima a partite in corso i punti di un'ora prima sembravano attuali.
Nel Formazione piccolo
e medio la riga c'è anche con «2 da controllare», sopra, e con il testo normale ci stanno tutte e due, anche sull'iPad: per fare
posto cedono prima il titolo del piccolo (resta il simbolo con la giornata), nel medio «punti attesi» e la fascia su due righe
(«attesi · tra 65 e 81» su una), poi la fascia («72,7 attesi»); per ultima, solo con il testo molto grande, la data della copia, e
«da controllare» mai (`DisposizioneWidget.proveFormazione`). Prima di cedere la data si accorcia in larghezza («dati di mer 25» →
«mer 25») e «2 da controllare» diventa «2 da vedere». Fino al 27/11 era il contrario (collaudo del 25/11, #838, #871): con il testo
grande piccolo e medio tenevano la sola data e perdevano «2 da controllare»; deciso nella #959 che i titolari da controllare sono più
utili della data. Test in `WidgetOraCopiaTests`; foto: `-DATI salvati` (copia di due giorni prima)
e `salvati_oggi` (copia di oggi), giri `iphone_salvati`, `iphone_salvati_testo_grande`, `ipad_salvati` e `ipad_salvati_testo_grande`
di `scripts/screenshot_widget.sh`.

## Collegamento automatico (Apple ID gratuito + SideStore)

L'utente non compila niente: l'app passa al widget l'indirizzo e il token `fw_` da sola. Come firma SideStore (sorgenti, ramo `develop`, novembre 2026):
- [verificato nel codice] registra il gruppo `group.it.schieraxi.app` come `group.it.schieraxi.app.<SQUADRA>`, uguale per app e widget (`FetchProvisioningProfilesOperation.adjustedGroupIdentifier`), e aggiunge la squadra al bundle id (`it.schieraxi.app.<SQUADRA>`).
- [verificato nel codice] dal commit 7866508 (15/9/2026) NON scrive più `ALTAppGroups` in Info.plist (prima sì; AltStore sì). Il nome vero si legge dal profilo `embedded.mobileprovision` di ogni pacchetto (`ProfiloFirma`), poi si prova con `containerURL(forSecurityApplicationGroupIdentifier:)`. Era il motivo per cui il widget restava da collegare.
- [verificato nel codice] firma con i permessi del profilo, solo quelli che l'app dichiara (ldid in `ipa.yml`); per `keychain-access-groups` tiene i gruppi dell'app e cambia il prefisso (prima del primo punto) con la squadra (`ALTSigner.swift` di AltSign). Da qui il ripiego: Keychain condiviso `<SQUADRA>.it.schieraxi.app.condiviso` (`PortachiaviCondiviso`). Il token della sessione resta nel gruppo privato dell'app.
- [da verificare sul telefono] che il profilo gratuito contenga davvero gruppo e `keychain-access-groups` e che widget e app vedano gli stessi dati. La riga Impostazioni > App lo dice: «Widget collegato automaticamente» o «Widget: tocca per collegare»; i dettagli in Avanzate > Diagnostica widget («gruppo sì/no · portachiavi sì/no»).

Ordine per indirizzo e token (`CodiceWidget.destinazione`, provato nei test): App Group con token > Keychain condiviso con token > codice incollato > indirizzo dell'app senza token > server pubblico (`ServerPubblico.indirizzo`). Il widget non chiede più l'indirizzo.

Ultimo ripiego (se né gruppo né Keychain funzionano):
- Widget non collegato (il server risponde 401 o non c'è niente): dice **«Tocca per collegare»** e il tocco apre `schieraxi://widget/collega`.
- L'app (foglio «Collega il widget», `Presentation/Lega/CollegaWidgetView.swift` con la logica in `CollegaWidgetModello.swift`, anche dal passo Widget della guida e dalla riga delle Impostazioni) si apre senza fare niente: l'indirizzo lo può aprire anche un'altra app o una pagina. Solo dopo il tocco su «Collega» chiede SEMPRE un token `fw_` nuovo (dal 26/11/2026, `TokenWidget.nuovo`: quello che il telefono ha può essere stato rifiutato dal server senza che l'app lo sappia; prima «Collega» diceva «collegato» e teneva il token vecchio) e riprova l'automatico; se il token nuovo non arriva dice «Il server non ha risposto»; solo se l'automatico non va crea il codice (`CodiceWidget`, prefisso `schieraxi1.`) e lo mette negli appunti di questo telefono per 2 minuti (niente Appunti universali).
- L'utente tiene premuto il widget > «Modifica widget» > attiva «Collegamento manuale» > incolla in «Codice di collegamento» (il campo compare solo con l'interruttore acceso, `parameterSummary` con `When`).
- Il server tiene un token per dispositivo (dal 26/11/2026; prima UNO per utente, e l'iPad che entrava o usciva spegneva il widget dell'iPhone dello stesso account): ogni token è legato alla sessione che l'ha chiesto, uno nuovo prende il posto solo di quello della stessa sessione, «Esci» chiude quello del suo dispositivo (`POST /api/account/esci`; l'app non manda più `DELETE /api/account/token-widget`) e i token senza legame nati prima del 20/11/2026 (il widget che li usava prende un 401 e il segnale lo ricollega). Quando l'app lo rinnova (a 7 giorni dalla scadenza dei 90) o si esce dall'account, il codice incollato smette di valere (con il collegamento automatico invece il token nuovo arriva da solo). Al 401 il widget cancella le sue copie e dice **«Tocca per collegare»**, senza dati vecchi.
- Segnale del 401 (dal 26/11/2026, `SegnaleWidget`): se il widget aveva un token, al 401 scrive nella cartella del gruppo un file suo (`widget-rifiutato.json`, il file condiviso lo scrive solo l'app) con l'impronta del collegamento rifiutato, mai il token. L'app lo legge all'apertura (`SessioneAccount.verifica` → `TokenWidget.assicura`) e nell'aggiornamento in background (`Aggiornamento.tokenDelWidget`): se è proprio il token che ha lei lo dimentica e ne chiede uno nuovo, poi toglie il segnale; uno per un altro token (codice incollato, token già sostituito) si toglie e basta. Finché il token rifiutato non è sostituito, Impostazioni > App dice «Widget: tocca per collegare» (`TokenWidget.accettato`). Senza App Group il segnale non c'è: resta «Tocca per collegare» e «Collega». Test in `WidgetTokenPerDispositivoTests`.
- Ogni copia del widget porta l'impronta del collegamento (`MemoriaWidget.impronta`: SHA-256 di indirizzo e token) e si mostra solo con lo stesso collegamento, anche senza App Group. All'uscita l'app pulisce file condiviso, Keychain condiviso e copie e ricarica i widget (`DatiLocali.dimenticaIlWidget`). Un «Esci» che non riesce (rete giù, server in errore) non pulisce niente: riassunto, copie e token del widget restano (il server toglie il token solo insieme alla sessione) e il widget resta collegato (#809). Una lettura della giornata partita prima di «Esci» e arrivata dopo non riscrive il riassunto dell'account uscito nel file condiviso (`Aggiornamento.elabora` guarda che la sessione sia ancora quella di quando è partita la lettura, `ChiLegge`).
- Il file condiviso (`condiviso.json`, con il token del widget) sta fuori dai backup del telefono, come gli elementi del Keychain (`isExcludedFromBackup`, a ogni scrittura): dopo un ripristino l'app lo riscrive alla prima apertura. Il token resta anche nel file e non solo nel Keychain condiviso, perché sul telefono non è ancora provato che il Keychain condiviso funzioni dove funziona il gruppo.
- Limite noto: con il collegamento manuale, se si esce dall'account senza rete il server non revoca il token e il widget continua a mostrare quell'account finché il token non scade o non si toglie il codice dal widget.

Tocchi (indirizzi `schieraxi://`): widget da collegare -> `widget/collega`, scadenza -> `oggi`, modulo e punti -> `formazione`, volti e righe dei giocatori -> `giocatore/<id>`, scambio -> `scambi`, svincolo e crediti -> `mercato`, grafico attesi e fatti -> `lega`.

Anteprime: il target `AnteprimaWidget` (solo CI, non entra nell IPA) mostra i widget con dati finti in tutte le misure; il workflow `Screenshot` (`screenshot.yml`, insieme alle foto dell app) li fotografa su iPhone e iPad (chiaro, scuro, dati parziali o assenti) e carica l artifact `screenshot-widget`. Ogni giro passa all'anteprima il suo aspetto (`-ASPETTO scuro|chiaro`), che vince su quello del simulatore: il simulatore cambia aspetto dopo un po' e le prime foto «scuro» dopo l'accensione dell'iPad uscivano chiare (#890).
