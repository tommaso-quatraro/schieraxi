#!/bin/bash
# Fotografa l'app nel simulatore di un Mac (lanciato da .github/workflows/screenshot.yml).
# L'app parte in modalità demo (argomento -DEMO: dati finti, nessuna rete) e con -DEMO_SCHERMATA <nome> si apre da sola
# sulla schermata da fotografare: dal simulatore da riga di comando non si può toccare lo schermo.
#
# Uso: scripts/screenshot.sh <Schieraxi.app per il simulatore> <cartella dei PNG>
#
# Nota: niente "set -e": se uno scatto fallisce si va avanti e si segnala alla fine.

APP="${1:?manca il percorso di Schieraxi.app}"
USCITA="${2:-screenshot}"
ID_APP="it.schieraxi.app"
ERRORI=0
ARGOMENTI_EXTRA=()
STILE_ARG=()   # -AppleInterfaceStyle Dark/Light: ripiego, vale per l'app anche se il simulatore non ha ancora cambiato aspetto
RADDRIZZA=0
mkdir -p "$USCITA"

# Tutte le schermate. Il suffisso -fondo = la schermata parte scorsa in fondo (si vede la parte sotto la piega).
TUTTE=(oggi oggi-fondo formazione formazione-fondo formazione-manuale formazione-confronto formazione-immagine
       mercato-consigliati mercato-classifica mercato-classifica-fondo mercato-calendario mercato-osservati mercato-asta mercato-asta-riparazione
       mercato-cerca giocatore giocatore-fondo ricerca
       scambi scambi-fondo scambi-offerta scambi-dettaglio scambi-analizza
       lega lega-squadre lega-rosa lega-regole lega-asta lega-stato lega-crediti lega-avvisi lega-diario lega-novita
       lega-importa lega-importa-csv lega-movimenti lega-stagione impostazioni-aspetto
       impostazioni impostazioni-crediti impostazioni-avanzate primo-avvio accesso-accedi accesso-registra accesso-recupero accesso-codice accesso-account accesso-rose accesso-rete accesso-limite accesso-non-valido)
# giro in tema chiaro: le schermate principali e le nuove (il tema scuro le ha tutte)
PER_CHIARO=(oggi formazione formazione-confronto formazione-immagine mercato-consigliati mercato-asta mercato-asta-riparazione mercato-classifica
            scambi scambi-offerta scambi-dettaglio lega lega-regole lega-stato impostazioni-aspetto lega-rosa giocatore giocatore-fondo ricerca)
PRINCIPALI=(oggi formazione mercato-consigliati mercato-classifica scambi lega giocatore)
PER_TESTO_GRANDE=(oggi oggi-fondo formazione formazione-fondo formazione-manuale formazione-confronto mercato-consigliati mercato-calendario
                  mercato-osservati mercato-asta scambi scambi-offerta scambi-dettaglio scambi-analizza lega lega-squadre lega-regole lega-stato
                  impostazioni-aspetto giocatore giocatore-fondo)
PER_IPAD=(oggi oggi-fondo formazione formazione-fondo formazione-manuale formazione-confronto mercato-consigliati mercato-classifica
          mercato-calendario mercato-osservati mercato-asta giocatore giocatore-fondo scambi scambi-offerta scambi-dettaglio scambi-analizza
          lega lega-squadre lega-rosa lega-regole lega-avvisi lega-diario impostazioni-aspetto)

# SCATTI=veloce (predefinito dei push su main): solo le schermate principali, per controllare in pochi minuti.
# SCATTI=completo: tutte le schermate, tutte le varianti (ci vuole quasi un'ora).
SCATTI="${SCATTI:-completo}"
if [ "$SCATTI" = "veloce" ]; then
  TUTTE=(oggi formazione giocatore mercato-classifica impostazioni-aspetto accesso-accedi accesso-limite primo-avvio impostazioni-fondo impostazioni-crediti)
  PER_CHIARO=(oggi giocatore primo-avvio impostazioni-crediti)
  PER_TESTO_GRANDE=(accesso-accedi)
  PRINCIPALI=(oggi lega)
  PER_IPAD=(formazione giocatore primo-avvio impostazioni-crediti)
