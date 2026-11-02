#!/bin/bash
# sentinella.sh - Sul server, ogni ora: rifa' IN SOLA LETTURA le risposte vere dell'app per ogni utente (Oggi, Formazione, Scelta,
# Diario, widget, Live: le stesse funzioni delle rotte, senza rete) e controlla che tornino (fanta/sentinella.py).
# Esito nella tabella `controlli` (pagina «Stato dei dati»); quando un controllo si rompe per la prima volta (visto 2 giri di fila)
# un solo avviso sul canale (~/.config/schieraxi/canale, o il file in SCHIERAXI_CANALE): solo «utente N», controllo e giornata.
#   Dal crontab dell'utente del server:  37 * * * * /bin/bash $HOME/fantacalcio/script/server/sentinella.sh >/dev/null 2>&1
#   Prova a mano (stampa, non avvisa e non segna niente):  bash ~/fantacalcio/script/server/sentinella.sh --senza-invio
# Log: ~/fantacalcio/dati/sentinella.log (ultime 3000 righe). Stato degli avvisi: dati/sentinella.json.
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i testi con accenti restano giusti
cd "$HOME/fantacalcio" || exit 1
# Se c'è dati/ambiente.env (le variabili del servizio, per esempio FANTA_MULTIUTENTE=1) le legge riga per riga, senza eseguirlo
# (solo CHIAVE=valore per FANTA_* e MAX_UTENTI, vedi leggi-ambiente.sh): senza il file non cambia niente.
. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env
mkdir -p dati "$HOME/.cache/fantacalcio"
umask 077     # log e stato leggibili solo dall'utente del server
LOG=dati/sentinella.log
exec 8>"$HOME/.cache/fantacalcio/blocco-sentinella"
flock -n 8 || exit 0                     # il giro di prima non ha ancora finito
# Non durante un aggiornamento dell'app (aggiorna-app.sh tiene il blocco mentre installa e riavvia): si aspettano al massimo 3 minuti,
# poi si salta il giro. Il blocco resta preso (condiviso) per tutto il giro, così il servizio non si riavvia a meta' controllo.
exec 7>"$HOME/.cache/fantacalcio/blocco-pubblicazione"
flock -s -w "${SCHIERAXI_ATTESA_BLOCCO:-180}" 7 || { echo "$(date '+%F %T') saltata: aggiornamento dell'app in corso" >> "$LOG"; exit 0; }
echo "=== $(date '+%F %T')" >> "$LOG"
if [ $# -gt 0 ]; then                    # a mano (per esempio --senza-invio): anche sullo schermo
  nice -n 15 timeout 1200 .venv/bin/python -m fanta sentinella --minuti "${SENTINELLA_MINUTI:-10}" "$@" 2>&1 | tee -a "$LOG"
else
  nice -n 15 timeout 1200 .venv/bin/python -m fanta sentinella --minuti "${SENTINELLA_MINUTI:-10}" >> "$LOG" 2>&1
fi
tail -n 3000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exit 0
