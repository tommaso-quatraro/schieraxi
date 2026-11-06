# Il lavoro del coordinatore diventa codice (ondata 1): piano

> **Per chi esegue:** skill `superpowers:subagent-driven-development` o `superpowers:executing-plans`. Tre lavori in parallelo,
> uno per agente, ognuno nel suo ramo e nella sua PR in bozza: **T1** strumenti della squadra, **T2** controlli delle PR in CI,
> **T3** coerenza web-iPhone come dati. Passi con `- [ ]`. I confini dei file (§3) non si superano.

**Obiettivo:** i passi che il coordinatore ripete a mano (stato, attese, annullamenti, pulizia, brief, foto, «pronta per
l'unione») diventano comandi con parametri e test; le regole che oggi si controllano a occhio diventano controlli automatici.
Niente spazio per errori o messaggi fuorvianti, e lo stesso metodo vale per chiunque contribuisca.

**Perché:** il 5-6/11 molti errori sono nati da passi fatti a mano: un `&&` che non controllava `mergeable` (jq esce 0 anche con
`CONFLICTING`), corse iOS annullate per sbaglio (anche `workflow_dispatch`), righe doppie in `docs/COERENZA-WEB-IPHONE.md` dopo le
unioni (`merge=union` duplica in silenzio), novità di altre PR ripubblicate, test che leggevano una novità per nome, brief
riscritti ogni volta, messaggi «nessuna novità» ripetuti.

**Strumenti:** Python 3.12 della sola libreria standard (niente dipendenze nuove), `gh` e `git` come comandi esterni, pytest.

## 1. Regole comuni

- Ogni comando che cambia qualcosa (annulla corse, toglie worktree, toglie la bozza, rilancia controlli) **di default fa solo la
  prova** e stampa cosa farebbe; agisce solo con `--esegui`.
- Nessun comando unisce una PR né fa push su `main` (lo vietano anche le regole di `.claude/settings.json`).
- `gh` e `git` si chiamano da **una sola funzione** per comando (iniettabile), così i test usano risposte finte e non toccano
  GitHub. Nessun test chiama la rete.
- Le uscite per le persone sono in italiano semplice; ogni comando ha anche `--json` per gli altri script.
- Codici di uscita documentati nel `--help`, mai «0 vuol dire tutto e niente» (l'errore di jq).
- Repository pubblico: niente indirizzi, nomi, token. Ciò che è privato arriva da variabili d'ambiente o da file fuori da git
  (es. `SCHIERAXI_URL` per l'indirizzo del server, letto solo se c'è).
- Lo stato salvato fra due giri (per dire solo ciò che è cambiato) sta in `.superpowers/squadra/` (già ignorata da git).

## 2. Cosa si costruisce

### T1. `script/squadra/`: i comandi del coordinatore
Entrata unica: `python script/squadra/squadra.py <comando> [opzioni]`. Moduli piccoli, un file per comando.

| Comando | Cosa fa | Note |
|---|---|---|
| `stato` | Una tabella: PR aperte (numero, titolo, bozza, `mergeable`, controlli verde/rosso/in corso, gruppo, età), tetti per gruppo (`server-web` n/4, `ios` n/3; le PR di soli documenti non contano), corse sui Mac in corso o in coda, issue aperte per obiettivo (sotto-issue di #165-#168), worktree locali (ramo, unito o no, modifiche). | Gruppi e tetti da `aree.json`. |
| `attendi <PR>` | Guarda **solo l'ultima corsa** del commit in testa alla PR, stampa solo quando cambia qualcosa, esce quando la PR è unita o c'è da fare. | Uscite: 0 unita; 2 conflitto (`DIRTY`); 3 rosso vero; 4 guasto d'infrastruttura (da rilanciare); 5 tempo scaduto. Intervallo e tempo massimo come parametri. |
| `annulla-superate` | Annulla le corse in coda o in corso partite da `push` o `pull_request` su un commit che non è più la testa del suo ramo. | **Mai** `workflow_dispatch` né `schedule` (prove rosse volute, foto). Test che lo provano. |
| `pulisci` | Elenca le worktree di `.claude/worktrees/` in tre gruppi: da togliere (ramo unito, cioè PR `MERGED` o commit già in `main`, e niente modifiche), con modifiche (da chiedere all'utente), senza PR. Con `--esegui` toglie solo il primo gruppo: `git worktree remove` senza `--force`, poi il ramo locale. | Le worktree bloccate da un agente vivo non si toccano. |
| `brief <issue>` | Riempie il modello `script/squadra/modello-brief.md` (copia pubblica del modello della squadra) con titolo e «fatto quando» dell'issue, agente, modello, ramo, e «Puoi toccare / NON toccare» presi da `aree.json` secondo le etichette dell'issue. | `--agente`, `--modello`, `--ramo`, `--tocca` per correggere. Stampa il brief, non lancia nulla. |
| `foto <PR>` (o `--da <commit>`) | Dai file iOS cambiati ricava le schermate da fotografare con `script/squadra/foto.json` (percorso → nomi di `ios/scripts/screenshot.sh`) e stampa il comando `gh workflow run screenshot.yml …`. Con `--lancia` lo lancia. | File iOS senza schermata in `foto.json` → avviso, non silenzio. |
| `pr-pronta <PR>` | Toglie la bozza **solo se** tutto torna: `mergeable` uguale a `MERGEABLE` (confronto esatto della stringa), controlli verdi sul commit in testa, descrizione e revisione a posto (stesse funzioni di T2), novità solo della PR, coerenza generata uguale ai dati (comando di T3), «Foto da fare» presente se la PR tocca `ios/`. Altrimenti stampa ogni motivo e esce con 1. | Usa le funzioni di `script/ci/controlla_pr.py` (T2) e `script/coerenza.py --controlla` (T3): si fa per ultimo, dopo che T2 e T3 sono su `main` (`git merge origin/main` nel ramo). |
| `giro` | La procedura fissa del coordinatore in un comando: `stato`, PR in conflitto, corse fallite per infrastruttura (rilancio con `--esegui`), `annulla-superate`, `pulisci` (solo prova), versione in produzione se `SCHIERAXI_URL` c'è. Confronta con il giro di prima e **stampa solo ciò che è cambiato**; «nessun cambiamento» solo con `--tutto`. | Uscita 0 niente di nuovo, 10 c'è qualcosa da guardare. |

Dati che T1 crea e possiede:
- `script/squadra/aree.json`: per ogni area (`server`, `web`, `ios`, `sito`, `ci`, `docs`, `test`) i percorsi (`fanta/web/**` →
  web, `fanta/**` → server, `script/server/**` → server, `requirements*` → server, `ios/**` → ios, `sito/**` → sito,
  `.github/**`, `script/ci/**`, `script/controlli/**`, `script/squadra/**` → ci, `docs/**` e `*.md` → docs, `tests/**` → test),
  il gruppo del tetto (`server-web`: server, web, sito, ci; `ios`: ios) e le aree «neutre» (docs, test: non cambiano il gruppo).
  Una PR che tocca `ios` e un'altra area di gruppo conta nel gruppo `ios`. Il primo percorso che corrisponde vince.
- `script/squadra/foto.json` e `script/squadra/modello-brief.md`.
- `script/squadra/LEGGIMI.md`: un paragrafo per comando, con un esempio.

### T2. Controlli delle PR in CI (`script/ci/controlla_pr.py`)
Funzioni pure, usate dal job in CI e da `pr-pronta`:
- `descrizione(corpo)`: le sezioni «Cosa cambia», «Perché», «Come l'ho provato» ci sono e non sono vuote (i commenti HTML del
  modello non contano). `Closes #N` o `Parte di #N` mancante: solo avviso (le correzioni di una riga non hanno issue).
- `revisione(corpo)`: sezione nuova «## Revisione» con almeno una riga `- <chi>: <esito>` (es. `- revisore: nessun rilievo
  bloccante`). Obbligatoria quando la PR **non** è in bozza. Esenti: bot e PR di soli documenti.
- `novita(file_cambiati_con_stato)`: in `fanta/novita.d/` al massimo **un** file, solo **aggiunto** (niente file di altre PR
  modificati o tolti); `fanta/novita.json` non si tocca a mano.
- `test_per_nome(cartella_tests)`: nessun test apre un file `fanta/novita.d/<nome>.json` per nome (il job `rilascia` lo sposta e
  il test diventa rosso su `main`). Il test di oggi che lo fa (`tests/test_grafica_b_web.py`) si corregge cercando per titolo
  sia in `novita.d` sia in `novita.json` senza nome di file, o leggendo una novità finta in `tests/dati/`.
- L'ambito di oggi (`controlla_ambito.py`, «per ora solo avvisi») diventa **bloccante**.

In CI: un passo nel job `ambito` di `.github/workflows/test.yml` (o un job nuovo nello stesso workflow, perché `unisci` lo possa
aspettare con `needs`). Gli script si prendono da `main` come oggi (`_ci-main`): un controllo nuovo vale dalla PR dopo la sua
unione, e se manca su `main` il passo salta e lo dice. Il corpo della PR arriva solo come variabile d'ambiente, mai dentro un
comando. Valutare se aggiungere `edited` ai tipi di evento solo per questo job (la descrizione cambia dopo la revisione) senza
rilanciare tutta la suite: scelta di T2, scritta nella PR.
Anche: `.github/pull_request_template.md` con la sezione «## Revisione»; `docs/METODO.md` (una riga per controllo).
Dopo il ramo, oltre alla revisione normale, il coordinatore lancia `agentic-actions-auditor` sui workflow toccati.

### T3. Coerenza web-iPhone come dati
- Dati in `docs/coerenza/`: `vocabolario.json` (righe: cosa, forma giusta, mai), `ammesse.json` (differenze volute con il
  motivo) e un file per schermata in `docs/coerenza/schermate/<schermata>.json` con le differenze aperte e chiuse (id stabile,
  web, iPhone, forma giusta, stato `da-fare` / `fatto` / `da-decidere`, chi la sistema: issue o PR). Un file per schermata così due
  PR su schermate diverse non si toccano.
- `script/coerenza.py`: `--scrivi` genera `docs/COERENZA-WEB-IPHONE.md` dai dati (le parti di testo fisse, regola e controlli,
  stanno in un modello nello stesso script o in `docs/coerenza/testa.md`); `--controlla` esce con 1 se il `.md` non è quello
  generato, se un id è doppio, se una riga è ripetuta, se manca un campo o uno stato è sconosciuto.
- `tests/test_coerenza_dati.py` lancia gli stessi controlli (così la CI li fa senza job nuovi).
- `.gitattributes`: via `merge=union` per il `.md` (duplicava in silenzio). Un conflitto sul `.md` si risolve rigenerandolo
  (`python script/coerenza.py --scrivi`) dopo aver unito i dati; scritto in testa al `.md` generato e in `docs/METODO.md`.
- Il contenuto di oggi passa nei dati **senza perdite** (stesso testo, stesso ordine): il `.md` generato al primo passo deve dire
  le stesse cose di quello di adesso; le differenze di forma (spazi, ordine delle colonne) vanno spiegate nella PR.
- `CLAUDE.md` (riga «Ogni modifica a una schermata…») e `docs/METODO.md`: «si cambiano i dati, non il `.md`».

## 3. Confini dei file (nessuno tocca i file degli altri)

| Agente | Può toccare | Non tocca |
|---|---|---|
| T1 | `script/squadra/**`, `tests/test_squadra_*.py`, `MAPPA.md` (una riga per la cartella nuova) | `script/ci/`, `.github/`, `docs/coerenza/`, `docs/COERENZA-WEB-IPHONE.md`, `fanta/`, `ios/` |
| T2 | `script/ci/controlla_pr.py`, `script/ci/controlla_ambito.py`, `tests/test_controlla_pr.py`, `tests/test_controlla_ambito.py`, `tests/test_grafica_b_web.py` (solo la lettura della novità), `.github/workflows/test.yml`, `.github/pull_request_template.md`, `docs/METODO.md` (righe dei controlli) | `script/squadra/`, `docs/coerenza/`, `fanta/`, `ios/` |
| T3 | `docs/coerenza/**`, `docs/COERENZA-WEB-IPHONE.md`, `script/coerenza.py`, `tests/test_coerenza_dati.py`, `.gitattributes` (la riga del `.md`), `CLAUDE.md` (la riga della coerenza), `docs/METODO.md` (righe della coerenza) | `script/squadra/`, `script/ci/`, `.github/`, `fanta/`, `ios/` |

`docs/METODO.md` lo toccano T2 e T3 in sezioni diverse: chi arriva secondo fa `git merge origin/main` e tiene tutte e due.
Nessuna di queste PR tocca `fanta/`, quindi **niente file di novità**.

## 4. Compiti

### T1
- [ ] T1.1 `aree.json` + `aree.py` (file → area → gruppo) con test sui casi di §2 (ios + web = gruppo ios; solo docs = nessun tetto).
- [ ] T1.2 Funzione unica per `gh`/`git` con risposte finte nei test; `stato` (tabella e `--json`).
- [ ] T1.3 `attendi` con i cinque codici di uscita, provati con sequenze di risposte finte.
- [ ] T1.4 `annulla-superate`: test che una corsa `workflow_dispatch` o `schedule` non si annulla mai, e che di default è solo prova.
- [ ] T1.5 `pulisci`: tre gruppi; test con worktree finte (unita pulita, unita con modifiche, senza PR, bloccata).
- [ ] T1.6 `brief` con `modello-brief.md`; test che «Puoi toccare» viene da `aree.json`.
- [ ] T1.7 `foto` con `foto.json`; test per file iOS senza schermata (avviso).
- [ ] T1.8 `giro` con stato salvato e stampa solo dei cambiamenti; test con due giri uguali (niente stampa) e due diversi.
- [ ] T1.9 (dopo che T2 e T3 sono su `main`) `pr-pronta`; test per ogni motivo di rifiuto, compreso `CONFLICTING` e `UNKNOWN`.
- [ ] T1.10 `LEGGIMI.md`, riga in `MAPPA.md`; prova vera in sola lettura: `stato` e `pulisci` (senza `--esegui`) sul repository
  vero, uscita incollata nella PR (togliendo nomi di rami se dicono troppo).

### T2
- [ ] T2.1 `descrizione` e `revisione`, test con corpi veri di PR passate (senza dati privati) e con il modello vuoto.
- [ ] T2.2 `novita` con lo stato dei file (`git diff --name-status`), test per aggiunto / modificato / tolto / due file.
- [ ] T2.3 `test_per_nome` e correzione di `tests/test_grafica_b_web.py`.
- [ ] T2.4 Passo in CI, ambito bloccante, modello della PR; prova con `act` non serve: test degli script + una PR di prova vera
  (questa stessa PR mostra i passi saltati perché gli script non sono ancora su `main`, e lo dice).
- [ ] T2.5 `docs/METODO.md`.

### T3
- [ ] T3.1 Schema dei dati e `script/coerenza.py --controlla` con test (id doppio, riga doppia, stato sconosciuto, `.md` diverso).
- [ ] T3.2 Passaggio del contenuto di oggi nei dati; `--scrivi`; confronto con il `.md` di prima (le differenze nella PR).
- [ ] T3.3 `.gitattributes`, `CLAUDE.md`, `docs/METODO.md`.

## 5. Fatto quando
- Suite intera verde una volta per ramo (`.venv\Scripts\python.exe -m pytest -q -n 2`).
- T1: ogni comando ha `--help`, test, e la prova vera di `stato` e `pulisci` nella PR.
- T2: i quattro controlli hanno test; l'ambito è bloccante; il modello della PR ha «Revisione».
- T3: `python script/coerenza.py --controlla` esce con 0 su `main` dopo l'unione e con 1 se si aggiunge a mano una riga al `.md`.
- Dopo le tre unioni il coordinatore usa `giro`, `attendi` e `pr-pronta` al posto dei comandi a mano, e aggiorna
  `~/.claude/squadra/REGOLE.md` e la skill `coordinatore` (fuori dal repository).

## 6. Scelte (del coordinatore; le può cambiare l'utente)
- Scelta mia: Python della libreria standard e non uno script di shell, perché i test girano uguali su Windows e in CI. Costo se
  sbagliata: basso.
- Scelta mia: «revisione registrata» = sezione «## Revisione» nella descrizione, non un commento o un'etichetta, perché il job
  la legge dal corpo della PR che ha già. Costo se sbagliata: un controllo da spostare.
- Scelta mia: il `.md` della coerenza resta in git (si legge su GitHub) ma è generato e controllato dai test. Costo se sbagliata:
  qualche conflitto sul `.md` da risolvere rigenerandolo.
- Scelta mia: i comandi che cambiano qualcosa fanno solo la prova se non c'è `--esegui`. Costo: un parametro in più da scrivere.
