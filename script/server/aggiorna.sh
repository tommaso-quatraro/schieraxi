#!/bin/bash
# aggiorna.sh - Sul server: scarica i dati nuovi per l'app Fanta, lancia il giro dei cambi e avvisa con ntfy se un passo non riesce.
#   Dal crontab dell'utente del server:  0 8,13,17,21 * * * /bin/bash $HOME/fantacalcio/script/server/aggiorna.sh >/dev/null 2>&1
# - Priorita' bassa (nice), così gli altri servizi del server non rallentano.
# - Guasti contati per passo dell'aggiornamento (listone, calendario, voti, probabili, Understat...), un file per passo rotto in
#   ~/.cache/fantacalcio/passi/: un avviso con il nome del passo alla seconda volta di fila (uno solo per giro, con tutti i passi),
#   e «funziona di nuovo» quando torna. Così una fonte rotta da giorni non nasconde il guasto di un'altra (#607). Il promemoria
#   di ogni giorno per un passo fermo lo manda il controllo di salute del server, non questo script.
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
PASSI="$HOME/.cache/fantacalcio/passi"     # un file per passo che non riesce: «giri di fila, ora dell'avviso (secondi, 0 = no), nome»
INTERO="aggiornamento"                      # il guasto di tutto il comando (fermo prima della fine, o senza un passo con il nome)
umask 077     # i log e i file nuovi di dati/ (indirizzi, iscrizioni) sono leggibili solo dall'utente del server
permessi_registri dati
canale=$(tr -d ' \r\n' < "${SCHIERAXI_CANALE:-$HOME/.config/schieraxi/canale}" 2>/dev/null)

avvisa() {   # titolo, testo
  [ -n "$canale" ] || return 0
  curl -fsS -m 20 -H 'Content-Type: application/json' \
    -d "{\"topic\":\"$canale\",\"title\":\"$1\",\"message\":\"$2\",\"priority\":3,\"tags\":[\"soccer\"]}" \
    https://ntfy.sh >/dev/null
}

testo_rotti() {   # righe «giri nome» dei passi da segnalare in questo giro: il testo di UN avviso
  local giri nome elenco="" quanti=0 primo="" primi_giri=""
  while read -r giri nome; do
    [ -n "$nome" ] || continue
    quanti=$(( quanti + 1 )); primo=$nome; primi_giri=$giri
    [ "$nome" = "$INTERO" ] && nome="aggiornamento intero"
    elenco="${elenco:+$elenco, }«$nome» ($giri giri di fila)"
  done <<< "$1"
  if [ "$quanti" -gt 1 ]; then echo "Aggiornamento dati, non riescono: $elenco."
  elif [ "$primo" = "$INTERO" ]; then echo "Aggiornamento dati non riuscito da $primi_giri giri di fila: dettagli in dati/aggiorna.log."
  else echo "Aggiornamento dati: «$primo» non riesce da $primi_giri giri di fila."; fi
}

testo_tornati() {   # nomi dei passi tornati (uno per riga): il testo di UN avviso
  local nome elenco="" quanti=0 primo=""
  while read -r nome; do
    [ -n "$nome" ] || continue
    quanti=$(( quanti + 1 )); primo=$nome
    [ "$nome" = "$INTERO" ] && nome="aggiornamento intero"
    elenco="${elenco:+$elenco, }«$nome»"
  done <<< "$1"
  if [ "$quanti" -gt 1 ]; then echo "Aggiornamento dati, funzionano di nuovo: $elenco."
  elif [ "$primo" = "$INTERO" ]; then echo "Aggiornamento dati di nuovo riuscito."
  else echo "Aggiornamento dati: «$primo» funziona di nuovo."; fi
}

