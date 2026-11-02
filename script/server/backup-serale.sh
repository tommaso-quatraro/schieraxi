#!/bin/bash
# backup-serale.sh - Sul server, una volta al giorno: salva in ~/fantacalcio/dati/backup/ una copia di regole, rose, scelte, osservati
# e impostazioni degli avvisi (le ultime 7). Niente chiavi. Serve per tornare indietro dopo un errore; la copia sta sullo stesso disco,
# quindi per proteggersi da un guasto del disco va portata altrove.
#   Dal crontab dell'utente del server:  30 3 * * * /bin/bash $HOME/fantacalcio/script/server/backup-serale.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i nomi con accenti restano giusti
cd "$HOME/fantacalcio" || exit 1
# Se c'è dati/ambiente.env (le variabili del servizio, per esempio FANTA_MULTIUTENTE=1) le legge riga per riga, senza eseguirlo
# (solo CHIAVE=valore per FANTA_* e MAX_UTENTI, vedi leggi-ambiente.sh): senza il file non cambia niente.
. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env
mkdir -p dati "$HOME/.cache/fantacalcio"
exec 6>"$HOME/.cache/fantacalcio/blocco-backup"
flock -n 6 || exit 0
umask 077     # i log e i file nuovi di dati/ (indirizzi, iscrizioni) sono leggibili solo dall'utente del server
chmod 600 dati/*.log 2>/dev/null
if ! out=$(nice -n 15 .venv/bin/python -m fanta backup 2>&1); then
  { echo "=== $(date '+%F %T')"; echo "$out"; } >> dati/backup.log
  tail -n 100 dati/backup.log > dati/backup.log.tmp && mv dati/backup.log.tmp dati/backup.log
fi
exit 0
