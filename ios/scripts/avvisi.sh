#!/bin/bash
# Avvisi di sistema nelle foto del simulatore (issue #393). Si carica con `source` da screenshot.sh e screenshot_widget.sh.
#
# Cosa succede: dopo l'accensione, il simulatore mostra per circa 5 secondi «Ready for Apple Intelligence» (non è dell'app:
# lo posta il servizio di Apple generativeexperiencesd, come invito «Follow Up»), una volta sola, di solito dopo 2-3 minuti
# (misurato in tre corse: 2:00, 2:50 e circa 3:30 dalla fine dell'accensione). Una foto scattata in quel momento lo porta dentro.
# Nel registro del simulatore si legge «Posted new Readiness CFU» e, subito dopo, la creazione della notifica di Impostazioni
# (SpringBoard, com.apple.usernotificationsd, NotificationsPipeline).
#
# Perché si fa così: non c'è un'impostazione documentata che lo tolga (il simulatore non ha un pulsante per Apple Intelligence,
# e un «defaults write» su un servizio di Apple cambia da una versione di iOS all'altra); dal simulatore da riga di comando non
# si può toccare lo schermo per chiudere il banner. Si fa invece in modo che sia già passato PRIMA delle foto: dopo
# l'accensione si interroga il registro («log show») finché l'avviso compare, si aspetta che sparisca, e solo allora si comincia.
# Il registro con «log stream» non va bene: arriva con 40 secondi di ritardo, a avviso già sparito (provato il 6/11).
#
#   avvisi_avvia <udid>       da chiamare appena il simulatore è acceso: segna l'ora
#   avvisi_attendi <udid> [s] aspetta l'avviso (al massimo s secondi, predefinito 400) e che sparisca
#   avvisi_ferma              da chiamare prima di spegnere: se l'avviso non è comparso durante l'attesa guarda se è comparso dopo
#   avvisi_riepilogo          una riga per il registro della corsa

AVVISI_PAUSA="${AVVISI_PAUSA:-12}"   # secondi in cui un avviso sta sullo schermo (visti 5), con margine
AVVISI_FILTRO='(subsystem == "com.apple.usernotificationsd" AND category == "NotificationsPipeline" AND eventMessage CONTAINS "[create,") OR (eventMessage CONTAINS "Posted new Readiness CFU")'
AVVISI_UDID=""
AVVISI_AVVIATO=0     # ora (secondi) dell'accensione
AVVISI_VISTO=""      # "" = non si è aspettato; "si" = visto durante l'attesa; "no" = non visto in tempo
AVVISI_TARDI=0       # righe di avviso viste dopo l'attesa (sono nelle foto fatte dopo)
AVVISI_ASPETTATI=0   # avvisi visti durante l'attesa e lasciati passare prima delle foto

# Quante righe di avviso ci sono nel registro del simulatore dall'accensione a oggi.
avvisi_contati() {
  local passati
  passati=$(( $(date +%s) - AVVISI_AVVIATO + 10 ))
  xcrun simctl spawn "$1" log show --last "${passati}s" --style compact --predicate "$AVVISI_FILTRO" 2>/dev/null \
    | grep -c '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] '
}

avvisi_avvia() {
  AVVISI_UDID="$1"
  AVVISI_AVVIATO=$(date +%s)
  AVVISI_VISTO=""
}

avvisi_attendi() {
  local udid="$1" massimo="${2:-${AVVISI_ATTESA_MAX:-400}}" inizio passati visti
  inizio=$(date +%s)
  echo "Aspetto l'avviso di Apple Intelligence (al massimo $massimo s): compare una sola volta dopo l'accensione e coprirebbe le foto"
  while :; do
    visti=$(avvisi_contati "$udid")
    passati=$(( $(date +%s) - inizio ))
    if [ "${visti:-0}" -gt 0 ]; then
      echo "  avviso visto ($((passati)) s di attesa, $(( $(date +%s) - AVVISI_AVVIATO )) s dall'accensione): aspetto $AVVISI_PAUSA s che sparisca"
      sleep "$AVVISI_PAUSA"
      AVVISI_VISTO=si
      AVVISI_ASPETTATI=$((AVVISI_ASPETTATI + 1))
      return 0
    fi
    if [ "$passati" -ge "$massimo" ]; then
      echo "  ATTENZIONE: nessun avviso in $massimo s: si va avanti (se comparirà più tardi, lo dirà il riepilogo)"
      AVVISI_VISTO=no
      return 0
    fi
    sleep 5
  done
}

avvisi_ferma() {
  local visti
  if [ -n "$AVVISI_UDID" ] && [ "$AVVISI_VISTO" = no ]; then
    visti=$(avvisi_contati "$AVVISI_UDID")
    if [ "${visti:-0}" -gt 0 ]; then
      AVVISI_TARDI=$((AVVISI_TARDI + visti))
      echo "ATTENZIONE: l'avviso di sistema è comparso DOPO l'attesa: le foto fatte in quel momento possono averlo sopra"
    fi
  fi
  AVVISI_UDID=""
  return 0
}

avvisi_riepilogo() {
  echo "Avvisi di sistema: aspettati prima delle foto: $AVVISI_ASPETTATI; comparsi dopo l'attesa: $AVVISI_TARDI"
  if [ "$AVVISI_TARDI" -gt 0 ]; then echo "  (controllare le foto: l'avviso può essere sopra quelle fatte dopo l'attesa)"; fi
}