# Guasti per passo, dalle righe di questo giro nel registro. fanta/aggiorna.py scrive «  ! <passo>: non riuscito (...)» per un passo
# fallito, «  - <passo>: saltato, ...» per una fonte spenta e «Fatto: ...» in fondo. Senza «Fatto:» (e con un'uscita di errore) il
# comando si è fermato prima della fine: è un guasto di tutto l'aggiornamento e non dice niente degli altri passi, che restano come
# sono. Il nome del passo viene dall'uscita: tiene solo lettere, cifre, spazi e trattini (fa da nome del file di stato e va nel JSON
# dell'avviso), al massimo 20 passi per giro. Un passo rotto si segnala UNA volta, alla seconda volta di fila, poi si tace finché
# non torna: il promemoria di ogni giorno per un passo fermo da oltre 24 ore lo manda il controllo di salute (fanta/salute.py).
# Un solo avviso per giro con tutti i passi da segnalare (rete giù = un avviso, non sei) e uno solo per quelli tornati. L'ora
# dell'avviso si segna solo se l'avviso è partito, e il file di un passo tornato si toglie solo dopo che «funziona di nuovo» è
# partito: se il servizio degli avvisi non risponde, si riprova al giro dopo.
controlla_passi() {   # uscita del comando, righe del registro prima del giro
  local giro rotti finito=0 adesso f n ultimo nome resto tornati="" da_avvisare="" i
  local -a file_tornati=() av_file=() av_n=() av_nome=()
  { mkdir -p "$PASSI" && [ ! -L "$PASSI" ]; } || return 0
  giro=$(tail -n +"$(( $2 + 1 ))" "$LOG")
  rotti=$(printf '%s\n' "$giro" | sed -n 's/^  ! \([^:]\{1,60\}\): non riuscito (.*/\1/p' | tr -cd 'A-Za-z0-9 \n-' \
          | sed 's/^ *//; s/ *$//' | grep -v '^$' | LC_ALL=C sort -u | head -n 20)
  if [ "$1" -eq 0 ] || printf '%s\n' "$giro" | grep -q '^Fatto: '; then finito=1; fi
  if [ "$1" -ne 0 ] && { [ "$finito" = 0 ] || [ -z "$rotti" ]; }; then
    rotti=$(printf '%s\n%s\n' "$rotti" "$INTERO" | grep -v '^$')
    finito=0                          # degli altri passi questo giro non dice niente: restano come sono
  fi
  adesso=$(date +%s)
  if [ "$finito" = 1 ]; then          # il giro è arrivato in fondo: i passi che non sono rotti stavolta sono tornati (o spenti)
    for f in "$PASSI"/*; do
      { [ -f "$f" ] && [ ! -L "$f" ]; } || continue
      n=0; ultimo=0; nome=""
      read -r n ultimo nome < "$f"
      [ -n "$nome" ] || nome=$(basename "$f")
      printf '%s\n' "$rotti" | grep -qxF -- "$nome" && continue
      if printf '%s\n' "$giro" | grep -qF -- "  - $nome: saltato"; then
        echo "passo «$nome»: spento, non si controlla più" >> "$LOG"
        rm -f -- "$f"
      else
        echo "passo «$nome»: di nuovo a posto (giri non riusciti di fila: $n)" >> "$LOG"
        if [[ $ultimo =~ ^[1-9][0-9]*$ ]]; then          # era stato segnalato: il file si toglie dopo l'avviso
          tornati="$tornati$nome"$'\n'; file_tornati+=("$f")
        else
          rm -f -- "$f"
        fi
      fi
    done
    if [ ${#file_tornati[@]} -gt 0 ] && avvisa "Fantacalcio" "$(testo_tornati "$(printf '%s' "$tornati" | LC_ALL=C sort)")"; then
      rm -f -- "${file_tornati[@]}"
    fi
  fi
  while IFS= read -r nome; do
    [ -n "$nome" ] || continue
    f="$PASSI/${nome// /-}"
    [ -L "$f" ] && continue
    n=0; ultimo=0
    if [ -f "$f" ]; then read -r n ultimo resto < "$f"; fi
    [[ $n =~ ^[0-9]{1,9}$ ]] || n=0
    [[ $ultimo =~ ^[0-9]{1,12}$ ]] || ultimo=0
    n=$(( n + 1 ))
    echo "passo «$nome»: non riuscito (giri di fila: $n)" >> "$LOG"
    echo "$n $ultimo $nome" > "$f"
    if [ "$n" -ge 2 ] && [ "$ultimo" = 0 ]; then         # una volta sola per guasto (mai segnalato finora)
      da_avvisare="$da_avvisare$n $nome"$'\n'; av_file+=("$f"); av_n+=("$n"); av_nome+=("$nome")
    fi
  done <<< "$rotti"
  if [ ${#av_file[@]} -gt 0 ] && avvisa "Fantacalcio" "$(testo_rotti "$da_avvisare")"; then
    for i in "${!av_file[@]}"; do echo "${av_n[$i]} $adesso ${av_nome[$i]}" > "${av_file[$i]}"; done
  fi
  return 0
}

exec 9>>"$HOME/.cache/fantacalcio/blocco"
flock -n 9 || exit 0          # un altro aggiornamento e' gia' in corso
rm -f "$HOME/.cache/fantacalcio/errori"     # il contatore unico di prima (fino a novembre 2026): non serve più

echo "=== $(date '+%F %T')" >> "$LOG"
righe_prima=$(wc -l < "$LOG")
nice -n 10 .venv/bin/python -m fanta aggiorna >> "$LOG" 2>&1
controlla_passi $? "$righe_prima"

# (la formazione e il mercato in memoria li prepara il servizio da solo: controlla i dati ogni minuto e,
# appena sono cambiati, li calcola in anticipo. Funziona anche con gli account e non serve nessuna richiesta da qui.)

# giro degli avvisi dei cambi: al massimo 10 minuti, cosi' un servizio di notifica lento non
# ferma il resto dello script. Si cambia con FANTA_MAX_SECONDI_GIRO_AVVISI nelle variabili del servizio (secondi; un valore non valido vale 600).
giro=${FANTA_MAX_SECONDI_GIRO_AVVISI:-600}; [[ $giro =~ ^[1-9][0-9]{0,4}$ ]] || giro=600
fermato() {   # comando, uscita: con 124 (tempo finito, vedi timeout) lo scrive nel log
  [ "$2" -eq 124 ] && echo "$1: fermato dopo $giro secondi (tempo massimo del giro)" >> "$LOG"
  return 0
}

# avviso sul telefono se cambia la formazione da schierare (un titolare non gioca piu')
nice -n 10 timeout "$giro" .venv/bin/python -m fanta cambi >> "$LOG" 2>&1 || fermato cambi $?
# prova del modello sulle ultime giornate (si rifà solo se è finita una giornata nuova)
nice -n 15 .venv/bin/python -m fanta affidabilita >> "$LOG" 2>&1

# ritagli dei volti dei calciatori: fino a 80 per giro e al massimo 6 minuti, sempre sotto le 30 richieste al minuto del servizio
# (le altre arrivano ai giri successivi). In fondo, cosi' non ritardano formazione e avvisi.
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
