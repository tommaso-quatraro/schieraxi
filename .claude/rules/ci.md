---
paths:
  - ".github/**"
  - "script/ci/**"
  - "script/squadra/**"
  - "script/controlli/**"
---
# Controlli, workflow e strumenti (`.github/`, `script/ci/`, `script/squadra/`)

- **Leggere lo stato di una pull request.** «Annullato» non è «fallito»: dopo un push nuovo i job della corsa vecchia
  risultano falliti. Conta l'ultima corsa di `test.yml` sul commit in testa
  (`gh run list --commit <sha> --workflow test.yml`).
- **Togliere la bozza.** `python script/squadra/squadra.py pr-pronta <PR> --esegui` al posto di `gh pr ready`: controlla che
  il ramo sia in pari con `main` (altrimenti `git merge origin/main`, mai push forzato), che i controlli siano verdi e che
  la descrizione sia completa. Tra un push e l'uscita dalla bozza lascia passare un paio di minuti, o GitHub perde una corsa.
- **Descrizione.** Il job `ambito` la legge quando parte la corsa: se la correggi dopo, serve una corsa nuova (un push,
  anche di un commit vuoto); «Re-run» rilegge quella vecchia. La riga `Aree:` vuole cartelle o file (`fanta, tests, docs`).
- **Ramo partito da un altro ramo**: porta con sé la sua voce di novità, che uscirebbe due volte. Prima di togliere la
  bozza `git diff --name-only origin/main HEAD -- fanta/novita.d` deve mostrare solo il file di questa pull request.
- **I controlli si prendono da `main`**: un controllo nuovo vale dalla pull request successiva alla sua unione. Ciò che può
  rompere `main` si controlla nella pull request, non dopo.
- **Workflow.** Solo azioni di GitHub, fissate per hash (unica eccezione `anthropics/claude-code-action`, nell'elenco delle
  azioni permesse: un suo aggiornamento va rifatto a mano, con test ed elenco aggiornati); permessi minimi; mai testo della
  pull request dentro `run:`; nessun segreto nei job che partono da un fork. `zizmor` e CodeQL lo segnalano ma per
  ora non bloccano l'unione: chi rivede un workflow lo controlla a mano.
- **Release.** `v<numero>` (server) la crea `rilascia`, sempre con `--latest=false`; `build-<N>` (iPhone) è l'unica
  «Latest» e la crea `ipa.yml`, che non si rinomina (il contatore è per file). Nessuna release creata a mano.
- **Strumenti della squadra.** Ogni passo che chi coordina fa due volte diventa un comando di `script/squadra/` con il suo
  test; senza `--esegui` i comandi mostrano solo cosa farebbero. Guida: `script/squadra/LEGGIMI.md`.
