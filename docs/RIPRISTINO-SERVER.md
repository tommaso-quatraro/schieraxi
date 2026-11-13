# Rifare il servizio da un backup

Come riportare in vita SchieraXI (più utenti, come in produzione) partendo soltanto da questo repository e da una copia
notturna di `script/server/backup-dati.sh` (`dati-AAAA-MM-GG.tar.gz`).

**Provato il 2/11/2026** su una cartella di prova: servizio di nuovo in piedi in **circa 5 minuti** (librerie 1,5 min,
statistiche 1,5 min, il resto meno di un minuto). Non sono compresi i passi di sistema (nginx, certificato, firewall, DNS):
quelli dipendono dal server e la loro configurazione non sta in questo repository.
Il passo 5 (registro delle giornate) è provato il 5/11/2026 su una cartella di prova con dati inventati: copia notturna,
pacchetto estratto, archivio nuovo; 7 giornate e 21 righe di giocatori tornate identiche, e il comando ripetuto non aggiunge niente.
L'archivio delle statistiche nella copia (#607, novembre 2026) è provato con dati inventati da `tests/test_script_server_avvisi.py`:
copia fatta con il servizio acceso (dati ancora nel file `-wal`), pacchetto estratto come al passo 2, archivio che si apre da solo
con gli stessi dati, e il passo 5 che non aggiunge niente.

## Cosa c'è nella copia notturna e cosa no

