# Rifare il servizio da un backup

Come riportare in vita SchieraXI (più utenti, come in produzione) partendo soltanto da questo repository e da una copia
notturna di `script/server/backup-dati.sh` (`dati-AAAA-MM-GG.tar.gz`).

**Provato il 2/11/2026** su una cartella di prova: servizio di nuovo in piedi in **circa 5 minuti** (librerie 1,5 min,
statistiche 1,5 min, il resto meno di un minuto). Non sono compresi i passi di sistema (nginx, certificato, firewall, DNS):
quelli dipendono dal server e la loro configurazione non sta in questo repository.
Il passo 5 (registro delle giornate) è provato il 5/11/2026 su una cartella di prova con dati inventati: copia notturna,
pacchetto estratto, archivio nuovo; 7 giornate e 21 righe di giocatori tornate identiche, e il comando ripetuto non aggiunge niente.

## Cosa c'è nella copia notturna e cosa no

| Nella copia | NON nella copia | Cosa succede se manca |
|---|---|---|
| `dati/account.sqlite` (account, sessioni, inviti, token del widget) | `dati/fanta.sqlite` (statistiche) | si ricostruisce: passo 4 (il registro delle giornate che c'era dentro si rimette al passo 5) |
| `dati/chiave-impronte.key` (va insieme agli account) | `dati/diario.json` delle giornate chiuse dopo la copia | si ricostruisce: passo 6 |
| `dati/utenti/<account>/` (regole, rose, scelte, diario, avvisi, immagini, backup) | `dati/vapid.json` (chiavi delle notifiche) | l'app ne crea di nuove da sola, ma ogni dispositivo deve **riattivare le notifiche** |
| `lega/` (regole, rose, immagini) | `push.json` (iscrizioni alle notifiche) | come sopra |
| `dati/scelte.json`, `diario.json`, `affidabilita.json`, ecc. | `dati/ambiente.env` (variabili del servizio, contiene segreti) | va riscritto: passo 3 |
| `dati/registro-giornate.json` (registro delle giornate: le tabelle `registro_*` dell'archivio, i numeri mostrati prima di ogni giornata; NON si ricostruiscono) | `dati/smtp.password` (password della casella email) | niente email finché non la riscrivi: passo 3 |
| | `dati/avatar_tratti.json` (non è pubblico) | volti con la carnagione neutra |
| | `~/.config/schieraxi/canale` (canale degli avvisi) | niente avvisi al gestore finché non lo rimetti |
| | `~/.config/schieraxi/chiavi-firma.asc` | si ricopia da `script/server/chiavi/` (vedi `script/server/LEGGIMI.md`, «Accendere») |
| | configurazione di sistema (nginx, systemd, fail2ban, ufw, crontab) | va tenuta dal gestore fuori da questo repository |

## Passi (utente del server, nella sua home)

1. **Codice**: `git clone https://github.com/<proprietario>/schieraxi.git fantacalcio && cd fantacalcio`.
   Python come in produzione (3.12): `python3 -m venv .venv && .venv/bin/python -m pip install --require-hashes -r requirements.txt`.
2. **Dati**: `tar -xzf ~/dati-AAAA-MM-GG.tar.gz -C ~/fantacalcio` (crea `dati/` e `lega/`). Su Windows con il `tar` di Git serve
   `tar --force-local -xzf ...` (altrimenti il `C:` del percorso viene preso per un server).
   Controllo: `.venv/bin/python -c "import sqlite3; print(sqlite3.connect('dati/account.sqlite').execute('PRAGMA integrity_check').fetchone()[0])"` → `ok`.
3. **`dati/ambiente.env`** (permessi 600), una riga `NOME=valore` per variabile. Senza le prime tre il servizio parte ma
   **non è quello di produzione**:
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
   `. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env` (legge il file senza eseguirlo; il servizio le prende da solo con il drop-in di systemd).
4. **Statistiche**: `.venv/bin/python -m fanta aggiorna` (circa 1,5 minuti, una cinquantina di richieste: si fa una volta sola).
5. **Registro delle giornate** (i numeri mostrati prima di ogni giornata, che non si riscaricano):
   `.venv/bin/python -m fanta.registro_copia importa dati/registro-giornate.json` → `Registro rimesso in .../dati/fanta.sqlite:
   N giornate, M righe di giocatori, K righe dei numeri nostri e J righe delle misure dei numeri nostri nuove; 0 righe c'erano già e
   sono rimaste com'erano.` Aggiunge solo le righe che mancano e non tocca il resto dell'archivio; con un file rovinato non scrive
   niente. Controllo: lo stesso comando una seconda volta dà `0 giornate, 0 righe di giocatori, 0 righe dei numeri nostri e 0 righe
   delle misure dei numeri nostri nuove`. Se `dati/registro-giornate.json` non c'è (copie fatte prima del 5/11/2026) il
   registro riparte vuoto. Le giornate salvate tra la notte della copia e il guasto sono perse: il registro non si rifà.
6. **Diario**: `.venv/bin/python -m fanta affidabilita` (rimette nel diario le giornate chiuse dopo la copia; pochi secondi).
7. **Controlli prima di aprire al pubblico**:
   - `.venv/bin/python -m fanta sentinella --senza-invio` → `0 rotture` (rifà per ogni utente le risposte di Oggi, Formazione,
     Diario, widget e Live). Un avviso `diario_mancante` vuol dire che il passo 6 non è stato fatto;
   - avviato il servizio: `curl -s -H "X-Fanta: 1" http://127.0.0.1:8000/api/account/me` contiene `"multiutente":true`,
     e `curl -s -o /dev/null -w "%{http_code}" -H "X-Fanta: 1" http://127.0.0.1:8000/api/formazione` dà `401`;
   - accesso: per non usare password vere crea un account di prova con `.venv/bin/python -m fanta invito --etichetta prova --admin`
     e iscriviti con quel codice; da amministratore `GET /api/admin/utenti` deve elencare gli account della copia (più quello di prova). Poi elimina l'account di prova.
8. **Sistema**: servizio systemd (`script/server/fantacalcio.service` più i drop-in del gestore), nginx, certificato, crontab
   (`script/server/LEGGIMI.md`), chiave delle firme e canale degli avvisi in `~/.config/schieraxi/`.

## Dopo il ripristino
- Avvisa gli utenti di riattivare le notifiche (le chiavi `vapid.json` sono nuove).
- Le sessioni e i token del widget della notte della copia tornano validi; chi ha cambiato password dopo la copia ritrova quella vecchia.
- Una prova di ripristino come questa conviene ripeterla ogni tanto su una cartella usa e getta, e cancellarla subito dopo:
  la copia contiene dati personali veri.
