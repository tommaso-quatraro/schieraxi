# iPhone come la web nuova: Formazione, Giornate, Impostazioni: piano

> **Per chi esegue:** agente `sviluppatore-ios`, un passo alla volta, ognuno in un ramo e una pull request in bozza sua, in una
> worktree sua. Prima del codice: `.claude/rules/ios.md`, `ios/README.md`, skill `ui-schieraxi` e `swiftui-pro`; per i widget la
> skill `widget-ios`. Test Swift prima del codice, visti fallire in CI (`gh workflow run ios.yml --ref <ramo> -f parte=unitari`).

**Obiettivo:** l'app nativa mostra le stesse cose della web rifatta il 12/11/2026, con gli stessi testi e numeri: tre schede
(Formazione, Giornate, Impostazioni) più la ricerca. Decisione del proprietario del 12/11 (#673): l'app resta nativa.
**Riferimenti:** web #637, #671, #675 (in revisione); spec `docs/superpowers/specs/2026-11-12-revisione-generale-design.md` §2;
`docs/COERENZA-WEB-IPHONE.md` righe 68-70 e le «da decidere» (2-4, 6, 10, 11, 16, 17, 20, 24, 30, 39, 47, 50-52, 61); la web in
`fanta/web/app.js` (`mostraFormazione`, `pedina`, `htmlScheda`, `mostraGiornate`), `dafare.js`, `impostazioni.js` (ramo della #675).

## Regole comuni a ogni passo
- **Niente rotte nuove.** Solo campi facoltativi nei modelli `Decodable` (un server vecchio non rompe niente). Un campo che
  l'iPhone legge deve esistere nel server, altrimenti `tests/test_contratto_ios.py` è rosso.
- **Testi:** chiavi in `ios/testi/<prefisso>.txt` (quelle non più usate si tolgono), poi `python script/testi.py --scrivi`; mai
  una frase della web riscritta a mano; i test confrontano con `Catalogo.…` e non leggono `fanta/web/` (`ios/Tests/file-esterni.txt`).
- **Numeri e stati dal server.** Le decisioni in cima le segna il server (decisione 1, §6). Dove la web applica ancora una regola
  sua (titolari diversi dalla consigliata, soglia di «gioca N%»), l'iPhone fa lo stesso in `Domain/`, con un test su dati inventati.
- **iOS 18 minimo:** `Tab(role: .search)` e `sidebarAdaptable` ci sono; su iOS lo stile `.checkbox` del `Toggle` non c'è (spunta
  «L'ho messa» = `Toggle` normale o pulsante con `checkmark.circle`); niente `Table` per la tabella delle Giornate (sul telefono
  mostra una colonna sola): `Grid`. Liquid Glass solo dietro `#available(iOS 26, *)` come oggi (`Support/Design/Vetro`).
- **`Domain/Modelli.swift`, `WidgetRiassunto.swift`, `Condiviso.swift`, `TempiLega.swift`, `Formato.swift` li compila anche il
  widget** (`ios/project.yml`): un campo nuovo lì usa solo tipi che il widget vede; quei file non si tolgono.
- **In ogni pull request:** `ios/README.md` («Cosa c'è» e «Da provare»), righe di `docs/coerenza/schermate/` passate a «fatto»
  (`python script/coerenza.py --scrivi`), nomi delle foto in `Support/Demo.swift`, `ios/scripts/screenshot.sh` (`TUTTE`, `PER_*`)
  e `script/squadra/foto.json` (con `tests/test_squadra_foto.py`, `tests/test_foto_fondo_lega.py`). Riga `Aree:` di conseguenza
  (`ios, docs, script/squadra, tests`). Schermata nuova o rifatta: foto sul ramo prima dell'unione, le scatta chi coordina.
- **Ordine dei commit:** testi del catalogo; test rossi; `Domain/`; viste; tolte le viste vecchie e i loro test; demo e foto;
  README e coerenza. Una corsa `parte=unitari` dopo `Domain/`, una completa alla fine; le corse vecchie si annullano.

## 1. Formazione (Oggi + Formazione)

**Web oggi (#637).** Si apre per prima. Testa per fase: prima «Giornata 8 · 11ª di Serie A» e «Si chiude sab 31 14:50 fra 3 h
10 min»; in corso «40,0 punti finora · circa 75 a fine giornata» e quanti devono ancora giocare; finita «83,0 punti (attesi
71,7)» con «Com'è andata», «Con la consigliata: …», recuperi mancanti e sotto la prossima giornata; arrivato a partite
cominciate la frase `formazione.per_la_prossima`; senza rose il benvenuto. Poi al massimo due decisioni con la loro azione;
modulo come menu («4-3-3 · 73,7 punti · consigliato») con punti attesi e «di solito fra 65 e 82»; campo con fantavoto atteso e
cognome, «gioca N%» solo sotto l'80% (arancio 50-79, rosso sotto 50), «In dubbio», «Infortunato», «Squalificato», «Fuori»,
«Rinviata» a parole, niente avversario; sotto il campo la riga dello stato («È la consigliata.» oppure «L'hai cambiata tu: 2
titolari diversi dalla consigliata (−0,4 punti attesi).» con «Torna alla consigliata»), «Copia per l'app della lega», spunta
«L'ho messa»; salvataggio automatico; panchina nell'ordine del server, «Non schierati» e «Infortunati e squalificati» chiusi,
partite rinviate. Una sola scheda del giocatore, con «Sostituisci».

**iPhone oggi.** Due schede: Oggi (`Presentation/Oggi/`: `OggiView`, `SezioneOggi`, `CartaFormazioneOggi`, `FasiGiornataView`,
`CartaSenzaFormazione`, `CapsulaGiornata`, `DaFare`, `TestiOggi`, `RigaCambioPanchina`, `PartiteRinviateView`; `Domain/FasiGiornata`)
e Formazione (`Presentation/Formazione/`, `Domain/StatoScelta`, `LetturaPedina`, `EsitoPedina`, `TestoFormazione`,
`Support/CampoFormazione`, `RigaGiocatore`) con Salva, «Modifica a mano», ballottaggi, nota del perché sotto il campo, foglio
«Perché questo numero» (`Support/PercheNumeroView`) e scheda a parte (`Mercato/SchedaGiocatoreView`).

**Passo 1a, scheda del giocatore** (ramo `iphone-scheda-unica`). Ordine della web: volto, nome, «Ruolo · club» (· Diffidato),
«In casa contro Como · sab 31 20:45» senza giornata (`formazione.partita_casa`/`partita_fuori`); fantavoto atteso «se gioca»
grande e «gioca» con la percentuale colorata sotto l'80% e lo stato a parole; la nota della fonte; «Perché è titolare» (solo
sulla consigliata, a formazione aperta: `perche_scelta`, ripiego `incerti`); «Perché questo numero» dentro; «Ultimi voti»; «Tutti i
numeri» in un `DisclosureGroup` chiuso (squadra o svincolato, quotazione, questa partita, prossime, forma, grafico, rendimento,
stagione, avanzate). A partita cominciata il fantavoto preso o lo stato. Il numero sul campo apre la scheda: via
`PercheNumeroView`. La soglia di «gioca N%» (0,8 e 0,5 sul numero arrotondato, come `giocaLetto`) sta in un tipo di `Domain/`
usato da scheda, pedina e sostituti. Dalla Formazione la scheda si apre subito con la previsione già letta, come la web.

**Passo 1b, Formazione unica** (ramo `iphone-formazione-unica`). `FormazioneView` prende la testa per fase, le decisioni e le
partite rinviate (vista spostata da `Oggi/`); i dati di `/api/oggi` restano in `OggiViewModel`, che continua a chiamare
`Aggiornamento.elabora` dopo ogni lettura fresca (widget e promemoria). Il conto si aggiorna ogni 30 secondi (`TimelineView`),
in corso si rilegge ogni 5 minuti (`seguiGiornata`). Decisioni (§6, 1): un campo facoltativo del server sulle voci di
`da_fare` di `GET /api/oggi`, per esempio `decisione` con il posto (1, 2, …), calcolato in `fanta/da_fare.py` con la regola di
oggi della web (`dfVera`, `dfDecisioni`: via `svincolato`, `scambio`, `diario`, dubbi senza alternativa, «non l'hai salvata»; prima
le urgenti con un'azione; un solo reparto scoperto), con test, `docs/API.md`, voce di novità e, se costa poco, `dafare.js` che lo
legge al posto della sua regola; se costa troppo, un passo server a parte prima della 1b. L'app mostra le prime due ancora sensate
con la formazione in pagina (come `vale` della web): «Urgente», «+0,9 punti attesi.», «Sostituisci» fa il cambio, «Usa la
consigliata», «Vedi la rosa», il primo avvio apre la guida. Modulo: `Menu` con i moduli del livello consigliato; a giornata
chiusa fisso. Pedina (§6, 2): resta il volto, sotto gli stessi numeri e testi della web (fantavoto, cognome, «gioca N%» solo sotto
l'80%, stato a parole), niente «vs NAP»; si aggiorna la differenza ammessa «Pedina sul campo». Riga dello stato: cinque stati
come la web (consigliata, cambiata, superata, non più valida, chiusa con le sue tre frasi); scelta non letta: errore con
«Riprova» e comandi spenti. Salvataggio automatico: ogni cambio degli 11 (modulo, «Sostituisci», decisione, spunta) è
`POST /api/formazione/valuta` con `salva: true` e If-Match (`scelta:<giornata>` di `Data/Versioni.swift`), «Torna alla
consigliata» è `DELETE /api/scelta`; una scrittura alla volta, risposta vecchia ignorata; 412 rilegge e lo dice
(`comune.cambiato_ricarico`), 409 `formazione_chiusa` rilegge, 400 `giocatore_bloccato` mostra il messaggio. Con la copia
salvata sul telefono i comandi che scrivono restano spenti con `formazione.copia_ferma`. «Copia per l'app della lega» usa
`TestoFormazione` nella forma di `testoFormazione` della web. La formazione di un'altra squadra resta in sola lettura. iPad: due
colonne (campo a sinistra; decisioni, panchina ed elenchi a destra), in ordine di lettura.
**Si tolgono:** la scheda Oggi e tutta `Presentation/Oggi/` tranne ciò che si sposta; migliori, «Da controllare», diffidati e
indisponibili come elenchi; Salva, «Annulla modifiche», «Modifica a mano», `SostituzioneSheet`, ballottaggi, nota del perché
sotto il campo, `PulsanteRigaStato`; `Domain/Ballottaggio` se nessuno lo usa più.
**Testi:** `Catalogo.Formazione`: stato_* (cinque stati e chiusa), torna_alla_consigliata, copia_lega, copiata_lega, non_copio,
messa, opzione_*, di_solito, oscilla, si_chiude, fra, chiusa_breve, in_corso, punti_finora, circa_fine, punti_e_attesi, punti,
come_andata, per_la_prossima, decisione_punti, usa_consigliata, quest_ordine_entra, non_schierati, indisponibili, senza_dati,
mancano_probabili_formazioni, sto_ancora_ricalcolando, scelta_non_letta, copia_ferma, la scheda e la sostituzione (sostituisci,
al_posto_di, sost_spiega, punti_rispetto, fv_atteso_breve, bloccati, perche_titolare, ultimi_voti, tutti_numeri, se_gioca,
partita_*), voce_*; `Catalogo.Oggi` (giornata_finita, con_consigliata, recupero_manca, ancora_da_giocare, tutti_giocato,
gia_iniziata_testo, cambi_panchina, cambio_*, benvenuto, rinvio_*); `Catalogo.Df`, `Lega.vediRosa`, `Tit`, `giocatore.gioca`.
**Rotte e campi:** `GET /api/oggi` (in più il campo delle decisioni), `GET /api/formazione`, `GET /api/scelta` (in più `messa`,
`messa_il`), `POST /api/formazione/valuta` (in più `messa`), `DELETE /api/scelta`, `PUT /api/regole/rinvio`, `GET /api/giocatore/<id>`.
**Widget e collegamenti:** `Sezione.da("oggi")` porta alla Formazione: valgono così `schieraxi://oggi` dei widget già sulla Home,
il tocco sugli avvisi ntfy (`bar_chart`) e le destinazioni di `da_fare`. Il codice dei widget non cambia.
**Test:** del server sul campo delle decisioni (pytest, con la regola di oggi della web), `DecisioniTests` (le prime due ancora
sensate), `StatoSceltaTests` riscritto (cinque stati, plurali, punti con `Formato.conSegno`),
`SalvataggioAutomaticoTests` (`ServerDiProva`: `salva` e `messa` nel corpo, If-Match, 412, 409, risposte fuori ordine, copia del
telefono senza comandi), `TestaFormazioneTests` (tre fasi, arrivo a giornata iniziata, senza rose), `SogliaGiocaTests`,
`TestoCopiaTests`, la lettura di `/api/oggi` che chiama ancora `Aggiornamento.elabora`, la scheda (ordine, partita senza giornata).
Via o riscritti: `Oggi*Tests`, `ModificaAManoModuliTests`, `ModificheNonSalvateTests`, `RigaStatoComeWebTests`,
`FormazioneComeLaWebTests`, `DemoSceltaComeOggiTests`, `PercheSceltaTests`; interfaccia `FumoUITests`, `FotoUITests`.
**Foto:** 1a `giocatore giocatore-fondo`; 1b, nomi nuovi, iPad compreso: `formazione formazione-fondo formazione-in-corso
formazione-finita formazione-rinvio formazione-chiusa formazione-cambiata formazione-sostituisci`; via `oggi*` e le vecchie varianti.

## 2. Giornate (il Diario)

**Web oggi (#671).** Seconda scheda. In cima «Finora il fantavoto atteso sbaglia in media di 1,4 punti a giocatore.» e «Dettagli»
(i numeri di «Quanto ci abbiamo preso»; la voce «la consigliata contro la tua» solo se una giornata ha `consigliata.origine:
"mostrata"`). Una riga per giornata, dalla più recente: nome, stagione se sono più di una, punti fatti grandi e «punti (attesi
71,7)» della formazione che conta (la tua, poi `automatica`, poi la consigliata); sotto «Hai schierato la consigliata.» o «2 cambi
tuoi: −1,5 punti rispetto alla consigliata.» solo con la consigliata mostrata, altrimenti «La tua formazione.», «Non l'avevi
cambiata…» o «Formazione non salvata…». Al tocco gli 11 in tre colonne Giocatore, Atteso (quello mostrato, `istantanea`, se no
`giocatori[].fv_atteso`), Preso (`giocatori[].fv` o «senza voto»), «Al posto di X hai messo Y.», un solo pulsante «Non è quello
che ho schierato» (non per le stagioni passate). Pagina vuota con il motivo (`motivo_vuoto`). Tablet: elenco e giornata affiancati.
**iPhone oggi.** Altro › Diario delle giornate: `Lega/DiarioView`, `ConfrontoDiarioView`, `SchedaScelteTueView`,
`QuantoCiAbbiamoPresoView`, `PrecisioneView`, `FormazioneManualeDiarioView`; `Domain/Diario`, `ConfrontoDiario`, `ScelteTue`.
**Cambia** (ramo `iphone-giornate`). Scheda «Giornate» nuova (`Presentation/Giornate/GiornateView`), seconda nella barra: a
questo punto Formazione, Giornate, Squadra, Altro, come la web fra #671 e #675. Righe con `DisclosureGroup` sul telefono, elenco
e dettaglio affiancati sull'iPad (la più recente aperta); «Dettagli» riusa `PrecisioneView`; la correzione riusa
`FormazioneManualeDiarioView` partendo dagli 11 della riga, `tipo: "manuale"` con la stagione, poi rilegge e porta VoiceOver
sulla riga (`AccessibilityFocusState`). «Com'è andata» della Formazione apre Giornate su quella giornata.
**Si tolgono:** la voce Diario di Altro (`VoceMenuLega`, `PaginaLega.diario`), `ConfrontoDiarioView`, `SchedaScelteTueView`,
`QuantoCiAbbiamoPresoView` (ripiego su `affidabilita`), «Ho schierato la consigliata», le due colonne affiancate.
**Testi:** `ios/testi/giornate.txt` nuovo con le 31 chiavi `giornate.*`; `Catalogo.Diario` (qp_*, af_titolo,
cosa_hai_schierato_titolo, correggi_spiega, salvata_manuale), `Catalogo.Avv.nDi11`, `Catalogo.Formazione.puntiEAttesi`.
**Rotte e campi:** `GET /api/diario` (in più, già nel server: `automatica`, `giocatori[]` con `fv` e `fv_atteso`, `motivo_vuoto`;
con la #642, ancora aperta: `consigliata.origine`, `precisione.confronto.senza_istantanea`; senza, niente confronto, come la web),
`GET /api/rosa`, `POST /api/diario/schierata`.
**Collegamenti:** `schieraxi://lega/diario` (voce `diario` di `da_fare`, con la giornata) e `schieraxi://giornate` aprono Giornate.
**Test:** `GiornateTests` (formazione che conta, frase della riga con e senza `origine`, atteso dall'istantanea, senza voto,
vuoto per motivo, `modificabile`), fixture inventate `Tests/Fixtures/diario-*.json` con e senza i campi della #642, correzione con
la stagione; via o riscritti `ConfrontoDiarioTests`, `DiarioEsitoTests`, `DiarioIntroComeLaWebTests`, `DemoDiarioTests`,
`ScelteTueTests`.
**Foto:** `giornate giornate-aperta giornate-dettagli` (telefono e iPad); via `lega-diario`, `lega-diario-fondo`.

## 3. Impostazioni, barra e ricerca

**Web (#675, da unire prima).** Barra Formazione, Giornate, Impostazioni più la ricerca. Impostazioni in una pagina: Avvisi
(«Avvisi su questo dispositivo», «Ore tranquille»), La mia lega (Aggiorna le rose, La mia squadra, Regole e scadenza, Le altre
squadre solo con `squadre_altrui` e più squadre; «Nuova stagione» quando serve), Il tuo account e Informazioni (righe che aprono
una pagina; le novità stanno in Informazioni), Aspetto, Gestione solo per chi gestisce il server. Regole e scadenza: in cima le due
domande del primo avvio (salvate al cambio), poi «Incolla il regolamento» → «Riconosci le regole» → «Salva queste regole», i
valori dietro «Modifica i valori».
**iPhone oggi.** Schede Squadra e Altro (`Lega/LegaView`, `VoceMenuLega`, `RigaVoceMenuLega`, `LegaPagine`, `LegaExtra`), foglio
Impostazioni dall'ingranaggio (`ImpostazioniView`, `AccountSezione`, `TestiImpostazioni`), avvisi con un interruttore per avviso
(`Gestione.swift`), `RegoleEditor`, lente e ingranaggio in ogni barra (`Mercato/RicercaGlobale`).
**Cambia** (ramo `iphone-impostazioni-barra`). `Sezione` = formazione, giornate, impostazioni; la ricerca è
`Tab(role: .search)` con `.searchable` (sull'iPad nella barra laterale); Cmd+1…3. `ImpostazioniView` diventa la radice della terza
scheda con un `NavigationStack`; `PaginaImpostazioni` prende le pagine di `PaginaLega`. Avvisi (§6, 4): un interruttore unico,
«Avvisi su questo dispositivo», come la web: accende o spegne il permesso di iOS e i promemoria locali che l'app ha già (nessuno
nuovo finché non è fatta la #676, che decide sul server quali avvisi arrivano); poi «Ore tranquille» (`PUT /api/avvisi` con il solo
`silenzio`); gli altri interruttori restano sul server come sono. Gestione = le Avanzate di oggi (server, aggiorna i dati, stato
dei dati, diagnostica del widget, certificato, SideStore, ntfy). Restano solo dell'iPhone, come differenze ammesse: «Animazioni
ridotte», la riga del widget, «C'è una versione nuova», la prova con dati di esempio. Ricerca (§6, 3): righe come la web (ruolo,
nome, club, quotazione da `/api/giocatori`); via fantavoto atteso, «gioca N%» e `PrevisioniRicerca` (lo scarico dell'elenco largo).
**Si tolgono:** schede Squadra e Altro, `LegaView`, `VoceMenuLega`, `RigaVoceMenuLega`, ingranaggio e foglio delle Impostazioni,
lente nelle barre, gli interruttori per singolo avviso e «Avviso se il consiglio cambia».
**Testi:** `Catalogo.Imp` (sez_avvisi, avvisi_qui, avvisi_qui_aiuto, ore_tranquille_aiuto, lega, regole, regole_sub,
mia_squadra_nessuna, altre_squadre, gestione, gestione_sub, informazioni_sub, aggiorna_spiega), `Catalogo.Lega` (voce_importa,
voce_importa_sub, mia_squadra, n_squadre), `Catalogo.Nav` (formazione, giornate), `Catalogo.Shell` (impostazioni, cerca),
`Catalogo.Avv` (ore_tranq, avevi_scelto_ore, quot), `Catalogo.Regole` e `Catalogo.Pav` della pagina Regole e scadenza.
**Rotte:** `GET/PUT /api/avvisi`, `GET/PUT /api/regole`, rose, `/api/stagione`, `/api/funzioni`, `/api/giocatori`: tutte di oggi.
**Collegamenti e stato salvato:** `squadra`, `mercato`, `altro`, `lega`, `scambi` aprono Impostazioni su La mia lega; `lega/rose`
Aggiorna le rose, `lega/regole` Regole e scadenza, `impostazioni/installazione` Gestione; file e immagini da Condividi aprono
Aggiorna le rose o lo stemma. `ultimaSezione` ricorda solo Formazione e Giornate (i valori vecchi si traducono). Widget invariati.
**Test:** `NavigazioneTests` (`Sezione.da` e `Collegamenti.interpreta` per ogni nome vecchio e percorso, stato salvato),
`ImpostazioniComeLaWebTests` (sezioni e righe secondo account, `squadre_altrui`, gestione), `AvvisiDispositivoTests` (interruttore
→ permesso, promemoria tolti e rimessi; ore tranquille mandano solo `silenzio`), `RegoleScadenzaTests`; via o riscritti
`MenuLegaComeLaWebTests`, `NotificheComeLaWebTests`, `SquadraAltroDalCatalogoTests`; interfaccia `FumoUITests`.
**Foto:** la barra cambia ovunque: le principali più `impostazioni impostazioni-fondo impostazioni-regole impostazioni-squadra
impostazioni-gestione ricerca`; via `squadra*`, `lega`, `lega-avvisi`.

## 4. Passi in ordine

| Passo | Ramo | Prima serve | Quando è finito |
|---|---|---|---|
| 1a | `iphone-scheda-unica` | piano unito (lo lancia chi coordina) | scheda come la web; corsa verde; foto `giocatore` guardate |
| 1b | `iphone-formazione-unica` | 1a unito; campo delle decisioni qui (`Aree:` anche `fanta`, `tests`) o in un passo server prima | barra Formazione, Squadra, Altro; Oggi non c'è più; foto sul ramo |
| 2 | `iphone-giornate` | 1b unito; #642 unita (o eccezione motivata in `tests/dati/contratto_ios_eccezioni.json`) | barra a quattro come la web di #671; Diario tolto da Altro |
| 3 | `iphone-impostazioni-barra` | 2 unito; #675 unita | barra a tre più la ricerca; Squadra e Altro tolte |

Ogni stato intermedio è un'app completa che si può installare. Se la 1b supera circa 2.500 righe cambiate, prima la logica (stato a
cinque, salvataggio automatico, con i test) senza le viste. Dopo il passo 3, un giro widget a parte sui loro testi («la tua scelta»).

## 5. Rischi
- **SideStore:** identificativo, App Group, schema, lavoro in background, nome dell'IPA e `project.yml` non cambiano: si aggiorna al posto.
- **Widget e promemoria:** oggi passano da `OggiViewModel` → `Aggiornamento.elabora`; resta anche senza la vista Oggi (test nella 1b).
- **Stato salvato:** `ultimaSezione` vecchia; chiavi `AppStorage` e suggerimenti TipKit delle viste tolte (in `OpzioniTolte.chiavi`);
  copie in `Caches/api` lette con i modelli nuovi (campi facoltativi); la copia mostrata all'apertura non deve poter scrivere.
- **Salvataggio automatico:** provare un modulo salva una scelta, e con una scelta salvata il server non manda i promemoria di
  un'ora e di un quarto d'ora (nota della #637, issue di chi coordina). Due dispositivi: If-Match e 412 già nel client, da provare.
- **Contratto con il server:** `origine` e `senza_istantanea` esistono solo con la #642 (`tests/test_contratto_ios.py` lo vede). Il
  campo delle decisioni esce sul server all'unione della 1b, prima della nuova IPA: web e iPhone vecchi lo ignorano.
- **Mac:** quattro pull request grandi; corse raggruppate, la completa e le foto solo a fine ramo.

## 6. Decisioni del proprietario (12/11, risposte sulla #677)
1. **Decisioni in cima:** le segna un campo del server, come i consigli (i client non ricalcolano). Si aggiunge nel passo 1b, con il
   suo test e la web che lo usa al posto della sua regola se costa poco; altrimenti un passo server a parte prima della 1b.
2. **Pedina:** sul campo resta il volto, con sotto gli stessi numeri e testi della web.
3. **Ricerca:** come la web (ruolo, nome, club, quotazione).
4. **Avvisi:** un interruttore unico come la web; quali avvisi arrivano lo decide il server (#676), fino ad allora niente promemoria nuovi.
