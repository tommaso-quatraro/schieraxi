#!/bin/bash
# copia-archivio-prova.sh - Ogni notte (crontab): copia l'archivio delle statistiche della produzione (~/fantacalcio/dati/fanta.sqlite)
# nell'ambiente di prova (~/schieraxi-prova/dati/fanta.sqlite), senza gli esiti della sentinella (copia_archivio.py, accanto a questo
# script). Legge la produzione in sola lettura: non ci scrive mai. Se la copia non riesce la prova tiene l'archivio di prima.
# Log: ~/schieraxi-prova/dati/copia-archivio.log (ultime 200 righe). Lo lancia anche prepara-prova.sh, per la prima copia.
# Opzione --prova: dice cosa farebbe e non scrive niente.
#   Dal crontab dell'utente del server:  20 4 * * * /bin/bash $HOME/schieraxi-prova/script/server/prova/copia-archivio-prova.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i messaggi con accenti restano giusti
PROVA=0
[ "${1:-}" = --prova ] && PROVA=1
ORIGINE="$HOME/fantacalcio/dati/fanta.sqlite"          # la produzione: solo letta
DEST="$HOME/schieraxi-prova"
ARCHIVIO="$DEST/dati/fanta.sqlite"
STATO="$HOME/.cache/schieraxi-prova"
LOG="$DEST/dati/copia-archivio.log"
QUI=$(cd "$(dirname "$0")" && pwd)
PY="$DEST/.venv/bin/python"

[ -x "$PY" ] || { echo "manca $PY: prima script/server/prova/prepara-prova.sh" >&2; exit 1; }
[ -f "$ORIGINE" ] || { echo "manca l'archivio della produzione $ORIGINE: niente da copiare" >&2; exit 1; }
if [ "$PROVA" = 1 ]; then
  echo "[prova] copierei $ORIGINE in $ARCHIVIO (sola lettura della produzione, senza la tabella controlli; log in $LOG)"
  exit 0
fi

mkdir -p "$STATO"
exec 6>"$STATO/blocco-copia-archivio"
flock -n 6 || exit 0                      # la copia di prima non ha ancora finito
umask 077                                 # archivio e log leggibili solo dall'utente del server
mkdir -p "$DEST/dati"
out=$(nice -n 19 "$PY" "$QUI/copia_archivio.py" "$ORIGINE" "$ARCHIVIO" 2>&1)
rc=$?
echo "$(date '+%F %T') $out" >> "$LOG"
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
echo "$out"
exit "$rc"