| Nella copia | NON nella copia | Cosa succede se manca |
|---|---|---|
| `dati/account.sqlite` (account, sessioni, inviti, token del widget) | `dati/diario.json` delle giornate chiuse dopo la copia | si ricostruisce: passo 6 |
| `dati/chiave-impronte.key` (va insieme agli account) | `dati/vapid.json` (chiavi delle notifiche) | l'app ne crea di nuove da sola, ma ogni dispositivo deve **riattivare le notifiche** |
| `dati/fanta.sqlite` (archivio delle statistiche, con il registro delle giornate; nelle copie da novembre 2026) | `push.json` (iscrizioni alle notifiche) | come sopra |
| `dati/utenti/<account>/` (regole, rose, scelte, diario, avvisi, immagini, backup) | `/etc/schieraxi/fantacalcio.env` (variabili del servizio, contiene segreti; fuori dalla cartella dell'app) | va riscritto: passo 3 |
| `lega/` (regole, rose, immagini) | `dati/smtp.password` (password della casella email) | niente email finché non la riscrivi: passo 3 |
| `dati/scelte.json`, `diario.json`, `affidabilita.json`, ecc. | `dati/avatar_tratti.json` (non è pubblico) | volti con la carnagione neutra |
| `dati/registro-giornate.json` (registro delle giornate: le tabelle `registro_*` dell'archivio, i numeri mostrati prima di ogni giornata; NON si ricostruiscono) | `~/.config/schieraxi/canale` (canale degli avvisi) | niente avvisi al gestore finché non lo rimetti |
| | `~/.config/schieraxi/chiavi-firma.asc` | si ricopia da `script/server/chiavi/` (vedi `script/server/LEGGIMI.md`, «Accendere») |
| | configurazione di sistema (nginx, systemd, fail2ban, ufw, crontab) | va tenuta dal gestore fuori da questo repository |
| | le statistiche arrivate dopo la notte della copia | si scaricano: passo 4 |

Le statistiche non si riscaricano tutte: una fonte che chiude o cambia non ridà le stagioni e le partite di prima. Per questo
l'archivio sta nella copia, preso con l'API di backup di SQLite senza fermare il servizio (qualche MB, meno di un secondo).
Le copie fatte prima di novembre 2026 non lo hanno: col passo 4 si riscarica quello che le fonti danno ancora.
Una notte in cui la copia dell'archivio non riesce, il pacchetto si salva lo stesso senza `dati/fanta.sqlite`, con un avviso, e le
copie di prima restano (quella notte non se ne toglie nessuna). In quel caso, al passo 2 estrai la copia più recente (account e
utenti aggiornati), poi il solo archivio dalla più recente che lo contiene (si vede con `tar -tzf ~/dati-AAAA-MM-GG.tar.gz`):
`tar -xzf ~/dati-AAAA-MM-GG.tar.gz -C ~/fantacalcio ./dati/fanta.sqlite`.

## Passi (utente del server, nella sua home)

1. **Codice**: `git clone https://github.com/<proprietario>/schieraxi.git fantacalcio && cd fantacalcio`.
   Python come in produzione (3.12): `python3 -m venv .venv && .venv/bin/python -m pip install --require-hashes -r requirements.txt`.
2. **Dati**: `tar -xzf ~/dati-AAAA-MM-GG.tar.gz -C ~/fantacalcio` (crea `dati/` e `lega/`; nelle copie da novembre 2026 anche
   `dati/fanta.sqlite`, un file solo senza `-wal`). Su Windows con il `tar` di Git serve
   `tar --force-local -xzf ...` (altrimenti il `C:` del percorso viene preso per un server).
   Su una cartella nuova, come qui, non c'è altro. Se invece ripristini sopra una cartella già usata: prima ferma il servizio e
   sposta via i file `-wal` e `-shm` accanto ai database (`dati/*.sqlite-wal`, `dati/*.sqlite-shm`), che sono dei database di prima
   e rovinerebbero quelli della copia.
   Sopra una cartella già usata restano anche le cartelle `dati/utenti/<numero>` degli account nati dopo la notte della copia:
   quegli account nel database della copia non ci sono, e i loro numeri tornano liberi per i prossimi iscritti. Prima di
   riavviare il servizio, cioè prima che qualcuno possa iscriversi:
   - `.venv/bin/python -m fanta cartelle-senza-account` elenca quelle cartelle (e i numeri rimasti nelle consigliate già
     mostrate). Sono di persone che dovranno iscriversi di nuovo: se vuoi tenerne i dati, sposta la cartella fuori da
     `dati/utenti/` (per esempio `mkdir -p dati/utenti-da-parte && mv dati/utenti/<numero> dati/utenti-da-parte/<numero>-ripristino`);
   - `.venv/bin/python -m fanta cartelle-senza-account --esegui` cancella quelle rimaste;
   - controllo: lo stesso comando senza `--esegui` → `Nessuna cartella senza account.`
   Con un `dati/account.sqlite` ricreato vuoto il comando non cancella niente (sembrerebbero tutte senza account): lì le cartelle
   in `dati/utenti/` vanno spostate a mano come sopra. Se una cartella resta lo stesso, il server la sposta da solo in
   `dati/utenti-da-parte/` quando il suo numero va a un account nuovo, con una riga `cartella_messa_da_parte` nel registro di
   sicurezza (Amministrazione): il nuovo account parte comunque vuoto. Le cartelle in `dati/utenti-da-parte/` non entrano nella
   copia notturna e non scadono da sole: hanno dati personali, toglile quando non servono più.
   Controllo: `.venv/bin/python -c "import sqlite3; print(sqlite3.connect('dati/account.sqlite').execute('PRAGMA integrity_check').fetchone()[0])"` → `ok`,
   e lo stesso con `dati/fanta.sqlite` e `PRAGMA quick_check` (se c'è) → `ok`.
3. **Variabili del servizio** in `/etc/schieraxi/fantacalcio.env`, un file di root che il servizio legge ma non può scrivere
   (cartella `750`, file `640`, proprietario `root`, gruppo quello dell'utente del servizio; comandi in «Spostare le variabili del
   servizio», qui sotto). Mai nella cartella dell'app: `dati/` la scrive il servizio, e systemd legge quel file come root.
   In una prova locale senza permessi di root va bene anche `dati/ambiente.env` (permessi 600): gli script lo leggono ancora, con
   un avviso. Una riga `NOME=valore` per variabile. Senza le prime tre il servizio parte ma **non è quello di produzione**:
   - `FANTA_MULTIUTENTE=1` (obbligatoria: senza, l'app parte senza login);
   - `FANTA_FONTI_PREDEFINITO=1` (nel codice pubblico le fonti dei dati sono spente: senza, il passo 4 non scarica niente);
   - `FANTA_PROFILO_FUNZIONI=completo` (le funzioni di un server già in uso);
   - `FANTA_PROXY=1` dietro nginx (in una prova locale senza nginx: `0`);
   - `FANTA_LEGA` (cartella `lega/` della copia, percorso assoluto), `FANTA_AVATAR_TRATTI=dati/avatar_tratti.json`;
   - `FANTA_CONTATTO`, `FANTA_TITOLARE` (pagine Privacy e Termini); `FANTA_GOOGLE_CLIENT_ID`, `FANTA_GOOGLE_CLIENT_SECRET`,
     `FANTA_GOOGLE_REDIRECT` (accesso con Google: se mancano, il pulsante sparisce e gli account restano usabili con la password);
   - email: `FANTA_MAIL=smtp`, `FANTA_SMTP_HOST`, `FANTA_SMTP_PORT`, `FANTA_SMTP_UTENTE`, `FANTA_MAIL_DA`, `FANTA_POSTA_FORNITORE` e
     `FANTA_SMTP_PASSWORD_FILE=dati/smtp.password` (un percorso relativo parte dalla cartella dell'app). La password NON è nella
     copia: va riscritta nel file senza farla comparire nella cronologia, con
     `(umask 077; IFS= read -rs -p "Password: " p; printf '%s\n' "$p" > dati/smtp.password; unset p)` (non si vede mentre la scrivi
     o la incolli). Senza, le email (codici di verifica e di recupero) non partono, il resto funziona.
   I valori non stanno nel repository. Per i comandi a mano (passi 4-7) le stesse variabili vanno caricate nella shell:
   `. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env` (legge il file senza eseguirlo, prima `/etc/schieraxi/fantacalcio.env`
   e solo se manca `dati/ambiente.env`; il servizio le prende da solo con il drop-in di systemd, `script/server/ambiente.conf.esempio`).
4. **Statistiche**: `.venv/bin/python -m fanta aggiorna`. Con `dati/fanta.sqlite` della copia (passo 2) scarica solo quello che
   manca o che può essere cambiato dalla notte della copia. Senza (copie di prima di novembre 2026) lo riscarica tutto: circa
   1,5 minuti, una cinquantina di richieste, e i dati storici che una fonte non dà più restano persi.
5. **Registro delle giornate** (i numeri mostrati prima di ogni giornata, che non si riscaricano). Con l'archivio della copia
   (passo 2) il registro c'è già e il comando qui sotto fa solo da controllo (`0 giornate, ... nuove`); rimette davvero le righe con
   le copie di prima di novembre 2026, dopo il passo 4:
   `.venv/bin/python -m fanta.registro_copia importa dati/registro-giornate.json` → `Registro rimesso in .../dati/fanta.sqlite:
   N giornate, M righe di giocatori, K righe dei numeri nostri, J righe delle misure dei numeri nostri e T versioni della taratura
   di «gioca N%» nuove; 0 righe c'erano già e sono rimaste com'erano.` Aggiunge solo le righe che mancano e non tocca il resto
   dell'archivio; con un file rovinato non scrive niente. Controllo: lo stesso comando una seconda volta dà `0 giornate, 0 righe di
   giocatori, 0 righe dei numeri nostri, 0 righe delle misure dei numeri nostri e 0 versioni della taratura di «gioca N%» nuove`.
   Se `dati/registro-giornate.json` non c'è (copie fatte prima del 5/11/2026) il
   registro riparte vuoto. Le giornate salvate tra la notte della copia e il guasto sono perse: il registro non si rifà.
   **Server tornato a una versione di prima della taratura di «gioca N%»** (#379, novembre 2026): le copie fatte dopo hanno anche
   la tabella `taratura_probabili` e quella versione le rifiuta (`il file contiene tabelle che non sono del registro:
   taratura_probabili`), senza scrivere niente. Prima si fa una copia del file senza la taratura (l'originale resta com'è), poi si
   rimette quella:
   `python3 -c "import json,sys; f=sys.argv[1]; d=json.load(open(f,encoding='utf-8')); d['tabelle'].pop('taratura_probabili',None); open(f+'.senza-taratura','w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False))" dati/registro-giornate.json`
   e poi `.venv/bin/python -m fanta.registro_copia importa dati/registro-giornate.json.senza-taratura`. La taratura non si perde:
   tornati a una versione che la conosce, `python -m fanta taratura-probabili` la rifà dal registro con gli stessi numeri (o si
   rimette il file originale, che aggiunge solo le righe che mancano).
6. **Diario**: `.venv/bin/python -m fanta affidabilita` (rimette nel diario le giornate chiuse dopo la copia; pochi secondi).
7. **Controlli prima di aprire al pubblico**:
   - `.venv/bin/python -m fanta sentinella --senza-invio` → `0 rotture` (rifà per ogni utente le risposte di Oggi, Formazione,
     Diario, widget e Live). Un avviso `diario_mancante` vuol dire che il passo 6 non è stato fatto;
   - avviato il servizio: `curl -s -H "X-Fanta: 1" http://127.0.0.1:8000/api/account/me` contiene `"multiutente":true`,
     e `curl -s -o /dev/null -w "%{http_code}" -H "X-Fanta: 1" http://127.0.0.1:8000/api/formazione` dà `401`;
   - accesso: per non usare password vere crea un account di prova con `.venv/bin/python -m fanta invito --etichetta prova --admin`
     e iscriviti con quel codice; da amministratore `GET /api/admin/utenti` deve elencare gli account della copia (più quello di prova). Poi elimina l'account di prova.
8. **Sistema**: servizio systemd (`script/server/fantacalcio.service`, il drop-in delle variabili `script/server/ambiente.conf.esempio`
   più quelli del gestore), nginx, certificato, crontab
   (`script/server/LEGGIMI.md`), chiave delle firme e canale degli avvisi in `~/.config/schieraxi/`.
   Fuso orario: l'app usa da sola l'ora italiana (Europe/Rome) qualunque sia quello del sistema (`fanta/fuso.py`) e la salute
   avvisa se non ci riesce. Per avere in ora italiana anche le righe dei registri scritte dagli script:
   `sudo timedatectl set-timezone Europe/Rome` (controllo: `timedatectl`, riga «Time zone»).

## Spostare le variabili del servizio

Fino a novembre 2026 le variabili stavano in `dati/ambiente.env`, dentro la cartella che il servizio scrive. systemd legge quel file
come root, prima del recinto del servizio, e segue i collegamenti simbolici: il posto giusto è un file di root che il servizio può
solo leggere. Lo spostamento lo fa il gestore, a mano, una volta sola; `<utente>` è l'utente del servizio e `<gruppo>` il suo gruppo
(di solito lo stesso nome). Si può fare prima o dopo l'aggiornamento degli script: finché il file vecchio resta (fino al passo 7),
gli script di prima lo leggono ancora e quelli nuovi leggono il file nuovo.

1. Guarda il drop-in di adesso: `systemctl cat fantacalcio`. Nel file `fantacalcio.service.d/ambiente.conf` ci devono essere solo
   `EnvironmentFile=` e `UMask=0077`; se c'è altro, aggiungilo nel passo 5.
2. Copia del drop-in di adesso, per tornare indietro:
   `sudo cp /etc/systemd/system/fantacalcio.service.d/ambiente.conf /etc/systemd/system/fantacalcio.service.d/ambiente.conf.prima`.
3. Cartella e file vuoto con i permessi giusti, poi il contenuto. Il file vecchio si legge come `<utente>` (mai come root: se al
   suo posto ci fosse un collegamento simbolico, root leggerebbe quello a cui punta):
   - `sudo install -d -m 750 -o root -g <gruppo> /etc/schieraxi`
   - `sudo install -m 640 -o root -g <gruppo> /dev/null /etc/schieraxi/fantacalcio.env`
   - `sudo -u <utente> cat /home/<utente>/fantacalcio/dati/ambiente.env | sudo tee /etc/schieraxi/fantacalcio.env >/dev/null`
4. Controllo: `sudo -u <utente> diff /home/<utente>/fantacalcio/dati/ambiente.env /etc/schieraxi/fantacalcio.env && echo uguali`
   e `sudo ls -l /etc/schieraxi` (`-rw-r----- root <gruppo> fantacalcio.env`).
5. Il drop-in punta al file nuovo (lo stesso contenuto di `script/server/ambiente.conf.esempio`; senza `-` davanti al percorso, così
   se il file manca il servizio non parte senza le sue variabili), poi si ricarica e si riavvia:
   - `printf '[Service]\nEnvironmentFile=/etc/schieraxi/fantacalcio.env\nUMask=0077\n' | sudo tee /etc/systemd/system/fantacalcio.service.d/ambiente.conf >/dev/null`
   - `sudo systemctl daemon-reload && sudo systemctl restart fantacalcio`
6. Controlli: `systemctl show fantacalcio -p EnvironmentFiles` mostra solo `/etc/schieraxi/fantacalcio.env`;
   `curl -s -H "X-Fanta: 1" http://127.0.0.1:8000/api/account/me` contiene `"multiutente":true`. Con gli script nuovi già
   installati, come `<utente>`, `bash ~/fantacalcio/script/server/sentinella.sh --senza-invio` non stampa
   `avviso: le variabili del servizio stanno ancora`.
7. Solo quando gli script nuovi sono installati (`grep -c fantacalcio.env ~/fantacalcio/script/server/leggi-ambiente.sh` dà almeno
   `1`) si toglie il file vecchio: come `<utente>`, `rm ~/fantacalcio/dati/ambiente.env`. Le modifiche alle variabili da qui in
   poi: `sudoedit /etc/schieraxi/fantacalcio.env`, poi `sudo systemctl restart fantacalcio`.

Per tornare indietro prima del passo 7:
`sudo mv /etc/systemd/system/fantacalcio.service.d/ambiente.conf.prima /etc/systemd/system/fantacalcio.service.d/ambiente.conf`,
poi `sudo systemctl daemon-reload && sudo systemctl restart fantacalcio`. Dopo il passo 7 serve prima riscrivere il file vecchio come
`<utente>`:
`sudo cat /etc/schieraxi/fantacalcio.env | sudo -u <utente> sh -c 'umask 077; cat > /home/<utente>/fantacalcio/dati/ambiente.env'`.

## Dopo il ripristino
- Avvisa gli utenti di riattivare le notifiche (le chiavi `vapid.json` sono nuove).
- Le sessioni e i token del widget della notte della copia tornano validi; chi ha cambiato password dopo la copia ritrova quella vecchia.
- Una prova di ripristino come questa conviene ripeterla ogni tanto su una cartella usa e getta, e cancellarla subito dopo:
  la copia contiene dati personali veri.

## Restringere le cartelle scrivibili dal servizio

Da fare solo con un ok a parte del proprietario. Il recinto del servizio (drop-in `fantacalcio.service.d/sicurezza.conf`, riga
`ReadWritePaths=`) deve lasciare scrivere solo le cartelle che servono: codice e `.venv` li eseguono anche gli script dei cron,
fuori dal recinto. Il servizio scrive solo in queste cartelle (lette nel codice, novembre 2026):
- `dati/` (archivio, account, cartelle degli utenti, cache, stati: `fanta/percorsi.py` e i moduli che usano `RADICE / "dati"`);
- la cartella della lega, `lega/` o quella di `FANTA_LEGA` (regole, rose, movimenti, immagini: `fanta/server.py`, `fanta/immagini.py`);
- il solo file `~/.cache/fantacalcio/blocco` (il blocco condiviso con `aggiorna.sh`, che il servizio apre in scrittura:
  `fanta/pianificatore.py`, `blocco_processo`). Il resto di `~/.cache` non serve al servizio.
Il codice (`fanta/`) e `.venv` li legge e basta (senza permesso di scrittura Python non salva i file `.pyc`, e va bene così).

1. Guarda il drop-in: `systemctl cat fantacalcio` (riga `ReadWritePaths=`), poi fanne una copia:
   `sudo cp /etc/systemd/system/fantacalcio.service.d/sicurezza.conf /etc/systemd/system/fantacalcio.service.d/sicurezza.conf.prima`.
2. Il file del blocco deve esistere prima (di solito lo crea già `aggiorna.sh`): come `<utente>`,
   `mkdir -p ~/.cache/fantacalcio && touch ~/.cache/fantacalcio/blocco`.
3. Con `sudoedit /etc/systemd/system/fantacalcio.service.d/sicurezza.conf` la riga diventa (una sola, percorsi assoluti; se
   `FANTA_LEGA` punta altrove, quella cartella al posto di `lega`). Il `-` davanti vuol dire «se manca, si salta»: senza, una
   cartella o un file mancante in `ReadWritePaths=` impedisce al servizio di partire. `dati/` c'è sempre e resta senza `-`:
   `ReadWritePaths=/home/<utente>/fantacalcio/dati -/home/<utente>/fantacalcio/lega -/home/<utente>/.cache/fantacalcio/blocco`
4. `sudo systemctl daemon-reload && sudo systemctl restart fantacalcio`; `systemctl is-active fantacalcio` dà `active`.
5. Controlli: `systemctl show fantacalcio -p ReadWritePaths` mostra i tre percorsi; `curl -s -H "X-Fanta: 1"
   http://127.0.0.1:8000/api/account/me` contiene `"multiutente":true`; nell'app una scelta salvata resta dopo aver ricaricato la
   pagina; dopo qualche minuto `journalctl -u fantacalcio --since "-15 min" | grep -ci "read-only"` dà `0`; come `<utente>`,
   `bash ~/fantacalcio/script/server/sentinella.sh --senza-invio` dà `0 rotture`.
6. Per tornare indietro:
   `sudo mv /etc/systemd/system/fantacalcio.service.d/sicurezza.conf.prima /etc/systemd/system/fantacalcio.service.d/sicurezza.conf`,
   poi `sudo systemctl daemon-reload && sudo systemctl restart fantacalcio`.
