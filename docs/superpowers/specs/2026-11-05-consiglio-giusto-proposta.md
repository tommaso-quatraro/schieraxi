# Il consiglio di formazione giusto, e spiegato: proposta da discutere

Stato: **proposta**, da discutere con il proprietario prima di ogni piano. Parte di #166, dopo #165.
Solo analisi: niente codice finché le decisioni del §4 non sono prese.
Confine con #165: lì i numeri del singolo giocatore (fantavoto atteso, «gioca N%», fascia); qui la scelta che ne nasce
(chi schierare, panchina, stabilità, perché).

## 1. Dove siamo (misura del 5/11/2026)

Come: copia dell'archivio di sviluppo, regole e rose della lega d'esempio (`lega/esempio/`, 10 squadre inventate), 600
simulazioni come l'app. **A** = giornate 2-8 del 2026-27 già giocate, 57 casi squadra-giornata (rose con almeno 20 presenti),
solo dati di prima e senza probabili, come `verifica`. **B** = giornata 9 con le probabili, la strada vera dell'app
(`consigli.formazione`), 10 squadre, 110 titolari. Script di misura fuori dal repository (lavoro L0).
Due scelte semplici di confronto: **S1** = fantamedia con il «gioca N%» del modello (quella di `verifica`);
**S2** = fantamedia tra chi ha preso voto la giornata prima, senza modello (quello che farebbe chi non ha l'app).

| Misura | Oggi |
|---|---|
| A. Punti veri a giornata: consigliata / S1 / S2 / senno di poi | 62,95 / 62,32 / 62,29 / 66,47 |
| A. Consigliata meno S2 | +0,66 (errore standard 0,49: non si distingue dal caso) |
| A. Casi con consigliata ≥ S2 | 39 su 57; 5 giornate su 7 |
| A. Quota del senno di poi presa dalla consigliata | 94,9% |
| `python -m fanta verifica` (300 simulazioni): consigliata / S1 / senno di poi, 2026-27 | 63,24 / 62,76 / 66,65 |
| A. Titolari senza voto per formazione: consigliata / S2 | 3,28 / 3,09 |
| A. Titolari senza voto né riserva entrata; casi con un utile rimasto fuori dalla panchina | 1,18 a formazione; 3 casi su 57 |
| B. Modulo ammesso, un portiere, panchina entro il numero | 10 squadre su 10 |
| B. Titolari «improbabili» (gioca sotto il 20%) | 12 su 110, in 8 squadre su 10 (8 «non tra i convocati previsti») |
| B. Di questi, con un compagno di ruolo che gioca al 50% o più | 9; metterlo al posto costa 0,004 punti attesi (mediana), al massimo 0,13 |
| B. Reparti dove un escluso ha più punti attesi del titolare più debole | 22 su 40; spiegati dalla nota «titolare anche se incerto»: 8 |
| B. «Perché questo numero» vuoto / senza un motivo del giocatore (solo «gioca N%», partita o «altro») | 18 / 48 titolari su 110 |
| Stabilità, piccolo aggiornamento dei dati: 3 o più titolari cambiano | A: 32 prove su 171 (19%); B: 10 su 30 (33%) |
| Stabilità, piccolo aggiornamento: quanto vale la nuova quando cambia | mediana +0,04 (A) e +0,03 (B) punti attesi; mai 0,5 o più |
| Stabilità, solo il seme della simulazione (stessi dati; l'app usa sempre lo stesso): almeno 1 titolare cambia | A: 67%; B: 57% |
| Diario d'esempio ricalcolato (5 giornate): attesi / fatti; giornate nella fascia | 63,4 / 60,8; 4 su 5 |
| Diario: consigliata contro schierata | non misurabile: la lega d'esempio non ha formazioni schierate |

«Piccolo aggiornamento» = ogni «gioca N%» spostato a caso di circa 3 punti e ogni fantavoto atteso di circa 0,1, 3 prove per
caso. È una prova di laboratorio [stima]: l'archivio non tiene le versioni delle probabili e nessuno registra quante volte la
consigliata cambia davvero.

Cosa dicono:
1. **La consigliata batte di poco le scelte semplici** (+0,6 punti a giornata) e prende il 95% del senno di poi. Con 57 casi
   la differenza non si distingue dal caso: serve misurarla ogni giornata, non una volta.
2. **La scelta è piatta e quindi ballerina.** Molte formazioni valgono quasi lo stesso: basta un ritocco minimo dei dati, o il
   numero di simulazioni (63,24 con 300, 62,95 con 600), per cambiare titolari. Quando 3 o più titolari cambiano, la nuova vale
   in mediana tre centesimi di punto. Oggi l'unica soglia è quella dell'avviso alla scadenza (`notifiche.SOGLIA_AVVISO_PUNTI`,
   1 punto); Formazione, Oggi, widget, Da fare e copia alla scadenza mostrano sempre l'ultima, per quanto piccolo il guadagno.
3. **Titolari che non giocano.** Con 5 cambi e la panchina per ruolo (regole d'esempio), un titolare al 2% con una riserva sicura dietro vale
   quanto la riserva titolare (il cambio entra quasi sempre): il modello li tratta come pari e a volte tiene l'improbabile.
   Per i numeri non è un errore; per chi legge sì, ed è proprio il «giocatori che non giocano» del «fatto quando» di #166.
   Toglierli costa quasi niente (0,004 punti).
4. **Il perché spiega il numero, non la scelta.** «Perché questo numero» confronta il giocatore con la media del ruolo; nessuna
   riga dice perché lui e non il compagno. La nota «titolare anche se incerto» copre 8 delle 22 scelte che sembrano storte.
   Un titolare improbabile ha come perché «non tra i convocati previsti»: la spiegazione contraddice il consiglio.
5. **Regole della lega rispettate**: moduli, portiere e panchina sempre giusti (la sentinella lo controlla ogni ora,
   `formazione_non_valida`); rinvii e scadenza già gestiti. Unico buco: dopo un **anticipo** già cominciato la consigliata
   non tiene fermi i suoi giocatori (`fasi.formazione_a_giornata_iniziata` cambia le schede, non la scelta) [verificato nel
   codice]. Nella lega del proprietario non è mai capitato.
6. **La panchina non è la leva**: solo in 3 casi su 57 è rimasto fuori un giocatore utile, il tetto di 5 cambi è stato
   raggiunto 2 volte su 57.

## 2. «Consiglio giusto» in modo misurabile

Si misurano nel Diario a ogni giornata finita, sulla consigliata **mostrata** (l'istantanea congelata alla scadenza), per
ogni utente; la soglia vale sulla media delle ultime 8 giornate (primo verdetto dopo 8 giornate, come #165).

| # | Indicatore | Soglia | Oggi |
|---|---|---|---|
| C1 | Valore: punti veri della consigliata meno S2, e meno la schierata quando è diversa | tutti e due ≥ 0 | +0,66 contro S2 (laboratorio); contro la schierata non misurato |
| C2 | Stabilità: cambi della consigliata nelle 24 ore prima della scadenza | nessun cambio di titolari che valga meno della soglia D2, se non per un titolare diventato fuori o improbabile | 19-33% dei piccoli aggiornamenti cambiano 3+ titolari per 0,03-0,04 punti |
| C3 | Chi gioca: titolari sotto il 20% (o infortunati, squalificati) con un compagno di ruolo al 50% o più | 0 a giornata | 9 su 110 (giornata 9) |
| C4 | Perché: scelte che sembrano storte (titolare con meno punti attesi di un escluso dello stesso ruolo) con la loro riga | tutte; titolari senza un motivo proprio ≤ 10% | 8 su 22; 48 su 110 |

## 3. Lavori possibili, in ordine di valore e rischio

Un piano = un ramo, una PR in bozza, ~3-6 compiti. Tutti sul server tranne L3 (server + web + iPhone nello stesso piano).

**L0. Misura in laboratorio** (valore alto, rischio nullo, 1 piano piccolo). Lo script di questa misura diventa
`python -m fanta verifica --consiglio`: S2, titolari improbabili, scelte storte, perché vuoti, stabilità con seme e ritocco.
È il «prima e dopo» di L1-L3. File: `fanta/verifica_consiglio.py` (nuovo), `fanta/__main__.py`, test.

**L1. Niente titolari che non giocano** (valore alto, rischio basso, 1 piano piccolo). In `formazione.migliore`, dopo la
ricerca: un titolare sotto il 20% (o fuori) cede il posto al miglior compagno di ruolo al 50% o più, se costa meno di 0,3 punti
attesi. Vale per tutti gli stili, quindi anche per Diario, Da fare, widget e avvisi. File: `fanta/formazione.py`, test;
`verifica` prima e dopo. Misura attesa sulla giornata 9: C3 da 9 a 0, punti attesi −0,01 in mediana per squadra.

**L2. Consiglio stabile** (valore alto, rischio medio, 1 piano; dopo L1 e D2). La consigliata di prima è l'istantanea già
salvata per la giornata (`diario.salva_istantanea`: a ogni apertura della Formazione prima della scadenza e dalla
copia automatica degli ultimi 10 minuti). La nuova la sostituisce
solo se vale almeno la soglia D2 in più ricalcolata con i dati nuovi, oppure se un titolare di prima è uscito dalla rosa,
fuori o improbabile. Così Formazione, Oggi, widget, Da fare, avviso e copia alla scadenza restano d'accordo.
File: `fanta/consigli.py` (scelta e chiave della cache con la formazione di prima), `fanta/diario.py` (lettura), test.

**L3. Il perché della scelta in una riga** (valore alto, rischio basso, 1 piano; dopo L1 e L2, D3). Il server scrive per ogni
titolare il motivo vero della scelta, come `Frase`: «titolare anche se incerto: se non gioca entra Y», «preferito a Y: più
punti attesi (5,4 contro 4,9)», «a pari punti gioca più sicuro di Y», altrimenti il primo motivo proprio di «perché questo
numero». Riusa il conto del Confronto (`consigli._in_formazione`). Nessuna schermata nuova.
File server: `fanta/perche_scelta.py` (nuovo), una riga in `consigli._calcola_formazione`, `fanta/frasi.py`,
`fanta/web/testi.js`, `docs/API.md`. Web: `fanta/web/app.js` (nota sotto il campo, riquadro del perché).
iPhone: `ios/Sources/Presentation/Formazione/FormazioneView.swift`, `ios/Sources/Support/PercheNumeroView.swift`.
`docs/GUIDA-UTENTE.md`, `docs/COERENZA-WEB-IPHONE.md`.

**L4. Gli indicatori nel Diario** (valore alto: è il «fatto quando»; rischio basso; 1 piano). Ogni voce del Diario aggiunge
i punti di S2, i titolari improbabili e quante volte la consigliata è cambiata nelle 24 ore prima della scadenza (contati
in `salva_istantanea` quando sovrascrive). C1-C4 vanno in Stato dei dati per il proprietario, con un avviso quando una media
esce dalla soglia per 2 giornate di fila (come #165 L1). File: `fanta/diario.py`, `fanta/stato_dati.py` (in comune con
#165 L1: prima uno, poi l'altro), test.

**L5. Anticipi già cominciati** (valore basso, mai capitato; rischio basso; issue `P3`). Dopo l'inizio di un anticipo i suoi
giocatori restano dove sono nella consigliata. File: `fanta/consigli.py`, `fanta/fasi.py`.

Ordine proposto: L0 e L1 insieme (file diversi) → L2 → L3; L4 insieme a L1 se #165 L1 è già unito, altrimenti dopo.
Aree senza sovrapposizioni: L0 (`verifica_consiglio.py`, `__main__.py`); L1 (`formazione.py`); L4 (`diario.py`,
`stato_dati.py`); L2 e L3 toccano `consigli.py`, quindi uno dopo l'altro.
Fuori da questo obiettivo: panchina (§1, punto 6), stili, scambi e mercato (già con il buon senso di `buon_senso.py`),
schermate nuove.

## 4. Decisioni per il proprietario

**D1. Gli indicatori e le soglie del §2 vanno bene?** Sono la definizione di «fatto» per #166.
Raccomandazione: sì così, da rivedere una volta dopo 8 giornate di L4.

**D2. Quanto deve valere un cambio perché il consiglio già mostrato cambi?** Oggi: sempre la migliore, anche per 0,01 punti.
Raccomandazione: **1 punto atteso**, la stessa soglia dell'avviso alla scadenza, così app e avvisi dicono la stessa cosa.
Un titolare diventato fuori o improbabile si cambia sempre. Costo: in qualche giornata si lascia meno di 1 punto atteso,
contro uno scarto tipico tra punti fatti e attesi di circa 6-7 punti.

**D3. Dove si legge il perché in una riga?** (a) sotto ogni nome, sempre; (b) solo per le scelte che sembrano storte, nella
nota sotto il campo che c'è già («titolare anche se incerto»), il resto al tocco sul giocatore.
Raccomandazione: (b): poche righe in più, nessuna schermata nuova, web e iPhone nello stesso piano.

## 5. Scelte mie (le può cambiare il proprietario)
- L1 senza chiedere: lo chiede già il «fatto quando» di #166 e costa 0,004 punti. Costo se sbagliata: quasi nullo.
- Riferimento semplice S2 e non S1: è quello che farebbe chi non ha l'app; oggi danno lo stesso numero (62,29 e 62,32).
- Stabilità misurata in laboratorio finché L4 non conta i cambi veri. Costo: il numero vero può essere diverso.
- Panchina e stili fuori: i numeri non mostrano un guadagno. Costo: se la lega vera ha regole diverse, da rimisurare.

## 6. Cosa non è verificato
- Tutto su rose d'esempio e archivio di sviluppo (giocate fino alla giornata 8, probabili solo della 9).
- Consigliata contro schierata e quante volte la consigliata cambia davvero: [da verificare] sul server, misura di L4.
- Titolari improbabili con le regole della lega vera (panchina, numero di cambi): [da verificare]; con meno cambi il fenomeno
  dovrebbe calare.
- La soglia 0,3 di L1 e il 20% / 50% di C3 sono scelte a mano: L0 dirà se reggono.
