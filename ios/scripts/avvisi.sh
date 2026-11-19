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
#   avvisi_coprono <udid> <inizio>  dopo ogni foto: vero se un avviso può essere sopra la foto cominciata all'ora <inizio>
#                             (in quel caso ha già aspettato che sparisca: basta rifare la foto)
#   avvisi_foto <udid> <file> una foto semplice («simctl io screenshot») controllata e, se serve, rifatta
#   avvisi_ferma              da chiamare prima di spegnere: se l'avviso non è comparso durante l'attesa guarda se è comparso dopo
#   avvisi_riepilogo          una riga per il registro della corsa
#
# Su iOS 26.5 l'invito non compare una volta sola (#601): dopo quello aspettato ne sono arrivati altri due mentre si
# fotografava (corsa 43131154860, uno sopra la foto accesso-account). Per questo, oltre all'attesa iniziale, ogni foto si
# controlla dopo lo scatto con avvisi_coprono e si rifà se l'avviso può esserci sopra.

AVVISI_PAUSA="${AVVISI_PAUSA:-12}"   # secondi in cui un avviso sta sullo schermo (visti 5), con margine
AVVISI_SCHERMO="${AVVISI_SCHERMO:-8}" # dopo una foto si guarda indietro di tanto: un avviso più vecchio è già sparito.
# Meno della pausa: la foto rifatta dopo la pausa non deve ritrovare l'avviso appena aspettato (corsa 44594837693).
# Solo la riga dell'invito di Apple Intelligence: un'altra notifica di sistema non deve chiudere l'attesa (e poi lasciare l'avviso vero
# sopra le foto). Subito dopo questa riga SpringBoard crea la notifica di Impostazioni (NotificationsPipeline, «[create,»), ma
# quella riga c'è per qualunque notifica e non serve.
AVVISI_FILTRO='eventMessage CONTAINS "Posted new Readiness CFU"'
AVVISI_UDID=""
AVVISI_AVVIATO=0     # ora (secondi) dell'accensione
AVVISI_FINE_ATTESA=0 # ora (secondi) in cui è finita l'attesa: gli avvisi dopo questa ora sono sulle foto
AVVISI_VISTO=""      # "" = non si è aspettato; "si" = visto durante l'attesa; "no" = non visto in tempo (solo per il registro)
AVVISI_TARDI=0       # righe di avviso viste dopo l'attesa (sono nelle foto fatte dopo)
AVVISI_ASPETTATI=0   # avvisi visti durante l'attesa e lasciati passare prima delle foto
AVVISI_RIFATTE=0     # foto rifatte perché un avviso poteva esserci sopra (avvisi_coprono)

# Quante righe di avviso ci sono nel registro del simulatore negli ultimi <secondi>.
avvisi_contati() {
  xcrun simctl spawn "$1" log show --last "${2}s" --style compact --predicate "$AVVISI_FILTRO" 2>/dev/null \
    | grep -c '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] '
}

avvisi_avvia() {
  AVVISI_UDID="$1"
  AVVISI_AVVIATO=$(date +%s)
  AVVISI_FINE_ATTESA=0
  AVVISI_VISTO=""
}

avvisi_attendi() {
  local udid="$1" massimo="${2:-${AVVISI_ATTESA_MAX:-400}}" inizio passati visti
  inizio=$(date +%s)
  echo "Aspetto l'avviso di Apple Intelligence (al massimo $massimo s): compare una sola volta dopo l'accensione e coprirebbe le foto"
  while :; do
    # finestra larga (3 ore): lo stesso simulatore riacceso (le foto dei widget dopo quelle dell'app) non ripete l'avviso,
    # che resta nel registro; senza guardare indietro si aspetterebbero 400 secondi per niente
    visti=$(avvisi_contati "$udid" "${AVVISI_FINESTRA:-10800}")
    passati=$(( $(date +%s) - inizio ))
    if [ "${visti:-0}" -gt 0 ]; then
      echo "  avviso visto ($((passati)) s di attesa, $(( $(date +%s) - AVVISI_AVVIATO )) s dall'accensione): aspetto $AVVISI_PAUSA s che sparisca"
      sleep "$AVVISI_PAUSA"
      AVVISI_FINE_ATTESA=$(date +%s)
      AVVISI_VISTO=si
      AVVISI_ASPETTATI=$((AVVISI_ASPETTATI + 1))
      return 0
    fi
    if [ "$passati" -ge "$massimo" ]; then
      echo "  ATTENZIONE: nessun avviso in $massimo s: si va avanti (se comparirà più tardi, lo dirà il riepilogo)"
      AVVISI_FINE_ATTESA=$(date +%s)
      AVVISI_VISTO=no
      return 0
    fi
    sleep 5
  done
}

