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
#   avvisi_coprono <udid> <inizio>  vero se un avviso può essere sopra la foto cominciata all'ora <inizio> (solo controllo)
#   avvisi_rifai <udid> <file> <inizio>  dopo una foto: se un avviso può esserci sopra aspetta che sparisca e la rifà (al
#                             massimo due volte); se resta, lo dice e la segna tra quelle da guardare (torna 1)
#   avvisi_foto <udid> <file> una foto semplice («simctl io screenshot») controllata con avvisi_rifai
#   avvisi_ferma              da chiamare prima di spegnere: se l'avviso non è comparso durante l'attesa guarda se è comparso dopo
#   avvisi_riepilogo          una riga per il registro della corsa
#
# #601: il filtro prende SOLO le righe del servizio generativeexperiencesd. Il processo «log show» scrive nel registro la propria
# riga di comando («log run noninteractively, ... args: ... Posted new Readiness CFU»), e con il solo testo ogni lettura
# ritrovava le letture di prima (corsa 44629200541): l'attesa iniziale finiva su una riga falsa, l'invito vero arrivava dopo,
# sopra le foto. L'invito vero è seguito, circa 9 secondi dopo, dalla notifica di Impostazioni creata da SpringBoard
# (bundle=com.apple.Preferences): il banner si vede da allora per qualche secondo, quindi la pausa è di 20 secondi.

AVVISI_PAUSA="${AVVISI_PAUSA:-20}"     # secondi dalla riga dell'invito alla fine del banner (notifica dopo ~9 s, visibile ~5 s), con margine
AVVISI_SCHERMO="${AVVISI_SCHERMO:-20}" # dopo una foto si guarda indietro di tanto: un invito più vecchio ha già finito il banner
# Solo la riga dell'invito di Apple Intelligence scritta dal suo servizio: un'altra notifica di sistema, o la riga di comando di
# «log show» che contiene lo stesso testo, non devono chiudere l'attesa (e poi lasciare l'avviso vero sopra le foto).
AVVISI_FILTRO='process == "generativeexperiencesd" AND eventMessage CONTAINS "Posted new Readiness CFU"'
AVVISI_UDID=""
AVVISI_AVVIATO=0     # ora (secondi) dell'accensione
AVVISI_FINE_ATTESA=0 # ora (secondi) in cui è finita l'attesa: gli avvisi dopo questa ora sono sulle foto
AVVISI_VISTO=""      # "" = non si è aspettato; "si" = visto durante l'attesa; "no" = non visto in tempo (solo per il registro)
AVVISI_TARDI=0       # righe di avviso viste dopo l'attesa (sono nelle foto fatte dopo)
AVVISI_ASPETTATI=0   # avvisi visti durante l'attesa e lasciati passare prima delle foto
AVVISI_RIFATTE=0     # foto rifatte perché un avviso poteva esserci sopra (avvisi_rifai)
AVVISI_GIA_VISTO=0   # ora (secondi) in cui si è visto l'ultimo invito già aspettato: la foto rifatta non deve ritrovarlo
AVVISI_DA_GUARDARE=()  # foto con l'avviso forse ancora sopra dopo i rifacimenti (o con un rifacimento non riuscito)

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
      AVVISI_GIA_VISTO=$(date +%s)
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

# Una foto cominciata all'ora <inizio> può avere l'avviso sopra se c'è un invito da AVVISI_SCHERMO secondi prima di <inizio> a ora,
# più nuovo dell'ultimo già aspettato (AVVISI_GIA_VISTO). Solo controllo: niente attese.
avvisi_coprono() {
  local udid="$1" inizio="$2" ora finestra limite visti
  ora=$(date +%s)
  finestra=$(( ora - inizio + AVVISI_SCHERMO ))
  if [ "$AVVISI_GIA_VISTO" -gt 0 ]; then
    limite=$(( ora - AVVISI_GIA_VISTO - 1 ))
    [ "$limite" -lt "$finestra" ] && finestra="$limite"
  fi
  [ "$finestra" -ge 1 ] || return 1
  visti=$(avvisi_contati "$udid" "$finestra")
  [ "${visti:-0}" -gt 0 ] || return 1
  AVVISI_GIA_VISTO="$ora"
  return 0
}

# Dopo una foto già scattata in <file> a partire da <inizio>: se l'avviso può esserci sopra, si aspetta che sparisca e si rifà
# (al massimo due volte). Torna 1, con un ATTENZIONE e la foto tra quelle da guardare, se l'avviso c'è ancora o uno scatto non riesce.
avvisi_rifai() {
  local udid="$1" file="$2" inizio="$3" giri=0
  while avvisi_coprono "$udid" "$inizio"; do
    if [ "$giri" -ge 2 ]; then
      echo "  ATTENZIONE: avviso di sistema ancora possibile dopo $giri rifacimenti: guardare $(basename "$file")"
      AVVISI_DA_GUARDARE+=("$(basename "$file")")
      return 1
    fi
    echo "  avviso di sistema durante la foto: aspetto $AVVISI_PAUSA s che sparisca e la rifaccio"
    sleep "$AVVISI_PAUSA"
    giri=$((giri + 1))
    inizio=$(date +%s)
    if ! xcrun simctl io "$udid" screenshot "$file" >/dev/null 2>&1; then
      echo "  ATTENZIONE: foto rifatta non riuscita: guardare $(basename "$file")"
      AVVISI_DA_GUARDARE+=("$(basename "$file")")
      return 1
    fi
    AVVISI_RIFATTE=$((AVVISI_RIFATTE + 1))
  done
  return 0
}

# Una foto semplice dello schermo, controllata e rifatta se serve.
avvisi_foto() {
  local udid="$1" file="$2" inizio
  inizio=$(date +%s)
  xcrun simctl io "$udid" screenshot "$file" >/dev/null 2>&1 || return 1
  avvisi_rifai "$udid" "$file" "$inizio"
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
      echo "ATTENZIONE: l'avviso di sistema è comparso DOPO l'attesa ($visti volte); foto rifatte finora: $AVVISI_RIFATTE"
      # le ore dell'invito, per capire quando e quanto spesso arriva
      xcrun simctl spawn "$AVVISI_UDID" log show --last "${da}s" --style compact --predicate "$AVVISI_FILTRO" 2>/dev/null \
        | grep '^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] ' | cut -c1-19 | sed 's/^/  avviso alle /'
    fi
  fi
  AVVISI_UDID=""
  return 0
}

avvisi_riepilogo() {
  echo "Avvisi di sistema: aspettati prima delle foto: $AVVISI_ASPETTATI; comparsi dopo l'attesa: $AVVISI_TARDI; foto rifatte per l'avviso: $AVVISI_RIFATTE"
  if [ "${#AVVISI_DA_GUARDARE[@]}" -gt 0 ]; then
    echo "  (controllare le foto: l'avviso può essere ancora sopra a ${AVVISI_DA_GUARDARE[*]})"
  elif [ "$AVVISI_TARDI" -gt 0 ] && [ "$AVVISI_RIFATTE" -eq 0 ]; then
    echo "  (controllare le foto: l'avviso è comparso dopo l'attesa ma nessuna foto è stata rifatta)"
  fi
}
