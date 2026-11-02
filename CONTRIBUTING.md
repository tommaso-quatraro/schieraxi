# Come contribuire

Grazie dell'interesse. SchieraXI è un progetto personale, curato da una persona nel tempo libero: le proposte sono
benvenute, ma le risposte possono richiedere giorni o settimane. Il progetto tiene poche funzioni, scelte con cura:
un'idea che aumenta molto la complessità si valuta caso per caso.

## Passi
1. Apri una **issue** per dire cosa vuoi cambiare e perché. Per un refuso o una correzione di una riga basta la pull request.
2. Fai un fork del repository, poi un ramo con un nome breve (per esempio `correggi-titoli-oggi`).
3. Fai passi piccoli, uno per volta. Ogni passo va provato davvero.
4. Prova la modifica: `python -m pytest -q` deve passare (l'ambiente è nel `README.md`).
   Se tocchi il modello di calcolo, lancia `python -m fanta verifica` prima e dopo e scrivi i due numeri nella pull request.
5. Apri la pull request e descrivi cosa cambia e come l'hai provato. I controlli automatici devono essere verdi.

## Regole
- **Niente segreti**: nessuna chiave, password o token, nemmeno di prova. Le chiavi stanno in `.env` o in `dati/`, mai in git.
- **Niente dati personali**: né indirizzi di server o IP, né email, né nomi di persone o di leghe e squadre reali.
  Usa segnaposto come `<indirizzo del server>`.
- **Niente dati di terzi**: non aggiungere pagine, tabelle o file copiati da altri siti, nemmeno nei test. Nei test usa
  estratti inventati e piccoli, come quelli in `tests/dati/`.
- **Le regole di una lega non vanno scritte nel codice**: stanno nella configurazione della lega.
- **Le fonti dati si interrogano con moderazione**: poche richieste, una alla volta, con cache. Prima di aggiungere una fonte
  nuova spiega nella issue le sue condizioni d'uso. Le fonti nuove partono spente.
- **Poche dipendenze**: prima di aggiungere una libreria, spiega nella pull request perché serve.
- **Workflow** (cartella `.github/workflows/`): solo server di GitHub (`ubuntu-latest` o `macos-*`), permessi minimi,
  nessun segreto e nessun trigger che dia accesso ai segreti a chi arriva da un fork.
- **Database degli account**: una migrazione già rilasciata non si modifica mai. Ogni cambio di struttura è una voce nuova in fondo a `MIGRAZIONI` in `fanta/account.py`.
- **Versione**: non cambiare il numero di versione. Se la modifica tocca `fanta/`, `script/` o `requirements.txt`, aggiungi
  un file `fanta/novita.d/<nome-breve>.json` così: `{"titolo": "...", "voci": ["..."]}`, senza numero. Il numero e le note
  della release li dà il progetto quando unisce la modifica.
- **Documentazione**: se cambi una schermata o un indirizzo del server, aggiorna nella stessa pull request `docs/GUIDA-UTENTE.md` o `docs/API.md`.
- **Italiano semplice**: testi e commenti sono in italiano, frasi brevi.

## Dopo la pull request
Chi cura il progetto la legge e risponde lì. Può chiedere modifiche, accettarle o spiegare perché no.

## Licenza
Contribuendo accetti che il tuo contributo abbia la stessa licenza del progetto (AGPL-3.0, file `LICENSE`).
Il nome e il logo restano marchi del titolare (`TRADEMARKS.md`).
