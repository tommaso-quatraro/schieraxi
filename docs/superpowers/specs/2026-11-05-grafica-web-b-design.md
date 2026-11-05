# Grafica della web app: direzione B «Distinta» (spec)

Data: 5/11/2026. Issue #354, sotto il macro obiettivo #167 («app semplice e uguale»). Stato: proposta, da mostrare al
proprietario prima del piano di lavoro (`docs/superpowers/plans/2026-11-05-grafica-web-b.md`).
Riguarda solo la web app (`fanta/web/`). L'app iPhone resta nativa. Il sito di presentazione è fuori ambito (§19).

## 1. Perché
Il proprietario, il 5/11: la web oggi «si vede troppo che è fatta con l'AI, la classica AI slop, è un po' troppo strana»;
deve essere «una web app all'avanguardia». Tra le due proposte ha scelto la B («Distinta») perché «sembra più comoda da usare
per un PC, dove idealmente si usa la web app», e ha aggiunto: «la cosa più importante è che sia usabile in maniera comoda,
quindi bisogna valutare tutto ciò che è più comodo da usare da un PC… se vuoi migliorarla ulteriormente sei libero di farlo».

Diagnosi della web di oggi (foto a 390 e 1440 px, chiaro e scuro, e lettura del codice):
1. **Tutto è una carta.** Oggi a 390 px ha 8 riquadri bordati con raggio 20 uno sotto l'altro; a 1440 px tre colonne di carte
   di altezze diverse (`.carta` in `fanta/web/stile.css`, circa riga 137).
2. **Manca il titolo della schermata.** In testa c'è il nome della squadra con due righe grigie e tre cerchi colorati; dentro
   Oggi il nome «SchieraXI» con lo slogan.
3. **Troppi segni per riga.** Una riga dei titolari ha 7-8 segni (lettera del ruolo in un quadrato colorato, anello colorato
   attorno al volto, numero sul volto, pallino della difficoltà, pillola di stato, numero sottolineato a puntini, cerchio «⇄»,
   barra della probabilità) ed è alta 100-150 px.
4. **Pulsanti a contorno in fila.** In «Da fare» tre «Sostituisci» identici, uno per riga.
5. **Tutto tinto di verde.** Fondo menta `#eaf3ee`, cerchi oliva in testata, lime, arancio e colori dei club insieme: nessun
   neutro su cui riposare l'occhio.
6. **Formazione: un muro prima del campo.** Moduli e stili in pillole su più righe, un paragrafo di 4 righe, la legenda che
   copre il campo.
7. **Barra imitata male sul PC.** A 1440 px la barra delle schede è una pillola verticale sospesa a metà altezza
   (`.schede` sopra i 900 px, circa riga 796), con 120 px di margine a sinistra persi su ogni pagina.
8. **Testi che spiegano tutto** in testa ai blocchi.

## 2. Direzione B in una frase
La web diventa una **distinta di gara**: niente carte, solo righe, fili e colonne di numeri; i numeri sono i protagonisti,
in un carattere semi-stretto con le cifre in colonna; una sola tinta per le azioni; sul PC le schede stanno in alto e il
dettaglio si apre accanto alla pagina, al telefono la barra sta in basso.

## 3. Obiettivi, non obiettivi, cose da evitare
**Obiettivi**
- Comodità sul PC prima di tutto (§5): meno clic, meno movimenti del mouse, tastiera, più cose confrontabili in vista.
- Aspetto sobrio e riconoscibile, che non sembri generato (`docs/STILE-SENZA-AI.md` resta valido).
- Al telefono (390 px) resta semplice: una colonna, barra in basso, niente scorrimenti di lato.
- Accessibilità WCAG 2.2 AA: axe senza errori a 390, 768, 1024 e 1440 px, in chiaro e in scuro.

**Non obiettivi**
- Nessuna funzione nuova del prodotto (principio «poche funzioni»). Si cambia come si vede e come si usa ciò che c'è.
- Nessun cambio di testi, numeri, rotte, API, regole di calcolo.
- Nessun cambio d'aspetto dell'app iPhone (resta nativa, §13).

**Cose da evitare (fallimento anche se «funziona»)**
- Il «giornale» generico: fili sottili ovunque, zero raggi, colonne fitte e anonime. La B prende dal calcio la sua struttura
  (la distinta, il tabellone, il campo), non dal quotidiano.
- Una schermata che sul telefono diventa una tabella da scorrere di lato.
- Un passaggio a metà visibile a lungo in produzione: ogni pull request unita lascia tutte le schermate coerenti (§15).

## 4. Principi
1. **La distinta.** Ogni schermata è un titolo, una riga di stato e sezioni. Una sezione è un titolo con un filo spesso sotto
   (2 px, colore del testo) e righe separate da un filo sottile. Niente scatole: lo spazio e i fili fanno i gruppi.
2. **I numeri comandano.** Fantavoto atteso, punti, conto alla rovescia, «gioca N%» e crediti stanno in colonne allineate a
   destra, con cifre tabellari, nello stesso punto in ogni riga e in ogni sezione della stessa schermata.
3. **Una cosa audace per schermata**, come oggi: il conto alla rovescia in Oggi, il campo in Formazione, il fantavoto atteso
   nella scheda, il guadagno nei Cambi consigliati.
4. **Colore solo con un significato.** Fondo neutro (bianco / grigio quasi nero). Verde = bene, rosso = male, arancio =
   dubbio, lime = scelto, una tinta per le azioni. I colori dei club solo in una lineetta accanto alla sigla.
5. **Azioni vicino ai dati.** L'azione di una riga sta nella riga, a destra, scritta come testo. Un solo pulsante pieno per
   schermata.
6. **Densità alta ma leggibile.** Più righe in vista, testo mai sotto 12 px, aree di tocco da 44 px.
7. **Stessa struttura del DOM dove si può.** Cambia lo stile, non il contratto con i test e con il codice: le classi esistenti
   restano (per esempio `.voce`, `.chips.scorri`, `#stato-scelta`) e si riscrive il loro aspetto. Il DOM cambia solo dove
   cambia la struttura (testata, barra, titolo della pagina, riga del giocatore, pannello affiancato).

