---
paths:
  - "fanta/**/*.py"
  - "script/server/**"
  - "tests/**"
  - "requirements*"
---
# Server (`fanta/`, `script/server/`)

- **Novità.** Una pull request che tocca `fanta/`, `script/server/` o `requirements.txt` aggiunge un solo file
  `fanta/novita.d/<nome-breve>.json` (minuscole, cifre, trattini), senza numero di versione:
  `{"titolo": "...", "voci": ["..."], "tecnico": ["..."]}`. `voci` dice cosa vede l'utente e dove, in italiano semplice, senza
  sigle, percorsi, metodi o codici; i dettagli vanno in `tecnico`. `fanta/novita.json` e `VERSIONE` di `fanta/web/sw.js` li
  scrive il job `rilascia`. Solo documenti, test o `ios/`: nessuna voce.
- **Calcolo.** Se cambi `modello.py`, `formazione.py`, `consigli.py` o ciò che li alimenta: `python -m fanta verifica` prima e
  dopo, con i due numeri nella pull request. Un cambio che peggiora la misura non si unisce senza una ragione scritta.
- **Tempo.** Chi calcola giornate, scadenze e fasi riceve `adesso` come argomento: niente orologio vero nella logica né nei
  test (un test legato alla data fallisce un giorno a caso e blocca tutte le pull request).
- **Archivio e account.** Una colonna nuova in una tabella che esiste già non arriva sugli archivi in uso se la scrivi solo
  nel `CREATE TABLE`: serve una migrazione (`PRAGMA table_info` + `ALTER TABLE`). Le voci di `MIGRAZIONI` in
  `fanta/account.py` già rilasciate non si modificano: se ne aggiunge una in fondo.
- **Client.** Web, iPhone e widget leggono le stesse rotte: aggiungere campi si può, togliere o rinominare un campo rompe le
  app già installate. Se l'API cambia apposta: `python script/ci/aggiorna_openapi.py` e `docs/API.md` nella stessa pull
  request. Stati, etichette e frasi nuove nascono qui (`fanta/frasi.py`): i client li mostrano.
- **Scelte dell'utente.** Una formazione salvata non cambia mai da sola. La consigliata già mostrata cambia solo per almeno
  un punto atteso in più o per un titolare diventato fuori o improbabile.
- **Guasti visibili.** Niente `except Exception` che prosegue in silenzio e niente ripieghi che fanno sembrare buono un dato
  vecchio o mancante: il guasto di una fonte o di un calcolo si deve vedere (errore, registro, salute), con il nome di ciò
  che si è rotto. Un ripiego va bene solo se è voluto e l'utente lo sa («dati di ieri»).
- **Più utenti.** Il numero dell'utente viene solo dalla sessione, mai da un parametro; ogni rotta personale passa da
  `contesto.py` ed è coperta da `tests/test_isolamento.py`. L'input dell'utente si valida e ha un tetto di dimensione; un
  indirizzo web scritto dall'utente è un rischio (solo https, niente reti private).
- **Scritture.** `percorsi.scrivi_sicuro`; un percorso costruito con un nome che viene dai dati si controlla con
  `percorsi.dentro`. Le risorse personali usano ETag e If-Match.
- **Script del server.** Girano dal cron su Linux e il server si aggiorna da solo a ogni release: uno script rotto ferma gli
  aggiornamenti. `bash -n` su ogni script toccato e un test che lo esegue davvero. `tests/test_script_server.py` può aprire
  finestre sul PC: lancialo una volta, non a ciclo.
- **Test.** Dati inventati e cartelle temporanee, mai i file veri. Nessun test legge un file di `fanta/novita.d/` per nome
  (dopo il rilascio non c'è più).
