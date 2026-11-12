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
IN_MOVIMENTO=0   # foto scattate allo scadere dell'attesa, con lo schermo che si muoveva ancora (vedi schermo_fermo.py)
NON_RIUSCITI=()  # foto rimaste a metà attesa perché uno scatto non è riuscito: problemi, non movimento (uscita 4 di schermo_fermo.py)
ARGOMENTI_EXTRA=()
ARGOMENTI_SCENARIO=()   # -DEMO_SCENARIO <nome>: le fotografie dal vero (SCATTI=vero)
TEMA_ARG=()    # -tema scuro/chiaro: l'app (AppStorage "tema") usa quel tema qualunque cosa dica il simulatore
STILE_ARG=()   # -AppleInterfaceStyle Dark/Light: ripiego, vale per l'app anche se il simulatore non ha ancora cambiato aspetto
RADDRIZZA=0
mkdir -p "$USCITA"
# Avvisi di sistema («Ready for Apple Intelligence»): si aspetta che compaiano e spariscano PRIMA delle foto (#393).
source "$(dirname "$0")/avvisi.sh"

# Tutte le schermate. Il suffisso -fondo = la schermata parte scorsa in fondo (si vede la parte sotto la piega).
TUTTE=(oggi oggi-fondo oggi-in-corso oggi-finita oggi-rinvio oggi-finita-recupero formazione formazione-fondo formazione-salvata formazione-modificata formazione-chiusa formazione-manuale
       giocatore giocatore-fondo ricerca
       squadra squadra-fondo guida marchio lega-diario-fondo
       lega lega-squadre lega-rosa lega-rosa-fondo lega-regole lega-regole-fondo lega-stato lega-stato-fondo lega-stato-nostri lega-avvisi lega-diario impostazioni-novita
       lega-importa lega-importa-salvate lega-importa-salvate-ok lega-importa-csv lega-stagione impostazioni-aspetto
       impostazioni impostazioni-fondo impostazioni-crediti impostazioni-avanzate primo-avvio collega-widget accesso-accedi accesso-registra accesso-recupero accesso-codice accesso-account accesso-account-fondo accesso-rose accesso-rete accesso-limite accesso-non-valido)
# giro in tema chiaro: le schermate principali e le nuove (il tema scuro le ha tutte)
PER_CHIARO=(oggi formazione
            lega lega-regole lega-stato impostazioni-aspetto lega-rosa giocatore giocatore-fondo ricerca)
PRINCIPALI=(oggi formazione squadra lega giocatore)
PER_TESTO_GRANDE=(oggi oggi-fondo formazione formazione-fondo formazione-manuale formazione-salvata formazione-modificata
                  lega lega-squadre lega-regole lega-stato
                  impostazioni-aspetto giocatore giocatore-fondo)
PER_IPAD=(oggi oggi-fondo formazione formazione-fondo formazione-manuale
          giocatore giocatore-fondo
          lega lega-squadre lega-rosa lega-regole lega-avvisi lega-diario impostazioni-aspetto)

# SCATTI=veloce (predefinito dei push su main): solo le schermate principali, per controllare in pochi minuti.
# SCATTI=completo: tutte le schermate, tutte le varianti (ci vuole quasi un'ora).
SCATTI="${SCATTI:-completo}"
if [ "$SCATTI" = "veloce" ]; then
  TUTTE=(oggi oggi-in-corso oggi-in-corso-fondo oggi-finita oggi-rinvio oggi-finita-recupero formazione giocatore lega-diario lega-regole-fondo impostazioni-aspetto accesso-accedi accesso-limite primo-avvio impostazioni-fondo impostazioni-crediti)
  PER_CHIARO=(oggi oggi-in-corso oggi-finita oggi-rinvio giocatore lega-diario primo-avvio impostazioni-crediti)
  PER_TESTO_GRANDE=(accesso-accedi oggi-in-corso)
  PRINCIPALI=(oggi lega)
  PER_IPAD=(oggi-in-corso oggi-finita formazione giocatore lega-diario primo-avvio impostazioni-crediti)
