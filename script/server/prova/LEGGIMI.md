# Ambiente di prova sullo stesso server

Una seconda copia dell'app, accanto alla produzione, con dati inventati: ogni versione nuova arriva qui **prima** che in produzione,
così un collaudo automatico (lavoro C2 del piano) la prova con un account finto e apre un'issue se qualcosa non va.
Piano: `docs/superpowers/plans/2026-11-08-ondata-2.md` (lavori C1-C3, §4). Issue #510.

**Nessun comando di questa pagina si esegue senza l'ok del proprietario.** Si lavora nella sessione `casa`, come utente della
produzione (`<utente>`, quello che ha `sudo`), un passo alla volta. Ogni passo ha la sua **Prova**: se non torna ci si ferma. Ogni passo
ha il suo **Indietro**; il ritorno indietro completo è il passo 4.11. Nei comandi `<dominio>`, `<utente>` e `<proprietario>` si scrivono
al momento: non vanno nel repository.
**Comandi con `--prova` e controlli a mano**: si lanciano ai minuti che finiscono per 2 o per 7 (12, 17, 22…), lontano dai giri
automatici (produzione ai minuti 0, 10, 20…; sito ai minuti 0 e 5; prova ai minuti 4 e 9), così non si incrociano due `git fetch`
sullo stesso clone.

| | Produzione (non cambia) | Ambiente di prova |
|---|---|---|
| Utente | `<utente>` | `schieraxi-prova` (utente di sistema, senza accesso con password né shell) |
| Cartella | `~/fantacalcio` | `/srv/schieraxi-prova/app` |
| Stato degli aggiornamenti | `~/.cache/fantacalcio` | `/srv/schieraxi-prova/.cache/schieraxi-prova` |
| Clone del codice e blocco | `~/schieraxi-src`, `~/.cache/fantacalcio/blocco-pubblicazione` | suoi: `/srv/schieraxi-prova/schieraxi-src`, `…/.cache/schieraxi-prova/blocco-pubblicazione` |
| Servizio | `fantacalcio`, `127.0.0.1:8000` | `schieraxi-prova`, `127.0.0.1:8001` |
| Indirizzo | `https://app.<dominio>` | `https://prova.<dominio>` (non indicizzato) |
| Utenti dell'app | quelli veri | solo l'account di collaudo (registrazione con invito) |
| Dati di calcio | aggiornati dalle fonti | copia notturna dell'archivio della produzione, senza gli esiti della sentinella, passata da `/srv/schieraxi-scambio` |
| Leghe | quelle vere | la lega d'esempio (squadre inventate) |
| Posta, avvisi, fonti, lavori periodici | accesi | spenti |
| Aggiornamenti | `aggiorna-app.sh`, aspetta la fine delle partite | lo stesso script con `SCHIERAXI_ISTANZA=prova` e l'utente della prova, subito |

In comune restano solo nginx (un blocco in più) e la cartella di scambio, in cui la produzione scrive e la prova legge e basta.

## Cosa protegge il recinto e cosa no

Protegge:
- **Utente separato.** Servizio, crontab e aggiornamenti della prova girano con `schieraxi-prova`, che non ha nessun permesso sui file
  della produzione. Il kernel non gli lascia aprire `/proc/<processo della produzione>/cwd`, `root`, `environ` e `fd` (servono lo
  stesso utente o root), quindi niente lettura dei dati della produzione passando dai suoi processi.
- **Casa della produzione chiusa agli altri utenti** (permessi `750` o `700`, controllo al passo 4.1): anche i file leggibili da tutti
  dentro la casa restano fuori portata della prova.
