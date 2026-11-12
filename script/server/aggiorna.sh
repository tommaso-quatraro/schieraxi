#!/bin/bash
# aggiorna.sh - Sul server: scarica i dati nuovi per l'app Fanta e avvisa l'iPhone con ntfy.
#   Dal crontab dell'utente del server:  0 8,13,17,21 * * * /bin/bash $HOME/fantacalcio/script/server/aggiorna.sh >/dev/null 2>&1
# - Priorita' bassa (nice), così gli altri servizi del server non rallentano.
# - Se l'aggiornamento fallisce 2 volte di fila: un solo avviso ("Fantacalcio: aggiornamento dati non riuscito").
# - "Formazione pronta": quando manca meno di 30 ore alla prossima giornata (una volta sola per giornata).
# - Canale ntfy: nome in ~/.config/schieraxi/canale (o nel file indicato da SCHIERAXI_CANALE). Messaggi generici, passano da ntfy.sh.
# - Log: ~/fantacalcio/dati/aggiorna.log (si tengono le ultime 2000 righe).
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): senza questo il testo dell'avviso uscirebbe con gli accenti sbagliati
QUI=$(cd "$(dirname "$0")" && pwd)     # la cartella di questo script (prima del cd)
. "$QUI/registri.sh" || exit 1          # registri senza collegamenti simbolici (registri.sh)
cd "$HOME/fantacalcio" || exit 1
# Le variabili del servizio (per esempio FANTA_MULTIUTENTE=1), da /etc/schieraxi/fantacalcio.env o, finché non è spostato, da
# dati/ambiente.env (con un avviso): le legge riga per riga, senza eseguirle
# (solo CHIAVE=valore per FANTA_* e MAX_UTENTI, vedi leggi-ambiente.sh): senza il file non cambia niente.
. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env
mkdir -p dati "$HOME/.cache/fantacalcio"
LOG=dati/aggiorna.log
registri_sicuri "$LOG" "$LOG.tmp" || exit 1
STATO="$HOME/.cache/fantacalcio/errori"
umask 077     # i log e i file nuovi di dati/ (indirizzi, iscrizioni) sono leggibili solo dall'utente del server
permessi_registri dati
canale=$(tr -d ' \r\n' < "${SCHIERAXI_CANALE:-$HOME/.config/schieraxi/canale}" 2>/dev/null)

avvisa() {   # titolo, testo
  [ -n "$canale" ] || return 0
  curl -fsS -m 20 -H 'Content-Type: application/json' \
    -d "{\"topic\":\"$canale\",\"title\":\"$1\",\"message\":\"$2\",\"priority\":3,\"tags\":[\"soccer\"]}" \
    https://ntfy.sh >/dev/null
}

exec 9>>"$HOME/.cache/fantacalcio/blocco"
flock -n 9 || exit 0          # un altro aggiornamento e' gia' in corso

echo "=== $(date '+%F %T')" >> "$LOG"
if nice -n 10 .venv/bin/python -m fanta aggiorna >> "$LOG" 2>&1; then
  rm -f "$STATO"
else
  n=$(( $(cat "$STATO" 2>/dev/null || echo 0) + 1 ))
  echo "$n" > "$STATO"
  [ "$n" -eq 2 ] && avvisa "Fantacalcio" "Aggiornamento dati non riuscito per due volte di fila."
fi

# (la formazione e il mercato in memoria li prepara il servizio da solo: controlla i dati ogni minuto e,
# appena sono cambiati, li calcola in anticipo. Funziona anche con gli account e non serve nessuna richiesta da qui.)

# giri degli avvisi (cambi, riepilogo, «formazione pronta»): ognuno al massimo 10 minuti, cosi' un servizio di notifica lento non
# ferma il resto dello script. Si cambia con FANTA_MAX_SECONDI_GIRO_AVVISI nelle variabili del servizio (secondi; un valore non valido vale 600).
giro=${FANTA_MAX_SECONDI_GIRO_AVVISI:-600}; [[ $giro =~ ^[1-9][0-9]{0,4}$ ]] || giro=600
fermato() {   # comando, uscita: con 124 (tempo finito, vedi timeout) lo scrive nel log
  [ "$2" -eq 124 ] && echo "$1: fermato dopo $giro secondi (tempo massimo del giro)" >> "$LOG"
  return 0
}

# avvisi sul telefono se sono cambiate le probabili dei miei giocatori
nice -n 10 timeout "$giro" .venv/bin/python -m fanta cambi >> "$LOG" 2>&1 || fermato cambi $?
# riepilogo di giornata (una volta per giornata, quando sono arrivati i voti)
nice -n 10 timeout "$giro" .venv/bin/python -m fanta riepilogo >> "$LOG" 2>&1 || fermato riepilogo $?
# prova del modello sulle ultime giornate (si rifà solo se è finita una giornata nuova)
nice -n 15 .venv/bin/python -m fanta affidabilita >> "$LOG" 2>&1

testo=$(nice -n 10 timeout "$giro" .venv/bin/python -m fanta avviso 2>>"$LOG") || fermato avviso $?
[ -n "$testo" ] && avvisa "Fantacalcio" "$testo"

# ritagli dei volti dei calciatori: fino a 80 per giro e al massimo 6 minuti, sempre sotto le 30 richieste al minuto del servizio
# (le altre arrivano ai giri successivi). In fondo, cosi' non ritardano formazione e avviso.
# Spento di norma (l'app usa i volti illustrati, nessuna foto): per riaccenderlo FANTA_FOTO=1 nelle variabili del servizio.
if [ "${FANTA_FOTO:-0}" = "1" ]; then
  nice -n 10 .venv/bin/python -m fanta foto --max 80 --minuti 6 >> "$LOG" 2>&1
fi

# taratura di «gioca N%» con le probabili (si accende e torna indietro da sola, docs/decisioni/0009): il calcolo vero si fa con una
# giornata nuova, e si rifa' a ogni giro dopo una riga pronta, rimandata o riaccesa. Ultimo passo, con priorita' bassa e al massimo
# 5 minuti, cosi' un errore o un blocco non ferma lo script e non ritarda dati, formazione e avvisi
nice -n 15 timeout 300 .venv/bin/python -m fanta taratura-probabili >> "$LOG" 2>&1 || echo "taratura-probabili: non riuscita (uscita $?)" >> "$LOG"

ruota_registro "$LOG" 2000
exit 0