fi

# SCHERMATE="a b c" (a mano, dal workflow): SOLO queste schermate, ma in tutte le varianti (come il collaudo):
# iPhone chiaro, scuro e testo grande, iPad verticale e orizzontale. Per fotografare solo le schermate toccate da una PR.
if [ -n "${SCHERMATE:-}" ]; then
  read -r -a TUTTE <<< "$SCHERMATE"
  SCATTI=collaudo
fi

# SCATTI=collaudo: OGNI schermata in scuro, chiaro e testo grandissimo (per il giro di stabilita'; un dispositivo per corsa).
if [ "$SCATTI" = "collaudo" ]; then
  PER_CHIARO=("${TUTTE[@]}")
  PER_TESTO_GRANDE=("${TUTTE[@]}")
  PRINCIPALI=("${TUTTE[@]}")
  PER_IPAD=("${TUTTE[@]}")
fi
# IPHONE=iphone|iphone-piccolo|iphone-grande (quale telefono); DISPOSITIVI=tutti|iphone|ipad (quali giri fare).
IPHONE="${IPHONE:-iphone}"
DISPOSITIVI="${DISPOSITIVI:-tutti}"

scegli() {
  python3 -I "$(dirname "$0")/scegli_simulatore.py" "$1"
}

scatta() {
  local udid="$1" etichetta="$2" nome="$3"
  local schermata="$nome" fondo=() cerca=() cosa=()
  case "$nome" in
    *-fondo) schermata="${nome%-fondo}"; fondo=(-DEMO_FONDO 1) ;;
    # Stato dei dati ha due riquadri lunghi quasi quanto lo schermo: «-fondo» mostra il consiglio di formazione, questa i gol attesi nostri
    lega-stato-nostri) schermata="lega-stato"; fondo=(-DEMO_FONDO nostri) ;;
  esac
  # «accesso-<scenario>»: la demo con gli account accesi (schermata di accesso, codice di recupero, account in Lega...).
  # Con «-fondo» lo scenario è lo stesso (accesso-account-fondo = scenario «account» con -DEMO_FONDO).
  case "$nome" in
    accesso-*) cosa=(-DEMO_ACCESSO "${schermata#accesso-}") ;;
    *) cosa=(-DEMO_SCHERMATA "$schermata") ;;
  esac
  # la ricerca globale si apre da sola con un testo già scritto
  case "$nome" in
    ricerca) cerca=(-DEMO_CERCA ma) ;;
  esac
  # il tema forzato tranne che nella schermata che mostra la scelta del tema (deve restare "Automatico")
  local tema=()
  [ "$nome" != "impostazioni-aspetto" ] && tema=(${TEMA_ARG[@]+"${TEMA_ARG[@]}"})
  xcrun simctl terminate "$udid" "$ID_APP" >/dev/null 2>&1
  sleep 1
  if ! xcrun simctl launch "$udid" "$ID_APP" -DEMO "${cosa[@]}" \
        ${fondo[@]+"${fondo[@]}"} ${cerca[@]+"${cerca[@]}"} ${ARGOMENTI_EXTRA[@]+"${ARGOMENTI_EXTRA[@]}"} ${ARGOMENTI_SCENARIO[@]+"${ARGOMENTI_SCENARIO[@]}"}         ${STILE_ARG[@]+"${STILE_ARG[@]}"} ${tema[@]+"${tema[@]}"} \
        -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null; then
    echo "ERRORE: l'app non parte ($etichetta / $nome)"
    ERRORI=$((ERRORI + 1))
    return
  fi
  # L'iPad disegna più lentamente (colonne, pagina a destra): con 3 secondi la foto di «lega» usciva con il solo caricamento.
  case "$etichetta" in
    ipad*) sleep 6 ;;
    *) sleep "${ATTESA_SCATTO:-3}" ;;   # 6 nelle fotografie dal vero: risposte grandi, schermate che caricano due volte
  esac
  # l'app deve essere ancora in esecuzione (altrimenti è andata in crash)
  if ! xcrun simctl spawn "$udid" launchctl list 2>/dev/null | grep -q "UIKitApplication:$ID_APP"; then
    echo "ATTENZIONE: l'app non risulta in esecuzione ($etichetta / $nome): crash?"
    ERRORI=$((ERRORI + 1))
  fi
  local file="$USCITA/${etichetta}_${nome}.png" esito
  # Si fotografa quando lo schermo è fermo (due foto di fila uguali): non mentre la schermata carica o i numeri salgono.
  # Prima bastavano i secondi fissi qui sopra, e la Formazione in orizzontale usciva con lo scheletro del caricamento.
  python3 -I "$(dirname "$0")/schermo_fermo.py" "$udid" "$file" "${ATTESA_FERMO:-8}"
  esito=$?
  if [ "$esito" -eq 3 ]; then
    echo "  ($etichetta / $nome: lo schermo si muoveva ancora dopo l'attesa, foto scattata lo stesso)"
    IN_MOVIMENTO=$((IN_MOVIMENTO + 1))
  elif [ "$esito" -eq 4 ]; then
    # Uno scatto dopo il primo non è riuscito: resta la foto di prima (forse ancora in movimento) e si tratta come le altre.
    echo "ERRORE: scatto non riuscito durante l'attesa ($etichetta / $nome): resta la foto di prima"
    ERRORI=$((ERRORI + 1))
    NON_RIUSCITI+=("$etichetta / $nome")
  elif [ "$esito" -ne 0 ]; then
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
  TEMA_ARG=(-tema scuro)
  if [ "$aspetto" = "chiaro" ]; then ui="light"; STILE_ARG=(-AppleInterfaceStyle Light); TEMA_ARG=(-tema chiaro); fi
  echo "=== $etichetta ($ui, testo $dimensione) ==="
  # Il cambio di aspetto del simulatore è asincrono e subito dopo l'avvio a volte non vale: capitava che le foto «scuro»
  # dell'iPhone uscissero chiare. Si cambia, si aspetta e si controlla (fino a 5 tentativi).
  local t letto
  for t in 1 2 3 4 5; do
    xcrun simctl ui "$udid" appearance "$ui"
    sleep 2
    letto=$(xcrun simctl ui "$udid" appearance 2>/dev/null | tr -d '[:space:]')
    [ "$letto" = "$ui" ] && break
    echo "  aspetto letto «$letto», voluto «$ui»: riprovo ($t)"
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
  avvisi_avvia "$udid"
  xcrun simctl status_bar "$udid" override --time "9:41" --batteryState charged --batteryLevel 100 \
    --cellularMode active --cellularBars 4 --wifiBars 3 >/dev/null 2>&1
  xcrun simctl uninstall "$udid" "$ID_APP" >/dev/null 2>&1
  xcrun simctl install "$udid" "$APP"
}

