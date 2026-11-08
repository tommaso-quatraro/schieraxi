# Ambiente di prova sullo stesso server

Una seconda copia dell'app, accanto alla produzione, con dati inventati: ogni versione nuova arriva qui **prima** che in produzione,
così un collaudo automatico (lavoro C2 del piano) la prova con un account finto e apre un'issue se qualcosa non va.
Piano: `docs/superpowers/plans/2026-11-08-ondata-2.md` (lavori C1-C3, §4). Issue #510.

**Nessun comando di questa pagina si esegue senza l'ok del proprietario.** Si lavora nella sessione `casa`, come utente del server
(`<utente>`), un passo alla volta. Ogni passo ha la sua **Prova**: se non torna ci si ferma. Ogni passo ha il suo **Indietro**;
il ritorno indietro completo è il passo 4.9. Nei comandi `<dominio>` e `<utente>` si scrivono al momento: non vanno nel repository.

| | Produzione (non cambia) | Ambiente di prova |
|---|---|---|
| Cartella | `~/fantacalcio` | `~/schieraxi-prova` |
| Stato degli aggiornamenti | `~/.cache/fantacalcio` | `~/.cache/schieraxi-prova` |
| Servizio | `fantacalcio`, `127.0.0.1:8000` | `schieraxi-prova`, `127.0.0.1:8001` |
| Indirizzo | `https://app.<dominio>` | `https://prova.<dominio>` (non indicizzato) |
| Utenti | quelli veri | solo l'account di collaudo (registrazione con invito) |
| Dati di calcio | aggiornati dalle fonti | copia notturna dell'archivio della produzione, senza gli esiti della sentinella |
| Leghe | quelle vere | la lega d'esempio (squadre inventate) |
| Posta, avvisi, fonti, lavori periodici | accesi | spenti |
| Aggiornamenti | `aggiorna-app.sh`, aspetta la fine delle partite | lo stesso script con `SCHIERAXI_ISTANZA=prova`, subito |

In comune restano solo nginx (un blocco in più), il clone `~/schieraxi-src` e la chiave delle firme (letta, mai cambiata).
Il servizio della prova è chiuso nella sua cartella: non vede `~/fantacalcio` (dati, lega vera, variabili), `~/backup-dati`,
`~/.config` (chiave delle firme, canale degli avvisi) né `~/.ssh`, e scrive solo in `~/schieraxi-prova/dati`.

## File di questa cartella

| File | A cosa serve |
|---|---|
| `prepara-prova.sh [--prova]` | passo 4.3: cartella, codice verificato, ambiente Python, dati, prima copia dell'archivio, stato. `--prova` dice cosa farebbe |
| `copia-archivio-prova.sh [--prova]` | ogni notte (passo 4.8): copia dell'archivio delle statistiche della produzione, letta e mai scritta |
| `copia_archivio.py` | la copia vera e propria (libreria standard di Python): sola lettura, senza la tabella `controlli`, tutto o niente |
| `schieraxi-prova.service` | passo 4.4: il servizio systemd, con memoria, processore e cartelle limitati |
| `ambiente-prova.env.esempio` | le variabili del servizio: account con invito, posta, lavori periodici e fonti spenti |
| `nginx-prova.conf.esempio` | passo 4.6: il blocco nginx di `prova.<dominio>`, con `X-Robots-Tag: noindex` |