fi

scegli() {
  python3 -I "$(dirname "$0")/scegli_simulatore.py" "$1"
}

scatta() {
  local udid="$1" etichetta="$2" nome="$3"
  local schermata="$nome" fondo=() cerca=() cosa=()
  case "$nome" in
    *-fondo) schermata="${nome%-fondo}"; fondo=(-DEMO_FONDO 1) ;;
  esac
  # «accesso-<scenario>»: la demo con gli account accesi (schermata di accesso, codice di recupero, account in Lega...)
  case "$nome" in
    accesso-*) cosa=(-DEMO_ACCESSO "${nome#accesso-}") ;;
    *) cosa=(-DEMO_SCHERMATA "$schermata") ;;
  esac
  # la ricerca globale si apre da sola con un testo già scritto
  case "$nome" in
    ricerca) cerca=(-DEMO_CERCA ma) ;;
  esac
  xcrun simctl terminate "$udid" "$ID_APP" >/dev/null 2>&1
  sleep 1
  if ! xcrun simctl launch "$udid" "$ID_APP" -DEMO "${cosa[@]}" \
        ${fondo[@]+"${fondo[@]}"} ${cerca[@]+"${cerca[@]}"} ${ARGOMENTI_EXTRA[@]+"${ARGOMENTI_EXTRA[@]}"}         ${STILE_ARG[@]+"${STILE_ARG[@]}"} \
        -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null; then
    echo "ERRORE: l'app non parte ($etichetta / $nome)"
    ERRORI=$((ERRORI + 1))
    return
  fi
  sleep 3
  # l'app deve essere ancora in esecuzione (altrimenti è andata in crash)
  if ! xcrun simctl spawn "$udid" launchctl list 2>/dev/null | grep -q "UIKitApplication:$ID_APP"; then
    echo "ATTENZIONE: l'app non risulta in esecuzione ($etichetta / $nome): crash?"
    ERRORI=$((ERRORI + 1))
  fi
  local file="$USCITA/${etichetta}_${nome}.png"
  if ! xcrun simctl io "$udid" screenshot "$file" >/dev/null 2>&1; then
    echo "ERRORE: scatto non riuscito ($etichetta / $nome)"
    ERRORI=$((ERRORI + 1))
    return
  fi
  # Se la foto è quasi vuota (nera) l'app non aveva ancora finito di disegnarsi: si riprova dopo qualche secondo.
  local peso
  peso=$(stat -f%z "$file" 2>/dev/null || echo 999999)
  if [ "$peso" -lt 150000 ]; then
    sleep 5
    xcrun simctl io "$udid" screenshot "$file" >/dev/null 2>&1
  fi
  # Il simulatore fotografa sempre lo schermo "in verticale": con l'app in orizzontale la foto esce girata di 90 gradi.
  if [ "$RADDRIZZA" = "1" ]; then
    sips -r 270 "$file" >/dev/null 2>&1
  fi
  local w h
  w=$(sips -g pixelWidth "$file" 2>/dev/null | awk '/pixelWidth/ {print $2}')
  h=$(sips -g pixelHeight "$file" 2>/dev/null | awk '/pixelHeight/ {print $2}')
  echo "  $etichetta / $nome: ${w}x${h}"
}

# giro <udid> <etichetta> <chiaro|scuro> <dimensione del testo> <schermate...>
giro() {
  local udid="$1" etichetta="$2" aspetto="$3" dimensione="$4"
  shift 4
  local ui="dark"
  STILE_ARG=(-AppleInterfaceStyle Dark)
  if [ "$aspetto" = "chiaro" ]; then ui="light"; STILE_ARG=(-AppleInterfaceStyle Light); fi
  echo "=== $etichetta ($ui, testo $dimensione) ==="
  # Il cambio di aspetto del simulatore � asincrono e subito dopo l'avvio a volte non vale: capitava che le foto �scuro�
  # dell'iPhone uscissero chiare. Si cambia, si aspetta e si controlla (fino a 5 tentativi).
  local t letto
  for t in 1 2 3 4 5; do
    xcrun simctl ui "$udid" appearance "$ui"
    sleep 2
    letto=$(xcrun simctl ui "$udid" appearance 2>/dev/null | tr -d '[:space:]')
    [ "$letto" = "$ui" ] && break
    echo "  aspetto letto �$letto�, voluto �$ui�: riprovo ($t)"
  done
  xcrun simctl ui "$udid" content_size "$dimensione"
  local s
  for s in "$@"; do
    scatta "$udid" "$etichetta" "$s"
  done
}

