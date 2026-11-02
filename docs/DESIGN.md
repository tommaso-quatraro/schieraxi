# SchieraXI: linee guida di design (web, iOS, Android)

Revisione del 30/10/2026 su screenshot web (390 px, `fanta/web/screenshot-*.png`) e iOS (artifact `screenshot-app`, run 41047749574).
Non verificato: tablet/PC e tema chiaro della web (solo lette le regole CSS; il grigio secondario è stato misurato nel browser il 2/11/2026, vedi «Grigio secondario»), Android. Valori del CSS in `fanta/web/stile.css`, di iOS in `Sources/Support/Design/Tema.swift`.
Densità e Mercato su iOS: le sta già correggendo l'agente iOS (PR non ancora pubblicata al momento della revisione: confrontare prima di iniziare).

## Principi
1. **Un dato principale per schermata/card**, visibile a colpo d'occhio (numero grande, tabulare). Il resto è secondario.
2. **Densità**: una card deve dire almeno 3 cose utili per 100 pt di altezza. Spiegazioni lunghe stanno dietro «Come si legge», non in testa alla pagina.
3. **Niente cose che si coprono**: contenuto, barra delle schede e accessori in basso non si sovrappongono mai (si lascia lo spazio sotto).
4. **Stesso nome, stesso aspetto, stessa posizione** su web, iOS e Android. Le parole sono quelle di `MARCHIO.md`.
5. Il colore non basta: ogni esito ha anche testo o simbolo. Contrasto testo almeno 4,5:1 (3:1 per testo grande) in chiaro e scuro.
6. Tocco minimo 44 pt/px. Rispettare testo grande di sistema e «Ridurre movimento».

## Scala tipografica (solo questi 7 livelli; oggi il CSS ne ha ~25 diversi, da 8,5 a 44 px)
| Livello | Web (px) | iOS | Uso |
|---|---|---|---|
| Numero eroe | 40, peso 700, arrotondato, cifre tabulari | rounded 40 bold | punti attesi, conto alla rovescia |
| Titolo pagina | 28 / 700 | `.largeTitle`/`.title.bold` | nome schermata |
| Titolo card | 18 / 650 | `.headline` | intestazione card |
| Valore | 17 / 650 | `.headline` | nome giocatore, fantavoto atteso nelle righe |
| Corpo | 15 / 400 | `.subheadline` | testo normale |
| Secondario | 13 / 450, `--testo-2` | `.footnote` | squadra, quotazione, spiegazioni brevi |
| Etichetta | 12 / 600 maiuscolo, spaziatura .06em | `.caption.weight(.semibold)` | intestazioni di sezione, unità («punti attesi») |
Mai sotto 12 px/`.caption`. Il secondario non usa opacità extra: o `--testo-2` o niente (dal 2/11/2026 anche la web: le partite finite e rinviate, i dubbi tolti e le voci non selezionabili passano a `--testo-2` invece di sbiadire).
Numeri sempre con cifre tabulari e virgola italiana (`6,9`).

## Spaziature e forme
- Griglia a 4: 4, 8, 12, 16, 24. Margine laterale 16. Spazio tra card 12 (oggi 14 iOS, 14-18 web). Padding card 14 verticale, 16 orizzontale.
- Raggi: card 20, elementi dentro la card 14, pillole 999. Oggi la web usa 7, 10, 14, 16, 18, 20, 24: ridurre a questi tre.
- Una riga di elenco: altezza 56-64 (compatta 48), separatore sottile, nessuna card dentro una card.

