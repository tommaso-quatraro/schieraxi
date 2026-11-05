# Gol e assist attesi nostri, Understat come metro (L3b di #165): piano

> **Per chi esegue:** skill `superpowers:subagent-driven-development` (consigliata) o `superpowers:executing-plans`, una fase alla
> volta, ognuna nel suo ramo e nella sua PR in bozza. Passi con `- [ ]`.

**Obiettivo:** i gol e gli assist attesi si calcolano con i soli dati di Fantacalcio.it e tornano con i gol veri. Poi si misurano
dal vivo contro la versione con Understat, si mostrano nella scheda del giocatore e infine si toglie Understat.

**Architettura:** la versione «nostra» è lo stesso `modello.previsioni` con i dati di `nostri.dati(d)` (prestazioni ricostruite dai
voti) e i parametri di `nostri.parametri()`. Le correzioni nuove stanno dietro campi di `modello.Parametri` spenti di default, e la
produzione non cambia fino alla Fase G1. Il registro delle giornate salva anche i numeri nostri e misura I4 dal vivo. Quando I4
regge, la produzione passa ai numeri nostri, la scheda li mostra e Understat si toglie.

**Strumenti:** Python, pandas, SQLite, pytest; web senza librerie; SwiftUI con Swift Testing.

**Spec:** `docs/superpowers/specs/2026-11-05-statistiche-affidabili-proposta.md` (§2 I4, §3 L3a e L3b, §4 D2: Understat si toglie
solo quando la misura «solo Fantacalcio.it» regge nel passato **e** per 8 giornate dal vivo). Misura di partenza: PR #332.

## 1. Perché oggi i gol attesi sono bassi (misura del 6/11/2026)