avvia_simulatore() {
  local udid="$1"
  xcrun simctl boot "$udid" 2>/dev/null
  xcrun simctl bootstatus "$udid" -b >/dev/null
  xcrun simctl status_bar "$udid" override --time "9:41" --batteryState charged --batteryLevel 100 \
    --cellularMode active --cellularBars 4 --wifiBars 3 >/dev/null 2>&1
  xcrun simctl uninstall "$udid" "$ID_APP" >/dev/null 2>&1
  xcrun simctl install "$udid" "$APP"
}

spegni_simulatore() {
  xcrun simctl shutdown "$1" >/dev/null 2>&1
}

# ---------------------------------------------------------------- iPhone
IFS=$'\t' read -r UDID_IPHONE NOME_IPHONE IOS_IPHONE <<< "$(scegli iphone)"
echo "iPhone: $NOME_IPHONE ($IOS_IPHONE) $UDID_IPHONE"
avvia_simulatore "$UDID_IPHONE"
# lancio di prova: il primo avvio è lento e la prima foto restava nera
xcrun simctl launch "$UDID_IPHONE" "$ID_APP" -DEMO -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null
sleep 10
xcrun simctl terminate "$UDID_IPHONE" "$ID_APP" >/dev/null 2>&1

giro "$UDID_IPHONE" iphone_scuro scuro large "${TUTTE[@]}"
giro "$UDID_IPHONE" iphone_chiaro chiaro large "${PER_CHIARO[@]}"
giro "$UDID_IPHONE" iphone_scuro_testogrande scuro accessibility-large "${PER_TESTO_GRANDE[@]}"
if [ "$SCATTI" != "veloce" ]; then
  giro "$UDID_IPHONE" iphone_chiaro_testomassimo chiaro accessibility-extra-extra-extra-large oggi formazione giocatore lega
  ARGOMENTI_EXTRA=(-DEMO_ORIENTAMENTO orizzontale)
  RADDRIZZA=1
  giro "$UDID_IPHONE" iphone_scuro_orizz scuro large oggi formazione mercato-consigliati
  RADDRIZZA=0
  ARGOMENTI_EXTRA=()
fi

# La schermata di avvio (tentativo: si fotografa subito dopo il lancio, può essere già passata) e la Home di iOS
# (serve a vedere nome e icona dell'app). Va fatta PRIMA della prova dello schema, che lascia a video una conferma di iOS.
xcrun simctl ui "$UDID_IPHONE" appearance dark
xcrun simctl terminate "$UDID_IPHONE" "$ID_APP" >/dev/null 2>&1
sleep 2
xcrun simctl launch "$UDID_IPHONE" "$ID_APP" -DEMO >/dev/null 2>&1
xcrun simctl io "$UDID_IPHONE" screenshot "$USCITA/avvio_iphone.png" >/dev/null 2>&1
sleep 4
for aspetto in dark light; do
  xcrun simctl ui "$UDID_IPHONE" appearance "$aspetto"
  xcrun simctl terminate "$UDID_IPHONE" "$ID_APP" >/dev/null 2>&1
  sleep 3
  xcrun simctl io "$UDID_IPHONE" screenshot "$USCITA/home_iphone_$aspetto.png" >/dev/null 2>&1
done