spegni_simulatore() {
  avvisi_ferma
  xcrun simctl shutdown "$1" >/dev/null 2>&1
}

# Prova dello schema schieraxi:// con "simctl openurl" (come un tocco su una notifica di ntfy). Le altre schermate si aprono
# con un argomento di lancio. I link di "simctl openurl" arrivano da CoreSimulatorBridge come da un'altra app e il simulatore
# chiede "Open in "SchieraXI"?" (issue #250: le foto mostravano la finestra). Si approva prima lo schema per chi apre i link,
# come farebbe il tocco su «Open»: chiave "<chi apre>--><schema in minuscolo>", valore il bundle id. Niente finestra da toccare.
prova_url() {
  local udid="$1"
  if ! xcrun simctl spawn "$udid" defaults write com.apple.launchservices.schemeapproval \
        "com.apple.CoreSimulator.CoreSimulatorBridge-->schieraxi" -string "$ID_APP" >/dev/null; then
    echo "ATTENZIONE: schema schieraxi:// non approvato: le foto prova-url possono mostrare la conferma di iOS"
    ERRORI=$((ERRORI + 1))
  fi
  xcrun simctl ui "$udid" appearance dark
  xcrun simctl ui "$udid" content_size large
  xcrun simctl terminate "$udid" "$ID_APP" >/dev/null 2>&1
  xcrun simctl launch "$udid" "$ID_APP" -DEMO -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null
  sleep 3
  xcrun simctl openurl "$udid" "schieraxi://formazione"
  sleep 3
  xcrun simctl io "$udid" screenshot "$USCITA/prova-url_openurl-formazione.png" >/dev/null 2>&1
  xcrun simctl openurl "$udid" "schieraxi://giocatore/203"
  sleep 3
  xcrun simctl io "$udid" screenshot "$USCITA/prova-url_openurl-giocatore.png" >/dev/null 2>&1
}