`../aggiorna-app.sh` con `SCHIERAXI_ISTANZA=prova` aggiorna la prova; senza la variabile fa quello di sempre.
`SCHIERAXI_ISTANZA=prova bash ../aggiorna-app.sh --configurazione` stampa cartelle, servizio e porta che userebbe, senza scrivere niente.

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
```

Si procede solo se, **con la produzione accesa**:
- la memoria disponibile (colonna `available` di `free -m`) è almeno **700 MB**;
- il disco libero (`df -h ~`, colonna `Avail`) è almeno **3 GB**;
- il Python della produzione sta fuori da `/home` (per esempio `/usr/bin/python3.12`): il servizio della prova non vede `/home`;
- systemd è la versione 238 o più nuova (prima riga di `systemctl --version`): serve per `ProtectHome=tmpfs`;
- `certbot` c'è (se manca, installarlo è una decisione del proprietario).

Altrimenti la proposta diventa «**prova accesa solo durante il collaudo**» (servizio senza `enable`, acceso a mano prima del collaudo
e spento dopo) e si torna dal proprietario prima di andare avanti.
Da annotare per i passi dopo: il file d'ambiente del servizio di oggi (`systemctl cat fantacalcio`), la forma della regola di `sudo`
per riavviare `fantacalcio` (`sudo -l`, serve al passo 4.5) e il nome del blocco nginx di `app.<dominio>`.

Indietro: niente, sono solo letture.

## 4.2 Indirizzo

Il proprietario, nel pannello del suo registrar: un record A `prova` con lo stesso indirizzo di `app` (e un AAAA, se `app` ce l'ha).

Prova: `nslookup prova.<dominio>` dà lo stesso indirizzo di `nslookup app.<dominio>`.

Indietro: il proprietario toglie il record `prova`.

## 4.3 Cartella, codice e dati

```
cd ~/fantacalcio && bash script/server/prova/prepara-prova.sh --prova
cd ~/fantacalcio && bash script/server/prova/prepara-prova.sh
```

Il primo comando dice cosa farà e non scrive niente; il secondo lo fa (qualche minuto, per le librerie). Mette in `~/schieraxi-prova`
il codice dell'ultima versione verificata dalla produzione (`~/.cache/fantacalcio/verificato`), la lega d'esempio, un ambiente Python
con le librerie bloccate dagli hash, `dati/ambiente.env` e la prima copia dell'archivio. Se si ferma a metà (per esempio la rete),
si rilancia: riprende da dove era arrivato e non cambia quello che c'è già.

Prova:
- `ls -a ~/schieraxi-prova` mostra `.venv`, `fanta`, `lega`, `script`, `tests`, `requirements.txt`, `dati`;
- `ls ~/schieraxi-prova/dati` mostra `ambiente.env`, `fanta.sqlite`, `copia-archivio.log`;
- `cat ~/.cache/schieraxi-prova/ultimo-rilascio` è uguale a `cat ~/.cache/fantacalcio/verificato`;
- `systemctl status fantacalcio --no-pager` è uguale a prima (stesso «Active: … since»).

Indietro: `mv ~/schieraxi-prova ~/schieraxi-prova.da-togliere && mv ~/.cache/schieraxi-prova ~/.cache/schieraxi-prova.da-togliere`
(si cancellano dopo una settimana, con l'ok del proprietario).

## 4.4 Servizio

```
sudo install -m 644 ~/schieraxi-prova/script/server/prova/schieraxi-prova.service /etc/systemd/system/schieraxi-prova.service
sudo sed -i "s/<utente>/$USER/g" /etc/systemd/system/schieraxi-prova.service
sudo systemd-analyze verify /etc/systemd/system/schieraxi-prova.service
sudo systemctl daemon-reload
sudo systemctl enable --now schieraxi-prova
systemctl status schieraxi-prova --no-pager
curl -s http://127.0.0.1:8001/api/salute
```

(Con «prova accesa solo durante il collaudo», al posto di `enable --now`: `sudo systemctl start schieraxi-prova`.)

Prova:
- lo stato è `active (running)` e la salute risponde con `"ok": true`;
- il servizio non vede la produzione:
  ```
  pid=$(systemctl show -p MainPID --value schieraxi-prova)
  sudo ls /proc/$pid/root/home/$USER                # solo schieraxi-prova
  sudo ls /proc/$pid/root/home/$USER/fantacalcio    # «No such file or directory»
  sudo cat /proc/$pid/environ | tr '\0' '\n' | grep -E '^FANTA_(MAIL|PIANIFICATORE|FONTE_)'    # spento / 0
  ```
- `systemctl status fantacalcio --no-pager` è uguale a prima.

Se non parte: `journalctl -u schieraxi-prova -n 50 --no-pager`. Se il motivo è `ProtectHome=tmpfs` (systemd vecchio o Python sotto
`/home`), con il proprietario si sceglie se mettere `ProtectHome=read-only` e togliere le righe `Bind…Paths` (le cartelle di
`InaccessiblePaths` restano nascoste).

Indietro: `sudo systemctl disable --now schieraxi-prova && sudo rm /etc/systemd/system/schieraxi-prova.service && sudo systemctl daemon-reload`.

## 4.5 Permesso di riavvio per gli aggiornamenti

```
sudo visudo -f /etc/sudoers.d/schieraxi-prova
```

con la sola riga (stessa forma della regola di oggi per `fantacalcio`, vista con `sudo -l` al passo 4.1; il percorso di `systemctl`
lo dice `command -v systemctl`):

```
<utente> ALL=(root) NOPASSWD: /usr/bin/systemctl restart schieraxi-prova
```

Prova: `sudo visudo -c` dice che i file sono a posto; `sudo -n systemctl restart schieraxi-prova && systemctl is-active schieraxi-prova`
dice `active` senza chiedere la password.

Indietro: `sudo rm /etc/sudoers.d/schieraxi-prova`.

## 4.6 nginx e certificato

```
sudo install -m 644 ~/schieraxi-prova/script/server/prova/nginx-prova.conf.esempio /etc/nginx/sites-available/schieraxi-prova
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

## 4.7 Account di collaudo