Come: archivio di sviluppo copiato nella cartella `dati/` della worktree (fuori da git), regole della lega d'esempio, 41 giornate
(2025-26 dalla 5ª alla 38ª, 2026-27 dalla 2ª all'8ª). Conto solo chi prende voto, con i numeri di `modello.previsioni` giornata per
giornata (solo dati di prima). Gli script di misura stanno nello scratchpad, non nel repository.

**Come si calcolano oggi** (`fanta/modello.py:_pezzi`):
- `e_gol = gol90 × min(minuti, 90)/90 × fattore`, con `gol90 = (storia + k_90 × partenza) / (minuti/90 + k_90)` e `k_90 = 16`.
  La storia sono gli npxG di Understat (`peso_xg = 1`); senza Understat sono i gol veri su azione. Per un titolare fisso, più della
  metà del peso va alla stima di partenza (retta sulla quotazione o media del ruolo).
- `fattore = gol attesi della squadra oggi / (base × attacco della squadra)`. È la difesa avversaria per il fattore campo: il livello
  del campionato (`base`) si semplifica e non arriva mai ai gol del giocatore.
- Rigori a parte: `e_rigori = quota × rigori a partita × fattore × min(1, minuti/75)`, con `quota = rc_w / (rs_w + 0,5)` e la
  memoria corta dei giocatori (0,92 a giornata, stagione prima 0,5).
- Nei confronti con i gol veri: gol attesi = `e_gol + 0,78 × e_rigori` (`verifica_pacchetti._con_registro`).

| Misura (chi prende voto) | 2025-26 | 2026-27 |
|---|---|---|
| Gol a partita in Serie A (xG di Understat a partita) | 2,43 (2,79) | 3,01 (3,40) |
| Gol attesi / gol veri: con Understat (oggi) · solo Fantacalcio.it | 1,011 · 0,857 | 0,827 · 0,694 |
| … solo Fantacalcio.it, gol su azione · gol su rigore | 0,899 · 0,427 | 0,712 · 0,283 |
| Rigori calciati: attesi contro veri (uguale con e senza Understat) | 40 contro 96 | 3,3 contro 13 |
| Somma delle quote dei rigoristi di una squadra (dovrebbe stare vicino a 1) | da 0,58 a 0,81 | da 0,27 a 0,41 |
| Minuti attesi contro minuti veri di Understat | −6% | −6% |
| Gol su azione, tasso del modello per i minuti veri / gol veri: solo Fantacalcio.it · con Understat | 0,979 · 1,146 | 0,777 · 0,916 |
| Assist attesi / veri: solo Fantacalcio.it · con Understat | 0,863 · 0,956 | 0,805 · 0,874 |
| Scarto più grande per fasce, solo Fantacalcio.it (soglia I4: 0,03) | 0,020 | 0,070 |

Gol attesi / veri, solo Fantacalcio.it: 2026-27 giornate 2-4 0,58, giornate 5-8 0,79. Per ruolo (due stagioni): A 0,83, C 0,79, D 0,88.
Minuti stimati da entrato e uscito: 68,0 a presenza con voto, 19,9 senza voto (il 9,1% delle presenze). Minuti attesi di chi prende
voto: 65,3 contro 69,3 veri.

**Le cause, dalla più sicura:**
1. **Rigori (causa più grande e sicura).** Il modello si aspetta 40 rigori contro 96 calciati, il 42%, con o senza Understat. Un rigore
   è raro (0,14 a squadra a partita): con la memoria corta e il «+0,5», molte squadre restano senza rigorista e la quota del primo
   rigorista è circa 0,5. I rigori sono il 9% dei gol (73 su 806 nel 2025-26), circa 5 dei 14 punti di sottostima del 2025-26.
2. **Minuti (−6%).** La media a presenza conta anche le presenze senza voto, che sono corte. La misura guarda solo chi prende voto.
3. **Livello del campionato.** Nel 2026-27 si segna il 24% in più. I tassi dei giocatori e la stima di partenza guardano soprattutto la
   stagione prima, e il fattore partita non vede il livello. È la parte grossa del 2026-27 (giornate 2-4: 0,58).
4. **Con Understat la media torna solo per compensazione:** con gli xG il tasso è il 15% sopra i gol veri (1,146) e copre i punti 1 e 2.

**Prova fuori dal codice (prototipo, solo misura):** quota dei rigori con memoria lunga, divisa nella squadra, e minuti dalle sole
presenze con voto. Si riporta «gol attesi / veri · scarto per fasce».

| | 2025-26 | 2026-27 |
|---|---|---|
| oggi, solo Fantacalcio.it | 0,857 · 0,020 | 0,694 · 0,070 |
| rigori divisi nella squadra (rigori attesi: 61 contro 96; 9,6 contro 13) | 0,877 · 0,035 | 0,717 · 0,076 |
| … più minuti dalle presenze con voto (minuti attesi da 65,3 a 68,2) | 0,918 · 0,039 | 0,752 · 0,069 |
| invece: un fattore unico tarato sulle giornate prima (memoria 0,95) | 1,028 · 0,088 | 0,833 · 0,060 |

**Perché non si parte da un fattore di taratura unico:** sistema la media ma peggiora le fasce (0,020 diventa 0,088), perché la
sottostima non è uguale per tutti. Copierebbe la compensazione che oggi fanno gli xG. Quindi la «taratura sui gol veri» si fa per
pezzi (rigori, minuti, livello). Un fattore per ruolo resta come ultimo ritocco, solo se le fasce non tornano (Compito C3).

## 2. Vincoli
- **Produzione invariata fino alla Fase G1.** Ogni correzione sta dietro un campo di `Parametri` spento di default. Prima e dopo
  ogni PR delle Fasi A-F, `python -m fanta verifica` deve dare righe identiche. Numeri di partenza [verificato il 6/11, archivio di
  sviluppo, rose della lega d'esempio]: rmse 1,424 (2025-26) e 1,592 (2026-27), fantamedia 1,494 e 1,834, punti 63,241 /
  fantamedia 62,762 / perfetta 66,654.
- Misura I4 nel passato, in ogni PR delle Fasi A-C: `python -m fanta verifica --pacchetti completo,solo_fantacalcio` (rose della lega
  d'esempio, 300 simulazioni) **e** `... --rose-sintetiche 20 --simulazioni 200`. Si scrivono nella PR le colonne `rmse_vs_completo_pct`,
  `vs_completo`, `scarto_gol`, `gol_su_veri`, `rigori_su_veri` e `assist_su_veri`, per stagione.
- Soglie I4 (D1, 5/11): errore del fantavoto al massimo +1% e punti al massimo −0,3 a giornata rispetto alla versione con Understat;
  scarto tra gol attesi e veri al massimo 0,03 in ogni fascia con almeno 50 casi. Dal vivo: media delle ultime 8 giornate misurate
  **con la stessa `nostri.VERSIONE`**.
- Registro: regole classiche `Regole()`, solo id e numeri, niente nomi. Una giornata non salvata in tempo è persa (nessun ricalcolo).
- Test con dati inventati. Comandi uno alla volta, test con `-n 2`:
  `.venv\Scripts\python.exe -m pytest -q -n 2` (un file: `... -m pytest -q tests\<file>.py`).
- Ogni PR che tocca `fanta/` ha un file `fanta/novita.d/<nome>.json`. Finché la produzione non cambia, le `voci` dicono «Nessun
  cambiamento visibile: …» (come la #332).
- Fasi E e G2: web e iPhone uguali (`docs/COERENZA-WEB-IPHONE.md`, skill `ui-schieraxi`). I numeri arrivano dal server e non si
  ricalcolano sul client.
- File comuni (`MAPPA.md`, `docs/API.md`): prima della PR si fa `git merge origin/main` e si risolvono le righe.

## 3. Da guardare in revisione
- **Interruttori spenti, produzione identica:** `verifica` riga per riga uguale in ogni PR delle Fasi A-F. Test
  `test_esegui_completo_identico_alla_verifica_normale` (c'è già) e prima/dopo nella PR.
- **Nessun dato dal futuro** nelle somme nuove (rigori con memoria lunga, livello, medie pesate): test
  `test_rigori_e_minuti_senza_dati_dal_futuro` (B) e `test_livello_senza_dati_dal_futuro` (C).
- **Squadra senza rigori nella storia, giocatore con sole presenze senza voto:** niente NaN né divisioni per zero. Test
  `test_squadra_senza_rigori_quote_zero` e `test_solo_presenze_senza_voto_minuti_di_partenza` (B).
- **Errore nei numeri nostri al momento del salvataggio:** il registro principale salva lo stesso, la giornata dei nostri manca e non
  conta, e nessuna eccezione esce da `giro`. Test `test_errore_dei_nostri_non_ferma_il_registro` (D).
- **`nostri.VERSIONE` cambiata a metà finestra:** il verdetto riparte da zero giornate. Test
  `test_verdetto_solo_con_otto_giornate_della_stessa_versione` (D). Chi cambia `nostri.parametri` o la formula dei nostri alza
  `VERSIONE` nella stessa PR (in revisione si controlla).

## 4. Fasi, aree, ordine

| Fase | PR | Area e file | Dopo | Insieme a |
|---|---|---|---|---|
| A Basi della misura | 1 | server: `fanta/nostri.py` (nuovo), `fanta/verifica_pacchetti.py`, test, `MAPPA.md` | — | — |
| B Taratura sui gol veri: rigori e minuti | 2 | server: `fanta/modello.py`, `fanta/nostri.py`, `tests/test_gol_attesi_nostri.py` | A | D |
| C Forza delle squadre e livello | 3 | server: `fanta/modello.py`, `fanta/nostri.py`, `prove/tara_forza_gol.py`, test | B | D, E |
| D Doppio calcolo nel registro (I4 dal vivo) | 4 | server: `fanta/registro_nostri.py` (nuovo), `archivio.py`, `registro_giornate.py` (solo `giro`), `registro_copia.py`, `stato_dati.py`, `docs/API.md`, `MAPPA.md` | A | B, C |
| E I4 in «Stato dei dati» | 5 | web: `app.js`, `testi.js` · iOS app: `Modelli.swift`, `RegistroGiornateSezione.swift`, test | D | C |
| F Laboratorio senza le statistiche di Understat | 6 | server: `verifica_pacchetti.py`, `verifica_fonti.py`, `__main__.py` (aiuto), test | C | D, E |
| *attesa* | — | 8 giornate dal vivo con la versione della Fase C, e misura nel passato entro soglia | C, D | — |
| G1 Passaggio ai numeri nostri | 7 | server: `modello.py`, `nostri.py`, `consigli.py` (`scheda_previsione`), `registro_giornate.py` (`giro`), Sotto il cofano, `docs/API.md` | attesa, F | — |
| G2 Scheda del giocatore | 8 | web: `app.js`, `testi.js` · iOS app: `SchedaGiocatoreView.swift`, `Modelli.swift`, fixture, test · `docs/GUIDA-UTENTE.md`, `docs/COERENZA-WEB-IPHONE.md` | G1 | — |
| H1 Via la fonte | 9 | server: `fonti/understat.py`, `aggiorna.py`, `archivio.py`, `modello.py`, `scheda.py`, `server.py`, `controlli.py`, `fonti_attive.py`, `listone.py`, `__main__.py`, `nostri.py`, `verifica_pacchetti.py`, test | G2 | — |
| H2 Crediti, testi, documenti | 10 | `testi_legali.py`, `contenuti/sotto-il-cofano*.json` · web: `testi.js` · iOS app: `NomiDati.swift`, fixture, `ios/fotografie/vero-*.json` · `README.md`, `MAPPA.md`, `docs/` | H1 | — |

Nessun compito tocca il widget iOS. La Fase D si può aprire subito dopo A: il conteggio delle 8 giornate riparte a ogni
`VERSIONE`, quindi vale da quando la versione della Fase C gira sul server.

---

## Fase A: basi della misura (PR 1)

### Compito A1: modulo `fanta/nostri.py`
**File:** crea `fanta/nostri.py`, `tests/test_nostri.py`. Modifica `fanta/verifica_pacchetti.py` (importa da `nostri` e tiene gli
stessi nomi: `solo_fantacalcio = nostri.dati`, `minuti_stimati`, `MINUTI_STIMATI`, `FASCE_GOL`, `FASCE_GOL_NOMI`, `MIN_CASI_FASCIA`).

**Produce:**
- `MINUTI_STIMATI`, `minuti_stimati(voti) -> pd.Series`, `FASCE_GOL`, `FASCE_GOL_NOMI`, `MIN_CASI_FASCIA` (spostati senza cambiarli);
- `dati(d: Dati) -> Dati` (oggi `verifica_pacchetti.solo_fantacalcio`, stesso corpo);
- `parametri(par: Parametri | None = None) -> Parametri` (oggi: `replace(par or Parametri(), peso_xg=0.0, peso_xa=0.0)`);
- `VERSIONE: str = "1"`: si alza a ogni cambio di `parametri` o della formula usata dai nostri;
- `gol_attesi(prev: pd.DataFrame, par: Parametri) -> pd.Series` = `e_gol + par.conversione_rigori × e_rigori` (l'unica definizione:
  la usano `_con_registro`, il registro e, nella Fase G1, la scheda);
- `previsioni(d, stagione, giornata, regole, probabili=None, giocatori=None, fattori_probabili=None) -> pd.DataFrame` =
  `modello.previsioni(dati(d), …, par=parametri())`.

- [ ] Test: `test_previsioni_nostre_non_leggono_understat` (xG e minuti di Understat cambiati a caso: stesso risultato),
  `test_parametri_nostri_senza_xg` (`peso_xg == peso_xa == 0`, il resto come `Parametri()`),
  `test_gol_attesi_con_i_rigori` (e_gol 0,20, e_rigori 0,50: 0,59). I test di `tests/test_verifica_pacchetti.py` passano senza cambiarli.
- [ ] Vederli fallire, scrivere, vederli passare. Commit.

### Compito A2: conti dei gol attesi nella tabella dei pacchetti
**File:** `fanta/verifica_pacchetti.py`, `tests/test_verifica_pacchetti.py`, `MAPPA.md` (riga di `nostri.py`),
`fanta/novita.d/gol-attesi-misura.json`.

**Produce:** `_con_registro` raccoglie anche `e_gol`, `e_rigori`, `e_assist`, `minuti` (e `gol_attesi` con `nostri.gol_attesi`).
`conti_attesi(d, regole, previsti) -> pd.DataFrame` dà una riga per stagione («tutte» e ciascuna), solo per chi prende voto, con le
colonne `stagione, casi, gol_su_veri, azione_su_veri, rigori_su_veri, assist_su_veri, minuti_attesi, minuti_stimati`. Qui
`rigori_su_veri` = rigori calciati attesi / calciati veri, `minuti_attesi` = media di `min(minuti, 90)` e `minuti_stimati` =
`nostri.minuti_stimati` delle righe vere. `tabella` aggiunge per scenario e stagione le colonne `gol_su_veri`, `rigori_su_veri` e
`assist_su_veri`.

- [ ] Test `test_conti_attesi_a_mano`: 3 giocatori inventati, 2 con voto e 1 senza (escluso). Attesi su azione 0,3 e 0,1, rigori
  attesi 0,5 e 0, assist attesi 0,2 e 0,2. Veri: 1 gol su azione, 1 rigore segnato su 1 calciato, 0 assist. Risultati:
  `azione_su_veri == 0,4`, `rigori_su_veri == 0,5`, `gol_su_veri == (0,4 + 0,39) / 2`, `assist_su_veri` NaN (nessun assist vero).
- [ ] Rosso, codice, verde. Suite intera. Commit.
- [ ] **Fatto quando:** `verifica` identica (§2). `--pacchetti completo,solo_fantacalcio` dà i numeri di #332 e, nelle colonne nuove,
  quelli del §1 a ±0,005 (`gol_su_veri` 1,011 / 0,827 e 0,857 / 0,694; `rigori_su_veri` circa 0,42 / 0,25 in tutti e due gli
  scenari). PR in bozza, «Parte di #165».

## Fase B: taratura sui gol veri, rigori e minuti (PR 2)

**File (tutta la fase):** `fanta/modello.py`, `fanta/nostri.py` (`parametri` accende i due campi; `VERSIONE = "2"`),
crea `tests/test_gol_attesi_nostri.py` (con un proprio costruttore di dati inventati: due stagioni, due squadre),
`fanta/novita.d/gol-attesi-rigori-minuti.json`.

### Compito B1: rigori con memoria lunga, divisi nella squadra
**Produce:** `Parametri.rigori_squadra: bool = False`, costanti `DECADIMENTO_RIGORI = 0.98`, `PESO_PREC_RIGORI = 0.8`. Acceso,
`quota_rig` prende il posto di `rc_w / (rs_w + 0,5)` e si calcola prima del ciclo sui giocatori:
```
w_r          = DECADIMENTO_RIGORI ** (t0 - t) × (1 se stessa stagione, altrimenti PESO_PREC_RIGORI)   # righe di U prima di data0
rc_lungo[i]  = Σ w_r × rigori_calciati delle presenze di i (con qualunque squadra)
S[T]         = Σ sui giocatori j della squadra T (in g) di p_storico[j] × rc_lungo[j]
quota_rig[i] = rc_lungo[i] / (rc_lungo[i] + S[T] − p_storico[i] × rc_lungo[i])   se rc_lungo[i] > 0, altrimenti 0
```
Il resto di `e_rigori` (rigori a partita × fattore × min(1, minuti/75)) non cambia.

- [ ] Test (interruttore acceso):
  - `test_rigorista_tiene_la_quota_senza_rigori_recenti`: ha calciato i 4 rigori della squadra nella stagione prima, poi 10 giornate
    senza rigori. `e_rigori ≥ 0,9 × rigori_partita × fattore`, e più di quanto dà l'interruttore spento.
  - `test_quote_di_due_rigoristi_sommano_uno`: A con 3 rigori e B con 1, tutti e due sempre in campo. Le quote sommano 1 (±0,05) e A > B.
  - `test_squadra_senza_rigori_quote_zero`: `e_rigori == 0`, niente NaN.
  - `test_rigori_e_minuti_senza_dati_dal_futuro`: un rigore nella giornata da prevedere non cambia niente.
- [ ] Rosso, codice, verde. Commit.

### Compito B2: minuti attesi «se prende voto»
**Produce:** `Parametri.minuti_con_voto: bool = False`. Acceso, subito dopo aver costruito `U` si tengono solo le righe la cui
coppia (`calciatore_id`, `stagione`, `giornata`) ha un voto in `Vv`. Così minuti a presenza, minuti da titolare e da subentro, tasso
per 90' e medie del ruolo guardano tutti le sole presenze con voto.

- [ ] Test: `test_minuti_attesi_solo_dalle_presenze_con_voto` (4 presenze con voto a 90' e 4 senza voto a 10': acceso, `minuti` più
  alto di spento e sopra 80; `e_gol` più alto), `test_solo_presenze_senza_voto_minuti_di_partenza` (niente NaN, minuti dalla
  formula senza presenze), e il caso «nessun dato dal futuro» del Compito B1 esteso ai minuti.
- [ ] Rosso, codice, verde. Suite intera. Commit.
- [ ] **Fatto quando:** `verifica` identica (§2). In `solo_fantacalcio` (prototipo §1 tra parentesi): `rigori_su_veri` almeno 0,60
  in tutte e due le stagioni (0,64 e 0,74), `gol_su_veri` almeno 0,90 e 0,73 (0,918 e 0,752), `minuti_attesi` almeno 67 (68,2).
  `rmse_vs_completo_pct` al massimo 0,1 punti sopra quello di prima (+0,47 e +0,81), `vs_completo` ≥ −0,3. `scarto_gol` si scrive
  ma qui non decide: può salire (prototipo 0,039) e si chiude nella Fase C. PR in bozza.

## Fase C: forza delle squadre e livello del campionato (PR 3)

**File (tutta la fase):** `fanta/modello.py`, `fanta/nostri.py` (`VERSIONE = "3"`), crea `prove/tara_forza_gol.py`,
`tests/test_gol_attesi_nostri.py`, `MAPPA.md` (riga dello script in `prove/`), `fanta/novita.d/gol-attesi-livello.json`.

### Compito C1: forza delle squadre sui soli gol, con il livello recente
**Produce:** `Parametri.decadimento_base: float | None = None`, `Forza.livello: float = 1.0`, costanti `LIVELLO_MIN = 0.8` e
`LIVELLO_MAX = 1.25`. Con `decadimento_base`, `forza_squadre` calcola `base_recente` (media dei gol a squadra a partita, pesi
`decadimento_base ** (t0 − t)` × `peso_stagione_prec_squadre` per la stagione prima) e mette
`livello = clip(base_recente / base, LIVELLO_MIN, LIVELLO_MAX)`. `Forza.gol_attesi` moltiplica i due gol attesi per `livello`. Il
livello va DOPO la stima di attacco e difesa, che altrimenti lo riassorbirebbero. Da qui passa anche ai gol del giocatore (il
`fattore` diventa difesa avversaria × campo × livello), al voto (`beta_voto`) e ai portieri.
`prove/tara_forza_gol.py` prova `decadimento_squadre` {0,95; 0,97; 0,98; 0,99}, `peso_stagione_prec_squadre` {0,5; 0,65; 0,8},
`k_squadre` {2; 3; 5} e `decadimento_base` {nessuno; 0,85; 0,90; 0,95} con i dati di `nostri.dati`. Misura i gol della squadra di ogni
partita (devianza di Poisson media e attesi/veri) sul 2025-26, dalla 5ª giornata, e controlla sul 2026-27. La prima riga è quella
di oggi. I valori scelti vanno in `nostri.parametri`.

- [ ] Test: `test_livello_segue_i_gol_recenti` (20 giornate a 2 gol a partita, poi 5 a 4: `livello > 1` e gol attesi più alti;
  senza `decadimento_base`, `livello == 1` e numeri di oggi), `test_livello_limitato` (salto enorme: 1,25),
  `test_livello_senza_dati_dal_futuro`.
- [ ] Rosso, codice, verde. Lanciare lo script e scrivere nella PR la sua tabella (riga di oggi e riga scelta). Commit.

### Compito C2: medie del ruolo pesate come i giocatori
**Produce:** `Parametri.medie_ruolo_pesate: bool = False`. Acceso, le medie del ruolo (`gol90`, `ass90`, `xg90`, `xa90`, `minuti`)
usano i pesi `U["w"]` dei giocatori invece della somma senza pesi su tutta la storia. Così la stima di partenza segue la stagione
come i giocatori.

- [ ] Test `test_medie_del_ruolo_seguono_la_stagione`: stagione prima a 0,1 gol per 90' e stagione nuova a 0,2 per il ruolo. Il
  giocatore senza storia ha `e_gol` più alto con il campo acceso.
- [ ] Rosso, codice, verde. Commit.

### Compito C3 (solo se serve): taratura per ruolo
Si fa solo se dopo C2, in `solo_fantacalcio` 2025-26, `scarto_gol` > 0,03 o `gol_su_veri` è fuori da 0,95-1,05.
**Produce:** `Parametri.taratura_gol: tuple[tuple[str, float], ...] = ()`, che moltiplica `e_gol` ed `e_assist` del ruolo. I fattori
sono veri / attesi per ruolo, sul 2025-26 soltanto (script `prove/tara_forza_gol.py --ruoli`), e si controllano sul 2026-27.
- [ ] Test `test_taratura_tocca_solo_il_suo_ruolo`. Rosso, codice, verde. Commit.

- [ ] **Fatto quando (= I4 nel passato):** `verifica` identica (§2). In `solo_fantacalcio`, in tutte e due le stagioni:
  `rmse_vs_completo_pct` ≤ +1 e `vs_completo` ≥ −0,3 (rose sintetiche e, per il 2026-27, rose d'esempio). Nel 2025-26
  `scarto_gol` ≤ 0,03 e `gol_su_veri` tra 0,95 e 1,05; nel 2026-27 si scrive lo scarto (se resta sopra 0,03: scelta S2). La riga
  `solo_fantacalcio` con le rose d'esempio e 300 simulazioni va nella PR: è quella che `verifica` deve ridare nella Fase G1.
  `VERSIONE` alzata. PR in bozza.

## Fase D: doppio calcolo nel registro, I4 dal vivo (PR 4, insieme a B e C)

**File:** crea `fanta/registro_nostri.py`, `tests/test_registro_nostri.py`. Modifica `fanta/archivio.py` (SCHEMA, due tabelle
nuove con `CREATE TABLE IF NOT EXISTS`, così gli archivi vecchi le ricevono senza `ALTER`), `fanta/registro_giornate.py` (solo
`giro`: tre passi in più), `fanta/registro_copia.py` (`TABELLE` più le due nuove), `tests/test_registro_copia.py`,
`fanta/stato_dati.py` (campo `registro_nostri`), `tests/test_stato_dati.py`, `docs/API.md`, `MAPPA.md`,
`fanta/novita.d/registro-gol-attesi-nostri.json`. Non tocca `modello.py` né `nostri.py`: li usa e basta.

**Produce:**
- tabella `registro_nostri` (stagione, giornata, calciatore_id, versione, p_voto, mu, mu_voto, e_gol, e_rigori, e_assist, minuti,
  e_rigori_mostrati; chiave stagione+giornata+calciatore_id) e tabella `registro_i4` (stagione, giornata, versione, misurato, voti,
  sq_nostri, sq_mostrati, rose, punti_nostri, punti_mostrati, fasce, fasce_mostrati, avvisato; chiave stagione+giornata).
  `fasce` = 6 × [casi, somma attesi, somma veri] con `nostri.FASCE_GOL`, in JSON;
- `previsioni_dal_vivo(db, giornata) -> pd.DataFrame` (indice id): `nostri.previsioni` con `consigli.dati(db)`, le probabili della
  giornata e `stato_dati.fattori`, come `consigli._calcola_previsioni`;
- `salva_se_serve(db, adesso, previsioni_nostre=None) -> int`: se la giornata è già in `registro_giornate` con `salvato`, non è in
  `registro_nostri` e la prima partita non è iniziata, salva i numeri nostri dei soli giocatori già in `registro_giocatori`, con
  `nostri.VERSIONE` ed `e_rigori` mostrato (da `consigli.previsioni`, in cache);
- `misura_giornata(db, stagione, giornata) -> dict | None`: solo per le partite giocate e con i voti (`registro_giornate._partite`).
  Calcola gli errori quadratici di chi prende voto con `registro_giornate.fantavoto_vero`, le fasce dei gol attesi (`nostri.gol_attesi`
  contro gol + rigori segnati) e i punti. I punti usano le stesse 20 rose estratte a sorte di I3 (stesso seme, stesso gruppo): per
  ognuna, formazione migliore con i numeri mostrati e con i nostri, e punti veri di tutte e due (`formazione.migliore`, `punteggio`);
- `chiudi_giornate(db, adesso) -> list[tuple[str, int]]`: misura le giornate già misurate da `registro_giornate` che hanno numeri
  nostri e non hanno ancora la riga in `registro_i4`;
- `medie(righe: list[dict]) -> dict`: `giornate`, `versione`, `errore_pct = √(sq_nostri / sq_mostrati) − 1`,
  `punti = (Σ punti_nostri − Σ punti_mostrati) / Σ rose`, `scarto_gol` (fasce sommate, solo quelle con almeno `MIN_CASI_FASCIA` casi),
  `gol_su_veri`, `verdetto` (8 giornate della versione di oggi), `regge` {errore, punti, gol} e `regge_tutto`;
  `SOGLIE = {"errore": 0.01, "punti": -0.3, "scarto_gol": 0.03}`, `FINESTRA = 8`;
- `avvisa(db, manda) -> bool`: la prima volta che `regge_tutto` è vero per una versione, un avviso al proprietario (canale della
  sentinella). Titolo «SchieraXI: gol attesi nostri»; testo con versione, i tre numeri e «si può passare alla Fase G1 del piano
  2026-11-06-gol-attesi-nostri»; niente nomi. Se non parte, si riprova al giro dopo. «Fuori soglia» qui non avvisa: all'inizio lo
  sarà di sicuro;
- `riepilogo(db) -> dict` per «Stato dei dati»: versione, soglie, medie, una riga per giornata (al massimo 38), niente nomi.

- [ ] Test (dati inventati, come `tests/test_registro_giornate.py`): `test_salva_i_nostri_numeri_insieme_ai_mostrati`,
  `test_non_salva_dopo_l_inizio_della_prima_partita`, `test_misura_errore_punti_e_fasce_a_mano`,
  `test_verdetto_solo_con_otto_giornate_della_stessa_versione` (7 della versione «3» e 1 della «2»: nessun verdetto),
  `test_avviso_una_volta_quando_regge`, `test_errore_dei_nostri_non_ferma_il_registro`, `test_riepilogo_senza_nomi`,
  `test_copia_notturna_porta_le_tabelle_nuove`.
- [ ] Rosso, codice, verde. Suite intera. `verifica` identica. Commit, PR in bozza.
- [ ] **Fatto quando**, dopo l'unione: alla prima giornata, in `GET /api/stato-dati`, `registro_nostri` ha una riga salvata e poi
  misurata (lo controlla il coordinatore).

## Fase E: I4 in «Stato dei dati» (PR 5, web e iOS, dopo D)

**File:** web `fanta/web/app.js` (accanto a `cartaRegistro`), `fanta/web/testi.js` (chiavi `sd.i4_*` in italiano e inglese). iOS
app: `ios/Sources/Domain/Modelli.swift` (campo facoltativo `registroNostri`), `ios/Sources/Presentation/Lega/RegistroGiornateSezione.swift`,
un test Swift (Swift Testing) di decodifica con fixture inventata. Poi `docs/COERENZA-WEB-IPHONE.md` (una riga).

**Cosa si vede**, uguale sui due lati, solo per chi amministra: un blocco «Gol attesi nostri (I4)» con «N/8 giornate · versione V»,
errore del fantavoto «+0,6%», punti «−0,1 a giornata», scarto per fasce «0,02», gol attesi / veri, e «Regge» o «Non ancora» per ogni
soglia. Sotto, le giornate (come le righe del registro). Prima di 8 giornate: «Verdetto dopo 8 giornate».

- [ ] Test Swift prima del codice. Codice web e iOS. `collaudo-web` a 390, 768, 1024 e 1440 px, chiaro e scuro, con un registro
  inventato di 3 e di 8 giornate: niente «undefined» o «NaN», numeri con la virgola. `ios / test` verde. Foto da fare: «Stato dei
  dati», se c'è in `screenshot.yml` [da verificare]. Commit, PR in bozza.

## Fase F: laboratorio senza le statistiche di Understat (PR 6, dopo C)

Serve prima della Fase G1: quando `modello.carica` non legge più le prestazioni di Understat, `verifica_pacchetti.tabella_fatti`
(tiri, passaggi chiave, xG) si romperebbe.
**File:** `fanta/verifica_pacchetti.py`, `fanta/verifica_fonti.py`, `fanta/__main__.py` (solo testi d'aiuto), test,
`fanta/novita.d/laboratorio-senza-understat.json`.
**Cambia:** via gli scenari che usano tiri, passaggi chiave o xG dei giocatori come fatti: `voto_stat`, `pacchetto_b`,
`pacchetto_b_xg`, `pacchetto_c`, `sportmonks_starter`. `tabella_fatti` non legge più `d.prestazioni`: `min90` viene da
`nostri.minuti_stimati`, e cambiano un poco `voto_eventi` e `pacchetto_a` (numeri prima/dopo nella PR). In `verifica_fonti` resta
`xg_fd` (xG di squadra di football-data nella forza, che resta generica); via `tiri_porta`, che mescola gli xG di Understat.
`senza_xg` e `solo_fantacalcio` restano fino alla Fase H1: servono al confronto della Fase G1.
- [ ] Test aggiornati: gli scenari rimasti girano, uno tolto dà «scenario sconosciuto». `verifica` identica (§2). PR in bozza.

## Attesa: quando si passa alla Fase G1
Servono tutte e tre: (1) Fase C chiusa con I4 nel passato entro soglia (o scelta S2); (2) avviso «gol attesi nostri» del registro,
cioè 8 giornate dal vivo con la versione della Fase C entro le tre soglie; (3) Fase F unita e nessuna PR delle Fasi B-C aperta. Il
coordinatore avvia G1 lontano dalla scadenza della giornata: in G1 cambiano tutti i numeri mostrati.

## Fase G1: la produzione passa ai numeri nostri (PR 7)

**File:** `fanta/modello.py`, `fanta/nostri.py`, `fanta/consigli.py` (solo `scheda_previsione`), `fanta/registro_giornate.py`
(`giro`: tolti i tre passi dei nostri; tabelle e `riepilogo` restano come storia), `fanta/contenuti/sotto-il-cofano.json` e `.en.json`,
`docs/SOTTO-IL-COFANO.md`, `docs/API.md`, `docs/API-SOTTO-IL-COFANO.md`, test, `fanta/novita.d/gol-attesi-nostri.json`.

**Produce:**
- `modello.prestazioni_da_voti(voti, partite) -> pd.DataFrame` (il corpo di `nostri.dati`). `carica` non legge più
  `prestazioni`/`partite_understat`: tiene le colonne `xg_casa` e `xg_trasferta` vuote, che servono a `verifica_fonti`;
- default di `Parametri` = i valori di `nostri.parametri` (gli interruttori restano fino a H1); `nostri.dati` usa
  `modello.prestazioni_da_voti` e `nostri.parametri` restituisce i default, ormai uguali;
- `scheda_previsione`: campi nuovi `gol_attesi_con_rigori` (`nostri.gol_attesi`, 2 decimali) e `minuti_attesi` (intero,
  `min(minuti, 90)`). Gli altri campi non cambiano.

- [ ] Test: `test_carica_senza_tabelle_di_understat`, `test_scheda_ha_gol_attesi_con_rigori_e_minuti`, e i test di Sotto il cofano
  verdi con i nuovi punti di codice.
- [ ] Rosso, codice, verde. Suite intera.
- [ ] **Fatto quando:** `verifica` dopo = la riga `solo_fantacalcio` della Fase C (stesse rose, 300 simulazioni) e prima = numeri del
  §2, tutti e due nella PR. `--pacchetti completo,solo_fantacalcio` dà due righe uguali. Voce di novità per l'utente: i gol attesi e il
  fantavoto atteso si calcolano solo con i voti di Fantacalcio.it e possono cambiare di poco. PR in bozza.

## Fase G2: la scheda del giocatore (PR 8, web e iOS)

**File:** web `fanta/web/app.js` (scheda, oggi righe ~1700-1713), `fanta/web/testi.js`. iOS app:
`ios/Sources/Presentation/Mercato/SchedaGiocatoreView.swift` (`rendimento(_:)` e blocco `avanzate` di `statistiche(_:)`),
`ios/Sources/Domain/Modelli.swift` (`golAttesiConRigori: Double?`, `minutiAttesi: Int?`; via `StatisticheAvanzate` e il rendimento
se non servono altrove), `ios/Tests/Fixtures/giocatore.json`, un test Swift. Poi `docs/GUIDA-UTENTE.md` e `docs/COERENZA-WEB-IPHONE.md`.

**Cosa cambia (D2):** spariscono la carta «Gol e assist rispetto alle occasioni» (web) / «Rende sopra o sotto le occasioni?» (iPhone)
e il blocco «Statistiche avanzate» (xG, xA, tiri e stagioni precedenti). In «Tutte le statistiche», sotto «Stagione», arriva
«Prossima partita» con tre tessere come le altre: «gol attesi» (`gol_attesi_con_rigori`, 2 decimali), «assist attesi»
(`assist_attesi`, 2 decimali) e «minuti attesi» (`minuti_attesi` e «'»). Non ci sono quando non c'è la previsione, quando il giocatore
è fuori o quando la partita è iniziata (stesse condizioni delle probabilità della carta in alto). Le chiavi di `testi.js` usate solo
dai blocchi tolti si tolgono (prima un grep).

- [ ] Test Swift prima del codice (decodifica dei campi nuovi; le tre tessere solo prima della partita). Codice web e iOS.
- [ ] `collaudo-web` a 390, 768, 1024 e 1440 px, chiaro e scuro, scheda di un attaccante, un portiere e un giocatore fuori, con la
  lega d'esempio. `ios / test` verde. Foto da fare: scheda del giocatore (nome in `screenshot.yml` [da verificare]). PR in bozza.

## Fase H1: via la fonte (PR 9)

**File:** cancella `fanta/fonti/understat.py`, i suoi test ed estratti in `tests/dati/`, e `fanta/nostri.py` (`registro_nostri` tiene
solo le funzioni di lettura). Modifica `fanta/aggiorna.py` (passo Understat, `understat_id`), `fanta/archivio.py` (niente più
tabelle di Understat negli archivi nuovi; quelle che ci sono restano: S3), `fanta/modello.py` (via i percorsi xG/xA del giocatore,
`XG_RIGORE`, `peso_xg`, `peso_xa` e gli interruttori, che restano sempre accesi), `fanta/verifica_pacchetti.py` (via `senza_xg` e
`solo_fantacalcio`, ormai uguali a `completo`), `fanta/scheda.py` (via `avanzate` e `rendimento`), `fanta/server.py` (riga di
`rendimento`), `fanta/controlli.py` (via `somma_xg`), `fanta/fonti_attive.py` (via `understat`), `fanta/listone.py`
(`nomi_completi`: scelta S1), `fanta/__main__.py` (scheda a terminale), test, `fanta/novita.d/via-understat.json`.
- [ ] Prima: `prove/misura_nomi.py --vero` (scelta S1) e grep di `understat`, `xg`, `xa` in `fanta/` e `tests/`. Dopo lo stesso grep
  trova solo `xg_casa`/`xg_trasferta` (forza generica) e la storia in `novita.json`.
- [ ] Suite intera. **Fatto quando:** `verifica` identica alla Fase G1, prima e dopo nella PR. `GET /api/giocatore/{id}` senza
  `avanzate` e `rendimento` (scritto in `docs/API.md`: i client li trattano già come facoltativi). PR in bozza.

## Fase H2: crediti, testi e documenti (PR 10)

**File:** `fanta/testi_legali.py` (crediti) con `tests/test_legale.py` e `tests/test_legale_dati.py`. Prima si controlla se serve
cambiare la data «aggiornato» [da verificare in `tests/test_legale.py`]. Poi `fanta/contenuti/sotto-il-cofano.json` e `.en.json`
(fonti, rischio), `docs/SOTTO-IL-COFANO.md`, `docs/API-SOTTO-IL-COFANO.md`, `README.md`, `MAPPA.md`, `docs/API.md`; web
`fanta/web/testi.js` (`sd.f_understat`, `sd.ctl_xg`); iOS app `ios/Sources/Domain/NomiDati.swift`, `ios/Tests/Fixtures/giocatore.json`,
`ios/Tests/SchieraxiTests/LegaViewModelTests.swift`, `ios/fotografie/vero-*.json` (si tolgono i campi `avanzate`, o si rifanno con
`prove/fotografie_dal_vero.py`).
- [ ] Grep finale di «Understat» in tutto il repository: resta solo la storia (`novita.json`, spec, piani). `ios / test` verde. PR in bozza.

---

## 5. Rischi
1. **Si toglie una compensazione e ne nasce un'altra:** gol attesi più alti alzano il fantavoto atteso di tutti, e l'errore del
   fantavoto può peggiorare. Freno: in B e C, `rmse_vs_completo_pct` è un cancello in ogni PR.
2. **Inizio di stagione:** con il 24% di gol in più nelle giornate 2-4 nessuna stima fatta prima ci arriva. Anche con Understat lo
   scarto per fasce del 2026-27 è 0,114. La soglia assoluta 0,03 può non tornare a inizio stagione: scelta S2.
3. **Taratura sul 2025-26 controllata solo su 7 giornate del 2026-27:** il controllo vero è la misura dal vivo (8 giornate).
4. **Rumore della misura dei punti dal vivo:** 20 rose a giornata, confronto a coppie sulle stesse rose. Lo scarto tipico della media
   su 8 giornate non è misurato [da verificare dopo le prime giornate]. Se balla troppo, si alzano le rose (costo di calcolo).
5. **`VERSIONE` dimenticata:** numeri di due versioni nella stessa finestra. Freno: regola in revisione (§3) e test D.
6. **Squadre senza rigori nella storia** (neopromosse a inizio stagione): quota zero, rigori sottostimati (scelta mia, sotto).
7. **Cosa si perde togliendo Understat, oltre alla scheda:** nomi per esteso nella ricerca e nell'importazione delle rose (S1); gli
   scenari di laboratorio che usano tiri e passaggi chiave (Fase F). I numeri storici restano nei documenti di misura.
8. **G1 cambia tutti i numeri mostrati:** la consigliata stabile cambia solo con almeno 1 punto in più, ma qualche avviso «cambia la
   formazione» può partire. Per questo G1 si unisce lontano dalla scadenza.

## 6. Scelte

### Per il proprietario (e quando)
- **Adesso:** niente di obbligatorio. Il piano segue D2 come approvata il 5/11.
- **S2, alla fine della Fase C** (solo se succede): se lo scarto per fasce torna nel 2025-26 ma non nel 2026-27, per un inizio di stagione
  che anche Understat sbaglia (0,114), la misura nel passato si giudica sul solo 2025-26 e dal vivo resta 0,03 assoluto?
  Raccomandazione: sì. È una revisione di D1, quindi decidi tu.
- **S4, prima della fine della Fase C** (facoltativa): una copia dell'archivio del server, solo dati di calcio e fuori da git, per
  rifare la misura nel passato con le giornate del 2026-27 dopo l'8ª. Rende la misura più solida; senza, si va avanti lo stesso.
- **Dopo l'avviso «gol attesi nostri»** (8 giornate dal vivo dalla versione della Fase C: verso gennaio 2027 [da verificare con il
  calendario]): niente da fare. Il coordinatore avvia G1, G2 e H secondo D2.
- **S1, prima della Fase H1:** i nomi per esteso vengono oggi da Understat e servono alla ricerca per nome e all'importazione delle rose.
  (a) Si perdono; (b) si continua a leggere la tabella già nell'archivio, senza scaricarla più (i giocatori nuovi non avranno il nome
  per esteso). Raccomandazione: (a), dopo la misura `prove/misura_nomi.py --vero` che dice quanti nomi cambiano. Se Fantacalcio.it dà
  già i nomi per esteso [da verificare], il problema sparisce.
- **S3, prima della Fase H1:** le tabelle di Understat nell'archivio del server restano (scelta di default, nessuna cancellazione) o si
  tolgono (è una cancellazione: serve il tuo ok)? Raccomandazione: restano fino al passaggio di stagione.

### Mie (le può cambiare il proprietario)
- Produzione invariata fino a G1, con le correzioni dietro interruttori, perché così l'errore di una fase non arriva all'utente.
  Costo se sbagliata: G1 cambia tutto in una volta, invece che a piccoli passi.
- Tabelle nuove per il registro dei nostri, invece di colonne in più in quelle che ci sono: l'archivio non ha un modo per aggiungere
  colonne. Costo: due tabelle in più nella copia notturna.
- Punti dal vivo sulle stesse 20 rose di I3, confrontate a coppie: niente costo di calcolo nuovo per le rose. Costo: rumore (rischio 4).
- Niente ripiego per le squadre senza rigori nella storia, finché la misura non lo chiede. Costo: rigori un po' bassi a inizio stagione.

## 7. Cosa non è verificato
- I numeri del prototipo (§1) sono stati calcolati fuori dal modello. Per i compagni di squadra hanno usato `p_voto` della giornata;
  il piano usa `p_storico`, che si conosce prima del ciclo. I numeri veri si vedono nelle Fasi B e C.
- Le soglie «fatto quando» di B vengono dal prototipo, non da una prova del codice.
- Archivio di sviluppo fino all'8ª giornata del 2026-27: il server ne ha di più (S4).
- Tempo di calcolo dei numeri nostri e delle 20 formazioni in più a ogni giornata sul server [da misurare nella Fase D].
- Nomi delle schermate in `screenshot.yml` per le foto di E e G2 [da verificare].
- Calendario della Serie A per stimare quando arrivano le 8 giornate [da verificare].
