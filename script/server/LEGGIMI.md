# Script del server

Si lanciano dal crontab dell'utente del server. Il servizio systemd è `fantacalcio.service` (sostituire `<utente>`).

| Script | Quando | Cosa fa |
|---|---|---|
| `aggiorna-app.sh` | ogni 10 min | installa `main` se cambiano `fanta`, `tests`, `script`, `requirements*` (mai `lega/`, `dati/`, `fanta/avatar_tratti.json`, `CLAUDE.md`), al massimo una volta ogni intervallo (predefinito 60 minuti, subito le urgenti: vedi «Rilasci raggruppati»), solo se i commit nuovi sono firmati (vedi sotto) e con le librerie bloccate dagli hash. `--prova`: dice cosa farebbe e non scrive. `--fidati COMMIT`: punto di partenza controllato a mano. Un'installazione riuscita sta solo nel registro `dati/pubblicazione.log`; avvisi sul telefono solo se qualcosa non va: versione rifiutata, librerie che non si installano, ritorno alla versione di prima, chiave delle firme mancante, e i guasti che prima restavano nel solo registro (GitHub che non risponde da tre giri, copia di GitHub senza il ramo `main`, versione senza tutte le cartelle, file della versione nuova che non si copiano, ambienti Python che non si scambiano), al massimo uno al giorno per motivo, con «di nuovo a posto» quando passa. Stato in `~/.cache/fantacalcio/guasto-<motivo>` |
| `pubblica-sito.sh` | ogni 5 min | tiene la cartella del sito (`/var/www/schieraxi-sito`) uguale a `sito/` di `main` |
| `aggiorna.sh` | 8, 13, 17, 21 | aggiorna i dati e manda gli avvisi. Guasti contati per passo dell'aggiornamento (listone, calendario, voti, probabili, Understat...): un avviso con il nome del passo alla seconda volta di fila, una volta sola finché dura, e «funziona di nuovo» quando torna; un solo avviso per giro con tutti i passi rotti, e uno solo per quelli tornati; se il servizio degli avvisi non risponde si riprova al giro dopo; un comando fermo prima della fine conta come guasto di tutto l'aggiornamento; una fonte spenta a mano si toglie senza avviso. Stato: un file per passo rotto in `~/.cache/fantacalcio/passi/` (giri di fila, ora dell'ultimo avviso, nome), una riga che comincia con «passo» nel log per ogni passo rotto o tornato. Ultimo passo: `python -m fanta taratura-probabili` (#379, `docs/decisioni/0009`: ritara «gioca N%» con le probabili sulle giornate giocate, lo accende da 8 giornate se sbaglia meno e torna ai numeri di partenza se peggiora; mai cambi nelle 24 ore prima della prima partita; avviso al proprietario a ogni cambio e dopo 3 giri falliti di fila; calcolo vero con una giornata nuova o dopo una riga pronta, rimandata o riaccesa; `nice -n 15`, al massimo 5 minuti, un errore va nel log e non ferma lo script). A mano: `.venv/bin/python -m fanta taratura-probabili --prova` (stampa i numeri, non scrive niente), `--spegni` (torna subito ai numeri di partenza e non ritara più) e `--accendi` (dopo `--spegni`: la prova riparte al giro dopo) |
| `promemoria.sh` | ogni 10 min | promemoria prima della scadenza e controllo di salute dell'app |
| `backup-dati.sh` | ogni notte | copia dei dati che non si rigenerano, compreso l'archivio delle statistiche `dati/fanta.sqlite` (API di backup di SQLite, a servizio acceso); ultime 14. Se non riesce solo la copia dell'archivio, il pacchetto si salva senza, quella notte non si tolgono le copie vecchie e parte un avviso (al massimo uno al giorno). Ripristino: `docs/RIPRISTINO-SERVER.md` |
| `backup-serale.sh` | ogni notte | copia di regole, rose, scelte (ultime 7) |
| `controllo-salute.sh` | ogni 5 min | app viva, dati freschi, disco, memoria, certificato; avvisi con ntfy |
| `sentinella.sh` | ogni ora (al minuto 37) | rifà in sola lettura le risposte vere dell'app per ogni utente (Oggi, Formazione, Scelta, Diario, widget, Live) e controlla 21 invarianti (`fanta/sentinella.py`); esito in «Stato dei dati», un avviso ntfy solo alla prima rottura confermata (2 giri), con «utente N» e mai nomi. Prova a mano: `bash ~/fantacalcio/script/server/sentinella.sh --senza-invio`. Log `dati/sentinella.log`, stato `dati/sentinella.json`. Tiene il blocco `blocco-pubblicazione` (condiviso) mentre gira: un aggiornamento dell'app aspetta il giro dopo |

Chi avvisa di cosa (canale degli avvisi del gestore):
- `aggiorna.sh`: un passo dei dati che non riesce, una volta sola alla seconda volta di fila, e quando torna; il promemoria di ogni giorno per un passo fermo da oltre 24 ore lo manda il controllo di salute del server (`fanta/salute.py`).
- `aggiorna-app.sh` e `backup-dati.sh`: aggiornamenti dell'app fermi, copia notturna senza l'archivio o non riuscita del tutto, al massimo un avviso al giorno per motivo (nessun altro li ripete), e quando tornano a posto.

`aggiorna-app.sh`, `pubblica-sito.sh` e il controllo di salute di `promemoria.sh` condividono il blocco
`~/.cache/fantacalcio/blocco-pubblicazione`: un solo `git fetch` alla volta sul clone e nessun allarme mentre l'app si riavvia.
I controlli di salute (`fanta/salute.py`, `controllo-salute.sh`) provano 3 volte a 5 secondi di distanza prima di dire «non risponde».

La configurazione di sistema (nginx, systemd, fail2ban, ufw, crontab) non è nel repository: va preparata per il proprio server.

Variabili del servizio: in `/etc/schieraxi/fantacalcio.env` (di root, `640`, gruppo dell'utente del servizio), date al servizio dal
drop-in di `ambiente.conf.esempio` e lette dagli script con `leggi-ambiente.sh`, senza eseguirle. Il posto di prima,
`dati/ambiente.env`, vale ancora con un avviso finché non lo si sposta: passi in `docs/RIPRISTINO-SERVER.md`, «Spostare le variabili
del servizio».

Registri: gli script dei cron girano fuori dal recinto del servizio ma scrivono i loro log in cartelle che scrive anche il servizio
(`dati/`, `~/.cache`). Per questo usano `registri.sh`: se al posto di un log (o del suo file di lavoro) c'è un collegamento simbolico
si fermano senza scrivere niente, ruotano i log con un file di lavoro sempre nuovo e cambiano i permessi solo dei log che sono file veri.

## Ambiente di prova

Una seconda copia dell'app sullo stesso server, con dati inventati, che riceve ogni versione prima della produzione. Gira con un
utente di sistema suo, `schieraxi-prova` (casa `/srv/schieraxi-prova`, servizio `schieraxi-prova` su `127.0.0.1:8001`), senza nessun
permesso sui file della produzione: clone del codice suo, dati di calcio da una copia che la produzione lascia ogni notte in
`/srv/schieraxi-scambio`. Script, servizio, nginx e tutti i comandi (con la prova di ogni passo e il ritorno indietro) stanno in
[`prova/LEGGIMI.md`](prova/LEGGIMI.md). Si accende solo con l'ok del proprietario.
`aggiorna-app.sh` la aggiorna con `SCHIERAXI_ISTANZA=prova` e l'utente della prova; senza la variabile fa quello di sempre
(`--configurazione` stampa cartella, stato, servizio, porta, clone e blocco che userebbe, senza scrivere niente; un valore sconosciuto,
o la prova nella casa della produzione, esce con 2 senza fare niente).

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

## Rilasci raggruppati: al massimo un'installazione all'ora

Le pull request si uniscono e hanno il loro numero di versione subito (job `rilascia`), ma ogni installazione riavvia il servizio e
aggiorna la web installata sul telefono: `aggiorna-app.sh` le raggruppa (#635).
- Fra due installazioni riuscite passa almeno un **intervallo**, 60 minuti di predefinito. Prima la versione nuova si rimanda (nel
  registro una riga sola per versione: «raggruppata: … installo … fra circa N minuti»); allo scadere si installa l'ultima versione di
  `main`, tutte insieme («fine del raggruppamento»). Un'installazione non riuscita (librerie, ritorno alla versione di prima) non fa
  ripartire l'intervallo. Si somma al rimando per le partite: si installa al primo giro libero dopo l'intervallo.
- **Tempi**: una pull request unita arriva in produzione entro circa 70 minuti (l'intervallo più il giro di 10 minuti); le urgenti, e
  tutte con l'intervallo a 0, entro 10 minuti; più tardi durante le partite e nell'ora prima di una scadenza. L'ambiente di prova le
  riceve tutte subito: serve al collaudo automatico.
- **Regolare l'intervallo**, sul server e senza toccare il repository: un numero di minuti da 0 a 1440 nel file
  `~/.config/schieraxi/intervallo-minuti`
  ```
  echo 0 > ~/.config/schieraxi/intervallo-minuti       # ogni versione subito, come prima
  echo 60 > ~/.config/schieraxi/intervallo-minuti      # al massimo una all'ora
  rm ~/.config/schieraxi/intervallo-minuti             # di nuovo il predefinito (60)
  ```
  oppure la variabile `SCHIERAXI_INTERVALLO_MINUTI` nella riga del crontab (vale più del file). Un valore non valido vale 60 e il
  registro lo dice. Il valore in uso va nel registro al primo giro e quando cambia:
  `grep "intervallo fra due installazioni" ~/fantacalcio/dati/pubblicazione.log | tail -n 1`.
- **Urgenze**: l'etichetta `P1` (o `urgente`) sulla pull request, messa prima dell'unione. Il job `rilascia` guarda le etichette delle
  pull request delle novità in attesa e, se una le ha, scrive nel commit di versione la riga `Rilascio: urgente`. Lo script la cerca,
  come riga intera, nei commit nuovi (dall'ultima versione installata) dopo la verifica delle firme e installa subito (nel registro:
  «versione urgente fra i commit nuovi»). Vale per le pull request con una voce di novità (quelle che toccano `fanta/`,
  `script/server/` o `requirements.txt`): le altre non hanno un commit di versione.
- **Subito, a mano**: `touch ~/.cache/fantacalcio/installa-subito` salta l'intervallo e il rimando per le partite (vedi sopra).
- **Unione senza ancora il commit di versione**: il job `rilascia` crea il commit «Versione …» 10-20 secondi dopo l'unione. Se un giro
  cade in mezzo (in `main` c'è ancora un file in `fanta/novita.d/` e il commit in testa ha meno di mezz'ora) si aspetta il giro dopo,
  invece di installare l'unione con numero di versione e novità vecchi. Oltre la mezz'ora (job `rilascia` fermo) si installa lo stesso,
  con una riga nel registro.
- **L'ultima versione rifiutata non lascia passare quelle sotto**: se la versione da installare viene rifiutata (firma, cartelle,
  librerie, ritorno alla versione di prima), le versioni buone arrivate prima e raggruppate con lei restano fuori anche loro. Non si
  installano da sole: un ripiego automatico su una versione mai provata potrebbe alternare due versioni rotte, con un riavvio a ogni
  giro. L'avviso del rifiuto lo dice («Anche le versioni arrivate prima, in attesa, non sono installate»); entrano con la prossima
  versione buona (una pull request che corregge o toglie quella rotta) oppure, per una firma, con `--fidati` dopo il controllo.
- Stato in `~/.cache/fantacalcio/`: `ultima-installazione` (ora d'inizio del giro dell'ultima installazione riuscita, in secondi),
  `raggruppata` (la versione rimandata), `intervallo-letto`. Senza `ultima-installazione` (la prima volta) si installa subito; se
  l'orologio del server è indietro rispetto a quell'ora non si aspetta (una riga nel registro).

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
- **Il ramo da installare** (dal 6/11/2026, parte di #481): è la punta del ramo `main` di origin, letta con
  `git show-ref --verify refs/remotes/origin/main`, che non cerca altri nomi: un tag o un ramo locale con un nome simile non prendono il
  suo posto. Se il ramo manca nel clone non installa niente («il ramo origin/main non esiste nel clone»). `pubblica-sito.sh` legge il
  ramo nello stesso modo. `verifica_catena` controlla anche che il commit stia nella storia di quel ramo: serve a chi la usa con un
  commit diverso dalla punta (nel giro di `aggiorna-app.sh` il commit è già la punta). Gli aggiornamenti normali non cambiano.
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
- Protegge da: commit senza firma, o firmati da un'altra chiave, spinti su `main` con `git push` (per esempio per errore), anche se
  nascosti sotto un commit firmato; force-push che riporta `main` a una versione vecchia o diversa (firmata ma che non discende
  dall'ultima verificata); una libreria nuova o modificata su PyPI (entra solo con una PR che cambia `requirements.txt`).
- NON protegge da: chi entra nell'account GitHub del proprietario (dal sito può unire PR o creare commit, e GitHub li firma lo stesso:
  **serve la verifica in due passaggi, 2FA**); chi ha un accesso in scrittura al repository (token o chiave rubati, chiave di deploy
  con scrittura): i suoi commit senza firma si fermano, ma la verifica da sola non basta, servono pochi accessi e la 2FA;
  il `GITHUB_TOKEN` dei job che scrivono (`unisci`, `rilascia`) può creare commit firmati
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
  `--fidati origin/main` vuol dire sempre il ramo `main` di origin, anche se nel clone c'è un tag con lo stesso nome.
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