# Dopo una foto cominciata all'ora <inizio>: un invito dal momento in cui poteva già essere sullo schermo (AVVISI_SCHERMO secondi
# prima di <inizio>) a ora vuol dire che la foto può averlo sopra. Allora si aspetta che sparisca (AVVISI_PAUSA) e si torna
# «vero»: chi chiama rifà la foto.
avvisi_coprono() {
  local udid="$1" inizio="$2" finestra visti
  finestra=$(( $(date +%s) - inizio + AVVISI_SCHERMO ))
  [ "$finestra" -ge 1 ] || finestra=1
  visti=$(avvisi_contati "$udid" "$finestra")
  if [ "${visti:-0}" -gt 0 ] && [ "${AVVISI_DIAGNOSI_FATTA:-0}" -lt 3 ]; then
    AVVISI_DIAGNOSI_FATTA=$(( ${AVVISI_DIAGNOSI_FATTA:-0} + 1 ))
    echo "  DIAGNOSI #601: righe dell'invito negli ultimi 60 s"
    xcrun simctl spawn "$udid" log show --last 60s --style compact --predicate "$AVVISI_FILTRO" 2>/dev/null | cut -c1-400 | sed 's/^/    /'
    echo "  DIAGNOSI #601: notifiche create da SpringBoard negli ultimi 60 s"
    xcrun simctl spawn "$udid" log show --last 60s --style compact       --predicate 'process == "SpringBoard" AND eventMessage CONTAINS "[create,"' 2>/dev/null | cut -c1-300 | sed 's/^/    /'
  fi
  if [ "${visti:-0}" -gt 0 ]; then
    echo "  avviso di sistema durante la foto: aspetto $AVVISI_PAUSA s che sparisca e la rifaccio"
    sleep "$AVVISI_PAUSA"
    AVVISI_RIFATTE=$((AVVISI_RIFATTE + 1))
    return 0
  fi
  return 1
}

# Una foto semplice dello schermo, controllata e rifatta (al massimo due volte) se un avviso può esserci sopra.
avvisi_foto() {
  local udid="$1" file="$2" giri=0 inizio
  while :; do
    inizio=$(date +%s)
    xcrun simctl io "$udid" screenshot "$file" >/dev/null 2>&1 || return 1
    avvisi_coprono "$udid" "$inizio" || return 0
    giri=$((giri + 1))
    [ "$giri" -le 2 ] || return 0
  done
}

# Prima di spegnere: dopo la fine dell'attesa è comparso un altro invito? (Sempre, qualunque cosa abbia visto l'attesa: se la
# riga del registro è più nuova della fine dell'attesa, le foto fatte da allora possono avere l'avviso sopra.)
avvisi_ferma() {
  local visti da
  if [ -n "$AVVISI_UDID" ]; then
    da="$AVVISI_FINE_ATTESA"
    [ "$da" -gt 0 ] || da="$AVVISI_AVVIATO"
    da=$(( $(date +%s) - da ))
    [ "$da" -ge 1 ] || da=1
    visti=$(avvisi_contati "$AVVISI_UDID" "$da")
    if [ "${visti:-0}" -gt 0 ]; then
      AVVISI_TARDI=$((AVVISI_TARDI + visti))
      echo "ATTENZIONE: l'avviso di sistema è comparso DOPO l'attesa ($visti volte): le foto con l'avviso sopra sono state rifatte (finora $AVVISI_RIFATTE)"
      # le ore dell'avviso, per capire ogni quanto si ripete
      xcrun simctl spawn "$AVVISI_UDID" log show --last "${da}s" --style compact --predicate "$AVVISI_FILTRO" 2>/dev/null         | grep '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] ' | cut -c1-19 | sed 's/^/  avviso alle /'
    fi
  fi
  AVVISI_UDID=""
  return 0
}

avvisi_riepilogo() {
  echo "Avvisi di sistema: aspettati prima delle foto: $AVVISI_ASPETTATI; comparsi dopo l'attesa: $AVVISI_TARDI; foto rifatte per l'avviso: $AVVISI_RIFATTE"
  if [ "$AVVISI_TARDI" -gt 0 ] && [ "$AVVISI_RIFATTE" -eq 0 ]; then
    echo "  (controllare le foto: l'avviso è comparso dopo l'attesa ma nessuna foto è stata rifatta)"
  fi
}