# In fondo al registro della corsa: quante foto, quanti problemi (con il nome delle foto rimaste a metà attesa), quante in movimento.
riepilogo() {
  echo "Scatti fatti: $(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' '). Problemi segnalati: $ERRORI. Foto con lo schermo ancora in movimento: $IN_MOVIMENTO"
  avvisi_riepilogo
  if [ "${#NON_RIUSCITI[@]}" -gt 0 ]; then
    echo "Tra i problemi, foto con uno scatto non riuscito durante l'attesa (resta la foto di prima):"
    printf '  %s\n' "${NON_RIUSCITI[@]}"
  fi
}

# ---------------------------------------------------------------- fotografie dal vero
# SCATTI=vero: le schermate con le risposte vere del server (nomi inventati) in tre momenti della giornata: vedi
# Sources/Support/ScenarioVero.swift e la cartella fotografie/. Un dispositivo per corsa (il workflow ne lancia tre in parallelo):
# DISPOSITIVI=ipad per l'iPad, altrimenti l'iPhone scelto da IPHONE (iphone-piccolo, iphone-grande, iphone).
# Nomi dei file: <dispositivo>_<aspetto>_<scenario>_<schermata>.png
FOTOGRAFIE="${FOTOGRAFIE:-fotografie}"
VERO_SCENARI=(vero-prima vero-in-corso vero-finita)
# prima della scadenza: tutte le schermate che mostrano i dati della lega
VERO_TUTTE=(oggi oggi-fondo formazione formazione-fondo formazione-manuale squadra squadra-fondo
            giocatore giocatore-fondo ricerca
            lega lega-squadre lega-rosa lega-regole lega-stato lega-diario lega-diario-fondo lega-stagione)
# giornata in corso e giornata finita: le schermate che cambiano con il momento
VERO_FASE=(oggi oggi-fondo formazione formazione-fondo squadra giocatore lega-diario)

