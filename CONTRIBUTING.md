# Come contribuire

Grazie dell'interesse. SchieraXI è un progetto personale, mantenuto da una persona nel tempo libero: le proposte sono
benvenute, ma le risposte possono richiedere giorni o settimane.

## Passi
1. Apri una **issue** per dire cosa vuoi cambiare e perché. Per un refuso o una correzione di una riga basta la pull request.
2. Fai un fork del repository, poi un ramo con un nome breve (per esempio `correggi-titoli-oggi`).
3. Fai passi piccoli, uno per volta. Ogni passo va provato davvero.
4. Prova la modifica: `python -m pytest -q` deve passare (vedi il README per l'ambiente).
   Se tocchi il modello di calcolo, lancia `python -m fanta verifica` prima e dopo, e scrivi i due numeri nella pull request.
5. Apri la pull request e descrivi cosa cambia e come l'hai provato. I controlli automatici devono essere verdi.

## Regole
- **Niente segreti**: nessuna chiave, password o token, nemmeno di prova. Le chiavi stanno in `.env` o in `dati/`, mai in git.
- **Niente indirizzi privati e niente dati personali**: né indirizzi di server, né email, né nomi di persone o di squadre
  reali. Usa segnaposto come `<indirizzo del server>`.
- **Niente dati di terzi**: non aggiungere pagine, tabelle o file copiati da altri siti, nemmeno nei test. Nei test usa
  estratti inventati e piccoli, come quelli in `tests/dati/`.
- **Le regole di una lega non vanno scritte nel codice**: stanno nella configurazione della lega.
- **Le fonti dati si interrogano con moderazione**: poche richieste, una alla volta, con cache. Non aggiungere una fonte
  nuova senza spiegare nella issue le sue condizioni d'uso.
- **Poche dipendenze**: prima di aggiungere una libreria, spiega nella pull request perché serve.
- **Workflow (cartella `.github/workflows/`)**: usano solo i server di GitHub (`ubuntu-latest` o `macos-*`), permessi minimi,
  nessun segreto e nessun trigger che dia accesso ai segreti a chi arriva da un fork.
- **Versione**: non cambiare il numero di versione nella pull request. Lo decide chi cura il progetto (le note stanno nelle release).
- **Documentazione**: se cambi una schermata o una rotta del server, aggiorna anche le guide in `docs/` nella stessa pull request.

## Dopo la pull request
Chi cura il progetto la legge e risponde nella pull request. Può chiedere modifiche, accettarle o spiegare perché no.
Il modo in cui le modifiche accettate arrivano nel repository è deciso da chi cura il progetto.

## Licenza
Contribuendo accetti che il tuo contributo abbia la stessa licenza del progetto (AGPL-3.0, file `LICENSE`).
