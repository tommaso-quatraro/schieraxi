# SchieraXI: architettura delle informazioni e flussi (web, iOS, Android)

Studio del 30/10/2026 su ~60 schermate iOS dell'utente (versione app 1.0.67, server 1.81), `LegaView.swift`, `vistaLega` in `fanta/web/app.js`,
`onboarding.js` e Android (`android/`, oggi solo Oggi e navigazione). Completa `docs/DESIGN.md` (aspetto) con il «dove sta cosa».
Etichette: [visto] = nelle schermate o nel codice; [proposta] = da decidere/fare.

## 1. Mappa attuale e problemi

Barra: **Oggi · Formazione · Mercato · Scambi · Lega** (uguale su web e iOS; Android solo Oggi). Lente di ricerca in ogni testata [visto].

| Scheda | Contenuto oggi [visto] |
|---|---|
| Oggi | timer + maglia, La tua formazione, Da controllare, Indisponibili in rosa, Diffidati, I tuoi migliori, Partite del turno |
| Formazione | Stile + moduli, Giornata (modulo, punti), Modifica a mano, Campo, Titolari, Panchina, Fuori dalla formazione |
| Mercato | 6 schede: Consigliati, Osservati, Asta (agosto/riparazione), Classifica (filtri ruolo + «solo svincolati»), Calendario, Cerca |
| Scambi | Trova per me (con quale squadra + «1 contro 1 … Fino a 4», Cerca scambi), Costruisci uno scambio, Valuta un'offerta, Chi accetta più volentieri |
| Lega (iOS) | marchio, **Il tuo account** (7 voci), Server (indirizzo, prova, squadra, stagione, versione, aggiorna dati), **Lega** (Aggiorna rose, Squadre e rose, Movimenti, Diario, Asta e riparazione, Regole, Crediti, Nuova stagione), **App e dati** (Aspetto, Icona, Backup, Avvisi del server, Stato dei dati, Novità), Promemoria, Widget (+ diagnostica), Certificato, Rinnovo SideStore, Notifiche ntfy, Versione |
| Lega (web) | account, Aggiorna rose (+ guida Comandi con indirizzi `/api/...`), squadre, incolla testo, movimenti, Diario, Stato dati, Crediti, Aspetto, Comandi di Apple, Icona, Avvisi, Backup, Regole, Novità, fonti, privacy |

Problemi principali:
1. **Lega è un cassetto di tutto**: 30+ voci su ~8 schermi di scorrimento; la lega vera (rose, regole) sta in mezzo ad account, server, certificato, widget, ntfy.
2. **Avvisi in quattro posti**: «Avvisi del server», «Promemoria», «Notifiche ntfy», widget; e le ore tranquille stanno solo negli avvisi del server.
3. **Doppioni**: Asta in Mercato e in Lega; Crediti delle squadre ripete i crediti già in Squadre; «Quanto ci azzecca/è affidabile il modello» in Stato dati e Diario; Classifica e Cerca sono lo stesso elenco di giocatori; «Ho ricevuto un'offerta» due volte in Scambi; Indisponibili in Oggi e «Fuori dalla formazione» in Formazione.
4. **Mercato con 6 schede** che non entrano (tagliate a destra e sinistra) e filtri su tre livelli.
5. **Scambi**: tre attività diverse impilate; l'errore di limite («20 ricerche… riprova tra 415 minuti… controlla la rete») mescola cause.
6. **Gergo visibile**: «token», «gruppo no · file no · indirizzo no», «ALTAppGroups», `POST /api/...`, 202/403 nelle Novità, «Dati-extra», «xG/xA», «oscilla di ±3»; indirizzo completo del server sempre in chiaro.
7. **Azioni senza ordine**: in Account «Elimina l'account» è in mezzo alle voci normali; «Aggiorna i dati» (admin) compare in Server e in Stato dati.
8. **Primo avvio diverso**: web ha 8 passi guidati; iOS chiede solo l'indirizzo e poi «Manca la tua squadra»; widget e stemma si scoprono per caso.

## 2. Nuova struttura [proposta]

**Le 5 schede restano** (stessi nomi, stesse icone: i collegamenti `schieraxi://oggi|formazione|mercato|scambi|lega` non cambiano).
In più **Impostazioni**: pulsante tondo con l'ingranaggio nella testata di ogni scheda, accanto alla lente (massimo 2 azioni come da DESIGN.md;
in Formazione «Condividi» va nel menu «Altro», già così sul web). Su iPad/PC è una voce in fondo alla barra laterale. Si apre come foglio (iOS/Android) o pagina (web).

