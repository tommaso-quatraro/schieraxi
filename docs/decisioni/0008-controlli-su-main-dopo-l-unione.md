# 0008. Dopo ogni unione i controlli girano anche su `main`

Data: 3/11/2026. Stato: accettata.

## Contesto e problema
Il job `unisci` unisce le pull request col token di GitHub (`GITHUB_TOKEN`), e le modifiche fatte con quel token non fanno
partire altri workflow: su `main` non girava nessun controllo dopo l'unione. Ogni pull request è provata solo con il `main` del
momento in cui è partita la sua corsa, quindi due pull request verdi ognuna da sola possono rompere `main` insieme senza che
nessuno lo provi (issue #183; caso sospetto: due `Cancello` nei test iOS dopo #89 e #21).

## Fattori della decisione
- Semplicità e sicurezza: repository pubblico, nessun segreto nuovo, nessun token personale, permessi minimi per job.
- I Mac di GitHub sono pochi: non si può provare iOS a ogni unione se `ios/` non è cambiata.
- Un rosso su `main` deve vedersi senza che qualcuno lo cerchi.
- Non cambiare la protezione di `main` né le impostazioni del repository.

## Opzioni considerate
- A. Dopo l'unione si lancia `test.yml` su `main` (`workflow_dispatch`, una delle poche cose che parte anche col token di
  GitHub), e se la corsa su `main` è rossa si apre un'issue `P1`.
- B. «Il ramo deve essere aggiornato prima dell'unione» e `unisci` aggiorna il ramo: ogni pull request costa un giro di controlli
  in più, e l'impostazione la cambia il proprietario.
- C. Una corsa iOS notturna su `main`: trova il guasto con ore di ritardo e da sola non copre la parte Python.

## Decisione
Scelta: «A», perché chiude il buco con due job piccoli e senza segreti nuovi.
- `prova-main` (permesso `actions: write` solo lì) parte dopo `unisci` e `rilascia` e lancia `gh workflow run test.yml --ref main`:
  prova il `main` finale, col commit di versione. Il lancio è un `workflow_dispatch`, quindi `unisci`, `rilascia` e `prova-main`
  (legati a `pull_request`) non ripartono e non c'è nessun giro continuo.
- Il job `cambi` decide se serve iOS anche per questi lanci: confronta con l'ultima corsa riuscita su `main`; se non lo sa,
  i test iOS girano comunque.
- `main-rosso` (permesso `issues: write` solo lì) apre l'issue `P1` «CI: main rosso» se un job della corsa su `main` fallisce
  (test, script del server, `pip-audit`, `ios`), o vi aggiunge un commento se è già aperta. Non gira per le pull request né per
  i lanci a mano su un ramo. L'issue non si chiude da sola (un esito verde di una corsa più vecchia, arrivato dopo, potrebbe
  nascondere un rosso vero): la chiude chi ha corretto, quando una corsa nuova su `main` è verde.

## Conseguenze
- Bene: ogni unione fa partire i controlli su `main`, iOS compreso quando serve; un rosso diventa un'issue `P1` che il giro del
  coordinatore vede.
- Male (il prezzo): è un controllo che arriva dopo l'unione, non la impedisce: `main` può restare rotto per il tempo di una
  corsa. Impedirlo davvero richiede l'opzione B (impostazione del repository, decide il proprietario). Una corsa in più per ogni
  unione (Linux, pochi minuti) e un Mac solo se `ios/` è cambiata dall'ultima corsa riuscita.
- Si vede solo dopo la prima unione che usa questo workflow: `tests/test_workflow_main.py` controlla la forma dei job, non il
  comportamento su GitHub.
- Come si controlla: `tests/test_workflow_main.py` (job, permessi, condizioni); `zizmor` e le regole di `tests/test_workflow_controlli.py`
  valgono anche per i job nuovi.
