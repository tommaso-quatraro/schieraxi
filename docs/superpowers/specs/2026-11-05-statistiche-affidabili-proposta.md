# Le nostre statistiche, affidabili: proposta da discutere

Stato: **proposta**, da discutere con il proprietario prima di ogni piano. Parte di #165.
Solo analisi: niente codice finché le decisioni del §4 non sono prese.

## 1. Dove siamo (misura del 5/11/2026)

Come: `python -m fanta verifica --incertezza`, `python -m fanta verifica --pacchetti completo,senza_xg --simulazioni 200` e
`prove/calibra_p_voto.py`, su una copia dell'archivio di sviluppo: 41 giornate (2025-26 dalla 5ª alla 38ª, 2026-27 dalla 2ª
all'8ª), regole e rose della lega d'esempio (`lega/esempio/`, squadre inventate). Ogni giornata usa solo i dati di prima.
Come sempre nella verifica, il passato non ha le probabili formazioni: «gioca N%» viene dalle presenze recenti.

| Misura | 2025-26 (34 g.) | 2026-27 (7 g.) |
|---|---|---|
| Errore del fantavoto atteso (radice dell'errore quadratico, chi ha preso voto) | 1,42 | 1,59 |
| Stesso errore scegliendo per fantamedia | 1,49 | 1,83 |
| Errore medio assoluto del fantavoto atteso | 0,94 | 1,02 |
| Brier di «gioca N%» (0 = perfetto, 0,25 = dire sempre 50%) | 0,151 | 0,130 |
| Errore di calibrazione di «gioca N%» (media di \|detto − giocato\| per fasce di 10 punti) | 2,1 punti % (stagione su cui è tarato) | 4,1 punti % (fuori campione) |
| Fascia «tra X e Y, 8 volte su 10»: punti veri dentro, tarata sull'altra stagione | 86% (680 casi) | 73% (197 casi) |
| Punti a giornata con le rose d'esempio: consigliata / per fantamedia / massimo col senno di poi | — | 63,2 / 62,8 / 66,7 |
| Senza gli xG di Understat (giocatori e squadre): errore del fantavoto | 1,43 (+0,4%) | 1,60 (+0,7%) |
| Senza gli xG di Understat: punti a giornata (prova a 200 simulazioni) | — | +0,1 |

Cosa dicono:
1. **Il fantavoto atteso batte la fantamedia**, di più a inizio stagione (−13%) che a fine stagione (−5%), quando la fantamedia ha
   tanti voti. Sui punti delle formazioni la differenza (+0,5 a giornata) è piccola: con 7 giornate e poche rose non si distingue dal caso.
2. **«Gioca N%» senza probabili è ben tarato**. Le fasce peggiori nel 2026-27: «10-20%» (detto 13%, giocato 6%, 1.300 casi)
   e «40-50%» (detto 45%, giocato 33%, 224 casi).
3. **«Gioca N%» con le probabili, cioè quello che l'utente vede, non è misurato qui**: l'archivio di sviluppo non ha probabili
   di giornate giocate. Il server le ha (Stato dei dati > Calibrazione delle probabili) [da verificare: quante giornate].
   Le costanti di `modello._p_da_probabili` (0,6 di subentro, 0,96, 0,75 in dubbio, 0,02 non citato) sono scelte a mano.
4. **La fascia è un po' stretta quest'anno**: 73% invece di 80%, e i punti fatti superano gli attesi (+2,0 in media sulle
   rose estratte a sorte del 2026-27).
5. **Gli xG di Understat aggiungono quasi niente**: toglierli peggiora l'errore dello 0,5%, la stessa soglia con cui una fonte
   nuova viene promossa. Ma lo scenario tiene i **minuti** e i **rigori calciati** di Understat: Fantacalcio.it dà voti, gol,
   assist, rigori segnati e sbagliati, cartellini, entrato e uscito, ma **non i minuti né i tiri** [verificato in
   `fanta/fonti/fantacalcio.py:leggi_voti`]. Lo scenario «solo Fantacalcio.it» non esiste ancora.
6. **La leva più grande sono i gol della squadra**, non quelli del giocatore: l'esperimento «oracolo» del 30/10 dice che sapere
   in anticipo i gol veri della squadra varrebbe +1,35 punti a giornata, sapere chi gioca +0,68, il rigorista +0,02.

Cosa c'è già: `affidabilita.py` rifà la prova sulle ultime 8 giornate a ogni giornata finita (Stato dei dati);
«Quanto ci abbiamo preso» nel Diario misura i giocatori dell'utente, con i numeri mostrati se c'è l'istantanea.
Cosa manca: i numeri **mostrati prima della scadenza per tutta la Serie A**, salvati giornata per giornata, con soglie e un
avviso quando una soglia salta. Senza questo registro «il numero regge» non si può dire.

## 2. «Affidabili» in modo misurabile

Si misurano a ogni giornata finita, su tutti i giocatori della Serie A, con i numeri **mostrati** prima della scadenza
(probabili comprese). Ogni soglia vale sulla media delle ultime 8 giornate registrate. «Regge» = la media è entro soglia (primo verdetto dopo 8 giornate).

| # | Indicatore | Soglia | Oggi |
|---|---|---|---|
| I1 | Errore del fantavoto atteso contro la fantamedia, sulle stesse giornate | almeno il 3% sotto | −5% e −13%: regge |
| I2 | Calibrazione di «gioca N%» mostrato | errore di calibrazione ≤ 5 punti % e Brier ≤ 0,15 | senza probabili 4,1 e 0,130; con le probabili non misurato |
| I3 | Fascia «8 volte su 10» | punti veri dentro tra 72% e 88% | 73%: al limite |
| I4 | Gol e assist attesi nostri (finché Understat serve da metro) | errore del fantavoto al massimo +1% e punti al massimo −0,3 a giornata rispetto alla versione con Understat; gol attesi tarati per fasce (scarto ≤ 0,03 gol a partita) | senza xG: +0,5% e +0,1, regge; senza minuti e rigori di Understat: non misurato |

## 3. Lavori possibili, in ordine di valore e rischio

Tutti sul server tranne L5. Stime in piani (un piano = un ramo, una PR in bozza, ~3-6 compiti).

**L1. Registro delle giornate** (valore alto, rischio basso, 1 piano, nessuna dipendenza). Poco prima della prima partita della giornata (come la copia alla scadenza) si salvano per ogni
giocatore della Serie A `p_voto`, `mu`, gol e assist attesi, minuti attesi e stato delle probabili, con le regole classiche come `precisione.pubblico` (circa 650 righe a
giornata, nell'archivio, niente dati personali). A giornata finita si calcolano I1-I3 e si scrive una riga per giornata; i numeri vanno in
Stato dei dati e un avviso parte al proprietario quando una media esce dalla soglia per 2 giornate di fila (come la sentinella).
File: modulo nuovo, `archivio.py` (tabella nuova), `pianificatore.py`, `stato_dati.py`, test.
Da partire subito: ogni giornata non registrata è persa, e per dire «regge» servono 8 giornate, circa due mesi di campionato.

**L2. «Gioca N%» con le probabili, ritarato** (valore medio-alto, rischio basso, 1 piano piccolo, dipende dai dati del server).
Stessa regressione già usata senza probabili (`prove/calibra_p_voto.py`), sulle probabili raccolte sul server, tarata su metà
delle giornate e provata sull'altra metà. Sostituisce le costanti scelte a mano; la correzione per gruppi (±15%) resta.
File: `modello.py` (`_p_da_probabili`), `prove/calibra_p_voto.py`, test. Prima e dopo: `python -m fanta verifica`.
Serve una copia dell'archivio del server (solo dati di calcio, fuori da git) o il calcolo sul server.
[da verificare: quante giornate con probabili ci sono sul server e se la tabella tiene l'ultima versione prima della partita.]

**L3a. Misura «solo Fantacalcio.it»** (valore alto, rischio basso, 1 piano piccolo, nessuna dipendenza; può andare insieme a L1).
Scenario nuovo in `verifica_pacchetti.py`: niente Understat; minuti stimati da entrato e uscito, rigori calciati = segnati +
sbagliati, forza delle squadre dai soli gol. Dice quanto costa davvero togliere Understat (I4) prima di scrivere il modello nuovo.

**L3b. Gol e assist attesi nostri, Understat come metro** (valore alto, rischio medio, 2-3 piani, dipende da L3a, L1 e D2).
Se L3a perde troppo: prima i minuti attesi, poi la forza delle squadre (la leva più grande). Poi le due versioni girano insieme
nel registro di L1 (I4) per 8 giornate. Se reggono: la scheda del giocatore mostra i nostri gol e assist attesi della prossima
partita (web e iPhone nello stesso piano, `docs/COERENZA-WEB-IPHONE.md`) al posto di xG, xA e tiri della stagione; poi si
toglie Understat (`fonti/understat.py`, `aggiorna.py`, `scheda.py`, il controllo `somma_xg` di `controlli.py`, crediti nelle
pagine legali), con `verifica` prima e dopo.

**L4. Fascia ritarata quando esce dalla soglia** (valore medio, rischio basso, 1-2 compiti, dipende da L1). Quando I3 esce da
72-88%, si rifà `verifica --incertezza` e si aggiornano le costanti di `incertezza.CALIBRAZIONE`. Può stare nel piano di L1.

**L5. La misura davanti all'utente** (valore medio, è l'identità dell'app; rischio basso; 1 piano web + iPhone; dipende da L1
con almeno 3 giornate e da D3). Una riga in più nella carta «Quanto ci abbiamo preso» del Diario: errore del fantavoto e
«gioca N%» su tutta la Serie A, anche quando vanno male. Nessuna schermata nuova.

Ordine proposto: L1 e L3a insieme (file diversi) → L2 → L5 → L3b → L4 quando serve.
Aree senza sovrapposizioni: L1 (modulo nuovo, `archivio.py`, `pianificatore.py`, `stato_dati.py`); L3a (`verifica_pacchetti.py`);
L2 (`modello.py`, `prove/calibra_p_voto.py`); L5 (`fanta/precisione.py`, `fanta/web/`, `ios/`, dopo L1).

Fuori da questo obiettivo: fonti nuove o a pagamento (decisione del 2/11), quote e scommesse (`docs/decisioni/0005`),
xG «veri» calcolati dai tiri (senza Understat i tiri non li abbiamo), schermate nuove.

## 4. Decisioni per il proprietario

**Decise il 5/11/2026: il proprietario ha approvato D1, D2 e D3 come raccomandato.**

**D1. Le soglie del §2 vanno bene?** Sono la definizione di «fatto» per #165.
Raccomandazione: sì così, da rivedere una volta dopo le prime 8 giornate del registro.

**D2. Quando togliamo Understat, e cosa perde la scheda del giocatore?** Togliendolo spariscono dalla scheda xG, xA, tiri e
«sopra o sotto le attese» della stagione (web e iPhone), sostituiti dai nostri gol e assist attesi della prossima partita.
Raccomandazione: si toglie quando la misura «solo Fantacalcio.it» regge nel passato **e** per 8 giornate dal vivo (I4); fino ad
allora resta come metro. Se L3a mostra che i minuti mancano troppo, ne riparliamo prima di scrivere il modello nuovo.

**D3. Mostriamo all'utente quanto ci prendiamo su tutta la Serie A?** Nel Diario è una riga in più in una carta che c'è già; sul
sito sarebbe una pubblicazione.
Raccomandazione: nel Diario sì (L5); sul sito dopo, con l'obiettivo «aperta agli altri» (#168).

## 5. Scelte mie (le può cambiare il proprietario)
- Misura su tutta la Serie A e sui numeri mostrati, non ricostruiti: è quello che l'utente vede e il campione è circa 20 volte più
  grande di una rosa. Costo se sbagliata: basso, il registro è piccolo.
- Soglia I1 relativa alla fantamedia, non assoluta: l'errore cambia molto tra inizio e fine stagione (1,59 e 1,42).
  Costo se sbagliata: un modello che peggiora insieme alla fantamedia non fa scattare l'avviso.
- Finestra di 8 giornate, come `affidabilita.MASSIMO_GIORNATE`: le soglie reagiscono lente. Costo: un avviso in ritardo.

## 6. Cosa non è verificato
- Calibrazione di «gioca N%» con le probabili: si misura solo sul server [da verificare].
- Perdita senza minuti e rigori di Understat: lavoro L3a [da misurare].
- Numeri sulle rose della lega vera: qui solo rose d'esempio; i punti delle formazioni del 2025-26 mancano perché le rose
  d'esempio non hanno abbastanza giocatori in quella stagione.
- L'archivio di sviluppo arriva all'8ª giornata del 2026-27; il server ne ha di più.
