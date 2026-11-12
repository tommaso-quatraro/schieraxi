#!/bin/bash
# esporta-archivio-prova.sh - Ogni notte, con l'utente della PRODUZIONE (il suo crontab): copia l'archivio delle statistiche
# (~/fantacalcio/dati/fanta.sqlite) nella cartella di scambio /srv/schieraxi-scambio, senza gli esiti della sentinella
# (copia_archivio.py, accanto a questo script). L'ambiente di prova gira con un altro utente, senza nessun permesso sui file della
# produzione: prende i dati di calcio solo da li', con copia-archivio-prova.sh (script/server/prova/LEGGIMI.md).
# Legge l'archivio della produzione in sola lettura e scrive solo nella cartella di scambio (la copia, 640: la legge il gruppo
# schieraxi-prova grazie al bit setgid della cartella, nessun altro), piu' il suo log e il suo blocco in ~/.cache/fantacalcio.
# Se la copia non riesce, nello scambio resta quella di prima.
# Opzione --prova: dice cosa farebbe e non scrive niente.
# Variabile per le prove: SCHIERAXI_SCAMBIO (cartella di scambio).
#   Dal crontab dell'utente del server:  10 4 * * * /bin/bash $HOME/fantacalcio/script/server/prova/esporta-archivio-prova.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i messaggi con accenti restano giusti
PROVA=0
[ "${1:-}" = --prova ] && PROVA=1
APP="$HOME/fantacalcio"
ORIGINE="$APP/dati/fanta.sqlite"                     # solo letto
SCAMBIO="${SCHIERAXI_SCAMBIO:-/srv/schieraxi-scambio}"
COPIA="$SCAMBIO/fanta.sqlite"
STATO="$HOME/.cache/fantacalcio"
LOG="$STATO/esporta-archivio-prova.log"
QUI=$(cd "$(dirname "$0")" && pwd)
PY="$APP/.venv/bin/python"

[ -x "$PY" ] || { echo "manca $PY: questo script gira con l'utente della produzione" >&2; exit 1; }
[ -f "$ORIGINE" ] || { echo "manca l'archivio della produzione $ORIGINE: niente da copiare" >&2; exit 1; }
[ -d "$SCAMBIO" ] || { echo "manca la cartella di scambio $SCAMBIO (script/server/prova/LEGGIMI.md, passo 4.3)" >&2; exit 1; }
for f in "$LOG" "$LOG.tmp"; do
  if [ -L "$f" ]; then echo "$f e' un collegamento simbolico: non scrivo niente" >&2; exit 1; fi
done
if [ "$PROVA" = 1 ]; then
  echo "[prova] copierei $ORIGINE in $COPIA (produzione solo letta, senza la tabella controlli; log in $LOG)"
  exit 0
fi

mkdir -p "$STATO"
exec 6>>"$STATO/blocco-esporta-prova"
flock -n 6 || exit 0                      # la copia di prima non ha ancora finito
umask 027                                 # la copia: leggibile dal gruppo della cartella di scambio, da nessun altro
out=$(nice -n 19 "$PY" "$QUI/copia_archivio.py" "$ORIGINE" "$COPIA" 2>&1)
rc=$?
umask 077
echo "$(date '+%F %T') $out" >> "$LOG"
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
echo "$out"
exit "$rc"
