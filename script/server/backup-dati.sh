#!/bin/bash
# backup-dati.sh - Sul server, una volta a notte: salva in ~/backup-dati/dati-AAAA-MM-GG.tar.gz una copia dei dati
# che non si rigenerano: account (account.sqlite, copiato con l'API di backup di SQLite), cartelle degli utenti,
# lega/ (regole, rose, movimenti, immagini), scelte, osservati, impostazioni degli avvisi, icona, diario, affidabilità,
# formazioni delle altre squadre, calendario della lega, stato del pianificatore, chiave delle impronte (chiave-impronte.key, 600),
# registro delle giornate (le tabelle registro_* dell'archivio, esportate in dati/registro-giornate.json: non si ricostruiscono).
# NON copia: chiavi (vapid.json), il file di configurazione dell'ambiente, iscrizioni alle notifiche (push.json), cache, backup già fatti,
# l'archivio delle statistiche (fanta.sqlite: si riscarica con `python -m fanta aggiorna`).
# Tiene le ultime 14 copie. Portarle anche fuori dal server (altro computer o altro disco).
# Non si installa da solo: serve la riga nel crontab dell'utente del server (ok dell'utente), per esempio:
#   45 3 * * * /bin/bash $HOME/fantacalcio/script/server/backup-dati.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i nomi con accenti restano giusti
RADICE="${FANTA_RADICE:-$HOME/fantacalcio}"          # per le prove si può cambiare; sul server è la cartella dell'app
DEST="${FANTA_BACKUP_DIR:-$HOME/backup-dati}"        # fuori dalla cartella dell'app: gli aggiornamenti non la toccano
PY="${FANTA_PYTHON:-python3}"
TIENI=14
CACHE="${FANTA_CACHE:-$HOME/.cache/fantacalcio}"       # stato e log (per le prove si può cambiare)
LOG="$CACHE/backup-dati.log"
cd "$RADICE" || exit 1
mkdir -p "$DEST" "$CACHE"
chmod 700 "$DEST"
exec 6>"$CACHE/blocco-backup-dati"
flock -n 6 || exit 0
umask 077     # le copie e i file temporanei sono leggibili solo dall'utente del server

fallito() {
  { echo "=== $(date '+%F %T') $1"; } >> "$LOG"
  tail -n 100 "$LOG" > "$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
  exit 1
}

oggi=$(date +%F)
out="$DEST/dati-$oggi.tar.gz"
tmp=$(mktemp -d "$DEST/.tmp-XXXXXX") || fallito "non riesco a creare la cartella temporanea"
trap 'rm -rf "$tmp"' EXIT
stage="$tmp/copia"
mkdir -p "$stage/dati"

# 1. Cose che esistono solo se l'app è installata: copia ciò che c'è, senza sbandierare errori per le mancanti.
[ -d lega ] && cp -a lega "$stage/"
[ -d dati/utenti ] && cp -a dati/utenti "$stage/dati/"
for f in scelte.json osservati.json avvisi-impostazioni.json icona.json diario.json affidabilita.json \
         formazioni_altre_squadre.json calendario_lega.json pianificatore.json; do
  [ -f "dati/$f" ] && cp -a "dati/$f" "$stage/dati/"
done
# La chiave delle impronte va insieme ad account.sqlite: senza, dopo un ripristino indirizzi e dispositivi noti non valgono più.
# Resta leggibile solo dall'utente del server (umask 077 sopra, più chmod per sicurezza).
if [ -f dati/chiave-impronte.key ]; then
  cp dati/chiave-impronte.key "$stage/dati/" && chmod 600 "$stage/dati/chiave-impronte.key"
fi

# 2. Database degli account: copia coerente anche mentre il servizio lo usa, poi controllo di integrità sulla copia.
if [ -f dati/account.sqlite ]; then
  if ! $PY -c '
import sqlite3, sys
s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2])
s.backup(d); d.close(); s.close()
c = sqlite3.connect(sys.argv[2]); esito = c.execute("PRAGMA integrity_check").fetchone()[0]; c.close()
sys.exit(0 if esito == "ok" else 1)
' dati/account.sqlite "$stage/dati/account.sqlite"; then
    fallito "copia del database degli account non riuscita (integrità)"
  fi
fi

# 3. Registro delle giornate: solo le sue tabelle, lette in sola lettura e tutte insieme (coerenti anche mentre il servizio scrive),
#    in un file JSON piccolo (fanta/registro_copia.py, solo libreria standard). Se non riesce, niente copia stanotte: così non parte
#    nemmeno la rotazione e restano le copie vecchie con il registro buono. Ripristino: docs/RIPRISTINO-SERVER.md.
if [ -f dati/fanta.sqlite ]; then
  if ! errore=$($PY -m fanta.registro_copia esporta --archivio dati/fanta.sqlite "$stage/dati/registro-giornate.json" 2>&1 >/dev/null); then
    fallito "copia del registro delle giornate non riuscita: $errore"
  fi
fi

# 4. Niente chiavi né iscrizioni alle notifiche né file a metà: tolti dalla copia prima di impacchettare.
find "$stage" \( -name push.json -o -name '*.tmp' \) -delete

# 5. Pacchetto nella stessa cartella (così lo spostamento finale è atomico), poi controllo che si possa leggere.
if ! tar -czf "$tmp/nuovo.tar.gz" -C "$stage" . || ! tar -tzf "$tmp/nuovo.tar.gz" >/dev/null; then
  fallito "pacchetto non riuscito"
fi
chmod 600 "$tmp/nuovo.tar.gz"
mv -f "$tmp/nuovo.tar.gz" "$out" || fallito "non riesco a salvare $out"

# 6. Rotazione: restano le ultime $TIENI copie (i nomi con la data si ordinano da soli).
ls -1 "$DEST"/dati-????-??-??.tar.gz 2>/dev/null | sort | head -n -"$TIENI" | while IFS= read -r vecchia; do
  rm -f -- "$vecchia"
done

date '+%F %T' > "$CACHE/ultimo-backup-dati"
exit 0
