# Rifare il servizio da un backup

Come riportare in vita SchieraXI (più utenti, come in produzione) partendo soltanto da questo repository e da una copia
notturna di `script/server/backup-dati.sh` (`dati-AAAA-MM-GG.tar.gz`).

**Provato il 2/11/2026** su una cartella di prova: servizio di nuovo in piedi in **circa 5 minuti** (librerie 1,5 min,
statistiche 1,5 min, il resto meno di un minuto). Non sono compresi i passi di sistema (nginx, certificato, firewall, DNS):
quelli dipendono dal server e la loro configurazione non sta in questo repository.

## Cosa c'è nella copia notturna e cosa no

| Nella copia | NON nella copia | Cosa succede se manca |
|---|---|---|
| `dati/account.sqlite` (account, sessioni, inviti, token del widget) | `dati/fanta.sqlite` (statistiche) | si ricostruisce: passo 4 |
| `dati/chiave-impronte.key` (va insieme agli account) | `dati/diario.json` delle giornate chiuse dopo la copia | si ricostruisce: passo 5 |
| `dati/utenti/<account>/` (regole, rose, scelte, diario, avvisi, immagini, backup) | `dati/vapid.json` (chiavi delle notifiche) | l'app ne crea di nuove da sola, ma ogni dispositivo deve **riattivare le notifiche** |
| `lega/` (regole, rose, immagini) | `push.json` (iscrizioni alle notifiche) | come sopra |
| `dati/scelte.json`, `diario.json`, `affidabilita.json`, ecc. | `dati/ambiente.env` (variabili del servizio, contiene segreti) | va riscritto: passo 3 |
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
     `FANTA_GOOGLE_REDIRECT` (accesso con Google: se mancano, il pulsante sparisce e gli account restano usabili con la password).
   I valori non stanno nel repository. Per i comandi a mano (passi 4-6) le stesse variabili vanno caricate nella shell:
   `. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env` (legge il file senza eseguirlo; il servizio le prende da solo con il drop-in di systemd).
4. **Statistiche**: `.venv/bin/python -m fanta aggiorna` (circa 1,5 minuti, una cinquantina di richieste: si fa una volta sola).
5. **Diario**: `.venv/bin/python -m fanta affidabilita` (rimette nel diario le giornate chiuse dopo la copia; pochi secondi).
6. **Controlli prima di aprire al pubblico**:
   - `.venv/bin/python -m fanta sentinella --senza-invio` → `0 rotture` (rifà per ogni utente le risposte di Oggi, Formazione,
     Diario, widget e Live). Un avviso `diario_mancante` vuol dire che il passo 5 non è stato fatto;
   - avviato il servizio: `curl -s -H "X-Fanta: 1" http://127.0.0.1:8000/api/account/me` contiene `"multiutente":true`,
     e `curl -s -o /dev/null -w "%{http_code}" -H "X-Fanta: 1" http://127.0.0.1:8000/api/formazione` dà `401`;
   - accesso: per non usare password vere crea un account di prova con `.venv/bin/python -m fanta invito --etichetta prova --admin`
     e iscriviti con quel codice; da amministratore `GET /api/admin/utenti` deve elencare gli account della copia (più quello di prova). Poi elimina l'account di prova.
7. **Sistema**: servizio systemd (`script/server/fantacalcio.service` più i drop-in del gestore), nginx, certificato, crontab
   (`script/server/LEGGIMI.md`), chiave delle firme e canale degli avvisi in `~/.config/schieraxi/`.

## Dopo il ripristino
- Avvisa gli utenti di riattivare le notifiche (le chiavi `vapid.json` sono nuove).
- Le sessioni e i token del widget della notte della copia tornano validi; chi ha cambiato password dopo la copia ritrova quella vecchia.
- Una prova di ripristino come questa conviene ripeterla ogni tanto su una cartella usa e getta, e cancellarla subito dopo:
  la copia contiene dati personali veri.