### Oggi (cruscotto)
1. Testata eroe: timer alla prima partita + «4-4-2 · 71,3 punti attesi» + stato della formazione (consigliata / tua scelta salvata) + UN pulsante «Apri la formazione».
2. **Da fare** (nuova card, solo se c'è qualcosa, max 4 righe, ognuna con un'azione): dubbi in formazione → «Sostituisci»; svincolato che migliora di +1,5 o più → «Vedi»; rose vecchie dopo una giornata con movimenti → «Aggiorna le rose»; certificato in scadenza (iOS) → «Rinnova»; nuova stagione → «Inizia».
3. Da controllare (dubbi + indisponibili + diffidati in un'unica card, raggruppati), I tuoi migliori, Partite del turno (chiusa di default).

### Formazione
Invariata nei contenuti (lavoro già in DESIGN.md #5/#7): controlli in una card, campo, titolari, panchina, fuori. Il tocco su un titolare = sostituisci.

### Mercato: da 6 a 4 schede
| Nuova | Contiene | Da |
|---|---|---|
| Consigliati | svincolati che migliorano la squadra; in finestra di riparazione anche «Ti conviene» | Consigliati + parte di Asta |
| Giocatori | un solo elenco con campo di ricerca in alto, filtro ruolo e «solo svincolati» in un menu Filtri | Classifica + Cerca |
| Osservati | come oggi | Osservati |
| Calendario | difficoltà prossime partite | Calendario |
Asta e riparazione esce da Mercato e va in Lega (è un evento di lega, due volte l'anno); in Consigliati resta un avviso «Riparazione aperta → piano».

### Scambi: un punto, tre modi
Controllo segmentato in alto: **Trova per me** (proposte; avversario «Tutte/…» e «fino a N» in una riga) · **Costruisci** (scegli chi dai e chi ricevi) ·
**Valuta un'offerta** (incolla il messaggio). Stesso risultato per tutti e tre: Dai/Ricevi, punti attesi prima e dopo, conguaglio crediti, giudizio, «Chi accetta più volentieri».
Il collegamento `schieraxi://scambi` apre «Trova per me». Il limite di ricerche si mostra come contatore («ne restano 3 oggi»), non come errore di rete.

### Lega (solo la lega)
- **Aggiorna le rose** in cima, con «ultimo aggiornamento: 28 ott».
- **La mia squadra**: nome, stemma, maglia (ora dentro la rosa, poco visibili), formazione consigliata per loro.
- **Squadre e rose** (crediti già nella riga di ogni squadra: la pagina Crediti diventa la modifica dei crediti dentro ogni squadra).
- **Movimenti e storico**, **Diario delle giornate** (con «Quanto ci azzecca SchieraXI» in parole semplici in cima).
- **Regole della lega**, **Asta e riparazione**, **Nuova stagione** (in cima come avviso solo quando serve, altrimenti in fondo).

### Impostazioni (gruppi, in quest'ordine)
| Gruppo | Contenuto | Note |
|---|---|---|
| Account e sicurezza | nome utente, ruolo, email, cambia password, codice di recupero, esci, esci da tutti i dispositivi; in fondo, separato e rosso, «Elimina l'account» | solo con account |
| Collegamento | stato («Collegato al server · dati delle 17:00»), indirizzo nascosto dietro «Modifica», Prova la connessione | web: non serve |
| Aspetto | tema, colore, densità, animazioni ridotte, all'apertura mostra, **icona dell'app** | Icona unita qui |
| Avvisi e promemoria | quali avvisi (cambi, 1 h prima, 15 min prima, riepilogo), promemoria sul telefono, ore tranquille, aggiornamento in background | una sola pagina |
| Widget | «Collega i widget» (un pulsante che copia il codice, spiegazione in 2 righe), quali widget esistono | iOS (Android quando ci sarà) |
| Dati e backup | scarica una copia, ripristina da file | |
| Installazione e rinnovo | scadenza del certificato, guida al rinnovo automatico con SideStore, «Apri Comandi» | **solo iOS** |
| Informazioni | Novità (testi per l'utente), versione dell'app e del server, fonti dei dati, privacy e termini | |
| Avanzate (chiuso) | Stato dei dati, Aggiorna i dati ora (solo admin), diagnostica del widget, notifiche ntfy e collegamenti `schieraxi://`, guida Comandi «Importa in SchieraXI» (web) | per chi sa cosa cerca |

Da togliere: marchio grande in cima a Lega (il marchio sta nel lancio e in Informazioni); riga «gruppo no · file no…» sotto il widget (va in Avanzate).

## 3. Flussi chiave [proposta]

**Primo avvio (uguale ovunque, avanzamento salvato sul server con `/api/onboarding`, come il web oggi)**
1. Collegamento (solo app native: indirizzo + prova). 2. Accesso. 3. Regole: incolla il regolamento di Leghe o tieni quelle standard.
4. Rose: file / Condividi / incolla. 5. Qual è la tua squadra. 6. Stemma e maglia (facoltativo, «Salta»). 7. Avvisi e promemoria.
8. Widget (iOS, facoltativo) e installazione (iOS: rinnovo SideStore). 9. Fine: apre Oggi con la formazione pronta.
Ogni passo saltato finisce in «Da fare» su Oggi; nessun passo blocca l'uso dell'app tranne 1-2 e 4-5.

**Aggiornare le rose**: da Lega (in cima), da «Da fare» su Oggi, o da Condividi su un file Excel (iOS/Android) → una pagina sola: «Scegli il file» (primario),
«Incolla il testo» (secondario, chiuso), opzione «Togli le squadre che non sono nel file» in «Opzioni». Dopo: riepilogo dei cambi → «Vedi la formazione aggiornata».

**«Cosa faccio oggi?»**: apro l'app → Oggi dice in una riga se la formazione è pronta e cosa resta da fare; ogni riga ha il suo pulsante. Niente da fare = «Tutto a posto, Mister».

**Cambiare la formazione**: Oggi → «Apri la formazione» → tocco un titolare → scelta fra le alternative con i punti → «Salva come mia scelta» (pulsante fisso in fondo finché ci sono modifiche non salvate) o «Torna alla consigliata».

**Scambi**: vedi sopra; dalla scheda giocatore «Proponi uno scambio per lui» apre «Costruisci» già compilato.

**Mercato**: Consigliati come prima schermata; da ogni giocatore Osserva / Confronta / Proponi scambio (se di un'altra squadra).

**Ricerca globale** (lente ovunque): risultati in gruppi: Giocatori, Squadre della lega, Pagine e impostazioni (scrivo «backup», «regole», «widget» e ci vado).
Su iOS restano Spotlight e i comandi Siri.

## 4. Linguaggio (testi per l'utente)

| Oggi | Diventa |
|---|---|
| «voto atteso», «FV atteso», «fantamedia attesa» (per il giocatore) | giocatore: **Fantavoto atteso** (se gioca, con «gioca N%»; in inglese «Expected fantasy score»); squadra: **punti attesi**. Il voto senza bonus è il **voto in pagella atteso** (solo nelle spiegazioni). Vedi `FANTAVOTO-ATTESO-IDENTITA.md` |
| «Titolare 90%» e «gioca 92%» nella stessa riga | una sola: **gioca 92%** (titolarità delle probabili nella scheda) |
| oscilla di ±3 | di solito tra 68 e 74 |
| gol rispetto agli xG, assist rispetto agli xA | gol rispetto alle occasioni avute |
| token, codice del widget, sessione | **codice di collegamento** del widget |
| Avvisi del server / Promemoria / ntfy | **Avvisi e promemoria** (ntfy solo in Avanzate) |
| Dati-extra, Crediti-giocatore 2026-10 | Statistiche in più, Quotazioni |
| Novità con `POST /api/...`, 202, 403 | solo cosa cambia per me; il dettaglio tecnico resta nel changelog di GitHub |
| errore sui fantavoti 1,60 / 1,82 | «SchieraXI sbaglia di 1,6 punti a giocatore, la media fantasy di 1,8» |
| euro (icona €) per i crediti | **crediti** con il simbolo dei crediti, mai € |
Parole fisse: **credito/crediti**, **svincolato**, **rosa**, **squadra** (fanta) vs **club** (Serie A), **giornata**, **modulo**, **stile**, **Mister** solo come saluto (`MARCHIO.md`).

## 5. Tablet, iPad e PC
- Barra laterale con le stesse 5 voci + Impostazioni in fondo (web ≥ 900 px, iPad, Android `NavigationSuiteScaffold` già presente).
- Due colonne dove c'è un elenco con dettaglio: Lega e Impostazioni (elenco a sinistra, pagina a destra), Mercato (elenco giocatori + scheda),
  Scambi (modo e scelte a sinistra, risultato a destra), Formazione (controlli a sinistra, campo a destra), Oggi (card su 2 colonne).

## 6. Piano a passi piccoli (ordine di valore; W = web, I = iOS, A = Android)

Regola per tutti i passi: i collegamenti `schieraxi://oggi|formazione|mercato|scambi|lega|giocatore/<id>`, i `?vista=` del web e i `widgetURL`
continuano a funzionare. Nuovi collegamenti solo in aggiunta: `schieraxi://impostazioni[/<gruppo>]`, `schieraxi://lega/rose`.
Le preferenze salvate con nomi vecchi (sezione di Mercato «Classifica», «Cerca», «Asta») si traducono nei nuovi nomi alla lettura.

1. **I+W Impostazioni**: nuova pagina con i gruppi della tabella, solo spostando le voci esistenti (nessuna funzione nuova); ingranaggio in testata; Lega perde account, server, aspetto, icona, avvisi, promemoria, widget, certificato, rinnovo, ntfy, backup, stato dati, novità.
   *Fatto quando: Lega a 390 px sta in 2 schermi; ogni voce vecchia si trova in Impostazioni o Lega (lista di controllo nella PR); `schieraxi://lega` apre Lega; test UI demo verdi.*
2. **I+W Avvisi e promemoria in una pagina** (ore tranquille comprese, ntfy in Avanzate). *Fatto quando: una sola voce «Avvisi» in tutta l'app; le ore tranquille si vedono vicino ai promemoria.*
3. **W+I Testi** (tabella §4) e Novità senza gergo (server: campo voci per l'utente separato da quelle tecniche, retrocompatibile). *Fatto quando: grep di «token», «xG», «/api/», «±» nelle stringhe visibili = 0 fuori da Avanzate.*
4. **I+W Mercato a 4 schede** (Giocatori = Classifica + Cerca; Asta in Lega). *Fatto quando: 4 schede intere a 390 px senza tagli; `schieraxi://mercato` invariato.*
5. **I+W Oggi cruscotto** con «Da fare» (server: campo `da_fare` in `/api/oggi`, facoltativo, prima lato server). *Fatto quando: con rose vecchie e un dubbio, Oggi mostra 2 righe con pulsante che porta al punto giusto.*
6. **I+W Scambi a tre modi**. *Fatto quando: le tre attività stanno in un controllo segmentato; il limite si vede come contatore.*
7. **I+W Lega riordinata** (La mia squadra con stemma e maglia; Crediti dentro Squadre; affidabilità in Diario). *Fatto quando: nessun doppione della tabella §1.3.*
8. **I Primo avvio a passi** riusando `/api/onboarding` del web. *Fatto quando: da app nuova in demo si arriva a Oggi passando per i 9 passi, saltando quelli facoltativi.*
9. **W+I Ricerca globale con pagine e impostazioni**. *Fatto quando: «backup» trova la pagina Backup.*
10. **I+W iPad/PC due colonne** (§5). *Fatto quando: screenshot iPad orizzontale e web 1280 px con elenco + dettaglio.*
11. **A**: costruire Formazione, Mercato, Scambi, Lega e Impostazioni direttamente con questa struttura. *Fatto quando: stesse voci e stessi nomi di iOS (lista di controllo).*
12. **Docs**: aggiornare `MAPPA.md` (web e iOS) e `DESIGN.md` dopo i passi 1, 4 e 6.

## 7. Decisioni dell'utente
- (a) Impostazioni dall'**ingranaggio in testata** (raccomandato) o dallo **stemma della mia squadra** al suo posto?
- (b) Asta e riparazione solo in Lega (raccomandato) o anche come scheda in Mercato durante la finestra?
- (c) «Quanto ci azzecca SchieraXI» visibile a tutti nel Diario (raccomandato) o solo in Avanzate?
- (d) Indirizzo del server nascosto di default (raccomandato: le schermate condivise non lo mostrano più)?