- **Recinto del servizio** (`schieraxi-prova.service`): niente `/home` (`ProtectHome=tmpfs`), tutto in sola lettura tranne
  `/srv/schieraxi-prova/app/dati` e una `/tmp` privata (`ProtectSystem=strict`), invisibili chiave delle firme, clone, stato e cartella di
  scambio (`InaccessiblePaths`), processi degli altri utenti nascosti dove il kernel lo permette (`ProtectProc=invisible`), niente `sudo`
  né programmi setuid (`NoNewPrivileges`), collegamenti solo con questo computer e mai verso internet (`IPAddressAllow=localhost`,
  `IPAddressDeny=any`), memoria e processore limitati.
- **Collegamenti simbolici rifiutati.** La cartella `app/dati` la scrive anche il servizio; gli script della prova (che girano fuori
  dal recinto del servizio, con lo stesso utente) non scrivono mai attraverso un collegamento simbolico messo lì al posto di un log o
  dell'archivio: si fermano.
- **Codice controllato.** Le versioni nuove si installano solo con le firme a posto, come in produzione (stesso `aggiorna-app.sh`). La
  chiave delle firme della prova sta in `/etc/schieraxi-prova/chiavi-firma.asc`, di root: la prova non la può cambiare (nella sua casa,
  che possiede, potrebbe).
- **Root non prende niente dalla prova.** Le variabili del servizio stanno nel file del servizio (niente `EnvironmentFile`, che systemd
  leggerebbe come root prima del recinto, seguendo i collegamenti simbolici); servizio, blocco nginx e script di preparazione si
  copiano dalla copia installata in produzione (`~/fantacalcio/script/server/prova/`), mai dalla cartella della prova.

Non protegge:
- kernel, memoria, processore e disco sono in comune (limitati per la prova, non separati);
- dalla prova si può chiamare l'app della produzione su `127.0.0.1:8000`, come farebbe un visitatore ma senza passare da nginx;
- i file leggibili da tutti fuori da `/home` (per esempio `/etc`) restano leggibili dai crontab della prova (il servizio li vede solo in
  sola lettura);
- un errore in `aggiorna-app.sh` arriva anche alla produzione, che usa lo stesso script: per questo la PR resta in bozza e i test
  confrontano la configurazione senza istanza con quella di sempre.

## File di questa cartella

| File | Chi lo usa | A cosa serve |
|---|---|---|
| `prepara-prova.sh [--prova] COMMIT` | utente della prova, una volta (4.5) | clone suo, codice di `COMMIT`, ambiente Python, dati, prima copia dell'archivio, stato |
| `esporta-archivio-prova.sh [--prova]` | utente della produzione, ogni notte (4.4, 4.10) | copia dell'archivio della produzione, letto e mai scritto, nella cartella di scambio |
| `copia-archivio-prova.sh [--prova]` | utente della prova, ogni notte (4.10) | dalla cartella di scambio all'archivio della prova |
| `copia_archivio.py` | i due script qui sopra | la copia vera e propria (libreria standard di Python): sola lettura, senza la tabella `controlli`, tutto o niente, mai attraverso collegamenti simbolici |
| `schieraxi-prova.service` | systemd (4.6) | il servizio, con il suo utente, il suo recinto e le sue variabili (account con invito; posta, lavori periodici e fonti spenti) |
| `nginx-prova.conf.esempio` | nginx (4.8) | il blocco di `prova.<dominio>`, con `X-Robots-Tag: noindex` |

`../aggiorna-app.sh` con `SCHIERAXI_ISTANZA=prova` aggiorna la prova; senza la variabile fa quello di sempre. Con
`--configurazione` stampa cartella, stato, servizio, porta, clone, blocco e chiave delle firme che userebbe, senza scrivere niente. Nella casa della
produzione, con `SCHIERAXI_ISTANZA=prova`, non parte.

## 4.1 Controlli in sola lettura (decidono se si procede)

