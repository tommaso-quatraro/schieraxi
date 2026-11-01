#!/bin/bash
# Fotografa i widget nel simulatore (lanciato da .github/workflows/screenshot.yml).
# L'app di anteprima (target AnteprimaWidget) mostra i widget con dati finti: -GALLERIA <widget>[-blocco], -DATI pieni|parziali|vuoto.
# Uso: scripts/screenshot_widget.sh <AnteprimaWidget.app per il simulatore> <cartella dei PNG>
APP="${1:?manca il percorso di AnteprimaWidget.app}"
USCITA="${2:-screenshot-widget}"
ID_APP="it.schieraxi.app.anteprima"
ERRORI=0
mkdir -p "$USCITA"

scegli() { python3 -I "$(dirname "$0")/scegli_simulatore.py" "$1"; }

scatta() {
  local udid="$1" etichetta="$2" nome="$3" dati="${4:-pieni}" larghezza="$5"
  local render="pieno" suffisso=""
  if [[ "$dati" == *+* ]]; then render="${dati##*+}"; dati="${dati%%+*}"; suffisso="_$render"; fi
  xcrun simctl terminate "$udid" "$ID_APP" >/dev/null 2>&1
  sleep 1
  if ! xcrun simctl launch "$udid" "$ID_APP" -GALLERIA "$nome" -DATI "$dati" -RENDER "$render" -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null; then
    echo "ERRORE: l'app non parte ($etichetta / $nome)"; ERRORI=$((ERRORI + 1)); return
  fi
  sleep 3
  if ! xcrun simctl spawn "$udid" launchctl list 2>/dev/null | grep -q "UIKitApplication:$ID_APP"; then
    echo "ATTENZIONE: l'app non risulta in esecuzione ($etichetta / $nome): crash?"; ERRORI=$((ERRORI + 1))
  fi
  local file="$USCITA/${etichetta}_${nome}_${dati}${suffisso}.png"
  if ! xcrun simctl io "$udid" screenshot "$file" >/dev/null 2>&1; then
    echo "ERRORE: scatto non riuscito ($etichetta / $nome)"; ERRORI=$((ERRORI + 1)); return
  fi
  if [ "$(stat -f%z "$file" 2>/dev/null || echo 999999)" -lt 30000 ]; then sleep 5; xcrun simctl io "$udid" screenshot "$file" >/dev/null 2>&1; fi
  sips --resampleWidth "$larghezza" "$file" >/dev/null 2>&1
  echo "  $etichetta / $nome / $dati"
}

giro() {   # giro <udid> <etichetta> <dark|light> <larghezza> <widget[:dati]...>
  local udid="$1" etichetta="$2" aspetto="$3" larghezza="$4"
  shift 4
  echo "=== $etichetta ($aspetto) ==="
  xcrun simctl ui "$udid" appearance "$aspetto"
  xcrun simctl ui "$udid" content_size "${DIMENSIONE:-large}"
  local s
  for s in "$@"; do
    scatta "$udid" "$etichetta" "${s%%:*}" "$( [[ "$s" == *:* ]] && echo "${s##*:}" || echo pieni )" "$larghezza"
  done
}

avvia() {
  local udid="$1"
  xcrun simctl boot "$udid" 2>/dev/null
  xcrun simctl bootstatus "$udid" -b >/dev/null
  xcrun simctl status_bar "$udid" override --time "9:41" --batteryState charged --batteryLevel 100 --cellularMode active --cellularBars 4 --wifiBars 3 >/dev/null 2>&1
  xcrun simctl uninstall "$udid" "$ID_APP" >/dev/null 2>&1
  xcrun simctl install "$udid" "$APP"
  xcrun simctl launch "$udid" "$ID_APP" -GALLERIA cruscotto >/dev/null
  sleep 8
  xcrun simctl terminate "$udid" "$ID_APP" >/dev/null 2>&1
}

TUTTI=(cruscotto cruscotto-blocco live live-blocco osservato osservato-blocco formazione formazione-blocco punti punti-blocco scambio scambio-blocco oggi dubbi rosa crediti crediti-blocco stato-blocco)

IFS=$'\t' read -r UDID_IPHONE NOME_IPHONE IOS_IPHONE <<< "$(scegli iphone)"
echo "iPhone: $NOME_IPHONE ($IOS_IPHONE)"
avvia "$UDID_IPHONE"
giro "$UDID_IPHONE" iphone_scuro dark 600 "${TUTTI[@]}" cruscotto:parziali cruscotto:vuoto punti:parziali scambio:parziali
giro "$UDID_IPHONE" iphone_chiaro light 600 cruscotto formazione punti scambio oggi osservato
# Stato vuoto (nessun dato dal server) e testo molto grande (impostazione di accessibilita'): niente deve tagliarsi o sovrapporsi.
giro "$UDID_IPHONE" iphone_vuoto dark 600 formazione:vuoto punti:vuoto formazione-blocco:vuoto punti-blocco:vuoto oggi:vuoto
DIMENSIONE=accessibility-extra-large giro "$UDID_IPHONE" iphone_testo_grande dark 600 formazione punti oggi crediti dubbi formazione-blocco punti-blocco
giro "$UDID_IPHONE" iphone_accentato dark 600 cruscotto:pieni+accentato formazione:pieni+accentato oggi:pieni+accentato osservato:pieni+accentato cruscotto-blocco:pieni+vivido
xcrun simctl shutdown "$UDID_IPHONE" >/dev/null 2>&1

IFS=$'\t' read -r UDID_IPAD NOME_IPAD IOS_IPAD <<< "$(scegli ipad)"
echo "iPad: $NOME_IPAD ($IOS_IPAD)"
avvia "$UDID_IPAD"
giro "$UDID_IPAD" ipad_scuro_verticale dark 800 cruscotto formazione punti scambio oggi rosa crediti stato-blocco cruscotto:parziali
giro "$UDID_IPAD" ipad_chiaro_verticale light 800 cruscotto formazione
DIMENSIONE=accessibility-extra-large giro "$UDID_IPAD" ipad_testo_grande dark 800 formazione punti

# Orizzontale: si ruota il simulatore con la tastiera (puo' non funzionare sul Mac di GitHub: in quel caso le foto restano verticali).
open -a Simulator --args -CurrentDeviceUDID "$UDID_IPAD" >/dev/null 2>&1
sleep 10
osascript -e 'tell application "Simulator" to activate' 2>&1
sleep 2
osascript -e 'tell application "System Events" to key code 123 using command down' 2>&1
sleep 3
giro "$UDID_IPAD" ipad_scuro_orizzontale dark 800 cruscotto formazione punti
for f in "$USCITA"/ipad_scuro_orizzontale_*.png; do sips -r 270 "$f" >/dev/null 2>&1; done
xcrun simctl shutdown "$UDID_IPAD" >/dev/null 2>&1

echo "Scatti fatti: $(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' '). Problemi: $ERRORI"
[ "$(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]
