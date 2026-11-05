# Registro delle giornate (L1 di #165) — piano

> **Per chi esegue:** skill `superpowers:executing-plans` (un esecutore, in questa worktree). Passi con `- [ ]`.

**Obiettivo:** poco prima della prima partita di ogni giornata il server salva i numeri mostrati per ogni giocatore della Serie A;
a giornata finita calcola I1-I3, li mostra in «Stato dei dati» (campo dell'API) e avvisa il proprietario quando una media resta
fuori soglia per 2 giornate di fila.

**Architettura:** modulo nuovo `fanta/registro_giornate.py` (funzioni pure + accesso all'archivio), due tabelle nuove
nell'archivio (`archivio.SCHEMA`, solo `CREATE TABLE IF NOT EXISTS`), un passo in più nel thread del pianificatore (una volta al
minuto), un campo `registro` in `stato_dati.riepilogo`. Nessuna richiesta in più alle fonti: si usano `consigli.previsioni` (già in
cache) e le tabelle `partite` e `voti`.

**Strumenti:** Python, SQLite, pandas, pytest. **Spec:** `docs/superpowers/specs/2026-11-05-statistiche-affidabili-proposta.md`
(§2 indicatori I1-I3, §3 L1, §4 decisioni approvate il 5/11).

## Vincoli
- Regole classiche (`Regole()`), come `precisione.pubblico`. Niente dati personali: solo id dei calciatori, numeri, giornate.
- Salvataggio negli ultimi `ANTICIPO = 10 minuti` prima della prima partita della giornata (`avvisi.prima_partita`), una volta sola.
  Non si salvano i giocatori la cui partita è già iniziata (anticipi).
- Finestra `FINESTRA = 8` giornate misurate; verdetto («regge» sì/no) e avviso solo a finestra piena (spec §2: «primo verdetto
  dopo 8 giornate»).
- Soglie (spec §2): I1 = errore quadratico del fantavoto atteso / quello della fantamedia − 1 ≤ −0,03; I2 = errore di
  calibrazione di «gioca N%» (fasce di 10 punti, media pesata) ≤ 0,05 e Brier ≤ 0,15; I3 = punti veri dentro la fascia 8 su 10
  tra 0,72 e 0,88, su 20 rose estratte a sorte (come `verifica --incertezza`: 3 P, 8 D, 8 C, 6 A tra chi ha `p_voto` ≥ 0,3,
  seme `1000 × giornata + anno`, 300 simulazioni).
- Misura a giornata finita: turno giocato (`fasi.fine_giornata`) da almeno 24 ore e voti per entrambe le squadre di ogni partita
  giocata; dopo 72 ore si misura comunque, senza le partite ancora senza voti. Contano solo le partite giocate.
- Avviso: canale del proprietario come la sentinella (`sentinella.manda_ntfy`); una media fuori soglia nella misura di questa
  giornata E della precedente; non si ripete finché resta fuori; se l'invio non riesce si riprova al minuto dopo.
- Interruttore `FANTA_REGISTRO_GIORNATE=0` (spento nei test da `conftest.py`, come `FANTA_COPIA_SCADENZA`); gira solo con il
  pianificatore acceso.
- Non si toccano: `formazione.py`, `consigli.py`, `verifica*.py`, `__main__.py`, `diario.py`, `fanta/web/`, `ios/`.

## Da guardare in revisione
- Archivio vecchio senza le tabelle: `archivio.apri` le aggiunge e non tocca il resto (test in Compito 1).
- Giocatore senza fantamedia (nessun voto prima): vale 6,0 come nella verifica (test in Compito 2).
- Partita rinviata o senza voti: i suoi giocatori non contano; la giornata si chiude lo stesso (test in Compito 2).
- Servizio fermo durante la finestra: la giornata non si salva e non si inventa niente dopo l'inizio (test in Compito 1).
- Canale non configurato o rete giù: l'avviso resta da mandare, nessun errore (test in Compito 3).

---

### Compito 1: tabelle e salvataggio prima della prima partita

**File:** crea `fanta/registro_giornate.py`, `tests/test_registro_giornate.py`; modifica `fanta/archivio.py` (SCHEMA e docstring:
il registro non si ricostruisce).

**Produce:**
- tabelle `registro_giocatori` (stagione, giornata, calciatore_id, ruolo, squadra, partita_id, p_voto, mu, mu_voto, e_gol,
  e_assist, minuti, stato, percentuale, dubbio, fantamedia; chiave stagione+giornata+calciatore_id) e `registro_giornate`
  (stagione, giornata, salvato, giocatori, con_probabili, misurato, voti, sq_modello, sq_fantamedia, presenze, brier_somma,
  fasce, fascia_casi, fascia_dentro, fuori, da_avvisare, avvisati; chiave stagione+giornata);
- `fantamedie(db, stagione, giornata, regole) -> dict[int, float]`;
- `salva(db, stagione, giornata, prev, con_probabili, adesso) -> int` (righe scritte; 0 se la giornata c'è già);
- `da_salvare(db, adesso) -> tuple[str, int] | None`;
- `salva_se_serve(db, adesso, previsioni=None) -> int` (`previsioni(db, regole, giornata)` come `consigli.previsioni`).

- [ ] Test: `test_archivio_vecchio_riceve_le_tabelle_senza_perdere_niente`, `test_salva_i_numeri_mostrati_una_volta_sola`
  (tre giocatori inventati, uno con partita già iniziata: 2 righe, fantamedia giusta, secondo `salva` = 0),
  `test_salva_solo_negli_ultimi_dieci_minuti_prima_della_prima_partita` (11 minuti prima: niente; 10 prima: sì; all'inizio: niente).
- [ ] Vederli fallire, scrivere il codice, vederli passare (`pytest -q tests/test_registro_giornate.py`). Commit.

### Compito 2: misura a giornata finita

**Produce:** `da_misurare(db, adesso) -> list[tuple[str, int]]`; `misura_giornata(db, stagione, giornata) -> dict | None` con
`voti, sq_modello, sq_fantamedia, presenze, brier_somma, fasce` (10 × [n, somma detto, giocati]), `fascia_casi, fascia_dentro`.

- [ ] Test con dati inventati (2 partite, 4 giocatori per numeri a mano + una rosa grande per I3):
  `test_misura_errore_brier_e_fasce_a_mano`, `test_senza_fantamedia_vale_sei`, `test_partita_rinviata_non_conta`,
  `test_si_misura_solo_a_giornata_finita_e_con_i_voti` (prima 24 ore: no; voti mancanti: no fino a 72 ore),
  `test_fascia_su_rose_estratte_a_sorte_e_ripetibile` (stessi numeri due volte, `fascia_casi` = 20).
- [ ] Rosso, codice, verde. Commit.

### Compito 3: medie, soglie, avviso

**Produce:** `medie(righe: list[dict]) -> dict` (i1, errori, brier, calibrazione, copertura, giornate, verdetto, regge, fuori);
`chiudi_giornate(db, adesso) -> list[tuple[str, int]]` (misura, scrive, decide `fuori`/`da_avvisare`/`avvisati`);
`avvisa(db, manda) -> bool`; `testo_avviso(fuori, m) -> tuple[str, str]`; `giro(adesso, db, manda=...)`.

- [ ] Test: `test_medie_sommano_le_giornate_della_finestra` (numeri a mano), `test_nessun_verdetto_prima_di_otto_giornate`,
  `test_avviso_dopo_due_giornate_fuori_soglia_una_volta_sola` (9ª fuori: niente; 10ª fuori: un avviso; 11ª fuori: niente;
  rientra e riesce due volte: nuovo avviso), `test_avviso_non_mandato_si_riprova`, `test_testo_avviso_senza_nomi`.
- [ ] Rosso, codice, verde. Commit.

### Compito 4: thread, Stato dei dati, documenti, novità

**File:** `fanta/pianificatore.py` (`sorveglia`: dopo il giro dei risultati, `_registro(adesso, db)` che non alza mai),
`fanta/stato_dati.py` (`riepilogo` → campo `registro` = `registro_giornate.riepilogo(db)`), `tests/conftest.py`
(`FANTA_REGISTRO_GIORNATE=0`), `tests/test_pianificatore.py`, `tests/test_stato_dati.py`, `docs/API.md`, `MAPPA.md`,
`fanta/novita.d/registro-giornate.json`.

- [ ] Test: `test_il_thread_chiama_il_registro` (acceso: una chiamata; spento: nessuna; un errore non ferma il giro),
  `test_stato_dati_ha_il_registro` (medie e righe per giornata, senza nomi).
- [ ] Rosso, codice, verde. Suite intera, `python -m fanta verifica` (numeri uguali a prima), commit, PR in bozza.