```
free -m
nproc
df -h ~
systemctl show fantacalcio -p MemoryCurrent -p MemoryPeak -p MemoryMax -p CPUWeight
systemctl cat fantacalcio
sudo -l
ls /etc/nginx/sites-enabled/
command -v certbot
readlink -f ~/fantacalcio/.venv/bin/python
systemctl --version
stat -c '%a %U:%G %n' ~ ~/fantacalcio ~/fantacalcio/dati ~/fantacalcio/lega ~/backup-dati ~/.config
grep -rn "$HOME" /etc/nginx/ || echo "nginx non usa la casa"
ls -l /etc/cron.allow /etc/cron.deny
pid=$(systemctl show -p MainPID --value fantacalcio)
sudo -u nobody ls /proc/$pid/cwd/dati          # atteso: Permission denied
sudo -u nobody cat /proc/$pid/environ          # atteso: Permission denied
sudo -u nobody ls ~/fantacalcio/dati           # atteso: Permission denied
```

Gli ultimi tre provano, con un utente qualunque (`nobody`), quello che la prova non deve poter fare: leggere la cartella dei dati
della produzione passando dal suo processo, leggerne le variabili, entrare nella sua casa.

Si procede solo se, **con la produzione accesa**:
- la memoria disponibile (colonna `available` di `free -m`) è almeno **700 MB** e il disco libero (`df -h ~`, colonna `Avail`) almeno **3 GB**;
- systemd è la versione 247 o più nuova (prima riga di `systemctl --version`: servono `ProtectHome=tmpfs` e `ProtectProc`);
- il Python della produzione (per esempio `/usr/bin/python3.12`) sta fuori da `/home`: la prova lo usa con il suo utente;
- i tre `sudo -u nobody` rispondono `Permission denied`;
- `certbot` c'è (se manca, installarlo è una decisione del proprietario).

Se la casa (`~`) ha un permesso che finisce per `5` o `1` (per esempio `755`), gli altri utenti ci entrano: con l'ok del proprietario,
e se `grep` su nginx non trova la casa, `chmod 750 ~` (indietro: `chmod <permesso di prima> ~`). Se esiste `/etc/cron.allow`, l'utente
della prova va aggiunto lì (decisione del proprietario). Altrimenti la proposta diventa «**prova accesa solo durante il collaudo**»
(servizio senza `enable`, acceso a mano prima del collaudo e spento dopo) e si torna dal proprietario prima di andare avanti.
Da annotare: il file d'ambiente del servizio di oggi (`systemctl cat fantacalcio`), la forma della regola di `sudo` per riavviare
`fantacalcio` (`sudo -l`, serve al passo 4.7) e il nome del blocco nginx di `app.<dominio>`.

Indietro: niente, sono solo letture.

## 4.2 Indirizzo

