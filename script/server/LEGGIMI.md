# Script del server

Si lanciano dal crontab dell'utente del server. Il servizio systemd è `fantacalcio.service` (sostituire `<utente>`).

| Script | Quando | Cosa fa |
|---|---|---|
| `aggiorna-app.sh` | ogni 10 min | installa `main` se cambiano `fanta`, `tests`, `script`, `requirements*` (mai `lega/`, `dati/`, `fanta/avatar_tratti.json`, `CLAUDE.md`), solo se i commit nuovi sono firmati (vedi sotto) e con le librerie bloccate dagli hash. `--prova`: dice cosa farebbe e non scrive. `--fidati COMMIT`: punto di partenza controllato a mano |
| `pubblica-sito.sh` | ogni 5 min | tiene la cartella del sito (`/var/www/schieraxi-sito`) uguale a `sito/` di `main` |
| `aggiorna.sh` | 8, 13, 17, 21 | aggiorna i dati e manda gli avvisi. Ultimo passo: `python -m fanta taratura-probabili` (#379, solo misura: quanto «gioca N%» con le probabili sbaglierebbe ritarato sulle giornate giocate; lavoro vero al massimo una volta per giornata, `nice -n 15`, al massimo 5 minuti, un errore va nel log e non ferma lo script). Prova a mano: `.venv/bin/python -m fanta taratura-probabili --prova` (non scrive niente) |
| `promemoria.sh` | ogni 10 min | promemoria prima della scadenza e controllo di salute dell'app |
| `backup-dati.sh` | ogni notte | copia dei dati che non si rigenerano (ultime 14) |
| `backup-serale.sh` | ogni notte | copia di regole, rose, scelte (ultime 7) |
| `controllo-salute.sh` | ogni 5 min | app viva, dati freschi, disco, memoria, certificato; avvisi con ntfy |
| `sentinella.sh` | ogni ora (al minuto 37) | rifà in sola lettura le risposte vere dell'app per ogni utente (Oggi, Formazione, Scelta, Diario, widget, Live) e controlla 21 invarianti (`fanta/sentinella.py`); esito in «Stato dei dati», un avviso ntfy solo alla prima rottura confermata (2 giri), con «utente N» e mai nomi. Prova a mano: `bash ~/fantacalcio/script/server/sentinella.sh --senza-invio`. Log `dati/sentinella.log`, stato `dati/sentinella.json`. Tiene il blocco `blocco-pubblicazione` (condiviso) mentre gira: un aggiornamento dell'app aspetta il giro dopo |

`aggiorna-app.sh`, `pubblica-sito.sh` e il controllo di salute di `promemoria.sh` condividono il blocco
`~/.cache/fantacalcio/blocco-pubblicazione`: un solo `git fetch` alla volta sul clone e nessun allarme mentre l'app si riavvia.
I controlli di salute (`fanta/salute.py`, `controllo-salute.sh`) provano 3 volte a 5 secondi di distanza prima di dire «non risponde».

La configurazione di sistema (nginx, systemd, fail2ban, ufw, crontab) non è nel repository: va preparata per il proprio server.

Crontab proposto (percorsi con `$HOME`, utente del server):

```
*/10 * * * * /bin/bash $HOME/fantacalcio/script/server/aggiorna-app.sh >/dev/null 2>&1
*/5  * * * * /bin/bash $HOME/fantacalcio/script/server/pubblica-sito.sh >/dev/null 2>&1
*/5  * * * * /bin/bash $HOME/fantacalcio/script/server/controllo-salute.sh >/dev/null 2>&1
*/10 * * * * /bin/bash $HOME/fantacalcio/script/server/promemoria.sh >/dev/null 2>&1
45 3 * * *   /bin/bash $HOME/fantacalcio/script/server/backup-dati.sh >/dev/null 2>&1
37 * * * *   /bin/bash $HOME/fantacalcio/script/server/sentinella.sh >/dev/null 2>&1
```
(più `aggiorna.sh` e `backup-serale.sh` se c'erano già nel crontab, con lo stesso orario di prima).

## Niente installazioni durante le partite

Installare una versione nuova riavvia il servizio. Per questo `aggiorna-app.sh` chiede prima alla versione installata
`python -m fanta momento-libero` (`fanta/libero.py`), che esce con:
- `3` = occupato: una partita di Serie A è in corso (da 10 minuti prima del calcio d'inizio a 130 minuti dopo, o più a lungo se la
  diretta salvata in `dati/live.json` la dà ancora in gioco, al massimo 4 ore) oppure manca meno di un'ora alla scadenza della
  formazione di una lega attiva. L'installazione si rimanda al primo giro libero e nel log c'è una riga sola per versione:
  «rimandata: partite in corso (motivo)»; quando poi si installa: «fine del rimando».
- `0` = libero. Ogni altro esito (comando che la versione installata non ha ancora, errore, più di 60 secondi) vale come libero:
  un controllo guasto non deve fermare gli aggiornamenti.

Emergenza (correzione urgente durante una partita): `touch ~/.cache/fantacalcio/installa-subito` (installa al prossimo giro e il
file si cancella da solo) oppure `SCHIERAXI_INSTALLA_SUBITO=1 bash ~/fantacalcio/script/server/aggiorna-app.sh`. Nel log:
«installazione forzata». Per vedere cosa direbbe adesso: `cd ~/fantacalcio && .venv/bin/python -m fanta momento-libero`.

## Aggiornamenti sicuri: firme dei commit e librerie bloccate

### Cosa controlla `aggiorna-app.sh`
- **Firme**: ogni commit nuovo della linea principale di `main` (dall'ultimo verificato fino a quello da installare) deve avere la firma
  di una chiave fidata. Oggi è la chiave con cui GitHub firma i commit che crea lui («web-flow»): le unioni *squash* delle PR (job `unisci`)
  e il commit «Versione X» del job `rilascia` (creato via API con `script/ci/commit_firmato.py`, niente `git push`).
  - Impronta: `968479A1AFF927E37D1A566BB5690EEEBB952194` (utente «GitHub», in uso dal 16/1/2024; fonte: https://github.com/web-flow.gpg).
  - Copia di riferimento nel repository: `script/server/chiavi/github-web-flow.asc`.
  - Quella che conta è la copia **sul server**, fuori dal repository: `~/.config/schieraxi/chiavi-firma.asc` (chi scrive su `main` non può cambiarla).
    **Se il file manca NON si installa niente** (dal 2/11/2026; prima la verifica si spegneva): una riga nel log per versione
    («NON installata: manca la chiave fidata») e un avviso «SchieraXI: aggiornamenti fermi» la prima volta (stato in
    `~/.cache/fantacalcio/senza-chiave`, si toglie da solo quando la chiave torna). Così un file cancellato per sbaglio o da un
    intruso non spegne la verifica. Per installare comunque senza firme serve l'interruttore esplicito `SCHIERAXI_SENZA_FIRME=1`
    (vale solo se la chiave manca: se c'è, le firme si controllano sempre).
  - Stato in `~/.cache/fantacalcio/`: `verificato` (ultimo commit con le firme a posto), `rifiutato` (versione da non riprovare).
  - Se una firma manca o non è fidata: non installa, scrive `rifiutato`, avviso «SchieraXI: aggiornamento bloccato» sul canale degli avvisi.
- **Librerie**: quando cambia `requirements.txt` prepara un ambiente Python **nuovo** accanto a quello in uso (`~/fantacalcio/.venv.nuova`)
  con `pip install --require-hashes`: solo le versioni e i file con l'hash scritto lì. Solo se l'installazione riesce tutta scambia le
  cartelle (`.venv` diventa `.venv.precedente`, la nuova diventa `.venv`): l'ambiente in uso non resta mai a metà. Funziona perché
  servizio e script usano solo `.venv/bin/python`.
  - Se pip non riesce (rete, PyPI, hash diverso) non tocca niente, rimette i file della versione di prima (il servizio non è stato
    riavviato) e **riprova ai giri dopo**: stato in `~/.cache/fantacalcio/librerie-fallite`, un avviso «rimandato» la prima volta;
    alla terza volta di fila rinuncia, scrive `rifiutato` e avvisa.
  - Se dopo il riavvio il servizio non risponde torna anche all'ambiente di prima.
  - Le versioni in `requirements.txt` sono quelle in produzione sul server (Python 3.12) al momento del blocco: il primo giro
    non cambia nessuna libreria, crea solo l'ambiente nuovo.

### Cosa protegge e cosa no
- Protegge da: commit spinti su `main` con `git push` (token o chiave rubati, chiave di deploy con scrittura, un errore), anche se nascosti
  sotto un commit firmato; force-push che riporta `main` a una versione vecchia o diversa (firmata ma che non discende dall'ultima verificata);
  una libreria nuova o modificata su PyPI (entra solo con una PR che cambia `requirements.txt`).
- NON protegge da: chi entra nell'account GitHub del proprietario (dal sito può unire PR o creare commit, e GitHub li firma lo stesso:
  **serve la verifica in due passaggi, 2FA**); il `GITHUB_TOKEN` dei job che scrivono (`unisci`, `rilascia`) può creare commit firmati
  via API (per questo quei job non eseguono codice delle PR); una PR maligna unita senza leggerla.
  In breve: la firma dice «è passato da GitHub», non «l'ha scritto il proprietario».
- **`http-ece` si compila dal sorgente**: su PyPI c'è solo il sorgente (l'hash di quello è controllato), ma per costruirlo pip scarica in
  un ambiente a parte gli strumenti di compilazione (`setuptools`, a volte `wheel`) **senza controllarne gli hash**: è un limite noto di pip.
  Succede a ogni ambiente nuovo, cioè quando cambia `requirements.txt` (pip può riusare la wheel già costruita nella sua cache). Per
  chiuderlo del tutto servirebbe una wheel di `http-ece` costruita una volta e conservata a parte: non fatto, il rischio è basso.
- `pubblica-sito.sh` (il sito statico) non controlla ancora le firme: stesso `verifica-firme.sh`, da collegare in un passo successivo.

### Casi limite
- **Commit spinto a mano su `main`** (anche dal proprietario): rifiutato. Si guarda cosa contiene e, se va bene:
  `bash ~/fantacalcio/script/server/aggiorna-app.sh --fidati origin/main` (installa al giro dopo). Meglio: sempre PR, mai push diretti.
- **PR aperte prima di questa modifica e unite dopo**: il loro giro di controlli usa ancora il vecchio `rilascia` (con `git push`), quindi il
  commit «Versione X» esce senza firma e il server lo rifiuta. Per questo la chiave si copia sul server solo quando quelle PR sono
  unite o ribasate (vedi «Accendere»). Se capita: controllare e `--fidati origin/main`.
- **Unione dal sito** con «Squash and merge» o «Create a merge commit»: GitHub firma il commit. Con «Rebase and merge» i commit ricreati
  da GitHub [da verificare]: meglio non usarlo.
- **La chiave di GitHub cambia** (l'ultima volta il 16/1/2024): le versioni nuove risultano «senza firma valida» e arriva l'avviso.
  Si scarica la nuova da https://github.com/web-flow.gpg, si controlla l'impronta sulla documentazione di GitHub, si aggiorna il file nel
  repository (PR) e la copia sul server (a mano). Poi `--fidati origin/main`.
- **Server spento a lungo**: al rientro controlla tutta la linea dall'ultimo `verificato`, anche se i commit sono tanti.
- **Manca `gpg`**: rifiuta tutto con il motivo nel log (`sudo apt install gnupg`).
- **Avvisi**: uno per versione. Ogni commit nuovo sopra uno rifiutato viene rifiutato di nuovo (con un nuovo avviso) finché non si usa `--fidati`.

### Accendere (una volta, sul server, con l'ok)
1. `gpg --version` (se manca: `sudo apt install gnupg`).
2. Unire la PR e aspettare che il server la installi (`dati/pubblicazione.log`: «librerie cambiate: preparo un ambiente Python nuovo»,
   poi «installata»). Le versioni sono le stesse già in produzione: `~/fantacalcio/.venv/bin/python -m pip freeze` deve dare le stesse
   righe di prima. Ci vuole qualche minuto in più (si scaricano le librerie); `.venv.precedente` occupa qualche centinaio di MB.
   Fino al passo 5, su un server nuovo senza chiave, si installa solo con `SCHIERAXI_SENZA_FIRME=1` (nella riga del crontab o a mano).
3. Controllare che GitHub firmi anche il commit del bot: `gh api repos/<proprietario>/schieraxi/commits/main --jq .commit.verification`
   deve dare `"verified": true` sia dopo un'unione sia dopo il commit «Versione X».
4. Nessuna PR aperta fatta prima di questa modifica (o ribasata su `main`).
5. Copiare la chiave e controllarne l'impronta:
   ```
   mkdir -p ~/.config/schieraxi
   cp ~/fantacalcio/script/server/chiavi/github-web-flow.asc ~/.config/schieraxi/chiavi-firma.asc
   chmod 644 ~/.config/schieraxi/chiavi-firma.asc
   gpg --show-keys ~/.config/schieraxi/chiavi-firma.asc      # 9684 79A1 AFF9 27E3 7D1A  566B B569 0EEE BB95 2194
   ```
6. Prova: `bash ~/fantacalcio/script/server/aggiorna-app.sh --prova` → «niente di nuovo» oppure «firme a posto».
7. Alla PR successiva: nel log «installata» e nessun «NON installata».

### Spegnere e tornare indietro
- Spegnere solo la verifica (sconsigliato): spostare la chiave NON basta più (senza chiave non installa niente). Servono tutte e due:
  `mv ~/.config/schieraxi/chiavi-firma.asc ~/.config/schieraxi/chiavi-firma.asc.spenta` e l'interruttore nella riga del crontab:
  `*/10 * * * * SCHIERAXI_SENZA_FIRME=1 /bin/bash $HOME/fantacalcio/script/server/aggiorna-app.sh >/dev/null 2>&1`.
  Una volta sola, a mano: `SCHIERAXI_SENZA_FIRME=1 bash ~/fantacalcio/script/server/aggiorna-app.sh`.
- Installare comunque una versione rifiutata, dopo averla guardata: `--fidati <commit>`.
- Librerie: lo script torna da solo all'ambiente di prima se il servizio non riparte. A mano (servizio fermo un momento):
  `cd ~/fantacalcio && mv .venv .venv.scartata && mv .venv.precedente .venv && sudo systemctl restart fantacalcio`.
- Togliere tutto: revert della PR su GitHub (l'unione è firmata da GitHub: passa la verifica) e spostare la chiave come sopra.

### Passaggio al repository nuovo (repository unico)
La storia nuova non contiene l'ultima versione installata: con la chiave presente il server rifiuta («non trovo la versione di partenza»)
e avvisa. Nel passo del piano in cui si clona il repository nuovo sul server: `--prova`, poi `--fidati origin/main` (il primo invio del
repository nuovo lo facciamo noi con `git push`, quindi senza firma), e solo dopo si aspetta il giro. In alternativa si spegne la verifica
per il passaggio e si riaccende dopo il `--fidati`. Il workflow del repository pubblico ha già il `rilascia` via API.

### Librerie bloccate: come si cambiano
- Elenchi scritti a mano: `requirements.in` (app), `requirements-dev.in` (test), `requirements-vincoli.in` (versioni imposte, col motivo;
  con `; python_version < "3.12"` valgono solo per i Python vecchi della CI, il server resta sulla versione principale).
- Rigenerare in locale: `.venv\Scripts\python.exe script\blocca_dipendenze.py`. Tiene le versioni che ci sono già; una libreria nuova prende
  la versione della `.venv`. Per allinearsi al server: `ssh <server> '~/fantacalcio/.venv/bin/python -m pip freeze' > freeze.txt`
  (sola lettura) e `... blocca_dipendenze.py --versioni freeze.txt`; per aggiornare tutto alla `.venv`: `--aggiorna`.
  Hash = tutti i file di PyPI per quella versione, così vale su ogni server Linux, in locale (Windows) e su GitHub. `--controlla` dice se i file sono da rifare.
- La CI prova con Python 3.12 come il server dove c'è (GitHub; sui runner propri con `CI_PYTHON312` nel `.env` del runner o con
  `python3.12`), altrimenti con 3.11 e un avviso: in quel caso numpy e soupsieve sono le versioni per i Python vecchi.
- Dependabot (repository pubblico) apre PR che cambiano versione e hash di una libreria; i controlli le installano con gli hash. Se la
  libreria nuova porta dipendenze nuove la PR non passa: si rigenera con lo script.


## nginx: la cartella del sito
Nel blocco del sito, oltre alla `root`, conviene bloccare le cartelle `.git` (il sito prima era un clone: `pubblica-sito.sh` la sposta fuori
dalla cartella servita, ma il blocco resta come seconda protezione):

```
location ~ /\.git { return 404; }
```
Dopo aver cambiato nginx: `sudo nginx -t` e poi la ricarica (con l'ok dell'utente). `pubblica-sito.sh` da solo non richiede ricariche.
La vecchia copia git si trova in `~/.cache/fantacalcio/sito-vecchio-git`; per tornare al sito di prima:
`git --git-dir=$HOME/.cache/fantacalcio/sito-vecchio-git --work-tree=/var/www/schieraxi-sito checkout -f`.
