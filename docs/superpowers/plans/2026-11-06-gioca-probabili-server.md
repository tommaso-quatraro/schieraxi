# «Gioca N%» con le probabili, ritarato sul server (L2 di #165, issue #379): piano

> **Per chi esegue:** skill `superpowers:subagent-driven-development` (consigliata) o `superpowers:executing-plans`, una PR alla
> volta (A, poi B, poi C), ognuna nel suo ramo e in bozza. Passi con `- [ ]`.

**Obiettivo:** le costanti scelte a mano di `modello._p_da_probabili` si ritarano da sole sul server, sulle giornate già giocate,
e il server le usa solo se sulle giornate più recenti sbagliano meno. Se poi peggiorano, torna da solo ai valori di partenza.

**Architettura:** un comando nuovo, `python -m fanta taratura-probabili`, gira come ultimo passo di `script/server/aggiorna.sh`
(4 volte al giorno, lavoro vero al massimo una volta per giornata). Legge solo l'archivio: le probabili salvate dal registro delle giornate
poco prima della prima partita (`registro_giocatori`) e i voti. Tara una regressione logistica su metà delle giornate, la prova
sull'altra metà e scrive l'esito nella tabella nuova `taratura_probabili`. Il modello legge la riga `attiva` (se c'è). Quando la
riga attiva cambia, una riga in `aggiornamenti` fa ricalcolare le previsioni, come dopo ogni aggiornamento dei dati.
Decisione: `docs/decisioni/0009-gioca-probabili-si-ritara-sul-server.md`.

**Strumenti:** Python, numpy, pandas, SQLite, pytest; web senza librerie; SwiftUI con Swift Testing.

**Spec:** `docs/superpowers/specs/2026-11-05-statistiche-affidabili-proposta.md` (§2 I2, §3 L2, §4 D1). Issue #379 (dati).
Decisione dell'utente del 6/11: niente tabelle di calcio copiate sul PC, la taratura gira dove ci sono tutte le giornate.

## 1. Da dove partiamo [verificato nel codice il 6/11]

- `modello._p_da_probabili(stato, perc, in_dubbio)`: titolare `(q + (1 − q) × 0,6) × 0,96` con `q` = percentuale/100 (80 se manca);
  panchina `1,0 × q` (20 se manca); infortunato o squalificato 0; in dubbio × 0,75; altri stati 0,02. Chi non è citato in una
  squadra coperta prende 0,02 direttamente in `_pezzi` (`stato = "non_citato"`).
- Correzione per gruppi (±15%, `stato_dati.fattori`): legge la tabella `probabili`, che tiene l'ultima lettura della giornata.
  `aggiorna.probabili` la cancella e la riscrive a ogni giro del cron senza guardare il calcio d'inizio: per le partite già
  iniziate l'ultima lettura può essere di dopo la scadenza. Quanto pesa davvero sui numeri del server: [da verificare].
- `registro_giocatori` (L1, dal 5/11) salva per ogni giocatore, negli ultimi 10 minuti prima della prima partita, `stato`,
  `percentuale`, `dubbio` e `p_voto` mostrato. `stato` vale `non_citato` per chi non è citato in una squadra coperta e NULL per le
  squadre senza probabili. È il momento in cui l'utente sceglie, ed è nella copia notturna (`registro_copia`).
- `python -m fanta verifica` non usa le probabili (il passato non le ha): con questo piano le sue righe restano identiche.
- `p_voto` entra anche nei minuti attesi dei titolari (`modello._pezzi`, `parte = min(1, percentuale / p_voto)`), quindi nel
  fantavoto atteso e nei gol e assist attesi. Con questo piano i minuti restano quelli della formula di partenza (§8).
- Calendario [da verificare]: se la giornata 11 (dal 6/11) è salvata nel registro, con la 14ª arrivano le 4 giornate della prima
  misura (verso il 9/12: solo `pronta` o `scartata`, nessun cambio) e con la 18ª le 8 giornate che servono per accendere
  (D1: verdetto dopo 8 giornate). **La prima accensione non può arrivare prima di metà gennaio 2027.**

## 2. Vincoli

- **Produzione invariata fino all'attivazione automatica.** In ogni PR `python -m fanta verifica` dà righe identiche prima e dopo
  (numeri nella PR). Finché la tabella non ha una riga `attiva`, `consigli.previsioni` dà gli stessi numeri di oggi.
- Soglie (D1 del 5/11, `registro_giornate.SOGLIE`): calibrazione ≤ 0,05 (5 punti) e Brier ≤ 0,15. Miglioramento richiesto: Brier
  almeno lo 0,5% più basso, la stessa regola con cui si promuove una fonte (`verifica_fonti.SOGLIA_ERRORE`).
- Almeno 4 giornate misurate con le probabili di prima della scadenza per fare la prova (issue #379); almeno 200 righe di
  titolari e 200 di panchinari sia nella metà di taratura sia in quella di prova. **Per accendere:** almeno 8 giornate (D1), cioè
  almeno 3 giornate di prova (con 8: 4 di taratura e 4 di prova) e almeno 3 di taratura, così la correzione per gruppi (±15%,
  `stato_dati.MIN_GIORNATE = 3`) si calcola davvero. Sotto, al massimo una riga `pronta`.
- La nuova deve battere **sia** la formula di adesso **sia** i numeri mostrati davvero (`registro_giocatori.p_voto`), e in almeno
  due terzi delle giornate di prova, per eccesso (3 → 2, 4 → 3).
- Nessuna fonte nuova, nessuna richiesta in rete: il comando legge e scrive solo l'archivio. Le fonti restano come sono.
- Mai dati veri nel repository: test con squadre e giocatori inventati, come `tests/test_registro_giornate.py`.
- I numeri mostrati non cambiano mai nelle 24 ore prima della prima partita di una giornata: il comando scrive solo `rimandata`,
  senza consumare la prova, e rifà tutto al primo giro fuori dalle 24 ore. Solo `--spegni` a mano vale subito.
- **La PR B non parte prima della risposta dell'utente a S1** (§8). La PR A sì: misura soltanto.
- Test con `-n 2`, comandi uno alla volta: `.venv\Scripts\python.exe -m pytest -q -n 2`.
- Ogni PR che tocca `fanta/` ha il suo `fanta/novita.d/<nome>.json`; `voci` senza nomi di file, rotte o dispositivi.

## 3. Da guardare in revisione

1. **Probabili di dopo la scadenza:** la taratura legge SOLO `registro_giocatori`, mai `probabili` né `probabili_storia`. Test
   `test_righe_ignorano_le_probabili_di_dopo` (A1).
2. **Partite senza voti o rinviate:** fuori dalle righe, come nella misura del registro (`registro_giornate._partite`). Test
   `test_righe_solo_partite_giocate_con_i_voti` (A1).
3. **Percentuale mancante e dati degeneri** (tutti i titolari in campo, gruppi piccoli): niente NaN né infiniti, coefficienti
   incoerenti = riga `scartata`, mai `attiva`. Test `test_percentuale_mancante_vale_80_e_20` e `test_dati_degeneri_scartati` (A2).
4. **Numeri che cambiano a ridosso della scadenza** (avvisi «cambia la formazione» a raffica) **e ritorno indietro perso** (i giri
   delle 13, 17 e 21 trovano «niente di nuovo» e la versione peggiore resta accesa per giorni): test
   `test_niente_cambi_nelle_24_ore_prima` e `test_ritorno_rimandato_non_si_perde` (B1).
5. **Tabella rovinata o assente:** `attiva(db)` dà None e l'app usa i valori di partenza, senza errori. Test
   `test_json_rovinato_valori_di_partenza` (B1).

## 4. PR, aree, ordine

| PR | Cosa | Area e file | Dopo | Non insieme a |
|---|---|---|---|---|
| A | La misura: righe, taratura, prova, comando | server: `fanta/taratura_probabili.py` (nuovo), `fanta/modello.py` (solo `_p_da_probabili`), `fanta/archivio.py`, `fanta/registro_copia.py`, `fanta/__main__.py`, `prove/calibra_p_voto.py`, `script/server/aggiorna.sh`, `script/server/LEGGIMI.md`, `MAPPA.md`, test | — | Fasi G1 e H1 del piano gol attesi (`modello.py`) |
| B | Il passaggio: attivazione, ritorno indietro, modello | server: `fanta/taratura_probabili.py`, `fanta/modello.py` (`previsioni`, `_pezzi`), `fanta/nostri.py` (solo `previsioni`), `fanta/consigli.py` (solo `_calcola_previsioni`), `fanta/registro_nostri.py` (solo `previsioni_dal_vivo`), `fanta/stato_dati.py`, `fanta/__main__.py`, `fanta/contenuti/sotto-il-cofano*.json`, `docs/SOTTO-IL-COFANO.md`, `docs/API.md`, `MAPPA.md`, test | A e la risposta dell'utente a S1 | G1, H1 (stessi file) |
| C | Una riga in «Stato dei dati» | web: `fanta/web/app.js`, `fanta/web/testi.js`, test · iOS app: `Modelli.swift`, `LegaExtra.swift`, `NomiDati.swift`, `ParoleRegistro.swift`, fixture e test · `docs/COERENZA-WEB-IPHONE.md` | B | altre PR su «Stato dei dati» |

Nessun compito tocca il widget iOS. A può partire subito: misura soltanto (da 4 giornate righe `pronta` o `scartata`). B parte
dopo la risposta dell'utente a S1; unita prima di 8 giornate, non accende niente.

---

## PR A: la misura (server)

### Compito A1: le righe di taratura
**File:** crea `fanta/taratura_probabili.py`, `tests/test_taratura_probabili.py` (costruttore di registro finto: partite, voti,
`registro_giornate` con `salvato`, `misurato`, `con_probabili = 1`, `registro_giocatori`).

**Produce:**
- `righe(db: sqlite3.Connection) -> pd.DataFrame`, colonne `stagione, giornata, calciatore_id, stato, percentuale, dubbio,
  p_mostrato, preso` (`p_mostrato` = `registro_giocatori.p_voto`, il numero che l'utente ha visto).
  Solo giornate di `registro_giornate` con `misurato` non NULL, `con_probabili = 1` e `persa` NULL; solo partite in
  `registro_giornate._partite(db, stagione, giornata)[0]`; solo `stato` non NULL (squadre coperte). `preso` = 1 se il giocatore
  ha il voto (`COLONNA_VOTO[registro_giornate.REGOLE.fonte_voto]` non NULL) in quella giornata.
- `giornate(r: pd.DataFrame) -> list[tuple[str, int]]`: le giornate delle righe, dalla più vecchia.
- `dividi(gg: list[tuple[str, int]]) -> tuple[list, list]`: (taratura, prova); prova = le ultime `min(len(gg) // 2, MAX_PROVA)`.
- Costanti: `MIN_GIORNATE = 4` (per la prova), `MIN_GIORNATE_ACCENSIONE = 8` e `MIN_PROVA_ACCENSIONE = 3` (per accendere, PR B),
  `MAX_PROVA = 8`, `MIN_RIGHE_STATO = 200`.

- [ ] Test: `test_righe_dal_registro` (2 giornate finte: righe, `p_mostrato` e `preso` giusti), `test_righe_ignorano_le_probabili_di_dopo`
  (righe in `probabili` e `probabili_storia` che dicono altro: risultato uguale), `test_righe_solo_partite_giocate_con_i_voti`
  (una partita rinviata e una senza voti: fuori), `test_squadre_senza_probabili_fuori` (stato NULL: fuori),
  `test_dividi` (`4 → 2 + 2`, `5 → 3 + 2`, `8 → 4 + 4`, `20 → 12 + 8`).
- [ ] Vederli fallire, scrivere, vederli passare. Commit.

### Compito A2: la formula tarata e la stima
**File:** `fanta/modello.py` (solo `_p_da_probabili`), `fanta/taratura_probabili.py`, `prove/calibra_p_voto.py`, test.

**Produce:**
- `modello._p_da_probabili(stato, perc, in_dubbio, taratura: dict | None = None) -> float`. Con `taratura=None` il corpo di oggi,
  identico. Con `taratura = {"titolare": [a, b], "panchina": [a, b], "dubbio": c, "non_citato": n}`: infortunato e squalificato 0;
  titolare `σ(a + b·q + c·dubbio)` con `q` = percentuale/100 (0,8 se manca); panchina uguale (0,2 se manca); `non_citato` → `n`;
  ogni altro stato 0,02 come oggi. `σ(z) = 1 / (1 + e^−z)`.
- `regressione_logistica(X: np.ndarray, y: np.ndarray) -> np.ndarray`: il corpo di `prove/calibra_p_voto.stima` (Newton, 50 passi,
  regolarizzazione 1e-3), spostato qui; `prove/calibra_p_voto.py` lo importa.
- `stima(r: pd.DataFrame) -> dict`: una regressione sola sulle righe titolare e panchina, colonne `[è_tit, è_tit·q, è_pan,
  è_pan·q, dubbio]` (senza costante comune), così `dubbio` è uno solo. `non_citato = (presi + 0,02·K) / (casi + K)` con
  `K_NON_CITATO = 50`. Numeri a 4 decimali.
- `coerente(t: dict) -> bool`: `b ≥ 0` per titolare e panchina, `c ≤ 0`, titolare ≥ panchina per `q` = 0; 0,1; …; 1,
  titolare al 100% tra 0,85 e 0,99 (oggi 0,96), `non_citato` ≤ 0,10, tutti i numeri finiti.

- [ ] Test: `test_senza_taratura_numeri_di_oggi` (una decina di casi, uguali ai valori di oggi: titolare 90% 0,9216, panchina 30%
  in dubbio 0,225, non citato 0,02), `test_stima_ritrova_la_curva` (5.000 righe finte con titolari che giocano con
  `σ(−1 + 4q)` e panchinari con `σ(−2,5 + 3q)`, seme fisso: coefficienti entro 0,3 dai veri), `test_percentuale_mancante_vale_80_e_20`,
  `test_dati_degeneri_scartati` (tutti i titolari in campo: numeri finiti e `coerente` falso),
  `test_regressione_spostata_stessi_pesi` (stessi pesi di prima su una tabella finta).
- [ ] Rosso, codice, verde. `prove/calibra_p_voto.py --stima 2025-26` sull'archivio di sviluppo stampa gli stessi pesi di prima
  (scriverli nella PR). Commit.

### Compito A3: la prova e il comando (solo misura)
**File:** `fanta/taratura_probabili.py`, `fanta/archivio.py` (SCHEMA), `fanta/registro_copia.py` (`TABELLE`),
`tests/test_registro_copia.py`, `fanta/__main__.py`, `script/server/aggiorna.sh`, `script/server/LEGGIMI.md`, `MAPPA.md`,
`fanta/novita.d/gioca-probabili-misura.json`, test.

**Produce:**
- Tabella `taratura_probabili (versione INTEGER PRIMARY KEY, creata TEXT, stato TEXT, coefficienti TEXT, taratura TEXT, prova TEXT,
  misura TEXT, motivo TEXT, avvisato INTEGER)` con `CREATE TABLE IF NOT EXISTS`. `stato`: `pronta`, `scartata` (qui); `attiva`,
  `rimandata`, `superata`, `ritirata`, `spenta`, `riaccesa` (PR B). `taratura` e `prova` = liste JSON `[[stagione, giornata], …]`.
  Nella copia notturna: `registro_copia.TABELLE` più `taratura_probabili`.
- `fattori_su(r: pd.DataFrame, taratura: dict | None) -> dict[str, float]`: gruppi di `modello.GRUPPI_PROBABILI` sulle righe, nella
  forma di `stato_dati.calibrazione`, poi `stato_dati.fattori_da` (import dentro la funzione: `stato_dati` importa `modello`).
- `misura(r: pd.DataFrame, taratura: dict | None, fattori: dict[str, float]) -> dict`: `{casi, brier, calibrazione, per_giornata}`.
  p = `_p_da_probabili` × fattore del gruppo, al massimo 0,99 (come `_pezzi`). Calibrazione come `prove/calibra_p_voto.
  errore_calibrazione` (fasce di 10 punti, media pesata di |detto − giocato|). `per_giornata` = Brier di ogni giornata.
- `misura_mostrati(r: pd.DataFrame) -> dict`: stessi numeri con `p_mostrato` al posto della formula.
- `verdetto(nuova: dict, attuale: dict, mostrati: dict, t: dict) -> tuple[bool, str]`. Passa solo se: `coerente(t)`;
  `nuova.brier ≤ min(attuale.brier, mostrati.brier) × (1 − SOGLIA_BRIER)` con `SOGLIA_BRIER = 0.005`; Brier della nuova più basso di
  tutti e due in almeno due terzi delle giornate di prova, per eccesso; `nuova.calibrazione ≤ 0.05` e `nuova.brier ≤ 0.15` (da
  `registro_giornate.SOGLIE`). Motivi: `migliora`, `incoerente`, `non_migliora`, `fuori_soglia`.
- `prova(db, attuale: dict | None) -> dict | None`: righe, `dividi`, `stima` sulla taratura, `misura` sulla prova per la nuova e per
  quella di adesso (`attuale`, None = valori di partenza), ognuna con i suoi `fattori_su` della metà di taratura, più
  `misura_mostrati`. None se le giornate sono meno di `MIN_GIORNATE` o una metà ha meno di `MIN_RIGHE_STATO` titolari o panchinari.
- `esegui(db, adesso: datetime) -> str` (una riga per il log). Con `ATTIVAZIONE = False` (costante, la accende la PR B): se la prova
  supera il verdetto scrive una riga `pronta`, altrimenti `scartata`. Non scrive niente se l'ultima riga ha la stessa lista `prova`
  (niente di nuovo) o se `prova` dà None («in attesa: N giornate su 4»).
- Comando `python -m fanta taratura-probabili [--prova]`: senza opzioni `esegui`; con `--prova` stampa giornate, casi, Brier e
  calibrazione di adesso e nuova, coefficienti, verdetto e secondi impiegati, e non scrive niente.
- `aggiorna.sh`, come ultimo passo, dopo l'avviso «Formazione pronta» e i ritagli dei volti, subito prima di `tail -n 2000`:
  `nice -n 15 timeout 300 .venv/bin/python -m fanta taratura-probabili >> "$LOG" 2>&1`. Così non ritarda dati, formazione e avvisi.
  Riga nella tabella di `LEGGIMI.md`.
- `voci` della novità: «Nessun cambiamento visibile: SchieraXI comincia a misurare quanto è giusto «gioca N%» con le probabili
  formazioni, sulle giornate già giocate.»

- [ ] Test: `test_verdetto` (migliora; Brier meglio solo dello 0,3%: `non_migliora`; meglio della formula ma non dei mostrati:
  `non_migliora`; meglio in media ma in una giornata su 3: `non_migliora`; in 2 su 3: `migliora`; calibrazione 0,06:
  `fuori_soglia`; incoerente), `test_prova_attesa_sotto_quattro_giornate`,
  `test_prova_curva_vera_batte_i_valori_di_partenza` (6 giornate finte dalla curva di A2, `p_mostrato` = formula di partenza:
  `pronta`),
  `test_prova_dati_dai_valori_di_partenza_non_migliora` (giornate finte generate con la formula di oggi: `scartata`),
  `test_esegui_non_riscrive_senza_giornate_nuove`, `test_esegui_non_cambia_le_previsioni` (`consigli.previsioni` uguale prima e
  dopo), `test_copia_notturna_porta_la_taratura`.
- [ ] Rosso, codice, verde. Suite intera. `verifica` identica. `--prova` su 20 giornate finte sul PC: meno di 5 secondi (scriverlo).
- [ ] **Fatto quando:** PR in bozza «Parte di #379» con `verifica` prima e dopo; dopo l'unione il log di `aggiorna.sh` sul server ha
  la riga del comando («in attesa: N giornate su 4»), lo controlla il coordinatore.

## PR B: il passaggio (server)

### Compito B1: attivazione, ritorno indietro, spegnimento
**File:** `fanta/taratura_probabili.py`, `fanta/__main__.py`, `tests/test_taratura_probabili.py`.

**Produce:**
- `ATTIVAZIONE = True`, `ANTICIPO_CAMBIO = timedelta(hours=24)`, `CHIAVE = "taratura-probabili"` (riga di `aggiornamenti`).
- `attiva(db) -> dict | None`: i coefficienti della riga `attiva` più recente; None se non c'è, se la tabella manca o se il JSON è
  rovinato (nel log il tipo d'errore, mai il contenuto).
- `vicina_la_scadenza(db, adesso) -> bool`: vero se la prima partita (`avvisi.prima_partita`) della giornata di
  `consigli.prossima_giornata` è tra adesso e 24 ore.
- `esegui(db, adesso, manda=None) -> str`, in quest'ordine:
  1. ultima riga `spenta` → niente. La regola «niente di nuovo» di A3 non vale se l'ultima riga è `pronta`, `rimandata` o
     `riaccesa`: allora si rifà tutto;
  2. **ritorno indietro**: se c'è una riga attiva e almeno 2 giornate dopo l'ultima della sua `prova`, `misura` su quelle giornate
     della riga attiva e dei valori di partenza (fattori dalle righe di prima). Se la attiva ha un Brier almeno lo 0,5% più alto o
     esce dalle soglie: diventa `ritirata` (`peggiorata` o `fuori_soglia`). Bastano 2 giornate: tornare ai numeri di partenza
     rischia meno che accendere;
  3. **nuova prova** contro quella di adesso: se supera il verdetto e ci sono almeno `MIN_GIORNATE_ACCENSIONE` (8) giornate e
     `MIN_PROVA_ACCENSIONE` (3) giornate di prova, diventa `attiva` e la vecchia `superata`; se supera ma le giornate sono meno,
     resta `pronta` (motivo `poche_giornate`); se non supera, `scartata`;
  4. **24 ore prima della prima partita**: se il passo 2 o il passo 3 cambierebbero la riga attiva, il comando scrive SOLO una riga
     `rimandata` (motivo `scadenza_vicina`; se l'ultima riga è già `rimandata` per le stesse giornate la aggiorna) e niente
     `ritirata`, `attiva`, `scartata` o `pronta`: la prova non si consuma e il primo giro fuori dalle 24 ore rifà i passi 2 e 3;
  5. ogni volta che la riga attiva cambia: le righe nuove o cambiate e `archivio.segna(db, CHIAVE,
     adesso.isoformat(timespec="seconds"))` nella STESSA transazione, con un solo `db.commit()` alla fine (se `segna` fallisce,
     `db.rollback()` e la riga attiva resta quella di prima). Così `consigli._versione` cambia insieme ai coefficienti e le
     previsioni si ricalcolano;
  6. avviso: per ogni riga `attiva` o `ritirata` con `avvisato` 0, `manda(titolo, testo)` (di base `sentinella.manda_ntfy`).
     Titolo «SchieraXI: «gioca N%»». Testi: «Versione N attiva: Brier X invece di Y, calibrazione Z punti, su K giornate di prova.»
     e «Tornato ai valori di partenza: la versione N sbagliava di più nelle ultime K giornate.» Niente nomi. Se non parte, si
     riprova al giro dopo.
- `python -m fanta taratura-probabili --spegni`: la riga attiva diventa `ritirata` (`spenta_a_mano`), una riga `spenta`, `segna`;
  vale subito. `--accendi`: una riga `riaccesa`, il giro dopo riprova da capo.

- [ ] Test: `test_attiva_quando_supera` (8 giornate finte dalla curva di A2: `attiva`), `test_pronta_sotto_otto_giornate`
  (6 giornate che superano il verdetto: `pronta`, `attiva(db)` None), `test_niente_cambi_nelle_24_ore_prima` (stessi dati:
  `rimandata`, poi `attiva` al giro fuori dalle 24 ore), `test_ritorno_rimandato_non_si_perde` (riga attiva, 2 giornate nuove
  generate con la formula di partenza; giro nelle 24 ore: `rimandata` e la attiva resta; secondo giro nelle 24 ore, stesse giornate:
  ancora `rimandata`, niente «niente di nuovo»; giro fuori dalle 24 ore: `ritirata` e `attiva(db)` None),
  `test_torna_indietro_se_peggiora`, `test_attiva_e_segna_nella_stessa_transazione` (`archivio.segna` che alza un errore: nessuna
  riga `attiva` nuova; senza errore la riga di `aggiornamenti` ha l'ora di `adesso` al secondo), `test_spegni_e_riaccendi`,
  `test_avviso_una_volta_senza_nomi`, `test_json_rovinato_valori_di_partenza`, `test_segna_solo_quando_cambia_la_attiva`.
- [ ] Rosso, codice, verde. Commit.

### Compito B2: il modello usa la riga attiva
**File:** `fanta/modello.py`, `fanta/nostri.py`, `fanta/consigli.py`, `fanta/registro_nostri.py`, `fanta/stato_dati.py`,
`tests/test_taratura_probabili.py`, `tests/test_stato_dati.py`.

**Produce:**
- `modello.previsioni(…, taratura: dict | None = None)`, passato a `_pezzi_condivisi` e `_pezzi` e messo nella chiave della memoria
  (`json.dumps(taratura, sort_keys=True)` o None). In `_pezzi` le due chiamate: `_p_da_probabili(stato, perc, dubbio, taratura)` e,
  per chi non è citato, `_p_da_probabili("non_citato", None, False, taratura)` al posto di `0.02`.
- **Minuti con la formula di partenza.** Nel calcolo dei minuti dei titolari (`parte = min(1, perc / 100 / p)`) `p` resta quello di
  oggi: senza taratura è `p_voto` (righe identiche a oggi); con la taratura è `_p_da_probabili(stato, perc, dubbio)` senza taratura e
  senza correzione per gruppi. Così la taratura cambia solo «gioca N%» (e i punti attesi `p × mu`), non i minuti, il fantavoto atteso,
  i gol e gli assist attesi. Si rivede quando anche il fantavoto atteso si misura con la taratura accesa (I1 e I4 del registro).
- `nostri.previsioni(…, taratura=None)` lo passa. `consigli._calcola_previsioni` e `registro_nostri.previsioni_dal_vivo` passano
  `taratura_probabili.attiva(db)` (così I4 confronta numeri con lo stesso «gioca N%»).
- `stato_dati.calibrazione(db, stagione)`: con una riga attiva, i gruppi si fanno sulle `taratura_probabili.righe(db)` della
  stagione (registro, prima della scadenza) e `previsto` usa la riga attiva; senza, com'è oggi. `taratura_probabili` si importa
  dentro le funzioni di `stato_dati` (giro di import: `consigli` → `stato_dati` → `taratura_probabili` → `registro_giornate` → `consigli`). Così la correzione per gruppi (±15%)
  resta e, con la taratura accesa, non legge più le probabili di dopo la scadenza.
- `stato_dati.riepilogo`: campo `calibrazione.taratura` = `taratura_probabili.riepilogo(db)`:
  `{stato: "in_attesa" | "attiva" | "non_attiva" | "spenta", giornate, minimo: 4, versione, dal, prova: {giornate, brier,
  brier_prima, brier_mostrati, calibrazione} | null, motivo}`; `motivo` è un codice (`poche_giornate`, `non_migliora`,
  `fuori_soglia`, `incoerente`, `peggiorata`, `scadenza_vicina`, `spenta_a_mano`) o null. Solo numeri, niente giocatori.

- [ ] Test: `test_previsioni_con_la_attiva_cambiano_solo_chi_e_nelle_probabili`, `test_minuti_con_la_formula_di_partenza`
  (titolare al 70%, senza correzione per gruppi: con e senza taratura `minuti`, `e_gol`, `e_assist` e `mu` uguali, `p_voto` diverso),
  `test_senza_attiva_previsioni_identiche`,
  `test_memoria_distingue_le_tarature`, `test_calibrazione_con_la_attiva_legge_il_registro`, `test_riepilogo_senza_nomi`.
- [ ] Rosso, codice, verde. Suite intera. `verifica` identica. Commit.

### Compito B3: documenti e testi
**File:** `docs/API.md` (campo `calibrazione.taratura` di `GET /api/stato-dati`; se `tests/test_contratto_api.py` lo chiede,
`python script/ci/aggiorna_openapi.py`), `fanta/contenuti/sotto-il-cofano.json` e `.en.json` (sezione `probabilita-giocare`, più
`fanta/taratura_probabili.py:esegui` in `fonte_codice`), `docs/SOTTO-IL-COFANO.md`, `MAPPA.md`, `fanta/novita.d/gioca-probabili-taratura.json`.

Frase da aggiungere in Sotto il cofano: «Questi numeri di partenza sono scelti a mano. Quando ci sono almeno 4 giornate giocate con
le probabili salvate poco prima della prima partita, il server li ritara da solo su metà delle giornate, li prova sull'altra metà e
li usa solo se sbagliano meno; se poi peggiorano, torna ai numeri di partenza.» `voci` della novità: «Quando ci sono abbastanza
giornate giocate, «gioca N%» con le probabili formazioni si tara da solo, e solo se così sbaglia meno.»

- [ ] `tests/test_sotto_il_cofano.py` e `tests/test_testi.py` verdi. Commit.
- [ ] **Fatto quando:** PR in bozza «Parte di #379», `verifica` prima e dopo identica. Dopo l'unione «Stato dei dati» del server ha
  `calibrazione.taratura` con `stato` `in_attesa` (lo controlla il coordinatore).

## PR C: una riga in «Stato dei dati» (web e iOS, dopo B)

**File:** web `fanta/web/app.js` (carta «Quanto azzecca il modello», e `nomiFonte` con `"taratura-probabili"`), `fanta/web/testi.js`
(chiavi `sd.tar_*` e `sd.f_taratura`, italiano e inglese), `tests/test_stato_dati_taratura_web.py` (con node, come
`tests/test_stato_dati_nostri_web.py`). iOS app: `ios/Sources/Domain/Modelli.swift` (`Calibrazione.taratura`, facoltativo),
`ios/Sources/Presentation/Lega/ParoleRegistro.swift` (la frase), `ios/Sources/Presentation/Lega/LegaExtra.swift` (piè della sezione
«Quanto sono giuste le previsioni»), `ios/Sources/Domain/NomiDati.swift` (`"taratura-probabili"`), `ios/Tests/Fixtures/stato-dati-taratura.json`
(come `stato-dati-nostri.json`), `ios/Tests/SchieraxiTests/TaraturaProbabiliTests.swift` (Swift Testing). Poi
`docs/COERENZA-WEB-IPHONE.md` (una riga) e `fanta/novita.d/stato-dati-taratura.json`.

**Cosa si vede**, uguale sui due lati, solo per chi amministra, sotto i gruppi della calibrazione:
- `in_attesa`: «Taratura con le probabili: in attesa · 2 giornate su 4»;
- `attiva`: «Taratura con le probabili: attiva dal 15/1 (versione 1) · nelle ultime 4 giornate Brier 0,091 invece di 0,097, scarto 2,1 punti»;
- `non_attiva`: «Taratura con le probabili: non attiva · non sbaglia meno dei numeri di partenza» (una frase per ogni `motivo`;
  con `poche_giornate`: «la prova passa, si accende con 8 giornate (ora 5)»);
- `spenta`: «Taratura con le probabili: spenta a mano».
In «Ultimi aggiornamenti dei dati» la riga `taratura-probabili` si legge «Taratura di «gioca N%»».

- [ ] Test Swift prima del codice (decodifica e le quattro frasi). Codice web e iOS. `collaudo-web` a 390, 768, 1024 e 1440 px,
  chiaro e scuro, con i quattro stati inventati: niente «undefined» o «NaN», numeri con la virgola. `ios / test` verde.
  Foto da fare: nessuna («Stato dei dati» non è tra le schermate di `screenshot.yml` [verificato: grep]).
- [ ] **Fatto quando:** PR in bozza «Parte di #379», web e iPhone con le stesse frasi.

---

## 5. Cosa vede l'utente

- Niente di nuovo da toccare. Dopo l'attivazione (non prima di metà gennaio 2027) cambiano i «gioca N%» dei giocatori citati nelle
  probabili, e con loro i punti attesi, le parole che ne dipendono («Probabile titolare», «In ballottaggio»…), gli incerti e la
  riga «gioca N%» del Diario. Fantavoto atteso, minuti, gol e assist attesi non cambiano (minuti con la formula di partenza, B2).
  La consigliata cambia se la nuova vale almeno un punto atteso in più **oppure** se un suo titolare diventa «fuori» o
  «improbabile», cioè scende sotto il 20% (`consigli.NON_GIOCA`, consigliata stabile). Mai nelle 24 ore prima della prima partita.
- Chi amministra: una riga in «Stato dei dati» (PR C) e un avviso quando una versione si accende o si spegne.
- Sotto il cofano: una frase in più nella sezione sulla probabilità di giocare (B3).

## 6. Quando si chiude #379

Il coordinatore chiude #379 alla prima misura vera del comando sul server (riga `pronta` o `scartata` con 4 o più giornate, verso
il 9/12 [da verificare]), con un commento con i numeri della prova (Brier e calibrazione: nuova, formula di adesso, mostrati). Fino
ad allora le PR dicono «Parte di #379». La prima accensione (da 8 giornate) si segue in #165.

## 7. Rischi

1. **Poche giornate, prova rumorosa:** da 4 a 7 giornate si misura soltanto (`pronta` o `scartata`). Si accende da 8 giornate
   (4 di prova, circa 2.000 righe), con lo 0,5% di miglioramento contro formula e mostrati e in almeno due terzi delle giornate di
   prova; il ritorno indietro usa lo stesso margine.
2. **Accendi e spegni a ripetizione:** al massimo un cambio per giornata misurata, con margini uguali nei due versi. Se succede
   più di due volte in una stagione, il coordinatore apre una issue.
3. **Numeri che cambiano senza una PR:** ogni versione resta nella tabella (coefficienti, giornate, misura) e nella copia notturna;
   avviso al proprietario a ogni cambio; `--spegni` vale subito.
4. **Correzione per gruppi su dati vecchi** quando la taratura è spenta: resta com'è oggi (legge `probabili`). Si sistema quando la
   taratura si è dimostrata stabile (issue P3 da aprire dopo il primo mese attivo).
5. **Server ripristinato da una copia:** la tabella torna con la copia notturna; senza, il comando riparte dal registro e ritrova
   gli stessi coefficienti (calcolo deterministico).

## 8. Scelte

### Per l'utente
- **S1, prima della PR B (la PR A non ne ha bisogno):** va bene che «gioca N%» cambi da solo, con un avviso a te a ogni cambio e lo
  spegnimento a mano, invece di una PR per ogni nuova taratura? Raccomandazione: sì. Con i dati che restano sul server una PR potrebbe
  solo copiare numeri che nessuno può rifare sul PC, e a ogni giornata ci vorrebbe un passo a mano. Se la risposta è no, la PR B
  cambia: il comando resta di sola misura e i coefficienti `pronta` entrano in `modello.py` con una PR.

### Mie (le può cambiare l'utente)
- **Sul server, come ultimo passo di `aggiorna.sh`** e non nel thread del servizio né in una riga di crontab nuova: lo script si
  aggiorna da solo con l'app, ha già il suo blocco e la priorità bassa, e un errore non tocca il servizio. Costo se sbagliata: il
  verdetto arriva fino a qualche ora dopo la misura del registro.
- **Minuti con la formula di partenza** finché il fantavoto atteso non si misura anche con la taratura accesa: la taratura cambia una
  cosa sola, misurata dal Brier. Costo: se un titolare sale di probabilità, i suoi minuti attesi non salgono insieme.
- **Accensione da 8 giornate, ritorno indietro da 2:** accendere cambia numeri non ancora visti dal vivo, tornare indietro riporta
  numeri già noti. Costo: una taratura buona aspetta fino a metà gennaio.
- **Solo `registro_giocatori` come fonte** e non anche `probabili_storia`: una strada sola, i numeri del momento in cui l'utente
  sceglie, già nella copia notturna, con i non citati. Costo: la giornata 10, raccolta solo in `probabili_storia`, non conta: le
  4 giornate arrivano circa una settimana dopo.
- **Coefficienti nell'archivio** (tabella più riga in `aggiornamenti`) e non in un file in `dati/` né in `modello.py`: la cache si
  rinnova con il meccanismo che c'è già. Costo: una tabella in più nella copia notturna.
- **Regressione logistica per titolare e panchina** con un solo peso per «in dubbio», come chiede la issue, e non le 4 costanti di
  oggi stimate a mano: segue meglio percentuali che non sono una retta. Costo: Sotto il cofano spiega una curva, non una formula.
- **Infortunati e squalificati restano a 0**, non tarati: è una regola, non una stima. Costo: i rari rientri a sorpresa restano a 0.
- **Laboratorio invariato:** `verifica_pacchetti` e `verifica_probabili_fonte2` continuano con i numeri di partenza.

## 9. Limiti del server

Il comando legge al massimo ~21.000 righe a stagione (circa 550 giocatori coperti × 38 giornate) e stima 5 numeri: il calcolo è
sotto il secondo; avvio di Python e pandas uno o due secondi, memoria di picco circa 150 MB [stima, da misurare con `--prova` sul
server]. Gira 4 volte al giorno con `nice -n 15` e `timeout 300`, nel blocco di `aggiorna.sh` (mai insieme a un aggiornamento), e
fa il lavoro vero al massimo una volta per giornata misurata. Nessuna richiesta in rete.

## 10. Cosa non è verificato

- Quante giornate ha già il registro sul server e se la 11ª è salvata [da verificare in «Stato dei dati»].
- Date delle giornate 12-18 e quindi quando arrivano 4 giornate (prima misura, verso il 9/12) e 8 (prima accensione possibile,
  verso metà gennaio 2027) [da verificare con il calendario].
- Quanto le probabili di dopo la scadenza spostano oggi la correzione per gruppi sul server [da verificare].
- Tempo e memoria del comando sul server [da misurare dopo la PR A].
- Coefficienti, Brier e calibrazione veri: si sapranno solo al primo verdetto.
