#!/bin/bash
# Avvisi di sistema nelle foto del simulatore (issue #393). Si carica con `source` da screenshot.sh e screenshot_widget.sh.
#
# Cosa succede: due o tre minuti dopo l'accensione, il simulatore mostra per circa 5 secondi «Ready for Apple Intelligence»
# (non è dell'app: lo posta il servizio di Apple generativeexperiencesd, come invito di «Follow Up»), e una foto scattata
# in quel momento lo porta dentro. Si vede nel registro del simulatore: «Posted new Readiness CFU» e, subito dopo, la creazione
# della notifica (SpringBoard, com.apple.usernotificationsd, NotificationsPipeline).
#
# Perché si fa così (e non spegnendo l'avviso): non c'è un'impostazione documentata che lo tolga (il simulatore non ha un
# pulsante per Apple Intelligence, e un «defaults write» su un servizio di Apple cambia da una versione di iOS all'altra);
# dal simulatore da riga di comando non si può toccare lo schermo per chiuderlo. Il registro invece dice con certezza QUANDO
# un avviso compare: lo script lo ascolta, e se un avviso è comparso durante (o poco prima) di uno scatto aspetta che sparisca e
# rifà la foto. Vale per qualunque notifica di sistema che passi da lì, non solo per questa.
#
#   avvisi_avvia <udid>       comincia ad ascoltare il registro di quel simulatore (dopo l'accensione)
#   avvisi_ferma              smette di ascoltare
#   avvisi_comparsi <ora>     vero se un avviso è comparso da (ora - pausa) in poi; <ora> = secondi di date +%s a inizio scatto
#   avvisi_aspetta            aspetta che l'ultimo avviso sia sparito dallo schermo
#   avvisi_riepilogo          una riga per il registro della corsa

AVVISI_FLAG="${AVVISI_FLAG:-${TMPDIR:-/tmp}/schieraxi-avvisi-$$}"
AVVISI_PAUSA="${AVVISI_PAUSA:-10}"   # secondi in cui un avviso sta sullo schermo (visti 5), con margine
AVVISI_FILTRO='(subsystem == "com.apple.usernotificationsd" AND category == "NotificationsPipeline" AND eventMessage CONTAINS "[create,") OR (eventMessage CONTAINS "Posted new Readiness CFU")'
AVVISI_UDID=""
AVVISI_PID=""
AVVISI_RIFATTE=0   # foto rifatte perché un avviso era sullo schermo

# Legge il registro da stdin: ogni riga che comincia con una data è un avviso; ne annota l'ora (secondi) in $AVVISI_FLAG
# e la riga in $AVVISI_FLAG.log. Le righe d'intestazione di «log stream» non cominciano con una data.
avvisi_registra() {
  local riga
  while IFS= read -r riga; do
    case "$riga" in
      [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\ *)
        date +%s > "$AVVISI_FLAG"
        echo "${riga:0:200}" >> "$AVVISI_FLAG.log"
        ;;
    esac
  done
}

avvisi_avvia() {
  avvisi_ferma
  AVVISI_UDID="$1"
  echo 0 > "$AVVISI_FLAG"
  touch "$AVVISI_FLAG.log"   # il registro resta tra un simulatore e l'altro (iPhone, poi iPad): il riepilogo li conta tutti
  ( xcrun simctl spawn "$AVVISI_UDID" log stream --level debug --style compact --predicate "$AVVISI_FILTRO" 2>/dev/null \
      | avvisi_registra ) &
  AVVISI_PID=$!
}

avvisi_ferma() {
  if [ -n "$AVVISI_PID" ]; then kill "$AVVISI_PID" 2>/dev/null; fi
  if [ -n "$AVVISI_UDID" ]; then pkill -f "simctl spawn $AVVISI_UDID log stream" 2>/dev/null; fi
  AVVISI_PID=""
  AVVISI_UDID=""
  return 0
}

# L'ora dell'ultimo avviso, 0 se non ce ne sono (o se il file è illeggibile).
avvisi_ultimo() {
  local t
  t=$(cat "$AVVISI_FLAG" 2>/dev/null)
  case "$t" in ''|*[!0-9]*) t=0 ;; esac
  echo "$t"
}

avvisi_comparsi() {
  local ultimo
  ultimo=$(avvisi_ultimo)
  [ "$ultimo" -gt 0 ] && [ "$ultimo" -ge $(( $1 - AVVISI_PAUSA )) ]
}

avvisi_aspetta() {
  local ultimo resto
  ultimo=$(avvisi_ultimo)
  [ "$ultimo" -gt 0 ] || return 0
  resto=$(( ultimo + AVVISI_PAUSA - $(date +%s) ))
  if [ "$resto" -gt 0 ]; then sleep "$resto"; fi
  return 0
}

avvisi_riepilogo() {
  local visti=0
  [ -f "$AVVISI_FLAG.log" ] && visti=$(wc -l < "$AVVISI_FLAG.log" | tr -d ' ')
  echo "Avvisi di sistema visti nel registro: $visti. Foto rifatte per un avviso: $AVVISI_RIFATTE"
  if [ "$visti" -gt 0 ]; then cut -c1-160 "$AVVISI_FLAG.log" | head -5; fi
}
