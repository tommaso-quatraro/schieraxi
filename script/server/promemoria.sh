#!/bin/bash
# promemoria.sh - Sul server, ogni 10 minuti: promemoria sul telefono (ntfy) un'ora e un quarto d'ora prima della scadenza
# della formazione. Legge solo il database locale; scrive nel log solo quando manda qualcosa.
#   Dal crontab dell'utente del server:  */10 * * * * /bin/bash $HOME/fantacalcio/script/server/promemoria.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i testi con accenti restano giusti
cd "$HOME/fantacalcio" || exit 1
# Se c'è dati/ambiente.env (le variabili del servizio, per esempio FANTA_MULTIUTENTE=1) le legge riga per riga, senza eseguirlo
# (solo CHIAVE=valore per FANTA_* e MAX_UTENTI, vedi leggi-ambiente.sh): senza il file non cambia niente.
. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env
mkdir -p dati "$HOME/.cache/fantacalcio"
exec 8>"$HOME/.cache/fantacalcio/blocco-promemoria"
flock -n 8 || exit 0
umask 077     # i log e i file nuovi di dati/ (indirizzi, iscrizioni) sono leggibili solo dall'utente del server
chmod 600 dati/*.log 2>/dev/null
out=$(nice -n 10 .venv/bin/python -m fanta promemoria 2>&1)
# controllo di salute dell'app: avvisa sul telefono se non risponde o se i dati non si aggiornano. Prima aspetta che aggiorna-app.sh
# abbia finito (blocco condiviso): mentre installa riavvia l'app e per qualche secondo non risponde (falsi allarmi del 1/11).
# Se l'installazione dura piu' di 3 minuti il controllo salta questo giro. Il controllo stesso riprova 3 volte (fanta/salute.py).
exec 7>"$HOME/.cache/fantacalcio/blocco-pubblicazione"
SALTI="$HOME/.cache/fantacalcio/salute-saltata"          # quante volte di fila il controllo e' saltato per il blocco
if flock -s -w "${SCHIERAXI_ATTESA_BLOCCO:-180}" 7; then
  out="$out$(nice -n 10 .venv/bin/python -m fanta salute 2>&1)"
  rm -f "$SALTI" "$SALTI.avvisato"
else
  out="${out}controllo di salute saltato: aggiornamento dell'app in corso"
  n=$(( $(cat "$SALTI" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$SALTI"
  # 3 salti di fila (mezz'ora): l'aggiornamento e' fermo (rete bloccata?). Un solo avviso finche' non torna normale.
  if [ "$n" -ge 3 ] && [ ! -e "$SALTI.avvisato" ]; then
    : > "$SALTI.avvisato"
    .venv/bin/python -c "
import sys
from fanta import notifiche
notifiche.invia(sys.argv[1], sys.argv[2], int(sys.argv[3]), 'warning')" "SchieraXI: controllo fermo" \
      "Il controllo di salute e' saltato 3 volte di fila: l'aggiornamento dell'app sembra bloccato." 4 >/dev/null 2>&1
    out="$out"$'\n'"avviso mandato: controllo di salute saltato $n volte"
  fi
fi
exec 7>&-
if [ -n "$out" ]; then
  { echo "=== $(date '+%F %T')"; echo "$out"; } >> dati/promemoria.log
  tail -n 300 dati/promemoria.log > dati/promemoria.log.tmp && mv dati/promemoria.log.tmp dati/promemoria.log
fi
exit 0