## Componenti standard
- **Card**: sfondo vetro/gradino sopra lo sfondo, titolo (18) + eventuale valore a destra; max 1 card «eroe» per schermata (la prima). Le altre sono piatte.
- **Riga giocatore** (una sola, uguale ovunque): avatar 40 con anello del ruolo | nome (Valore) e sotto UNA riga secondaria «SQUADRA · quot. N · stato» | a destra fantavoto atteso (Valore, colore semantico; nella Formazione il tocco sul numero apre «Perché questo numero») e sotto «gioca 90%» (Etichetta). Max 2 righe di testo a sinistra; icone di stato come simbolo accanto al nome, non come righe in più.
- **Segmenti/tab di sezione** (Mercato: Consigliati, Osservati, Asta, Classifica, Calendario, Cerca; Lega): al massimo 4 voci in un controllo segmentato a tutta larghezza; oltre le 4, voci in una striscia scorrevole con la voce attiva sempre portata in vista e un bordo sfumato che mostra che scorre. Mai voci tagliate o testo a 12 px stretto (oggi web: 6 voci a 12,5 px; iOS: «Osservati» e «Cerca» tagliate).
- **Barra delle schede principale** (Oggi, Formazione, Mercato, Scambi, Lega): sempre sotto il contenuto in un'area riservata (non sopra). Sull'iPhone è la `TabView` di sistema; nessun accessorio nella stessa zona (vedi incoerenze). Da 900 px su web: colonna a sinistra.
- **Intestazione pagina**: titolo pagina (28) + al massimo 2 azioni a destra (cerca, aggiorna/condividi); sottotitolo di stato (giornata, ultimo aggiornamento) in Secondario. Uguale su tutte le schermate.
- **Intestazione di sezione**: Etichetta (12 maiuscolo) con eventuale conteggio a destra; sopra 16, sotto 8.
- **Chip di scelta** (modulo, stile): una sola riga scorrevole o un menu; con valore piccolo accanto («4-3-3 · 71,1»). Quello attivo: lime (`--capitano`) con testo scuro, uguale su web e iOS.
- **Stato vuoto**: simbolo 32, una frase che dice cosa manca, un solo pulsante che dice cosa fare («Importa le rose»). Mai solo grigio.
- **Errore**: riga/card rossa (`--rosso`) con simbolo, cosa è successo, come rimediare, pulsante «Riprova». Voce di `MARCHIO.md`.
- **Caricamento**: il marchio animato solo a schermo intero; dentro una card, scheletri (righe grigie) della forma finale; non lasciare solo il testo «Carico…».
- **Pulsanti**: 1 primario per schermata (pieno: verde `--verde` nel tema scuro, oliva `#526600` con testo bianco nel tema chiaro, vedi `MARCHIO.md`, «Contrasto dei colori delle azioni»), secondari a contorno, distruttivi in rosso. Mai 3 pulsanti a contorno in fila (oggi Formazione web: Modifica, Copia, Condividi).

## Colori semantici
| Significato | Scuro | Chiaro | Note |
|---|---|---|---|
| Positivo (bonus, guadagno, sicuro) | `#3DDC97` | `#0A7D4C` | web `--verde`; iOS oggi `Color.green` di sistema: allineare |
| Negativo (malus, rischio) | `#FF6B5E` | `#B3261E` | `--rosso` |
| Attenzione (dubbio, diffidato) | `#FFB04A` | `#9C5400` | `--arancio` |
| Neutro/secondario | `#BCCDC2` | `#46564D` | `--testo-2` (web) e `Color.testoSecondario` (iOS): lo STESSO valore, l'unico grigio dei testi secondari (vedi «Grigio secondario» sotto) |
| Capitano / selezione | `#D4F34A` | `#86A800` (solo fondo, mai testo) | `--capitano`; sopra il lime testo scuro (`--capitano-testo`) |
| Azione (pulsanti, testo di azione) | `#3DDC97` (`--azione`) | `#526600` (testo bianco sopra) | Dal 31/10/2026: in chiaro mai il lime per il testo; `MARCHIO.md`, «Contrasto dei colori delle azioni» |
| Informazione | `#62A9FF` | `#1A5BB5` | `--blu` |
Il giallo (`--giallo`) resta solo per la stella «consigliato». Un valore positivo ha il segno `+`, uno negativo `−`.