```
cd ~/schieraxi-prova && .venv/bin/python -m fanta invito --etichetta collaudo
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
con la cartella della prova (passo 4.9).

## 4.8 Aggiornamenti e archivio

`crontab -e`, due righe nuove (le righe di oggi non cambiano):

```
4-59/5 * * * * SCHIERAXI_ISTANZA=prova /bin/bash $HOME/schieraxi-prova/script/server/aggiorna-app.sh >/dev/null 2>&1
20 4 * * *     /bin/bash $HOME/schieraxi-prova/script/server/prova/copia-archivio-prova.sh >/dev/null 2>&1
```

La prova guarda se c'è una versione nuova ogni 5 minuti, ai minuti 4, 9, 14…: la produzione guarda ai minuti 0, 10, 20… e aspetta la
fine delle partite, quindi di solito la prova ha la versione nuova prima. I minuti diversi evitano anche di aspettare il blocco del
clone insieme alla produzione e al sito. La copia dell'archivio si rifà ogni notte alle 4:20.
Con «prova accesa solo durante il collaudo» la prima riga resta fuori: a ogni versione riavvierebbe, cioè accenderebbe, il servizio.
In quel caso si lancia a mano prima del collaudo (`SCHIERAXI_ISTANZA=prova bash ~/schieraxi-prova/script/server/aggiorna-app.sh`).

Prova:
- `SCHIERAXI_ISTANZA=prova bash ~/schieraxi-prova/script/server/aggiorna-app.sh --configurazione` mostra `~/schieraxi-prova`,
  `schieraxi-prova` e `8001`;
- `SCHIERAXI_ISTANZA=prova bash ~/schieraxi-prova/script/server/aggiorna-app.sh --prova` dice «niente di nuovo» o «firme a posto»;
- `bash ~/schieraxi-prova/script/server/prova/copia-archivio-prova.sh --prova` dice cosa copierebbe;
- `crontab -l`: le righe di prima ci sono tutte, uguali;
- dopo il primo rilascio: `tail ~/schieraxi-prova/dati/pubblicazione.log` dice «installata»; la mattina dopo
  `tail ~/schieraxi-prova/dati/copia-archivio.log` dice «archivio della prova aggiornato»;
- quando c'è il collaudo (lavoro C2): GitHub, Actions → «Collaudo della prova» → «Run workflow» → verde.

Indietro: `crontab -e` e si tolgono le due righe.

## 4.9 Tornare indietro (tutto, in quest'ordine)

```
crontab -e                                   # togliere le due righe della prova
sudo systemctl disable --now schieraxi-prova
sudo rm /etc/nginx/sites-enabled/schieraxi-prova
sudo nginx -t && sudo systemctl reload nginx
sudo certbot delete --cert-name prova.<dominio>
sudo rm /etc/systemd/system/schieraxi-prova.service /etc/sudoers.d/schieraxi-prova /etc/nginx/sites-available/schieraxi-prova
sudo systemctl daemon-reload
mv ~/schieraxi-prova ~/schieraxi-prova.da-togliere                 # si cancellano dopo una settimana, con l'ok del proprietario
mv ~/.cache/schieraxi-prova ~/.cache/schieraxi-prova.da-togliere
```

Sul PC, dalla cartella del repository:

```
gh secret delete PROVA_URL
gh secret delete PROVA_UTENTE
gh secret delete PROVA_PASSWORD
gh workflow disable collaudo-prova.yml
```

Poi il proprietario toglie il record `prova` dal registrar. `aggiorna-app.sh` resta com'è: senza `SCHIERAXI_ISTANZA` fa quello di sempre.

## Dove guardare se qualcosa non va

- servizio: `systemctl status schieraxi-prova --no-pager`, `journalctl -u schieraxi-prova -n 50 --no-pager`;
- memoria: `systemctl show schieraxi-prova -p MemoryCurrent -p MemoryPeak` (il tetto è 500 MB: oltre, systemd ferma la prova e la
  riavvia, la produzione non se ne accorge);
- aggiornamenti: `~/schieraxi-prova/dati/pubblicazione.log`; copia dell'archivio: `~/schieraxi-prova/dati/copia-archivio.log`;
- versione rifiutata per le firme: la prova non avvisa, ma la stessa versione la rifiuta anche la produzione, che avvisa. Se dopo il
  controllo si usa `--fidati` per la produzione (`../LEGGIMI.md`, «Casi limite»), lo stesso va fatto per la prova:
  `SCHIERAXI_ISTANZA=prova bash ~/schieraxi-prova/script/server/aggiorna-app.sh --fidati origin/main`.

## Scelte (le può cambiare il proprietario)

- `ProtectHome=tmpfs` con le sole cartelle della prova montate, invece di nascondere solo `~/fantacalcio/dati`: così il servizio non
  vede nemmeno la lega vera in `~/fantacalcio/lega` né le copie degli account in `~/backup-dati`. Costo se sbagliata: due righe da
  cambiare (passo 4.4).
- La copia notturna scrive sopra l'archivio della prova con l'API di backup di sqlite, non rinominando un file nuovo: la prova lo
  tiene aperto in modo WAL e un file nuovo accanto al `-wal` del vecchio sarebbe un archivio rovinato.
- La prova controlla ogni 5 minuti, ai minuti 4, 9, 14…, invece che ogni 10 come la produzione: così di solito ha la versione nuova prima.
- La prova non manda avvisi: il canale che troverebbe è quello della produzione. Se non si aggiorna se ne accorge il collaudo (C2).
- La lega d'esempio la mette `prepara-prova.sh`; `aggiorna-app.sh` non la rinnova (installa le stesse cartelle della produzione).
  Per rinnovarla: `mv ~/schieraxi-prova/lega ~/schieraxi-prova/lega.vecchia` e di nuovo `prepara-prova.sh`.
