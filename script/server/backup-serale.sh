#!/bin/bash
# backup-serale.sh - Sul server, una volta al giorno: salva in ~/fantacalcio/dati/backup/ una copia di regole, rose, scelte, osservati
# e impostazioni degli avvisi (le ultime 7). Niente chiavi. Serve per tornare indietro dopo un errore; la copia sta sullo stesso disco,
# quindi per proteggersi da un guasto del disco va portata altrove. Se la copia non riesce: riga in dati/backup.log e un avviso ntfy
# (canale in ~/.config/schieraxi/canale o nel file di SCHIERAXI_CANALE; il cron gira una volta al giorno, quindi al massimo uno al giorno).
#   Dal crontab dell'utente del server:  30 3 * * * /bin/bash $HOME/fantacalcio/script/server/backup-serale.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i nomi con accenti restano giusti
QUI=$(cd "$(dirname "$0")" && pwd)     # la cartella di questo script (prima del cd)
. "$QUI/registri.sh" || exit 1          # registri senza collegamenti simbolici (registri.sh)
cd "$HOME/fantacalcio" || exit 1
# Le variabili del servizio (per esempio FANTA_MULTIUTENTE=1), da /etc/schieraxi/fantacalcio.env o, finché non è spostato, da
# dati/ambiente.env (con un avviso): le legge riga per riga, senza eseguirle
# (solo CHIAVE=valore per FANTA_* e MAX_UTENTI, vedi leggi-ambiente.sh): senza il file non cambia niente.
. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env
mkdir -p dati "$HOME/.cache/fantacalcio"
registri_sicuri dati/backup.log dati/backup.log.tmp || exit 1
exec 6>>"$HOME/.cache/fantacalcio/blocco-backup"
flock -n 6 || exit 0
umask 077     # i log e i file nuovi di dati/ (indirizzi, iscrizioni) sono leggibili solo dall'utente del server
permessi_registri dati

avvisa() {   # testo (senza percorsi né dati: passa da ntfy.sh); esce con 0 solo se l'avviso è partito
  local canale
  canale=$(tr -d ' \r\n' < "${SCHIERAXI_CANALE:-$HOME/.config/schieraxi/canale}" 2>/dev/null)
  [ -n "$canale" ] || return 1
  # il corpo (con il nome del canale) passa dallo standard input: non compare tra gli argomenti del comando, visibili a tutti con ps
  printf '%s' "{\"topic\":\"$canale\",\"title\":\"SchieraXI: copia serale\",\"message\":\"$1\",\"priority\":4,\"tags\":[\"floppy_disk\"]}" \
    | curl -fsS -m 20 -H 'Content-Type: application/json' --data-binary @- https://ntfy.sh >/dev/null 2>&1
}

if ! out=$(nice -n 15 .venv/bin/python -m fanta backup 2>&1); then
  { echo "=== $(date '+%F %T')"; echo "$out"; } >> dati/backup.log
  ruota_registro dati/backup.log 100
  avvisa "Copia serale non riuscita (regole, rose, scelte e account): dettagli in backup.log."
fi
exit 0