## 5. Comodità sul PC (criterio n. 1)
Proposte scelte. Ognuna usa funzioni che esistono già; nessuna aggiunge una funzione al prodotto.

| # | Proposta | Perché (cosa risparmia) |
|---|---|---|
| C1 | **Schede in alto da 900 px**: una testata sola, alta 56 px, ferma in alto: nome disegnato a sinistra, le 4 schede (Oggi, Formazione, Squadra, Altro) come linguette con una linea sotto quella attiva, il campo di ricerca sempre aperto, l'ingranaggio (e «Aggiorna i dati» per l'amministratore). Sparisce la pillola verticale con i suoi 120 px di margine | Il mouse va sempre nello stesso posto in alto, come in ogni sito; la pagina guadagna 120 px di larghezza |
| C2 | **Le schede sono collegamenti veri** (`<a href="/?vista=formazione">`) e **il tasto Indietro funziona**: ogni cambio di scheda o di pagina di Squadra/Altro scrive l'indirizzo nella cronologia (`history.pushState`); Indietro e Avanti del browser e del mouse portano alla schermata di prima | Oggi Indietro fa uscire dall'app. Con i collegamenti veri si apre una scheda in un'altra finestra del browser (clic centrale, Ctrl+clic) per confrontare due schermate |
| C3 | **Tastiera**: restano `/` (cerca), `1`-`4` (schede), `,` (impostazioni), `Esc` (chiude il pannello). Si aggiunge **Ctrl+S / ⌘+S nella Formazione** = il pulsante «Salva» visibile in quel momento (`#salva-scelta` o `#salva-questa`); se non c'è niente da salvare il tasto fa quello che fa di solito il browser. Il campo di ricerca mostra il segno `/` | Salvare è l'azione più frequente della settimana; `/` si scopre guardando il campo |
| C4 | **Ricerca sempre aperta in testata** (da 900 px): si scrive subito; i risultati compaiono nel pannello affiancato (C5); Invio o clic su un risultato apre la scheda nello stesso pannello. Sotto i 900 px resta l'icona che apre la ricerca di oggi | Un clic e un tasto in meno per la cosa che si fa più spesso fuori dalla Formazione |
| C5 | **Pannello affiancato da 1200 px**: scheda del giocatore, confronto, scelta per il confronto, sostituzione di un titolare, «Perché questo numero» e risultati della ricerca si aprono in una colonna a destra (larga tra 400 e 520 px) che **non copre la pagina**: la pagina si stringe, resta visibile e si può usare. Un clic su un altro giocatore della lista cambia il contenuto del pannello. `Esc` o «✕» lo chiudono e il focus torna dove era. Sotto i 1200 px resta il foglio di oggi (dal basso sul telefono, di lato e modale tra 1100 e 1199 px). Le altre finestre (primo avvio, anteprima delle rose, conferme, novità) restano modali | Si scorrono i titolari e si guarda la scheda di uno, poi del successivo, senza chiudere e riaprire; si vede il campo mentre si sceglie il sostituto |
| C6 | **Formazione: campo ed elenco affiancati** da 768 px: a sinistra il campo, fermo mentre si scorre (se ci sta nello schermo, regola `controllaFerme` di oggi); a destra cifre, stato della scelta con «Salva», modulo, stile, titolari, panchina, fuori. Da 900 px due colonne 5:7 | Si cambia modulo o titolare e si vede subito il campo; niente su e giù |
| C7 | **Intestazioni ferme**: la testata resta in alto (PC); negli elenchi lunghi (Elenco dei giocatori, rosa di una squadra) la riga con i nomi delle colonne resta ferma sotto la testata mentre si scorre | Si confrontano i numeri a metà elenco sapendo cosa sono |
| C8 | **Numeri in colonna, confrontabili**: in ogni elenco le colonne «gioca N%» e «fantavoto atteso» hanno la stessa larghezza e lo stesso allineamento a destra in tutte le sezioni della schermata (Titolari, Panchina e Fuori allineati tra loro); sul PC una colonna «Partita» separata | L'occhio scende lungo una colonna invece di cercare il numero in ogni riga |
| C9 | **Azioni vicine ai dati**: «Sostituisci», «Controlla», «⇄», «✎» stanno nella riga, a destra, come testo o icona da 44 px, sempre visibili (anche senza passare il mouse: sul tablet il passaggio non c'è). Nella Formazione «Salva» sta nella riga dello stato della scelta, in alto, e resta in vista finché ci sono modifiche | Meno strada tra il dato e l'azione |
| C10 | **Squadra e Altro a due colonne** da 1100 px: l'elenco delle voci a sinistra (fisso, 280 px) e la pagina scelta a destra, come le Impostazioni già fanno da 768 px. All'apertura a destra c'è la voce aperta l'ultima volta in quella scheda (`stato.legaTorna`), altrimenti la prima del menu. Sotto i 1100 px resta una cosa alla volta con «‹ Squadra» | Si passa da Seguiti a Elenco a Calendario con un clic, senza tornare al menu |
| C11 | **Passaggio del mouse e focus chiari**: riga sotto il mouse con il fondo `--superficie`; focus da tastiera con un bordo di 2 px nel colore del testo e 2 px di stacco, mai nascosto da testata, barra o pannello | Si sa sempre dove si è, con il mouse e con la tastiera |
| C12 | **Larghezza giusta**: contenuto al massimo 1240 px, centrato; sopra i 1800 px resta l'ingrandimento a gradini di oggi (`--z`). Righe di testo al massimo 70 caratteri | Su un monitor largo i numeri non finiscono lontani dai nomi |

Proposte valutate e scartate:
- **Menu dei comandi con Ctrl+K**: sarebbe una funzione nuova; `/` e `1`-`4` bastano.
- **Frecce ↑/↓ per muoversi tra le righe**: Tab funziona già e le frecce servono già allo scorrimento della pagina.
- **Righe come vere tabelle `<table>`**: ogni riga oggi è un pulsante che apre la scheda; una tabella con righe cliccabili è
  più difficile per i lettori di schermo. Le righe restano elenchi con colonne disegnate dal CSS (`grid`) e una riga di
  intestazione visiva nascosta ai lettori, mentre il nome del pulsante dice tutto («Rossi, fantavoto atteso 6,8, gioca 85%…»).
- **Azioni che compaiono solo al passaggio del mouse**: non si scoprono e sul tablet non ci sono.
- **Riordinare le colonne con un clic sull'intestazione**: funzione nuova.

## 6. Al telefono (390 px)
- In cima alla pagina il **titolo della schermata** (32 px) con a destra due icone da 44 px (cerca, impostazioni; la terza,
  «Aggiorna i dati», solo per l'amministratore). Sotto, la **riga di stato** in grigio: «Giornata 11 · Real Esempio · dati di
  oggi 08:10». Titolo e icone scorrono via con la pagina (non sono fermi in alto): più spazio per i dati.
- **Barra in basso piena**, a tutta larghezza, con un filo sopra; la voce attiva ha il testo pieno e una linea di 3 px in alto
  nel colore delle azioni. Niente capsula, niente lente che scorre. Il contenuto finisce sempre sopra la barra.
- Una colonna. Righe da 56-64 px: volto, nome e una riga secondaria a sinistra, i numeri a destra. La colonna «Partita» del PC
  diventa la riga secondaria.
- Moduli e stili: una riga che scorre di lato (come oggi), con la voce scelta portata in vista.
- La scheda del giocatore resta il foglio che sale dal basso.
- Sotto i 320 px utili (zoom al 200%, testo «Molto grande») valgono le regole di oggi della «Pagina strettissima»
  (`docs/DESIGN.md`): restano tutte, adattate ai nuovi componenti.

Tra 768 e 899 px (iPad in verticale): barra in basso come al telefono, contenuto su due colonne in Oggi e Formazione.

## 7. Token

### 7.1 Colori
Nomi delle variabili: si tengono quelli di oggi (`--sfondo`, `--testo`, `--testo-2`, `--verde`, `--rosso`, `--arancio`,
`--blu`, `--capitano`, `--azione`, `--azione-testo`, `--bordo`, `--bordo-campo`, `--solido`, `--campo`), così il codice e i
test che li leggono restano validi. Se ne aggiungono due: `--superficie` (passaggio del mouse, pannello, intestazioni ferme) e
`--filo` (separatori tra le righe). `--vetro` e `--vetro-carta` diventano superfici piene (§7.6) e spariscono quando nessuna
regola li usa più.

| Variabile | Chiaro | Scuro | Uso |
|---|---|---|---|
| `--sfondo` | `#FFFFFF` (prima `#EAF3EE` menta) | `#121513` (prima `#07100B`) | fondo della pagina |
| `--superficie` | `#F4F5F2` | `#1A1E1C` | riga sotto il mouse, pannello, barra, intestazioni ferme |
| `--solido` | `#FFFFFF` (uguale) | `#1A1E1C` (prima `#101A14`) | dentro campi di testo, anelli e grafici |
| `--filo` | `#DDE1DC` | `#2E3430` | separatori (decorativi, nessun minimo di contrasto) |
| `--testo` | `#10201A` (uguale) | `#E9EDEA` (prima `#EEF6F0`, meno verde) | testo, filo spesso delle sezioni, focus |
| `--testo-2` | `#46564D` (uguale) | `#BCCDC2` (uguale) | secondario; resta legato all'iPhone (`Tema.secondario*`) |
| `--azione` | `#526600` (uguale, oliva) | `#3DDC97` (uguale) | pulsante pieno, link, linea della scheda attiva |
| `--azione-testo` | `#FFFFFF` | `#04301C` | scritta sul pulsante pieno |
| `--capitano` (scelta) | `#86A800` | `#D4F34A` | voce scelta di modulo e stile, con scritta `#1A2600` |
| `--bordo-campo` | `#728379` (uguale) | `#66796E` (uguale) | bordo di campi, menu, controlli segmentati |
| `--verde`, `--rosso`, `--arancio`, `--blu` | uguali a oggi | uguali a oggi | esiti (tabella di `docs/DESIGN.md`) |
| `--campo` | `#187A41` (uguale) | `#146B3A` (uguale) | il campo |

Contrasti (formula WCAG 2.x, calcolati il 5/11 con uno script; [verificato]):

| Testo | su `--sfondo` chiaro | su `--superficie` chiara | su `--sfondo` scuro | su `--superficie` scura |
|---|---|---|---|---|
| `--testo` | 16,9 | 15,4 | 15,6 | 14,3 |
| `--testo-2` | 7,8 | 7,1 | 11,1 | 10,2 |
| `--azione` | 6,4 | 5,9 | 10,4 | 9,5 |
| `--verde` | 5,2 | 4,7 | 10,4 | 9,5 |
| `--rosso` | 6,5 | 6,0 | 6,6 | 6,0 |
| `--arancio` | 5,7 | 5,2 | 10,1 | 9,3 |
| `--blu` | 6,6 | 6,0 | 7,6 | 6,9 |
| scritta sul pulsante pieno | 6,4 (bianco su oliva) | – | 8,2 | – |

Controlli (non testo, almeno 3:1): `--bordo-campo` chiaro 4,0 sul bianco e 3,7 sulla superficie; scuro 4,0 e 3,6.
La voce scelta in lime chiaro `#86A800` sta a 2,8:1 dal bianco: **da sola non basta** per dire «scelto» (WCAG 1.4.11). Per
questo la voce scelta ha anche un bordo di 2 px nel colore del testo, la scritta in grassetto e `aria-pressed="true"`.
Il bianco sul campo vale 5,4:1 (chiaro) e 6,6:1 (scuro); il numero scuro sul disco bianco della pedina 16,9:1; «⚠ gioca 45%»
(scritta `#2A1600` su `#FFB04A`) 9,5:1.

Colore delle azioni nel tema chiaro: la prova B usava un verde bosco `#0B6B3A` (6,6:1 sul bianco). Oggi è oliva `#526600`, lo
stesso dell'iPhone, e un test (`tests/test_design_web.py`) tiene uguali i due lati. **Lo decide il proprietario** (§18, scelta 1);
finché non risponde resta l'oliva, che non chiede lavoro in più.

`<meta name="theme-color">` diventa due righe con `media` (chiaro `#FFFFFF`, scuro `#121513`); `manifest.webmanifest` e la
pagina «Nessuna connessione» di `sw.js` prendono il fondo scuro nuovo.

### 7.2 Caratteri
- **Testo**: carattere di sistema (`-apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", Roboto,
  system-ui, sans-serif`). Nessun file da scaricare.
- **Numeri e titoli delle schermate**: **Archivo** semi-stretto, servito dal nostro server, con le cifre tabellari
  (`font-variant-numeric: tabular-nums`). Variabile CSS `--font-numeri: "Archivo", <carattere di sistema>`. Si usa per: titolo
  della schermata, numero eroe, fantavoto atteso, punti, «gioca N%», crediti, ore, risultati, disco della pedina.
- **Ripiego**: se il file non arriva (prima visita senza rete, server vecchio) si usa il carattere di sistema con le cifre
  tabellari: le colonne restano allineate, cambia solo il disegno. `font-display: swap`.
- Il nome «SchieraXI» nella testata del PC è il **nome disegnato compatto** (i tracciati SVG del simbolo `#wm-c` di
  `sito/index.html`, generati da `assets/marchio/wordmark/genera.py`), non testo: nessun carattere in più.
- File: `fanta/web/caratteri/archivo.woff2` più `fanta/web/caratteri/OFL.txt`. Dettagli e licenza in §16.

### 7.3 Scala tipografica
Restano i 7 livelli di `docs/DESIGN.md` (stessi nomi `--t-*`, mai sotto 12 px); cambiano alcuni valori:

| Livello | Valore | Carattere | Uso |
|---|---|---|---|
| `--t-eroe` | 56 px al telefono, 72 px da 900 px | Archivo 600 | conto alla rovescia, punti a giornata finita |
| `--t-titolo` | 32 px | Archivo 600 | titolo della schermata, cifre grandi (modulo, punti attesi) |
| `--t-card` | 17 px | sistema 650 | titolo di sezione |
| `--t-valore` | 20 px | Archivo 600 | fantavoto atteso e numeri principali delle righe |
| `--t-corpo` | 15 px | sistema 400; nomi 650 | testo, nomi dei giocatori |
| `--t-sec` | 13 px | sistema 400 | riga secondaria, riga di stato, «gioca N%» |
| `--t-eti` | 12 px | sistema 550 | intestazioni di colonna, voci della barra in basso |

Interlinea 1,4 per il testo, 1,05 per i numeri grandi. Titoli al massimo su 2 righe a 390 px.

### 7.4 Spaziature
Griglia a 4: 4, 8, 12, 16, 24, 32. Margine laterale 16 px al telefono, 32 px da 900 px. Tra una sezione e l'altra 32 px
(24 al telefono). Righe: 56 px al telefono (due righe di testo), 48 px sul PC (una riga). Spazio tra colonne di numeri 12 px.

### 7.5 Fili e raggi
- Filo sottile `1px solid var(--filo)` tra le righe; filo spesso `2px solid var(--testo)` sotto il titolo di una sezione.
- Raggi: `--r-in` 8 px (pulsanti, campi, controlli segmentati, pannello), `--r-card` 12 px (campo, foto, immagine da
  condividere), `--r-pill` 999 px (solo «⚠ gioca N%» sul campo e il contatore di «Da fare»).
- Nessuna ombra, tranne il pannello e il foglio che stanno sopra la pagina (`--ombra`, una sola). Niente sfocatura
  (`backdrop-filter`): testata, barra e pannello sono pieni.

### 7.6 Superfici e movimento
- Le superfici sono piene: `--vetro` = `--sfondo`, `--vetro-carta` = `--sfondo` (poi tolte).
- Movimento: restano solo quelli che rispondono a un gesto (apertura del pannello, del foglio e dei dettagli, pedine che
  entrano nel campo quando cambia il modulo) e i loro equivalenti calmi. Spariscono la lente che scorre nella barra, la
  pressione che rimpicciolisce le righe, l'entrata delle colonne. Nessuna `transition: all`.

## 8. Componenti
1. **Testata** (da 900 px): `<header>` fermo in alto, 56 px, fondo `--sfondo`, filo sotto. Ordine: nome disegnato (link a
   Oggi) · `<nav>` con le 4 linguette · campo di ricerca (280 px, etichetta per i lettori «Cerca un giocatore», segno `/`) ·
   ingranaggio · «Aggiorna i dati» (solo amministratore). Una sola `<nav>` in tutto il documento: al telefono la stessa nav è
   la barra in basso (CSS `position: fixed`), così i test e il codice hanno un solo elenco di schede. Anche i pulsanti esistono
   una volta sola: al telefono la testata non è ferma, nome disegnato e campo di ricerca sono nascosti, e le icone (cerca,
   ingranaggio, aggiorna) stanno in alto a destra sulla stessa riga del titolo della pagina (testata in posizione assoluta sopra
   l'angolo del `main`, che lascia lo spazio a destra del titolo). Niente id doppi.
2. **Titolo della schermata**: `<h1>` in cima a `main`, scritto da `pagina()` (§10), con la riga di stato sotto. Un solo `h1`
   per pagina; la testata non ha più un `h1`. Le pagine dentro Squadra e Altro hanno il loro titolo («Diario delle giornate»).
3. **Sezione**: `<section>` con `<h2>` (17 px, filo spesso sotto, a destra un conteggio grigio se serve: «Titolari 11»).
   Sostituisce la carta. Una carta resta solo dove raggruppa davvero qualcosa che si muove insieme: la proposta di uno scambio.
4. **Riga del giocatore** (una sola, uguale ovunque):
   - telefono: `[volto 36] [nome 15/650 · riga secondaria 13 grigia: «RON vs LAG · sab 7 20:45»] [gioca 85%] [6,8]`;
     l'etichetta del server (es. «In dubbio · gioca 55%» o «Probabile titolare») va in una terza riga, come testo nel colore
     del suo tono, senza fondo e senza bordo;
   - PC: una riga: `[volto 36] [nome] [Partita] [etichetta] [gioca 85%] [6,8] [azione]`;
   - la sigla della squadra del giocatore ha davanti una **lineetta di 3 px nel colore sociale** (decorativa: la sigla dice già
     la squadra);
   - il ruolo è una lettera grigia (P, D, C, A) in una colonna stretta, senza quadrato colorato; nella Formazione il ruolo lo
     dice già la posizione e la colonna resta;
   - l'indice (0-100) resta, come numero piccolo e neutro sul volto, senza anello colorato;
   - «gioca N%» scritto così (vocabolario), grigio; sotto il 70% arancio e in grassetto; a partita iniziata il fantavoto preso
     o «–», come oggi (`esitoPartita`);
   - si tolgono: pallino della difficoltà (resta nella scheda e nel Calendario; l'iPhone non lo mostra nelle righe), barra della
     probabilità, sottolineatura a puntini del numero (il tocco sul numero apre ancora «Perché questo numero»; il segno è il
     cursore a manina e il nome del pulsante).
5. **Intestazione delle colonne**: riga di 12 px grigia sopra l'elenco («Partita», «fantavoto atteso»), allineata alle colonne,
   nascosta ai lettori di schermo (`aria-hidden`): il nome del pulsante della riga dice già tutto. Ferma sotto la testata negli
   elenchi lunghi (C7).
6. **Numero eroe e cifre**: numero grande in Archivo senza scatola; due cifre affiancate separate da un filo verticale
   («Modulo consigliato 4-4-2 | Punti attesi 65,5 · tra 55 e 76»).
7. **Pulsanti**: pieno (`--azione`, raggio 8, almeno 44 px, 48 px quello grande al telefono) uno per schermata; secondario =
   testo nel colore delle azioni senza bordo (nelle righe) o bordo `--bordo-campo` con testo `--testo` (da solo); distruttivo
   in rosso. Mai tre pulsanti a contorno in fila: oltre il secondo si usa «Altro ▾».
8. **Controllo segmentato** (modulo, stile, sezioni di Mercato e Scambi): bordo `--bordo-campo`, voci separate da filo, la voce
   scelta in lime con bordo 2 px `--testo` e scritta scura; il valore piccolo accanto («4-3-3 64,8»). Telefono: scorre di lato;
   PC: va a capo se non ci sta.
9. **Etichette (ex pillole)**: testo 13 px nel colore del tono (`--eti-verde`, `--eti-arancio`, `--eti-rosso`, grigio per il
   neutro), senza fondo né bordo; più etichette nella stessa riga separate da « · ». Restano pillole solo «⚠ gioca N%» sul campo
   e il contatore di «Da fare».
10. **Campo**: fondo `--campo` piatto (niente bagliore), raggio 12, linee bianche al 40%. **Pedina**: disco bianco da 44 px
    con il fantavoto atteso in Archivo scuro (il numero è la pedina), sotto il cognome intero e «gioca N%» o lo stato,
    poi «vs LAG» / «@ LAG» con la lineetta del colore sociale. Sotto il 70% un anello arancio di 3 px attorno al disco e
    «⚠ gioca 57%» nella pillola arancio. I volti restano negli elenchi (scelta 2 di §18). La legenda non copre più il campo:
    «Cosa vuol dire» è un collegamento sotto il campo che apre la spiegazione lì sotto.
11. **Pannello affiancato** (C5): `aside` a destra, sotto la testata, fino al fondo della finestra, fondo `--sfondo`, filo a
    sinistra, «✕» da 44 px, titolo del contenuto come nome (`aria-labelledby`); finestra non modale (`role="dialog"` senza
    `aria-modal`), la pagina sotto resta attiva. `main` si stringe di quanto è largo il pannello.
12. **Stati vuoti**: una riga grigia che dice cosa manca e un pulsante che dice cosa fare («Importa le rose»). Niente
    riquadri.
13. **Avvisi e errori**: riga con un filo di 3 px a sinistra nel colore del significato (arancio dubbio, rosso errore), testo
    `--testo`, azione a destra («Riprova»). Il messaggio che passa (toast) resta, in basso a sinistra sul PC, pieno, senza vetro.
14. **Caricamento**: righe grigie della forma finale (scheletri), come oggi; il marchio animato solo a schermo intero.

## 9. Schermate
Le forme sotto valgono per i dati; i testi sono quelli di `fanta/web/testi.js` (nessuno cambia).

**Oggi** (PC: due colonne 5:7; telefono: una colonna in quest'ordine)
```
Oggi                                                    [cerca] [⚙]
Giornata 11 · Real Esempio · dati di oggi 08:10
La formazione si chiude tra                  | I tuoi migliori della giornata ─────────
1 giorno 2 h            (eroe, Archivo)      |            Partita            gioca  fantavoto atteso
ven 6 20:35, 10 min prima della prima partita| [o] Valvesi  ▌RON vs LAG sab 7 20:45  gioca 85%  8,3
Modulo consigliato | Punti attesi            | ...
4-4-2              | 65,5                    | Da controllare  3 in formazione ─────────
[ Apri la formazione ]  (pulsante pieno)     | [o] Gobbato   In dubbio · gioca 68%      6,1
Da fare  3 ────────────────────────          | Partite del turno ──────────────────────
Rondani è in dubbio · meglio Lusardi, +0,8   | domani 20:45   POG vs MAR
                               Sostituisci   | sab 7 15:00    VIL vs FOR   1 tuo titolare
```
Si toglie il nome «SchieraXI» con lo slogan. La maglia della mia squadra (se caricata) resta accanto al conto alla rovescia, ma
dritta, alta 72 px e senza ombra (oggi 150 px, inclinata, con ombra); lo stemma sta nella riga di stato, alto 20 px, prima del
nome della squadra. Il banner delle novità diventa una riga con filo («Novità della versione 1.402»).

**Formazione**: a sinistra il campo (fermo se ci sta); a destra, dall'alto: cifre (modulo, punti attesi con la fascia), riga
dello stato della scelta con «Salva» e «Altro ▾» (Modifica a mano, Copia, Condividi), Modulo, Stile, una riga di nota con
«Come si legge», Titolari, Panchina («entra il primo che può»), Fuori dalla formazione (chiuso). Al telefono stesso ordine con
il campo dopo Stile. A giornata chiusa: niente pulsanti, la riga di stato con la frase di `formazione.stato_chiusa*`.

**Squadra e Altro**: da 1100 px elenco delle voci a sinistra e pagina a destra (C10). Elenco dei giocatori con filtri in una
riga (ruolo come controllo segmentato, «solo svincolati», ricerca) e intestazione ferma; Cambi consigliati come righe con il
guadagno grande a destra; Calendario come tabella con le celle colorate per difficoltà (unica tabella vera, resta); Seguiti,
Squadre e rose, Aggiorna le rose come righe. Altro: Scambi (tre modi nel controllo segmentato; da 900 px scelte a sinistra e
risultato a destra, come oggi), Diario (righe per giornata, numeri in colonna), Regole (righe con «−/+» a destra), Movimenti,
Crediti, Nuova stagione, Novità.

**Scheda del giocatore** (pannello o foglio): in cima volto 56 px, nome (Archivo 32), ruolo · club · quotazione; sotto il
numero eroe (fantavoto atteso) e «gioca N%» affiancati come cifre; la partita in una riga; «Perché questo numero» come righe
con l'effetto a destra; prossime partite come celle; forma; statistiche in griglia di numeri senza riquadri; in fondo le azioni
(Segui, Confronta) come pulsanti.

**Impostazioni, accesso, primo avvio**: stessa struttura di oggi (gruppi a sinistra da 768 px), con sezioni e righe al posto
delle carte; la pagina d'accesso resta un modulo centrato largo al massimo 420 px, senza carta.

## 10. Struttura del codice (vincoli per chi esegue)
- `pagina(html, opz)` in `fanta/web/app.js` resta l'unico punto che scrive `main`. Prende due opzioni nuove:
  `opz.titolo` (testo del titolo; senza, il nome della scheda attiva da `t("nav.<scheda>")`) e `opz.stato` (`false` per non
  mostrare la riga di stato). Scrive `<header class="capo-pagina"><h1>…</h1><p class="stato-pagina">…</p></header>` prima del
  contenuto.
- `vai(vista, gruppo, opz)` scrive la cronologia (`history.pushState({ vista, gruppo }, "", "/?vista=…")`) tranne quando arriva
  da `popstate` (`opz.daCronologia`). La domanda «esci senza salvare?» della Formazione vale anche per Indietro: se l'utente
  resta, l'indirizzo torna quello della Formazione.
- `apriFoglio(html, opz)`: `opz.affianco === true` chiede il pannello affiancato; sotto i 1200 px l'opzione non cambia niente.
  Lo usano `apriGiocatore`, `apriConfronto`, `apriScelta`, `apriSostituzione`, il foglio del «Perché» e la ricerca.
- La `<nav class="schede">` sta dentro la testata in `index.html`; le voci sono `<a class="scheda" data-vista="…" href="/?vista=…">`.
- Il CSS resta un file solo (`stile.css`), con le sezioni nell'ordine di oggi; le regole vecchie che non servono più si tolgono
  nella stessa PR che le rende inutili.

## 11. Cosa si toglie
Fondo menta; vetro sfocato su testata, barra e foglio; carte bordate per ogni blocco (`.carta` diventa una sezione senza
bordo e senza fondo); capsula della barra con la lente che scorre; pillola verticale della barra sul PC e i 120 px di margine;
cerchi colorati delle icone in testata; nome e slogan dentro Oggi; maglia grande inclinata con ombra (resta piccola e dritta);
quadratino colorato del ruolo; anello colorato dell'indice; pallino della difficoltà nelle righe; barra della probabilità;
sottolineatura a puntini; pillole con fondo e bordo (tranne le due di §8.9); legenda sopra il campo; bagliore del campo; ombre
sulle pedine; pulsazione arancio della pedina in dubbio (resta l'anello fermo); pressione che rimpicciolisce righe e pulsanti;
entrata a dissolvenza delle colonne; tre pulsanti a contorno in fila.

## 12. Cosa NON cambia
- Testi e traduzioni (`fanta/web/testi.js`): nessuna frase cambia. Le frasi nuove sono poche e solo dove serve un nome di
  colonna o un nome per i lettori di schermo, in italiano e in inglese (`tests/test_testi.py`).
- Numeri, formati (virgola, «−0,4», «gioca 92%», «vs PAR» / «@ UDI», date), vocabolario di `docs/COERENZA-WEB-IPHONE.md`.
- Rotte e API: nessuna. Gli indirizzi `?vista=…` e `?vista=impostazioni&gruppo=…` restano validi.
- Funzioni e voci dei menu (`VOCI_LEGA`), ordine delle sezioni, densità compatta sempre, lingua, temi chiaro e scuro e
  «Animazioni ridotte».
- Regole di accessibilità già prese: focus mai nascosto (`scroll-padding`, `controllaFerme`), aree da 44 px, pagina
  strettissima sotto i 320 px, nomi accessibili delle pedine, contrasto delle sigle.
- Ingrandimento a gradini sopra i 1800 px (`--z`).

## 13. Coerenza con l'iPhone
L'iPhone resta nativo: stessi contenuti, testi e numeri, aspetto suo. Per ogni schermata il piano ha il compito web e il
compito iPhone; il compito iPhone di questa spec è un controllo, non un cambio d'aspetto:
- **La web si avvicina all'iPhone** (nessun lavoro sull'iPhone): titolo della schermata invece del nome della squadra
  (`docs/DESIGN.md`, incoerenza n. 15); niente slogan dentro l'app; niente pallino della difficoltà nelle righe.
- **Differenze ammesse nuove** (da scrivere in `docs/COERENZA-WEB-IPHONE.md`, «Differenze ammesse», nella PR che le introduce):
  sigla della squadra con la lineetta del colore sociale sulla web e nei colori sociali sull'iPhone (testo uguale); pedina
  della web con il numero nel disco e senza volto, quella dell'iPhone con il volto (contenuto uguale: fantavoto, cognome,
  «gioca N%» o stato, avversario); etichette come testo colorato sulla web e come pillole sull'iPhone (parole e toni uguali).
- Se il proprietario sceglie il verde bosco anche sull'iPhone (§18, scelta 1c), una PR piccola mista web + iPhone cambia
  `stile.css`, `Aspetto.swift` e `Tema.swift` insieme (un test confronta i due lati): unico lavoro iOS di questo piano.

## 14. Accessibilità
- axe (`tests/strumenti/axe/axe.min.js`, 4.14.0) senza violazioni `critical` e `serious` su ogni schermata toccata, a 390, 768,
  1024 e 1440 px, in chiaro e in scuro, a ogni PR.
- Focus visibile su tutto: `:focus-visible` con bordo 2 px `--testo` e stacco 2 px (bianco sul campo); mai coperto da testata,
  barra o pannello (WCAG 2.4.11); intestazioni ferme comprese nel `scroll-padding-top`.
- Pannello affiancato: non intrappola il focus (non è modale), `Esc` lo chiude e il focus torna all'elemento che l'ha aperto;
  il titolo del contenuto prende il focus all'apertura (`tabindex="-1"`).
- Linguette: `<a>` con `aria-current="page"` sulla scheda attiva; ordine del Tab: testata, contenuto, pannello.
- Colore mai da solo: «gioca 45%» arancio ha anche il «⚠» sul campo e l'etichetta a parole nelle righe; la voce scelta ha anche
  il bordo e `aria-pressed`.
- Aree di tocco da 44 px anche per le azioni scritte come testo nelle righe.
- Riflusso: nessuno scorrimento di lato da 320 px in su; sotto i 320 px le regole della «Pagina strettissima».

## 15. Rischi
1. **Test che leggono CSS, HTML e JavaScript della web.** Leggono `stile.css` 30 file di test, `index.html` 11, `app.js` 68,
   gli altri file `.js` della web 28 (conteggi del 5/11 con `grep -l` in `tests/`). Quelli che fissano l'aspetto da cambiare:
   `test_design_web.py` (colori legati all'iPhone, regole della barra, del foglio, delle pillole, colonne sui PC),
   `test_stile_senza_ai_web.py`, `test_accessibilita.py`, `test_accessibilita_formazione_web.py` (sigla, pedina, entrata),
   `test_riflusso_web.py` (testata, righe, chip e campo sotto i 320 px), `test_focus_bersagli_web.py` (testata ferma,
   barra, `controllaFerme`), `test_etichette_intere_web.py` (pillole), `test_testo_intero_web.py` (pedine, legenda),
   `test_formazione_ritocchi_web.py` (slogan in Oggi, griglia delle partite), `test_oggi_maglia_web.py` (maglia),
   `test_oggi_migliori_dafare_web.py`, `test_mercato_web.py`, `test_scambi_web.py`, `test_impostazioni_web.py`,
   `test_lega_web.py`, `test_touch_44.py`, `test_movimento_calmo.py`, `test_avatar_interfaccia.py`, `test_sw_web.py`.
   Regola: un test che fissa una regola tolta si riscrive per fissare la regola nuova **con lo stesso scopo** (contrasto,
   44 px, niente «…», focus in vista) e si vede fallire prima del cambio; non si cancella un controllo senza mettere al suo
   posto quello equivalente. Per trovarli prima di ogni PR:
   `grep -ln "stile.css\|index.html\|app.js" tests/*.py` e `grep -n "<selettore>" tests/*.py`.
2. **Molti test girano pezzi di `app.js` con node** (cercano le funzioni per nome). Cambiare la firma di `pagina`, `vai`,
   `apriFoglio`, `voceGiocatore` li rompe: le firme nuove aggiungono parametri in fondo, facoltativi.
3. **Produzione a metà.** Ogni PR unita va in produzione da sola. L'ordine del piano lascia sempre l'app coerente: prima
   colori, poi struttura comune, poi schermate. Nessuna PR lascia una schermata con due stili mischiati.
4. **Carattere.** Con gli account accesi un file fuori dall'elenco dei pubblici risponde 401 (anche nella pagina d'accesso):
   `/caratteri/` va in `STATICI_PREFISSI` di `fanta/rotte_account.py`. Il tipo del file `.woff2` in Python sul PC di prova non
   è conosciuto (`mimetypes.guess_type("a.woff2")` → `None`, Python 3.13 su Windows, provato il 5/11): il server lo registra
   (`mimetypes.add_type("font/woff2", ".woff2")`). Il file va nell'elenco `FILE` di `sw.js` (offline).
5. **Pannello non modale.** Il foglio di oggi rende la pagina inerte (`bloccaSfondo`); il pannello affiancato no. Rischi: due
   pannelli aperti, focus perso, pagina che si stringe mentre si scrive. Solo i contenuti di C5 lo usano; ridimensionando
   la finestra sotto i 1200 px con il pannello aperto il pannello diventa il foglio modale di oggi.
6. **Cronologia.** `pushState` con la domanda «esci senza salvare?» e con il foglio aperto. Regola: Indietro cambia schermata
   come un clic su una scheda (il foglio o il pannello si chiudono con lei); se la Formazione ha modifiche non salvate parte la
   domanda di oggi e, se l'utente resta, l'indirizzo torna quello della Formazione. Il foglio non scrive nella cronologia.
7. **Ripiego del carattere.** Con il carattere di sistema i numeri hanno un'altra larghezza: le colonne hanno larghezze in `ch`
   o in px sufficienti per «gioca 100%» e «10,0» con tutti e due i caratteri.
8. **Contrasto della scelta in lime chiaro** sotto 3:1 da solo: risolto con il bordo (§7.1). Lo controlla axe solo in parte:
   va guardato nella foto.

## 16. Ricerca: il carattere Archivo
| Dato | Valore | Fonte | Stato |
|---|---|---|---|
| Licenza | SIL Open Font License 1.1 | `assets/marchio/wordmark/OFL.txt`; [google/fonts METADATA.pb](https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/METADATA.pb) | [verificato] |
| Nome riservato (Reserved Font Name) | nessuno nella riga del copyright («Copyright 2020 The Archivo Project Authors (https://github.com/Omnibus-Type/Archivo)»): un sottoinsieme può chiamarsi ancora Archivo | `OFL.txt` qui sopra; [METADATA.pb](https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/METADATA.pb) | [verificato] |
| Condizione della OFL per ridistribuire | ogni copia porta il copyright e la licenza, anche nei campi del file | `OFL.txt`, condizione 2 | [verificato] |
| Assi del carattere variabile | larghezza `wdth` 62-125, peso `wght` 100-900 | [METADATA.pb](https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/METADATA.pb) | [verificato] |
| File di partenza | `Archivo[wdth,wght].ttf`, 658.596 byte, in `ofl/archivo/` di google/fonts | `gh api repos/google/fonts/contents/ofl/archivo` | [verificato] il 5/11 (la PR registra commit e SHA-256 del file usato) |
| Lettere | latin, latin-ext (italiano e accenti compresi) | METADATA.pb, «subsets» | [verificato] |
| Cifre tabellari (`tnum`) dentro Archivo | da controllare sul file con fontTools prima di generare | – | [da verificare] |
| Strumento | `fonttools varLib.instancer <file> wdth=87.5 wght=400:700`, poi `pyftsubset … --flavor=woff2 --layout-features+=tnum,lnum --name-IDs='*'` | [instancer](https://fonttools.readthedocs.io/en/latest/varLib/instancer.html), [subset](https://fonttools.readthedocs.io/en/latest/subset/index.html) | [verificato] |
| `pyftsubset` tiene da solo `tnum`? | no: le funzioni tenute di norma non comprendono `tnum`; va chiesta | [subset](https://fonttools.readthedocs.io/en/latest/subset/index.html) | [verificato] |
| `pyftsubset` tiene da solo la licenza nel file? | no: di norma tiene solo i nomi 0-6 (il copyright sì, la licenza 13-14 no): serve `--name-IDs='*'`, e accanto al file c'è `OFL.txt` | [subset](https://fonttools.readthedocs.io/en/latest/subset/index.html) | [verificato] |
| WOFF2 richiede Brotli in Python | sì (`pip install fonttools brotli`, in un ambiente a parte come per `genera.py`) | [subset](https://fonttools.readthedocs.io/en/latest/subset/index.html) | [verificato] |
| Precaricamento con `crossorigin` anche dallo stesso server | sì, per i caratteri è obbligatorio | [MDN, rel=preload](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/preload) | [verificato] |
| CSP del server | `font-src 'self'` già presente in `fanta/server.py` | codice | [verificato] |
| Peso del file finale | obiettivo 60 KB o meno (latino, larghezza fissa 87,5, peso 400-700) | da misurare | [da verificare] |

Lettere da tenere: U+0020-007E, U+00A0-00FF, U+0131, U+0152-0153, U+2013-2014, U+2018-201E, U+2022, U+2026, U+2009, U+202F,
U+2212 (il meno tipografico di «−0,4»). Il «⚠» e le icone restano del sistema.

## 17. Scelte mie
- **Scelta mia: pannello affiancato da 1200 px e non modale** perché a quella larghezza la pagina resta larga almeno 680 px;
  costo se sbagliata: una soglia da spostare (una variabile CSS e una costante in `app.js`).
- **Scelta mia: cronologia del browser e schede come collegamenti** perché è il comportamento che ci si aspetta da un sito sul
  PC e non aggiunge funzioni; costo se sbagliata: togliere `pushState` (poche righe), gli indirizzi restano.
- **Scelta mia: Ctrl+S / ⌘+S nella Formazione** perché salvare è l'azione più frequente; se non c'è niente da salvare il tasto
  non viene fermato; costo se sbagliata: togliere un gestore.
- **Scelta mia: ricerca aperta in testata con i risultati nel pannello** invece di un menu a tendina sotto il campo, perché
  riusa il pannello e la scheda si apre nello stesso posto; costo: se il proprietario preferisce il menu a tendina, un
  componente in più.
- **Scelta mia: Squadra e Altro a due colonne da 1100 px**, come già le Impostazioni; costo se sbagliata: la regola si toglie
  e torna una cosa alla volta.
- **Scelta mia: etichette in una terza riga al telefono** invece di toglierle: l'iPhone le mostra, i contenuti devono restare
  uguali; costo: righe da 64-68 px invece di 56 quando c'è un'etichetta.
- **Scelta mia: «gioca N%» resta scritto intero nella cella** (non «85%» sotto un'intestazione «gioca» come nella prova B),
  perché il vocabolario vieta la percentuale da sola.
- **Scelta mia: nessun interruttore temporaneo «grafica nuova / vecchia»**: un doppio stile nello stesso file costerebbe più del
  passaggio a gradini.

## 18. Scelte per l'utente
1. **Colore delle azioni nel tema chiaro.** (a) resta l'oliva `#526600` di oggi, uguale all'iPhone: nessun lavoro in più;
   (b) verde bosco `#0B6B3A` della prova B solo sulla web: si scioglie il legame web-iPhone nel test per il tema chiaro;
   (c) verde bosco su web e iPhone: una PR piccola mista web + iPhone. Consiglio (a) per partire: il colore delle azioni si vede
   su un pulsante per schermata e sui collegamenti, e cambiarlo dopo costa due righe. Finché non rispondi vale (a).
2. **Volti sul campo.** La prova B mette il fantavoto nel disco della pedina e lascia i volti solo negli elenchi. Oggi
   `docs/STILE-SENZA-AI.md` conta i volti sul campo tra le cose «che ha solo questa app». Si va come la prova B (consiglio)
   o si tiene il volto piccolo (40 px) con il numero sotto? Finché non rispondi vale la prova B, nella PR della Formazione.
3. **Sito di presentazione.** La prova `sito.html` esiste: va rifatto nello stesso stile? Se sì, issue a parte dopo questa.

## 19. Fuori ambito
Il sito (`sito/`), l'app iPhone (salvo la scelta 1c), il widget, le immagini da condividere (restano come sono, salvo i colori
del fondo se servono), nuove funzioni, nuove schermate, il contenuto delle notifiche.