# Copia i file degli scenari nella cartella Documenti dell'app nel simulatore (l'app li legge da lì: non entrano nell'IPA).
copia_fotografie() {
  local udid="$1" dati
  dati=$(xcrun simctl get_app_container "$udid" "$ID_APP" data 2>/dev/null)
  if [ -z "$dati" ] || [ ! -d "$dati" ]; then
    echo "ERRORE: cartella dei dati dell'app non trovata: le foto mostrerebbero la demo di sempre"
    return 1
  fi
  mkdir -p "$dati/Documents/fotografie"
  cp "$FOTOGRAFIE"/*.json "$dati/Documents/fotografie/" || return 1
  echo "  scenari copiati: $(ls "$dati/Documents/fotografie" | tr '\n' ' ')"
}

# giro_vero <udid> <etichetta> <chiaro|scuro> <dimensione del testo>: ogni scenario con le sue schermate
giro_vero() {
  local udid="$1" etichetta="$2" aspetto="$3" dimensione="$4" sc
  for sc in "${VERO_SCENARI[@]}"; do
    ARGOMENTI_SCENARIO=(-DEMO_SCENARIO "$sc")
    if [ "$sc" = "vero-prima" ]; then
      giro "$udid" "${etichetta}_${sc}" "$aspetto" "$dimensione" "${VERO_TUTTE[@]}"
    else
      giro "$udid" "${etichetta}_${sc}" "$aspetto" "$dimensione" "${VERO_FASE[@]}"
    fi
  done
  ARGOMENTI_SCENARIO=()
}

if [ "$SCATTI" = "vero" ]; then
  ATTESA_SCATTO=6
  if ! ls "$FOTOGRAFIE"/vero-*.json >/dev/null 2>&1; then
    echo "ERRORE: nessuno scenario in $FOTOGRAFIE/ (si preparano con prove/fotografie_dal_vero.py nel repository del server)"
    exit 1
  fi
  if [ "$DISPOSITIVI" = "ipad" ]; then QUALE=ipad; else QUALE="$IPHONE"; fi
  IFS=$'\t' read -r UDID_VERO NOME_VERO IOS_VERO <<< "$(scegli "$QUALE")"
  echo "Fotografie dal vero su: $NOME_VERO ($IOS_VERO)"
  avvia_simulatore "$UDID_VERO"
  # lancio di prova (il primo avvio è lento) che crea anche la cartella dei dati dell'app
  xcrun simctl launch "$UDID_VERO" "$ID_APP" -DEMO -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null
  sleep 10
  xcrun simctl terminate "$UDID_VERO" "$ID_APP" >/dev/null 2>&1
  avvisi_attendi "$UDID_VERO"
  copia_fotografie "$UDID_VERO" || exit 1
  giro_vero "$UDID_VERO" "${QUALE}_scuro" scuro large
  giro_vero "$UDID_VERO" "${QUALE}_chiaro" chiaro large
  if [ "$QUALE" = "ipad" ]; then
    # orizzontale: si ruota il simulatore con la tastiera come nel giro normale (le foto escono girate e si raddrizzano)
    open -a Simulator --args -CurrentDeviceUDID "$UDID_VERO" >/dev/null 2>&1
    sleep 10
    osascript -e 'tell application "Simulator" to activate' 2>&1
    sleep 2
    osascript -e 'tell application "System Events" to key code 123 using command down' 2>&1
    sleep 3
    RADDRIZZA=1
    giro_vero "$UDID_VERO" "${QUALE}-orizzontale_scuro" scuro large
    giro_vero "$UDID_VERO" "${QUALE}-orizzontale_chiaro" chiaro large
    RADDRIZZA=0
  else
    giro_vero "$UDID_VERO" "${QUALE}_scuro-testogrande" scuro accessibility-large
  fi
  spegni_simulatore "$UDID_VERO"
  riepilogo
  [ "$(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]
  exit $?
fi

# ---------------------------------------------------------------- iPhone
if [ "$DISPOSITIVI" != "ipad" ]; then
IFS=$'\t' read -r UDID_IPHONE NOME_IPHONE IOS_IPHONE <<< "$(scegli "$IPHONE")"
echo "iPhone: $NOME_IPHONE ($IOS_IPHONE) $UDID_IPHONE"
avvia_simulatore "$UDID_IPHONE"
# lancio di prova: il primo avvio è lento e la prima foto restava nera
xcrun simctl launch "$UDID_IPHONE" "$ID_APP" -DEMO -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null
sleep 10
xcrun simctl terminate "$UDID_IPHONE" "$ID_APP" >/dev/null 2>&1
avvisi_attendi "$UDID_IPHONE"

giro "$UDID_IPHONE" iphone_scuro scuro large "${TUTTE[@]}"
giro "$UDID_IPHONE" iphone_chiaro chiaro large "${PER_CHIARO[@]}"
giro "$UDID_IPHONE" iphone_scuro_testogrande scuro accessibility-large "${PER_TESTO_GRANDE[@]}"
if [ "$SCATTI" = "collaudo" ]; then
  giro "$UDID_IPHONE" iphone_chiaro_testomassimo chiaro accessibility-extra-extra-extra-large "${TUTTE[@]}"
  ARGOMENTI_EXTRA=(-DEMO_ORIENTAMENTO orizzontale)
  RADDRIZZA=1
  giro "$UDID_IPHONE" iphone_scuro_orizz scuro large oggi formazione squadra giocatore lega lega-diario impostazioni accesso-accedi
  RADDRIZZA=0
  ARGOMENTI_EXTRA=()
elif [ "$SCATTI" != "veloce" ]; then
  giro "$UDID_IPHONE" iphone_chiaro_testomassimo chiaro accessibility-extra-extra-extra-large oggi formazione giocatore lega
  ARGOMENTI_EXTRA=(-DEMO_ORIENTAMENTO orizzontale)
  RADDRIZZA=1
  giro "$UDID_IPHONE" iphone_scuro_orizz scuro large oggi formazione
  RADDRIZZA=0
  ARGOMENTI_EXTRA=()
fi

# La schermata di avvio (tentativo: si fotografa subito dopo il lancio, può essere già passata) e la Home di iOS
# (serve a vedere nome e icona dell'app). Va fatta PRIMA della prova dello schema, che lascia l'app aperta sul giocatore.
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
prova_url "$UDID_IPHONE"

spegni_simulatore "$UDID_IPHONE"
fi
if [ "$DISPOSITIVI" = "iphone" ]; then
  riepilogo
  [ "$(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]
  exit $?
fi

# ---------------------------------------------------------------- iPad
IFS=$'\t' read -r UDID_IPAD NOME_IPAD IOS_IPAD <<< "$(scegli ipad)"
echo "iPad: $NOME_IPAD ($IOS_IPAD) $UDID_IPAD"
avvia_simulatore "$UDID_IPAD"
# lancio di prova: il primo avvio sul simulatore dell'iPad è lento e la prima foto restava sul caricamento
xcrun simctl launch "$UDID_IPAD" "$ID_APP" -DEMO -AppleLanguages "(it)" -AppleLocale it_IT >/dev/null
sleep 10
xcrun simctl terminate "$UDID_IPAD" "$ID_APP" >/dev/null 2>&1
avvisi_attendi "$UDID_IPAD"

giro "$UDID_IPAD" ipad_scuro_verticale scuro large "${PER_IPAD[@]}"
if [ "$SCATTI" = "veloce" ]; then
  giro "$UDID_IPAD" ipad_chiaro_verticale chiaro large "${PRINCIPALI[@]}"
elif [ "$SCATTI" = "collaudo" ]; then
  giro "$UDID_IPAD" ipad_chiaro_verticale chiaro large "${TUTTE[@]}"
  giro "$UDID_IPAD" ipad_chiaro_testomassimo chiaro accessibility-extra-extra-extra-large "${TUTTE[@]}"
else
  giro "$UDID_IPAD" ipad_chiaro_verticale chiaro large "${PRINCIPALI[@]}" impostazioni-aspetto
  giro "$UDID_IPAD" ipad_scuro_testogrande scuro accessibility-large oggi formazione lega
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
  giro "$UDID_IPAD" ipad_chiaro_orizzontale chiaro large oggi-in-corso oggi-finita
  giro "$UDID_IPAD" ipad_scuro_orizzontale scuro large oggi formazione giocatore lega-diario lega
elif [ "$SCATTI" = "collaudo" ]; then
  giro "$UDID_IPAD" ipad_scuro_orizzontale scuro large "${TUTTE[@]}"
  giro "$UDID_IPAD" ipad_chiaro_orizzontale chiaro large "${TUTTE[@]}"
else
  giro "$UDID_IPAD" ipad_scuro_orizzontale scuro large "${PRINCIPALI[@]}" formazione-manuale lega-squadre
  giro "$UDID_IPAD" ipad_chiaro_orizzontale chiaro large oggi formazione lega
fi
RADDRIZZA=0

xcrun simctl ui "$UDID_IPAD" appearance dark
xcrun simctl terminate "$UDID_IPAD" "$ID_APP" >/dev/null 2>&1
sleep 3
xcrun simctl io "$UDID_IPAD" screenshot "$USCITA/home_ipad_dark.png" >/dev/null 2>&1

spegni_simulatore "$UDID_IPAD"

riepilogo
# Le foto mancanti non fanno fallire il lavoro: si guardano nell'artifact. Fallisce solo se non c'è nessuna foto.
[ "$(ls "$USCITA"/*.png 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]
