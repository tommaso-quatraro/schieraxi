# SchieraXI: come si lavora nel repository

SchieraXI è un'app libera (licenza AGPL-3.0) che consiglia la formazione del fantacalcio per una lega classic di Serie A.
Questo file dice come si lavora sul codice. Dove sta ogni cosa: `MAPPA.md`. Come si usa l'app: `README.md`.

## Regole
- Testi e commenti per l'utente: italiano semplice.
- Niente dati veri nel repository: né chiavi, password, token, file `.env`, né indirizzi di server o di reti private,
  né email personali, né nomi di persone o di squadre reali.
- Nei documenti usa il segnaposto `<indirizzo-del-server>`. Nei test e negli esempi usa dati inventati
  (`lega/esempio/`, `tests/dati/`).
- Le regole di una lega non si scrivono nel codice: stanno nel file di configurazione della lega (`regole.json`, `rose.json`).
- Le fonti dati si interrogano con poche richieste, una alla volta, con cache. Una fonte nuova si propone in una issue,
  con le sue condizioni d'uso. Le fonti restano spente di default.
- Passi piccoli: ogni passo va provato davvero prima del commit. Non dire che una cosa funziona se non l'hai eseguita.
- Commit in italiano. Un ramo per ogni lavoro.
- Ogni modifica a una schermata vale per web e iPhone: vedi `docs/COERENZA-WEB-IPHONE.md`.

## Flusso di lavoro
1. Issue: cosa cambiare e perché. Per una correzione di una riga basta la pull request.
2. Ramo nuovo da `main`: `git switch -c nome-breve`.
3. Modifiche piccole, con test mirati.
4. Pull request verso `main`. Nella descrizione: cosa cambia e come l'hai provato. Scrivi `Closes #N` se c'è una issue.
5. I controlli di GitHub (cartella `.github/workflows/`) devono essere verdi prima dell'unione.
6. L'unione si fa con «squash» e il ramo si cancella. Le pull request del proprietario si uniscono da sole quando i controlli
   passano; quelle degli altri le unisce chi cura il progetto.

## Metodo: Superpowers e questo repository
- Per il **come** si lavora (idea, piano, test prima del codice, ricerca dei difetti, revisione, verifica) comandano le skill di
  Superpowers, usate così come sono. Il metodo in breve: `docs/METODO.md`.
- Questo file comanda su ciò che è del progetto, anche quando una skill dice altro:
  - ogni ramo finisce con una pull request su `main` (`Closes #N`): mai unione in locale né a mano (la fa il job `unisci`),
    mai rami lasciati a metà;
  - test prima del codice sì, ma il codice già scritto non si butta: si scrive il test che fallisce sul comportamento
    sbagliato, lo si vede fallire, poi si corregge;
  - la revisione si fa prima di aprire la pull request, perché l'unione è automatica;
  - ramo indietro rispetto a `main`: `git merge origin/main` nel ramo, niente push forzato;
  - spec e piani in italiano in `docs/superpowers/specs/` e `docs/superpowers/plans/`, senza dati veri (repository pubblico);
  - novità in `fanta/novita.d/`, coerenza web-iPhone, foto iOS lanciate da una sola persona (`docs/METODO.md`).

## Divieti fissi per Claude Code
`.claude/settings.json` ha regole `deny` che Claude Code applica da solo, in ogni modalità di permesso, a chi lavora con Claude Code
in questo repository: niente `gh pr merge` (l'unione la fa il job `unisci`), niente push su `main` (si passa sempre da una pull
request), niente push forzato, niente `git commit --no-verify` (il controllo prima del commit non si salta). Le frasi nelle
istruzioni si possono dimenticare, queste regole no. Coprono le forme abituali dei comandi, non ogni modo di scriverli: la difesa
vera resta su GitHub (protezione di `main`). Non toccano i job di GitHub Actions (`unisci`, `rilascia`), che girano senza Claude Code.
Le eccezioni personali vanno in `.claude/settings.local.json`, che resta fuori da git; un divieto però vale lo stesso.

## Test
- Ambiente (Windows): `python -m venv .venv`, poi `.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt`.
  Su macOS e Linux usa `.venv/bin/python`.
- Tutti i test: `.venv\Scripts\python.exe -m pytest -q`. Un file solo: `.venv\Scripts\python.exe -m pytest -q tests\test_rose_csv.py`.
- Modello di calcolo: prima e dopo la modifica lancia `python -m fanta verifica`, e scrivi i due numeri nella pull request.
- Se cambi una schermata o una rotta del server, aggiorna `docs/GUIDA-UTENTE.md` o `docs/API.md` nella stessa pull request.

## Versioni e novità
- Il numero di versione non si scrive a mano: lo dà il job `rilascia` quando la pull request si unisce.
- Una pull request che tocca `fanta/`, `script/server/` o `requirements.txt` aggiunge un solo file
  `fanta/novita.d/<nome-breve>.json` (minuscole, cifre, trattini), senza numero:

  ```json
  {"titolo": "...", "voci": ["..."], "tecnico": ["..."]}
  ```

  - `voci`: cosa vede l'utente. Italiano semplice, niente sigle, percorsi di file, metodi HTTP o codici.
  - `tecnico`: dettagli per chi sviluppa (facoltativo).
- Non toccare `fanta/novita.json` né `VERSIONE` in `fanta/web/sw.js`: li aggiorna il job `rilascia`.
- Dopo una modifica ai file di `sito/`, alza a mano `VERSIONE` in `sito/sw.js`.
- Le pull request solo di documenti o di test non hanno bisogno di una voce di novità.

## Cosa non va mai nel repository
- Cartella `dati/`, lega vera (`lega/` tranne `lega/esempio/`), file `.env`, database `*.sqlite`, chiavi, certificati, log.
- File con dati personali, o copie di pagine e tabelle prese da siti di terzi.
- Prima di ogni commit: `git status` e `git diff --staged`. Se hai un dubbio, non committare.

## Rilascio (per chi cura il progetto)
- Release del server `v<numero>`: la crea il job `rilascia`, sempre con `--latest=false`.
- App per iPhone: release `build-<N>`, l'unica marcata «Latest». Il suo numero cresce sempre.
- Non creare a mano release marcate «Latest».