STILE_ARG=()
# Prova dello schema schieraxi:// con "simctl openurl" (come un tocco su una notifica di ntfy). Su alcuni sistemi iOS chiede
# conferma "Aprire in SchieraXI?": la foto lo mostra. Per questo le altre schermate si aprono con un argomento di lancio.
xcrun simctl ui "$UDID_IPHONE" appearance dark
xcrun simctl ui "$UDID_IPHONE" content_size large
xcrun simctl terminate "$UDID_IPHONE" "$ID_APP" >/dev/null 2>&1
xcrun simctl launch "$UDID_IPHONE" "$ID_APP" -DEMO -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null
sleep 3
xcrun simctl openurl "$UDID_IPHONE" "schieraxi://formazione"
sleep 3
xcrun simctl io "$UDID_IPHONE" screenshot "$USCITA/prova-url_openurl-formazione.png" >/dev/null 2>&1
xcrun simctl openurl "$UDID_IPHONE" "schieraxi://giocatore/203"
sleep 3
xcrun simctl io "$UDID_IPHONE" screenshot "$USCITA/prova-url_openurl-giocatore.png" >/dev/null 2>&1

spegni_simulatore "$UDID_IPHONE"

# ---------------------------------------------------------------- iPad
IFS=$'\t' read -r UDID_IPAD NOME_IPAD IOS_IPAD <<< "$(scegli ipad)"
echo "iPad: $NOME_IPAD ($IOS_IPAD) $UDID_IPAD"
avvia_simulatore "$UDID_IPAD"
# lancio di prova: il primo avvio sul simulatore dell'iPad è lento e la prima foto restava sul caricamento
xcrun simctl launch "$UDID_IPAD" "$ID_APP" -DEMO -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null
sleep 10
xcrun simctl terminate "$UDID_IPAD" "$ID_APP" >/dev/null 2>&1

giro "$UDID_IPAD" ipad_scuro_verticale scuro large "${PER_IPAD[@]}"
if [ "$SCATTI" = "veloce" ]; then
  giro "$UDID_IPAD" ipad_chiaro_verticale chiaro large "${PRINCIPALI[@]}"
else
  giro "$UDID_IPAD" ipad_chiaro_verticale chiaro large "${PRINCIPALI[@]}" formazione-confronto mercato-asta scambi-offerta impostazioni-aspetto
  giro "$UDID_IPAD" ipad_scuro_testogrande scuro accessibility-large oggi formazione mercato-consigliati scambi lega
fi

# Orizzontale: su iPad l'app non può forzare la rotazione (multitasking), quindi si ruota il simulatore con la tastiera
# (Cmd+freccia sinistra nella finestra di Simulator). Può non funzionare sul Mac di GitHub: in quel caso le foto restano verticali.
echo "=== rotazione dell'iPad con la tastiera ==="
open -a Simulator --args -CurrentDeviceUDID "$UDID_IPAD" >/dev/null 2>&1
sleep 10
osascript -e 'tell application "Simulator" to activate' 2>&1
sleep 2
osascript -e 'tell application "System Events" to key code 123 using command down' 2>&1
sleep 3
RADDRIZZA=1   # col simulatore ruotato la foto esce girata di 90 gradi (come sull'iPhone)
if [ "$SCATTI" = "veloce" ]; then
  giro "$UDID_IPAD" ipad_scuro_orizzontale scuro large oggi formazione lega
else
  giro "$UDID_IPAD" ipad_scuro_orizzontale scuro large "${PRINCIPALI[@]}" formazione-manuale mercato-calendario lega-squadre
  giro "$UDID_IPAD" ipad_chiaro_orizzontale chiaro large oggi formazione mercato-classifica lega
fi
RADDRIZZA=0

xcrun simctl ui "$UDID_IPAD" appearance dark
xcrun simctl terminate "$UDID_IPAD" "$ID_APP" >/dev/null 2>&1
sleep 3
xcrun simctl io "$UDID_IPAD" screenshot "$USCITA/home_ipad_dark.png" >/dev/null 2>&1

spegni_simulatore "$UDID_IPAD"

echo "Scatti fatti: $(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' '). Problemi segnalati: $ERRORI"
# Le foto mancanti non fanno fallire il lavoro: si guardano nell'artifact. Fallisce solo se non c'è nessuna foto.
[ "$(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]