## Grigio secondario (2/11/2026)
Un solo grigio per sottotitoli, didascalie, orari, intestazioni di elenco e testi «spenti»: web `--testo-2` in `fanta/web/stile.css`, iOS `Tema.secondarioChiaro`/`secondarioScuro`. Stessi due valori, `#46564D` in chiaro e `#BCCDC2` in scuro; un test (`test_design_web.py`) li tiene uguali. Regole:
- Nel CSS e nel JS nessun altro grigio per il testo: niente `opacity` sul testo (sbiadire un grigio già grigio lo portava sotto 3:1: le partite finite erano a 2,0:1 in chiaro), niente grigi scritti a mano. Una riga «finita» o «rinviata» cambia il colore dei nomi in `--testo-2`; il risultato resta in `--testo`. Le parti disattivate di un controllo (`:disabled`) possono avere opacità, il testo no.
- Il grigio deve valere 4,5:1 (3:1 sopra 24 px o 18,66 px in grassetto) su bianco, carte e fondo piatto; sul fondo sfumato più carico, senza carta sopra, in chiaro arriva a 4,3:1 (è il punto con le due macchie sovrapposte). La testata (sticky) ha un vetro più opaco (80%) perché il campo verde le passa sotto.

Contrasto di `--testo-2` sui fondi principali (calcolo con `prove/contrasto_web/fondi.py`; i due «punti più carichi» del fondo sfumato sono i pixel più scuri/più chiari misurati sul fondo vero, 20 immagini, 2 larghezze, 5 momenti dell'animazione):

| Fondo chiaro | prima `#587064` | dopo `#46564D` |
|---|---|---|
| bianco | 5,36 | 7,78 |
| fondo piatto (#eaf3ee) | 4,74 | 6,87 |
| carta su fondo piatto | 5,18 | 7,52 |
| fondo sfumato, punto più carico | 2,95 | 4,29 |
| carta su fondo sfumato più carico | 4,59 | 6,66 |

| Fondo scuro | prima `#B3C6BA` | dopo `#BCCDC2` |
|---|---|---|
| fondo piatto (#07100b) | 10,76 | 11,63 |
| carta su fondo piatto | 7,93 | 8,57 |
| fondo sfumato, punto più carico | 3,95 | 4,27 |
| carta su fondo sfumato più carico | 5,36 | 5,79 |
| carta con riflesso del dito (+22% bianco) | 2,87 | 3,10 |

Contrasto vero sul telefono e sul PC (`prove/contrasto_web/scatta.mjs` + `analizza.py`: Chrome senza finestra apre Oggi, Formazione, Rosa, Diario, Impostazioni a 390 e 1440 px in chiaro e scuro, scorre le pagine, toglie le lettere e confronta il colore di ogni testo con il fondo vero sotto le sue lettere, al 10% peggiore; un testo contato una volta sola). Testi secondari (colore `--testo-2` o sbiaditi dall'opacità):

| Tema e larghezza | testi | peggiore prima | peggiore dopo | 10% più bassi prima | dopo | sotto 4,5:1 prima | dopo |
|---|---|---|---|---|---|---|---|
| chiaro 390 px | 390 | 1,22 | 1,77 (*) | 3,64 | 6,05 | 92 | 1 |
| chiaro 1440 px | 424 | 2,11 | 4,47 | 3,69 | 6,40 | 92 | 1 |
| scuro 390 px | 390 | 2,97 | 3,93 | 4,62 | 6,26 | 36 | 3 |
| scuro 1440 px | 424 | 3,14 | 3,89 | 5,10 | 7,07 | 29 | 4 |

(*) un solo testo: una lettera «A» del Diario mentre scorre sotto il bordo alto del foglio; ferma vale 7,5:1.

Rimasti sotto 4,5:1: in chiaro nulla di rilevante; in scuro il simbolo «○» (3,9:1) e le righe «Giornata 10 · …» e «Modulo» sulla scheda con l'alone verde (4,1 a 4,3:1). Per portarle oltre 4,5:1 servirebbe un grigio scuro più chiaro di `#BCCDC2`, ma allora web e iOS non sarebbero più uguali: da decidere insieme.

## Gerarchia e densità: regole
- In ogni card il numero chiave è il più grande e a destra o sotto il titolo; l'unità sta sotto in Etichetta.
- Non ripetere lo stesso dato in due card contigue (oggi «3-4-3 · 73,7» compare in Oggi e due volte in Formazione).
- Testi di spiegazione: massimo 2 righe visibili; il resto in «Come funziona» comprimibile.
- Elenchi lunghi: righe, non card. Una card per elemento solo se ha azioni proprie (proposta di scambio).
- Densità «compatta» (Aspetto) = righe da 48 e un livello di Secondario in meno; è l'impostazione consigliata di default per elenchi di più di 10 voci.

## Tablet e PC
- iPad/web ≥ 900 px: barra a colonna a sinistra, contenuto max 980; ≥ 1100: 2 colonne, ≥ 1700: 3 (già nel CSS). Il campo di formazione ha larghezza massima 620 e sta accanto alle card di controllo, non sopra.
- iPad iOS: stesso schema (colonna di controllo a sinistra, campo a destra); oggi è un telefono allargato. Elenchi di righe giocatore a 2 colonne in orizzontale.
- Numeri e testi non crescono oltre la scala sopra (la web a 2600 px porta il corpo a 18).

# Incoerenze trovate (ordinate per severità)

Gravità: A = blocca/si legge male, M = fastidio, B = rifinitura. Responsabile: W = web, I = iOS, A = Android.

| # | Dove | Problema | Grav. | Correzione |
|---|---|---|---|---|
| 1 | I tutte | Accessorio «Giornata 11 6:59:24» sopra la barra delle schede: due barre impilate che coprono ~15% dello schermo e il contenuto passa sotto | A | Togliere l'accessorio (il conto alla rovescia sta già in Oggi) o mostrarlo solo in Oggi; riservare lo spazio in basso |
| 2 | W tutte | Barra schede fissa e galleggiante copre l'ultima riga/campo (si vede in screenshot) pur con padding-bottom 106 px; il vetro lascia leggere il testo sotto | A | Barra con fondo opaco al 90% e sfumatura; verificare padding con tastiera e safe area |
| 3 | W Mercato | 6 segmenti in una riga a 12,5 px, stretti | A | Striscia scorrevole o 4 + «Altro» (vedi componente segmenti) |
| 4 | I Mercato | Striscia di pillole tagliata a sinistra («Osservati») e destra; sotto un secondo controllo segmentato (Tutti/P/D/C/A) e un interruttore: tre livelli di filtri prima del contenuto | A | Già in carico all'agente iOS: una striscia, filtro ruolo in una riga, interruttore dentro un menu filtri |
| 5 | W Formazione | La prima card (modulo + 7 chip + 5 chip stile + 3 pulsanti + nota) occupa oltre un intero schermo prima del campo | A | Dato principale (modulo + punti attesi) in una riga; moduli e stile in due righe scorrevoli o menu; pulsanti in un menu «Azioni»; campo visibile senza scorrere |
| 6 | W Mercato > Consigliati | Card di proposta alta ~140 px per 3 dati; «Esce/Entra» in Etichetta, nome, punti guadagnati centrati e piccoli | A | Riga da 72: Esce → Entra con avatar e voto, a destra «+5,0» grande; dettaglio +5 giornate in Secondario. Già in carico a iOS per la card proposta: replicare lo stesso schema |
| 7 | I Formazione | 4 card prima del campo (Stile, Giornata 11, «Modifica a mano», Campo): la card del solo pulsante spreca spazio; il modulo si ripete | M | Fondere Stile e Giornata in una card; pulsante «Modifica a mano» nella barra azioni in alto |
| 8 | I Oggi | Card eroe con timer enorme + maglia, poi 3 card; «Novità nell'app» spezzata su 2 righe | M | Timer a 40 px, riga novità a 1 riga con chiusura; «Da controllare» più in alto (è l'azione utile) |
| 9 | I Mercato Classifica | Riga giocatore a 4 righe di testo (nome, partita, titolare %, quot. svincolato); «gioca 90%» ripete «Titolare 90%» | M | Dato ripetuto via; 2 righe: nome; «GENOA vs COMO · quot. 19 · svincolato»; secondario con contrasto più alto (oggi grigio spento) |
| 10 | W/I | Colore positivo: web `#3DDC97`/`#0A7D4C`, iOS `Color.green` di sistema (diverso, in chiaro poco contrasto) | M | Colori semantici in `Tema.swift` uguali alla tabella |
| 11 | W/I | Chip modulo: web verde pieno, iOS lime pieno; stile: web chip, iOS menu | M | Lime per attivo ovunque (decisione: sì); stile = menu su entrambi |
| 12 | W | Scala tipografica con 25 dimensioni (8,5-44 px), 7 raggi, 10+ paddings | M | Variabili CSS `--t-*`, `--r-*`, `--s-*` e sostituzione graduale |
| 13 | W | Testi secondari (`--testo-2` su vetro, 12-13 px; sotto 11 px) poco evidenti | M | Fatto il 2/11/2026: `--testo-2` unico `#BCCDC2` / `#46564D` come iOS, niente opacità sul testo. Resta: secondario min 13 px, minimo 12 px |
| 14 | I | Testi secondari iOS `.secondary` sul fondo con sfumatura verde: contrasto basso | M | Usare `Color.secondary` solo su fondo piatto; su gradiente `.primary.opacity(.75)` |
| 15 | W | Intestazione: titolo = nome squadra, sottotitolo con giornata; iOS: titolo = nome schermata (grande) | M | Scegliere iOS (titolo schermata) anche su web, nome squadra nella riga di stato |
| 16 | I/W | Pulsante cerca/aggiorna: web 2 icone in cerchio, iOS 1 o 2 in una capsula | B | Capsula con 2 azioni al massimo, stesso ordine |
| 17 | W vs I | Icona/nome sezioni uguali, ma «Lega» web ha il pallino rosso per novità, iOS no | B | Stesso badge su iOS |
| 18 | I iPad | Layout telefonico allargato | M | Colonne come da sezione Tablet |
| 19 | W/I | Caricamento: web spinner + testo, iOS in parte marchio animato | B | Scheletri nelle card, marchio solo schermo intero |
| 20 | A | Android non controllato | ? | Da fare dopo i passi W e I: stessa tabella, Material 3 |

# Piano a passi piccoli (ognuno = una PR, «fatto quando» in corsivo)

**Web** (versione + `sw.js` da alzare)
1. Variabili CSS di scala (`--t-*`, `--r-*`, `--s-*`), nessun cambio visivo. *Fatto quando: gli 11 px e sotto spariscono, i test passano e 390 px identico.*
2. Barra schede: area riservata e fondo più leggibile (#2). *Il campo e l'ultima card si leggono interi, chiaro e scuro.*
3. Segmenti scorrevoli di Mercato/Lega (#3). *6 voci leggibili a 390 px.*
4. Formazione: card di controllo compatta (#5). *Campo visibile al primo schermo a 390 px; stessi comandi.*
5. Proposte Mercato in riga da 72 (#6, dopo la PR iOS per lo stesso schema). *Almeno 5 proposte in uno schermo.*
6. Riga giocatore unica (Mercato, Rosa, Osservati) e secondario più leggibile (#9, #13). *Una sola funzione che disegna la riga.*
7. Intestazione uniforme e tablet/iPad (#15, #16, #18). *Prova a 820 e 1280 px, chiaro e scuro.*

**iOS** (dopo la PR in corso su Mercato/densità; nessuna duplicazione)
1. Via l'accessorio del conto alla rovescia sopra la barra (#1). *Una sola barra in basso in tutti gli screenshot.*
2. Colori semantici in `Tema.swift` (#10, #14) e scala dei caratteri. *Nessun `.font` fuori dalla scala.*
3. Formazione: card unica di controllo, «Modifica a mano» fra le azioni (#7, #11). *Campo entro il primo schermo.*
4. Oggi più compatta (#8) e badge «Lega» (#17).
5. iPad: due colonne (#18). *Screenshot iPad orizzontale con colonna di controllo.*

**Android**
1. Verificare lo stato attuale con la stessa tabella (#20), poi applicare scala, colori e componenti di questo documento.

**Decisioni per l'utente**: (a) togliere del tutto il conto alla rovescia dalla barra in basso su iOS? (b) lime come colore di «selezione» su tutta la web (oggi verde)? (c) densità compatta di default?
