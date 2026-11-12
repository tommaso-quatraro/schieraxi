#!/bin/bash
# backup-dati.sh - Sul server, una volta a notte: salva in ~/backup-dati/dati-AAAA-MM-GG.tar.gz una copia dei dati
# che non si rigenerano: account (account.sqlite, copiato con l'API di backup di SQLite), cartelle degli utenti,
# lega/ (regole, rose, movimenti, immagini), scelte, osservati, impostazioni degli avvisi, icona, diario, affidabilità,
# formazioni delle altre squadre, calendario della lega, stato del pianificatore, chiave delle impronte (chiave-impronte.key, 600),
# registro delle giornate (le tabelle registro_* dell'archivio, esportate in dati/registro-giornate.json: non si ricostruiscono),
# archivio delle statistiche (fanta.sqlite, copiato con l'API di backup di SQLite: non tutto si riscarica, una fonte che non risponde
# più non ridà i suoi dati storici).
# NON copia: chiavi (vapid.json), il file di configurazione dell'ambiente, iscrizioni alle notifiche (push.json), cache, backup già fatti.
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
QUI=$(cd "$(dirname "$0")" && pwd)     # la cartella di questo script (prima del cd)
. "$QUI/registri.sh" || exit 1          # registri senza collegamenti simbolici (registri.sh)
registri_sicuri "$LOG" "$LOG.tmp" || exit 1     # ~/.cache la scrive anche il servizio
cd "$RADICE" || exit 1
mkdir -p "$DEST" "$CACHE"
chmod 700 "$DEST"
exec 6>>"$CACHE/blocco-backup-dati"
flock -n 6 || exit 0
umask 077     # le copie e i file temporanei sono leggibili solo dall'utente del server

fallito() {
  { echo "=== $(date '+%F %T') $1"; } >> "$LOG"
  ruota_registro "$LOG" 100
  exit 1
}

# Avvisi al gestore (solo per la copia dell'archivio, vedi 3b): canale ntfy come aggiorna.sh, in ~/.config/schieraxi/canale (o nel file
# di SCHIERAXI_CANALE). Al massimo uno al giorno (meno un'ora di tolleranza: il cron parte ogni notte alla stessa ora).
GIORNO=86400
TOLLERANZA=3600
SEGNO_ARCHIVIO="$CACHE/avvisato-copia-archivio"     # ora (secondi) dell'ultimo avviso «copia senza l'archivio»
avvisa() {   # testo; esce con 0 solo se l'avviso è partito
  local canale
  canale=$(tr -d ' \r\n' < "${SCHIERAXI_CANALE:-$HOME/.config/schieraxi/canale}" 2>/dev/null)
  [ -n "$canale" ] || return 1
  curl -fsS -m 20 -H 'Content-Type: application/json' \
    -d "{\"topic\":\"$canale\",\"title\":\"SchieraXI: copia notturna\",\"message\":\"$1\",\"priority\":4,\"tags\":[\"floppy_disk\"]}" \
    https://ntfy.sh >/dev/null 2>&1
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

# 3b. Archivio delle statistiche (qualche MB): copia coerente con l'API di backup di SQLite, come per gli account, aperto in sola
#     lettura (mode=ro: non lo cambia mai) e senza fermare il servizio (in modo WAL chi legge non blocca chi scrive; la copia prende
#     anche i dati confermati ancora nel file -wal). La copia esce dal modo WAL (un file solo, che si apre senza file di appoggio) e si
#     controlla (quick_check). Ripristino: docs/RIPRISTINO-SERVER.md, passo 2.
#     Se non riesce, il resto si salva lo stesso (account, utenti e registro non aspettano l'archivio), ma quella notte niente rotazione:
#     restano le copie di prima, con l'archivio. Più un avviso, al massimo uno al giorno, e uno quando la copia torna completa.
archivio=""                           # ok | non-riuscito (vuoto: l'archivio non c'è, per esempio su un server appena installato)
if [ -f dati/fanta.sqlite ]; then
  archivio=ok
  if ! errore=$($PY -c '
import sqlite3, sys
from pathlib import Path
s = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + "?mode=ro", uri=True, timeout=60)
d = sqlite3.connect(sys.argv[2])
s.backup(d); s.close()
d.execute("PRAGMA journal_mode = DELETE")
esito = d.execute("PRAGMA quick_check").fetchone()[0]; d.close()
sys.exit(0 if esito == "ok" else "controllo della copia: " + esito)
' dati/fanta.sqlite "$stage/dati/fanta.sqlite" 2>&1 >/dev/null); then
    archivio=non-riuscito
    rm -f -- "$stage/dati/fanta.sqlite" "$stage/dati/fanta.sqlite-journal" "$stage/dati/fanta.sqlite-wal" "$stage/dati/fanta.sqlite-shm"
    echo "=== $(date '+%F %T') copia dell'archivio delle statistiche non riuscita: $(printf '%s\n' "$errore" | tail -n 1)" \
         "(copia salvata senza l'archivio, copie di prima tenute)" >> "$LOG"
    ruota_registro "$LOG" 100
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

# 6. Rotazione: restano le ultime $TIENI copie (i nomi con la data si ordinano da soli). Non con una copia senza l'archivio (3b).
if [ "$archivio" != non-riuscito ]; then
  ls -1 "$DEST"/dati-????-??-??.tar.gz 2>/dev/null | sort | head -n -"$TIENI" | while IFS= read -r vecchia; do
    rm -f -- "$vecchia"
  done
fi

# 7. Avvisi sull'archivio (3b), dopo che la copia è salvata. L'ora si segna e il segno si toglie solo se l'avviso è partito.
if [ "$archivio" = non-riuscito ]; then
  ultimo=$(cat "$SEGNO_ARCHIVIO" 2>/dev/null); [[ $ultimo =~ ^[0-9]{1,12}$ ]] || ultimo=0
  adesso=$(date +%s)
  if [ ! -L "$SEGNO_ARCHIVIO" ] && [ $(( adesso - ultimo )) -ge $(( GIORNO - TOLLERANZA )) ] \
     && avvisa "La copia di stanotte non contiene l'archivio delle statistiche (motivo in backup-dati.log): le copie di prima restano."; then
    echo "$adesso" > "$SEGNO_ARCHIVIO"
  fi
elif [ "$archivio" = ok ] && [ -f "$SEGNO_ARCHIVIO" ] && [ ! -L "$SEGNO_ARCHIVIO" ]; then
  avvisa "La copia notturna contiene di nuovo l'archivio delle statistiche." && rm -f -- "$SEGNO_ARCHIVIO"
fi

date '+%F %T' > "$CACHE/ultimo-backup-dati"
exit 0