Il proprietario, nel pannello del suo registrar: un record A `prova` con lo stesso indirizzo di `app` (e un AAAA, se `app` ce l'ha).

Prova: `nslookup prova.<dominio>` dà lo stesso indirizzo di `nslookup app.<dominio>`.

Indietro: il proprietario toglie il record `prova`.

## 4.3 Utente, cartelle e chiave delle firme

```
sudo useradd --system --home-dir /srv/schieraxi-prova --no-create-home --shell /usr/sbin/nologin schieraxi-prova
sudo install -d -o schieraxi-prova -g schieraxi-prova -m 700 /srv/schieraxi-prova
sudo install -d -o <utente> -g schieraxi-prova -m 2750 /srv/schieraxi-scambio
sudo install -D -o root -g root -m 644 ~/.config/schieraxi/chiavi-firma.asc /etc/schieraxi-prova/chiavi-firma.asc
```

Scelta: casa in `/srv` e non in `/home`, perché il recinto del servizio nasconde tutta `/home` (cioè la produzione) senza eccezioni, e
perché è un utente di servizio, non una persona. La cartella di scambio è della produzione (che ci scrive) con il gruppo della prova
(che legge e basta; il bit setgid `2` dà quel gruppo a ogni file nuovo). La chiave delle firme è pubblica; la copia sta in
`/etc/schieraxi-prova`, di root, fuori dalla casa della prova: la prova non la può cambiare (`aggiorna-app.sh` con
`SCHIERAXI_ISTANZA=prova` la cerca lì).

Prova:
```
getent passwd schieraxi-prova                                      # casa /srv/schieraxi-prova, shell /usr/sbin/nologin
ls -ld /srv/schieraxi-prova /srv/schieraxi-scambio                  # drwx------ schieraxi-prova; drwxr-s--- <utente> schieraxi-prova
pid=$(systemctl show -p MainPID --value fantacalcio)
sudo -u schieraxi-prova ls /proc/$pid/cwd/dati                      # Permission denied
sudo -u schieraxi-prova ls ~/fantacalcio/dati                       # Permission denied
gpg --show-keys /etc/schieraxi-prova/chiavi-firma.asc              # la stessa impronta di ../LEGGIMI.md, «Accendere»
ls -l /etc/schieraxi-prova/chiavi-firma.asc                         # -rw-r--r-- root root
```

Indietro: questi comandi non toccano la produzione.
```
sudo userdel schieraxi-prova
sudo mv /srv/schieraxi-prova /srv/schieraxi-prova.da-togliere
sudo mv /srv/schieraxi-scambio /srv/schieraxi-scambio.da-togliere
sudo rm /etc/schieraxi-prova/chiavi-firma.asc && sudo rmdir /etc/schieraxi-prova
```

## 4.4 Prima copia dei dati di calcio per la prova

Con l'utente della produzione, nella sua casa:
```
bash ~/fantacalcio/script/server/prova/esporta-archivio-prova.sh --prova
bash ~/fantacalcio/script/server/prova/esporta-archivio-prova.sh
```

Legge `~/fantacalcio/dati/fanta.sqlite` in sola lettura e mette in `/srv/schieraxi-scambio/fanta.sqlite` una copia senza la tabella
`controlli` (gli esiti della sentinella). La stessa cosa poi la fa ogni notte il crontab della produzione (passo 4.10).

Prova:
```
ls -l /srv/schieraxi-scambio                                        # fanta.sqlite, -rw-r----- <utente> schieraxi-prova
sudo -u schieraxi-prova python3 -c "import sqlite3; c = sqlite3.connect('file:/srv/schieraxi-scambio/fanta.sqlite?mode=ro', uri=True); print(c.execute('select count(*) from calciatori').fetchone()[0], c.execute('select count(*) from controlli').fetchone()[0])"
```
Il primo numero è quello dei calciatori (qualche centinaio), il secondo `0`. `tail -n 3 ~/.cache/fantacalcio/esporta-archivio-prova.log`
dice «archivio aggiornato».

Indietro: `mv /srv/schieraxi-scambio/fanta.sqlite /srv/schieraxi-scambio/fanta.sqlite.da-togliere`.

## 4.5 Cartella, codice e dati della prova

```
cd /
v=$(cat ~/.cache/fantacalcio/verificato); echo "$v"
py=$(readlink -f ~/fantacalcio/.venv/bin/python); echo "$py"
sudo install -D -o root -g root -m 755 ~/fantacalcio/script/server/prova/prepara-prova.sh /usr/local/lib/schieraxi-prova/prepara-prova.sh
sudo -u schieraxi-prova -H env SCHIERAXI_PYTHON="$py" bash /usr/local/lib/schieraxi-prova/prepara-prova.sh --prova "$v"
sudo -u schieraxi-prova -H env SCHIERAXI_PYTHON="$py" bash /usr/local/lib/schieraxi-prova/prepara-prova.sh "$v"
```

`v` è l'ultima versione verificata dalla produzione, `py` il suo Python. Lo script lo copia root dalla copia installata in produzione
(che la prova non può leggere) in `/usr/local/lib/schieraxi-prova`, una cartella di root: non nella casa della prova, dove lei potrebbe
mettere un collegamento al suo posto. Poi gira con l'utente della prova. Il comando con `--prova` dice cosa farà e non scrive niente;
il secondo crea il clone suo (`/srv/schieraxi-prova/schieraxi-src`), mette in `/srv/schieraxi-prova/app` il codice di `v`, la lega
d'esempio, l'ambiente Python con le librerie bloccate dagli hash, la cartella `dati` e la prima copia dell'archivio presa dalla
cartella di scambio (qualche minuto, per le librerie). Le variabili del servizio non stanno lì: sono nel file del servizio (passo 4.6).
Se si ferma a metà (per esempio la rete) si rilancia: riprende da dove era arrivato e non cambia quello che c'è già.
Da qui in avanti i comandi su file dentro `/srv/schieraxi-prova` girano con l'utente della prova (`sudo -u schieraxi-prova …`), mai
come root: root seguirebbe un collegamento simbolico messo lì dalla prova.

Prova:
- `sudo -u schieraxi-prova ls -a /srv/schieraxi-prova/app` mostra `.venv`, `fanta`, `lega`, `script`, `tests`, `requirements.txt`, `dati`;
- `sudo -u schieraxi-prova ls -l /srv/schieraxi-prova/app/dati` mostra `fanta.sqlite` e `copia-archivio.log`, di `schieraxi-prova` (cartella `drwx------`);
- `sudo -u schieraxi-prova cat /srv/schieraxi-prova/.cache/schieraxi-prova/ultimo-rilascio` è uguale a `$v`;
- `systemctl status fantacalcio --no-pager` è uguale a prima (stesso «Active: … since»).

Indietro: `sudo -u schieraxi-prova mv /srv/schieraxi-prova/app /srv/schieraxi-prova/app.da-togliere`,
`sudo -u schieraxi-prova mv /srv/schieraxi-prova/.cache /srv/schieraxi-prova/.cache.da-togliere` (si cancellano dopo una settimana, con
l'ok del proprietario) e `sudo rm /usr/local/lib/schieraxi-prova/prepara-prova.sh`, poi `sudo rmdir /usr/local/lib/schieraxi-prova`.

## 4.6 Servizio

```
sudo install -o root -g root -m 644 ~/fantacalcio/script/server/prova/schieraxi-prova.service /etc/systemd/system/schieraxi-prova.service
sudo systemd-analyze verify /etc/systemd/system/schieraxi-prova.service
sudo systemctl daemon-reload
sudo systemctl enable --now schieraxi-prova
systemctl status schieraxi-prova --no-pager
curl -s http://127.0.0.1:8001/api/salute
```

(Con «prova accesa solo durante il collaudo», al posto di `enable --now`: `sudo systemctl start schieraxi-prova`.)

Prova:
- lo stato è `active (running)` e la salute risponde con `"ok": true`;
- il servizio gira con il suo utente, dentro il recinto:
  ```
  pid=$(systemctl show -p MainPID --value schieraxi-prova)
  ps -o user= -p "$pid"                                              # schieraxi-prova
  sudo ls -A /proc/$pid/root/home                                   # niente: /home per lui è vuota
  sudo cat /proc/$pid/environ | tr '\0' '\n' | grep -E '^FANTA_(MAIL|PIANIFICATORE|FONTE_)'    # spento / 0
  systemd-analyze security schieraxi-prova | tail -n 1               # il punteggio di esposizione, da annotare
  ```
- `systemctl status fantacalcio --no-pager` è uguale a prima.

Se non parte: `journalctl -u schieraxi-prova -n 50 --no-pager`. Se il motivo è una riga del recinto non supportata (systemd vecchio),
si decide con il proprietario se toglierla (la protezione dell'utente separato resta).

Indietro: `sudo systemctl disable --now schieraxi-prova && sudo rm /etc/systemd/system/schieraxi-prova.service && sudo systemctl daemon-reload`.

## 4.7 Permesso di riavvio per gli aggiornamenti

L'aggiornamento della prova (passo 4.10) riavvia il suo servizio: serve una regola di `sudo` per quel solo comando.

```
sudo visudo -f /etc/sudoers.d/schieraxi-prova
```

con la sola riga (il percorso di `systemctl` lo dice `command -v systemctl`; stessa forma della regola di oggi per `fantacalcio`,
vista con `sudo -l` al passo 4.1):

```
schieraxi-prova ALL=(root) NOPASSWD: /usr/bin/systemctl restart schieraxi-prova
```

Prova: `sudo visudo -c` dice che i file sono a posto; `sudo -u schieraxi-prova sudo -n systemctl restart schieraxi-prova && systemctl is-active schieraxi-prova`
dice `active`; `sudo -u schieraxi-prova sudo -n systemctl restart fantacalcio` viene rifiutato.

Indietro: `sudo rm /etc/sudoers.d/schieraxi-prova`.

## 4.8 nginx e certificato

```
sudo install -o root -g root -m 644 ~/fantacalcio/script/server/prova/nginx-prova.conf.esempio /etc/nginx/sites-available/schieraxi-prova
sudo sed -i "s/<dominio>/IL-DOMINIO/g" /etc/nginx/sites-available/schieraxi-prova
sudo ln -s /etc/nginx/sites-available/schieraxi-prova /etc/nginx/sites-enabled/schieraxi-prova
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d prova.<dominio>
curl -sI https://prova.<dominio>/api/salute
```

(`IL-DOMINIO` si scrive al momento, non va nel repository.) Le intestazioni di sicurezza le mette l'app, uguali alla produzione; se il
blocco nginx di `app.<dominio>` ne aggiunge altre, si copiano uguali nel blocco della prova prima del `nginx -t`.

Prova: la risposta è `200` con l'intestazione `X-Robots-Tag: noindex, nofollow`; il sito e l'app di sempre rispondono come prima
(`curl -sI https://app.<dominio>/api/salute`).

Indietro:
```
sudo rm /etc/nginx/sites-enabled/schieraxi-prova
sudo nginx -t && sudo systemctl reload nginx
sudo certbot delete --cert-name prova.<dominio>
sudo rm /etc/nginx/sites-available/schieraxi-prova
```

## 4.9 Account di collaudo

```
cd /
sudo -u schieraxi-prova -H bash -c 'cd ~/app && .venv/bin/python -m fanta invito --etichetta collaudo'
```

Con il codice, su `https://prova.<dominio>`: registrazione dell'utente `collaudo` con una password lunga generata dal gestore delle
password, poi «Prova con gli esempi» (lega d'esempio). Sul PC, dalla cartella del repository (il valore si scrive quando lo chiede, così
non resta nella cronologia):

```
gh secret set PROVA_URL
gh secret set PROVA_UTENTE
gh secret set PROVA_PASSWORD
```

Prova: l'accesso con `collaudo` su `https://prova.<dominio>` mostra Oggi con le squadre d'esempio; `gh secret list` elenca i tre nomi.

Indietro: `gh secret delete PROVA_URL`, `gh secret delete PROVA_UTENTE`, `gh secret delete PROVA_PASSWORD`. L'account se ne va
con la cartella della prova (passo 4.11).

## 4.10 Crontab

Produzione: prima una copia del crontab di oggi, poi una riga nuova (quelle di oggi non cambiano):

```
crontab -l > ~/crontab-prima-prova.txt
crontab -e
```
con la riga
```
10 4 * * *     /bin/bash $HOME/fantacalcio/script/server/prova/esporta-archivio-prova.sh >/dev/null 2>&1
```

Prova (`sudo crontab -u schieraxi-prova -e`, due righe):

```
4-59/5 * * * * SCHIERAXI_ISTANZA=prova /bin/bash $HOME/app/script/server/aggiorna-app.sh >/dev/null 2>&1
40 4 * * *     /bin/bash $HOME/app/script/server/prova/copia-archivio-prova.sh >/dev/null 2>&1
```

La prova guarda se c'è una versione nuova ogni 5 minuti, ai minuti 4, 9, 14…: la produzione guarda ai minuti 0, 10, 20… e aspetta la
fine delle partite, quindi di solito la prova ha la versione nuova prima. La copia dell'archivio parte dalla produzione alle 4:10 e
arriva nella prova alle 4:40. Con «prova accesa solo durante il collaudo» la riga di `aggiorna-app.sh` resta fuori: a ogni versione
riavvierebbe, cioè accenderebbe, il servizio; in quel caso si lancia a mano prima del collaudo.

Prova: ai minuti che finiscono per 2 o per 7,
```
cd /
sudo -u schieraxi-prova -H env SCHIERAXI_ISTANZA=prova bash /srv/schieraxi-prova/app/script/server/aggiorna-app.sh --configurazione
sudo -u schieraxi-prova -H env SCHIERAXI_ISTANZA=prova bash /srv/schieraxi-prova/app/script/server/aggiorna-app.sh --prova
sudo -u schieraxi-prova -H bash /srv/schieraxi-prova/app/script/server/prova/copia-archivio-prova.sh --prova
crontab -l | diff ~/crontab-prima-prova.txt -    # una sola riga in più: quella dell'esportazione
sudo crontab -u schieraxi-prova -l           # le due righe della prova
```
Il primo mostra `/srv/schieraxi-prova/app`, `schieraxi-prova`, `8001`, clone e blocco suoi e la chiave in `/etc/schieraxi-prova`; il secondo «niente di nuovo» o «firme a
posto». Dopo il primo rilascio `sudo -u schieraxi-prova tail /srv/schieraxi-prova/app/dati/pubblicazione.log` dice «installata»; la
mattina dopo `sudo -u schieraxi-prova tail /srv/schieraxi-prova/app/dati/copia-archivio.log` dice «archivio aggiornato». Quando c'è il collaudo (lavoro C2): GitHub,
Actions → «Collaudo della prova» → «Run workflow» → verde.

Indietro: `sudo crontab -u schieraxi-prova -r` (toglie tutto il crontab della prova) e `crontab ~/crontab-prima-prova.txt` (rimette il
crontab della produzione com'era prima; se nel frattempo ci sono state altre modifiche, invece, `crontab -e` e si toglie solo la riga
dell'esportazione).

## 4.11 Tornare indietro (tutto, in quest'ordine)

```
sudo crontab -u schieraxi-prova -r            # il crontab della prova
crontab ~/crontab-prima-prova.txt             # il crontab della produzione com'era prima (altre modifiche dopo: crontab -e e via la riga)
sudo systemctl disable --now schieraxi-prova
sudo rm /etc/nginx/sites-enabled/schieraxi-prova
sudo nginx -t && sudo systemctl reload nginx
sudo certbot delete --cert-name prova.<dominio>
sudo rm /etc/systemd/system/schieraxi-prova.service /etc/sudoers.d/schieraxi-prova /etc/nginx/sites-available/schieraxi-prova
sudo systemctl daemon-reload
sudo userdel schieraxi-prova
sudo mv /srv/schieraxi-prova /srv/schieraxi-prova.da-togliere      # si cancellano dopo una settimana, con l'ok del proprietario
sudo mv /srv/schieraxi-scambio /srv/schieraxi-scambio.da-togliere
sudo rm /etc/schieraxi-prova/chiavi-firma.asc && sudo rmdir /etc/schieraxi-prova
sudo rm /usr/local/lib/schieraxi-prova/prepara-prova.sh && sudo rmdir /usr/local/lib/schieraxi-prova
```

Root sposta la casa della prova tutta intera (`/srv/schieraxi-prova` è una voce di `/srv`, che è di root: la prova non la può
sostituire con un collegamento) e non entra mai dentro.

Sul PC, dalla cartella del repository:

```
gh secret delete PROVA_URL
gh secret delete PROVA_UTENTE
gh secret delete PROVA_PASSWORD
gh workflow disable collaudo-prova.yml
```

Poi il proprietario toglie il record `prova` dal registrar (e, se al passo 4.1 aveva cambiato il permesso della casa, decide se
rimetterlo com'era). `aggiorna-app.sh` resta com'è: senza `SCHIERAXI_ISTANZA` fa quello di sempre.

## Dove guardare se qualcosa non va

- servizio: `systemctl status schieraxi-prova --no-pager`, `journalctl -u schieraxi-prova -n 50 --no-pager`;
- memoria: `systemctl show schieraxi-prova -p MemoryCurrent -p MemoryPeak` (il tetto è 500 MB: oltre, systemd ferma la prova e la
  riavvia, la produzione non se ne accorge);
- aggiornamenti: `sudo -u schieraxi-prova tail /srv/schieraxi-prova/app/dati/pubblicazione.log`; copia dell'archivio:
  `~/.cache/fantacalcio/esporta-archivio-prova.log` (produzione) e `sudo -u schieraxi-prova tail /srv/schieraxi-prova/app/dati/copia-archivio.log` (prova);
- uno script della prova che dice «collegamento simbolico» si è fermato apposta: al posto di un log o dell'archivio in `app/dati` c'è
  un collegamento. Si guarda chi l'ha messo prima di toglierlo (`sudo -u schieraxi-prova ls -l /srv/schieraxi-prova/app/dati`);
- versione rifiutata per le firme: la prova non avvisa, ma la stessa versione la rifiuta anche la produzione, che avvisa. Se dopo il
  controllo si usa `--fidati` per la produzione (`../LEGGIMI.md`, «Casi limite»), lo stesso va fatto per la prova:
  `sudo -u schieraxi-prova -H env SCHIERAXI_ISTANZA=prova bash /srv/schieraxi-prova/app/script/server/aggiorna-app.sh --fidati origin/main`.

## Scelte (le può cambiare il proprietario)

- Utente di sistema separato con casa in `/srv`: vedi passo 4.3. Costo: tre passi in più (utente, cartella di scambio, una riga nel
  crontab della produzione).
- Clone del codice suo invece di quello della produzione: la prova non ha bisogno di nessun permesso sulla casa della produzione, e
  con il clone ha anche blocco e cartella di verifica delle firme suoi (niente da aspettare, niente da condividere). Costo: un `git
  fetch` in più ogni 5 minuti.
- Dati di calcio passati da una cartella di scambio scritta dalla produzione, invece di dare alla prova il permesso di leggere
  l'archivio della produzione.
- La copia scrive sopra l'archivio della prova con l'API di backup di sqlite, non rinominando un file nuovo: la prova lo tiene aperto
  in modo WAL e un file nuovo accanto al `-wal` del vecchio sarebbe un archivio rovinato.
- La prova controlla ogni 5 minuti, ai minuti 4, 9, 14…, invece che ogni 10 come la produzione: così di solito ha la versione nuova prima.
- La prova non manda avvisi (andrebbero al canale della produzione). Se non si aggiorna se ne accorge il collaudo (C2).
- Variabili del servizio scritte nel file del servizio invece che in un file d'ambiente: non sono segrete, e un `EnvironmentFile` in
  una cartella della prova sarebbe letto da systemd come root. Per cambiarne una si cambia il file in `/etc/systemd/system` (o, meglio,
  la copia nel repository) e poi `sudo systemctl daemon-reload` e `sudo systemctl restart schieraxi-prova`.
- La lega d'esempio la mette `prepara-prova.sh`; `aggiorna-app.sh` non la rinnova (installa le stesse cartelle della produzione).
  Per rinnovarla: `sudo -u schieraxi-prova mv /srv/schieraxi-prova/app/lega /srv/schieraxi-prova/app/lega.vecchia` (con l'utente della
  prova: come root seguirebbe un eventuale collegamento al posto di `app`) e di nuovo il passo 4.5.
