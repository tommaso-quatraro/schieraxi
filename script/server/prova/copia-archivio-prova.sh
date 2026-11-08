#!/bin/bash
# copia-archivio-prova.sh - Ogni notte, con l'utente della PROVA (schieraxi-prova, il suo crontab): prende la copia dell'archivio delle
# statistiche che la produzione lascia nella cartella di scambio (/srv/schieraxi-scambio/fanta.sqlite, esporta-archivio-prova.sh) e la
# mette nell'archivio della prova (~/app/dati/fanta.sqlite) con copia_archivio.py, accanto a questo script. La copia dello scambio
# si legge e basta. Se non riesce la prova tiene l'archivio di prima. Lo lancia anche prepara-prova.sh, per la prima copia.
# La cartella dati la scrive anche il servizio della prova: se al posto del log (o dell'archivio) c'e' un collegamento simbolico,
# lo script si ferma senza scrivere.
# Log: ~/app/dati/copia-archivio.log (ultime 200 righe).
# Opzione --prova: dice cosa farebbe e non scrive niente.
# Variabile per le prove: SCHIERAXI_SCAMBIO (cartella di scambio).
#   Dal crontab dell'utente della prova:  40 4 * * * /bin/bash $HOME/app/script/server/prova/copia-archivio-prova.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i messaggi con accenti restano giusti
PROVA=0
[ "${1:-}" = --prova ] && PROVA=1
ORIGINE="${SCHIERAXI_SCAMBIO:-/srv/schieraxi-scambio}/fanta.sqlite"      # la copia della produzione: solo letta
DEST="$HOME/app"
ARCHIVIO="$DEST/dati/fanta.sqlite"
STATO="$HOME/.cache/schieraxi-prova"
LOG="$DEST/dati/copia-archivio.log"
QUI=$(cd "$(dirname "$0")" && pwd)
PY="$DEST/.venv/bin/python"

if [ -e "$HOME/fantacalcio" ]; then
  echo "questa e' la casa della produzione: lo script gira con l'utente della prova, schieraxi-prova" >&2; exit 1
fi
[ -x "$PY" ] || { echo "manca $PY: prima script/server/prova/prepara-prova.sh" >&2; exit 1; }
[ -f "$ORIGINE" ] || { echo "manca la copia della produzione $ORIGINE: la fa esporta-archivio-prova.sh (LEGGIMI.md, passo 4.4)" >&2; exit 1; }
for f in "$LOG" "$LOG.tmp"; do
  if [ -L "$f" ]; then echo "$f e' un collegamento simbolico: non scrivo niente" >&2; exit 1; fi
done
if [ "$PROVA" = 1 ]; then
  echo "[prova] copierei $ORIGINE in $ARCHIVIO (copia solo letta, senza la tabella controlli; log in $LOG)"
  exit 0
fi

mkdir -p "$STATO"
exec 6>"$STATO/blocco-copia-archivio"
flock -n 6 || exit 0                      # la copia di prima non ha ancora finito
umask 077                                 # archivio e log leggibili solo dall'utente della prova
mkdir -p "$DEST/dati"
out=$(nice -n 19 "$PY" "$QUI/copia_archivio.py" "$ORIGINE" "$ARCHIVIO" 2>&1)
rc=$?
echo "$(date '+%F %T') $out" >> "$LOG"
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
echo "$out"
exit "$rc"
