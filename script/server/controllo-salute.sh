#!/bin/bash
# controllo-salute.sh - Sul server SchieraXI, ogni 5 minuti (crontab dell'utente del server): controlla in SOLA LETTURA
# l'app (https://app.schieraxi.it, rotte /api/account/me e /api/salute), lo spazio del disco, la memoria, il certificato e l'ultimo aggiornamento dei dati.
# Avvisa sul telefono con ntfy (canale in ~/.config/schieraxi/canale, o il file indicato da SCHIERAXI_CANALE).
# Soglie:
#   - app non raggiungibile: avviso solo dopo 2 controlli di fila (circa 10 minuti)
#   - disco pieno oltre l'80%
#   - memoria disponibile sotto il 10%
#   - certificato che scade tra meno di 14 giorni
#   - ultimo aggiornamento dei dati piu' vecchio di 12 ore
# Quando un problema torna a posto, manda un avviso "risolto". Non cambia niente sull'app.
# Stato e log in ~/.cache/controllo/ (avvisi.log, ultimo-giro, fallimenti, aperto-<problema>).
#
# Cron:   */5 * * * * /bin/bash $HOME/fantacalcio/script/server/controllo-salute.sh >/dev/null 2>&1
# Prova:  bash ~/fantacalcio/script/server/controllo-salute.sh --prova          (manda un avviso finto, non tocca lo stato)
# Senza inviare: CONTROLLO_SENZA_INVIO=1 bash ~/fantacalcio/script/server/controllo-salute.sh   (stampa cosa manderebbe)
# Per le prove: CONTROLLO_DIR=/tmp/prova-controllo (cartella di stato a parte), CONTROLLO_PAUSA=0 (niente attese fra le prove).

export LC_ALL=C
URL="${CONTROLLO_URL:-https://app.schieraxi.it}"     # CONTROLLO_URL solo per le prove
HOST="app.schieraxi.it"
dir="${CONTROLLO_DIR:-$HOME/.cache/controllo}"
mkdir -p "$dir"; chmod 700 "$dir"
log="$dir/avvisi.log"
CANALE=$(tr -d ' \r\n' < "${SCHIERAXI_CANALE:-$HOME/.config/schieraxi/canale}" 2>/dev/null)
export CANALE

# $1 titolo, $2 testo, $3 priorita' 1-5, $4 tag. Il canale non viene mai stampato.
manda() {
  if [ -n "$CONTROLLO_SENZA_INVIO" ]; then echo "[prova, non inviato] $1: $2"; return 0; fi
  [ -n "$CANALE" ] || return 1
  json=$(python3 -c '
import json, os, sys
print(json.dumps({"topic": os.environ["CANALE"], "title": sys.argv[1], "message": sys.argv[2],
                  "priority": int(sys.argv[3]), "tags": [sys.argv[4]]}))' "$1" "$2" "$3" "$4") || return 1
  # il corpo (con il nome del canale) passa dallo standard input: non compare tra gli argomenti del comando, visibili a tutti con ps
  printf '%s' "$json" | curl -fsS -m 20 -H 'Content-Type: application/json' --data-binary @- "${CONTROLLO_NTFY_URL:-https://ntfy.sh}" >/dev/null
}

if [ "$1" = "--prova" ]; then
  manda "SchieraXI: prova" "Avviso finto del controllo di salute: se lo leggi, le notifiche dal server funzionano." 3 white_check_mark \
    && echo "Inviata." || { echo "NON inviata (canale mancante o internet non raggiungibile)."; exit 1; }
  exit 0
fi

# Problemi: "apri <chiave> <titolo> <testo> <priorita> <tag>" avvisa una sola volta; "chiudi <chiave> <titolo> <testo>" avvisa quando tornano a posto.
# Se l'invio fallisce, non si segna niente e si riprova al giro dopo.
apri() {
  [ -f "$dir/aperto-$1" ] && return 0
  if manda "$2" "$3" "$4" "$5"; then
    touch "$dir/aperto-$1"; echo "$(date '+%F %T') APERTO $1: $3" >> "$log"
  fi
}
chiudi() {
  [ -f "$dir/aperto-$1" ] || return 0
  if manda "$2 (risolto)" "$3" 3 white_check_mark; then
    rm -f "$dir/aperto-$1"; echo "$(date '+%F %T') RISOLTO $1" >> "$log"
  fi
}

# ---- app viva: /api/account/me risponde 200, oppure 401 che dice "multiutente" (senza login). Con gli account accesi
# /api/stato chiede l'accesso, quindi non serve a controllare che l'app sia viva. 2 controlli di fila senza risposta prima di avvisare.
# Ogni controllo prova 3 volte a 5 secondi di distanza: un riavvio dell'app (aggiorna-app.sh) dura qualche secondo e non conta.
vivo=0
for tentativo in 1 2 3; do
  me_codice=$(curl -s -m 15 -o "$dir/me.tmp" -w '%{http_code}' -H 'X-Fanta: 1' "$URL/api/account/me" 2>/dev/null)
  me_corpo=$(cat "$dir/me.tmp" 2>/dev/null)
  rm -f "$dir/me.tmp"
  if [ "$me_codice" = "200" ] || { [ "$me_codice" = "401" ] && printf '%s' "$me_corpo" | grep -q 'multiutente'; }; then vivo=1; break; fi
  [ "$tentativo" -lt 3 ] && sleep "${CONTROLLO_PAUSA:-5}"
done
if [ "$vivo" = 1 ]; then
  rm -f "$dir/fallimenti"
  chiudi sito "SchieraXI: app" "L'app risponde di nuovo."
else
  n=$(( $(cat "$dir/fallimenti" 2>/dev/null || echo 0) + 1 ))
  echo "$n" > "$dir/fallimenti"
  [ "$n" -ge 2 ] && apri sito "SchieraXI: app" "L'app non risponde da almeno 2 controlli (circa 10 minuti). Controllare il server." 5 rotating_light
fi

# ---- dati (da /api/salute, rotta pubblica senza dati personali): database illeggibile (503 / ok:false), nessun aggiornamento
# registrato (ultimo_aggiornamento null) o piu' vecchio di 12 ore
if [ "$vivo" = 1 ]; then
  sal_codice=$(curl -sS -m 15 -o "$dir/salute.tmp" -w '%{http_code}' "$URL/api/salute" 2>/dev/null)
  corpo=$(cat "$dir/salute.tmp" 2>/dev/null); rm -f "$dir/salute.tmp"
  esito=""
  if [ "$sal_codice" = "503" ]; then
    esito="KO"
  elif [ "$sal_codice" = "200" ] && [ -n "$corpo" ]; then
    esito=$(printf '%s' "$corpo" | python3 -c '
import datetime, json, sys, zoneinfo
try:
    d = json.load(sys.stdin)
    if d.get("ok") is False:
        print("KO"); sys.exit(0)
    t = d.get("ultimo_aggiornamento")
    if not t:
        print("NULL"); sys.exit(0)
    fuso = zoneinfo.ZoneInfo("Europe/Rome")
    ora = datetime.datetime.fromisoformat(t).replace(tzinfo=fuso)
    print(int((datetime.datetime.now(fuso) - ora).total_seconds() // 3600))
except Exception:
    pass' 2>/dev/null)
  fi
  case "$esito" in
    "") ;;     # nessuna risposta utile (429, errore di rete...): non si decide niente
    KO) apri dati "SchieraXI: dati" "Il database dei dati non si legge (la rotta di salute risponde con errore). Controllare il server." 5 rotating_light ;;
    NULL) apri dati "SchieraXI: dati" "Nessun aggiornamento dei dati risulta registrato. Controllare il cron di aggiornamento." 4 warning ;;
    *) if [ "$esito" -gt 12 ]; then
         apri dati "SchieraXI: dati" "I dati non si aggiornano da circa $esito ore (limite 12). Controllare il cron di aggiornamento." 4 warning
       else
         chiudi dati "SchieraXI: dati" "I dati si aggiornano di nuovo."
       fi ;;
  esac
fi

# ---- sicurezza: l'allarme "aperta senza accesso" scatta SOLO se /api/formazione risponde 200 senza login, oppure se
# /api/account/me risponde 200 senza "multiutente": true. 502, 503, 429, 000... vogliono dire "non raggiungibile" (lo dice il controllo
# sopra), non "aperta". Si chiude solo se /api/formazione chiede il login (401/403) e /api/account/me conferma multiutente.
codice=$(curl -s -m 15 -o /dev/null -w '%{http_code}' -H 'X-Fanta: 1' "$URL/api/formazione" 2>/dev/null)
me_ok=0; printf '%s' "$me_corpo" | grep -q '"multiutente": *true' && me_ok=1
if [ "$codice" = "200" ] || { [ "$me_codice" = "200" ] && [ "$me_ok" = 0 ]; }; then
  apri sicurezza "SchieraXI: l'app e' aperta senza accesso!" "Senza login l'app risponde (formazione: $codice, account: $me_codice). Verificare subito il servizio fantacalcio: drop-in systemd FANTA_MULTIUTENTE." 5 rotating_light
elif { [ "$codice" = "401" ] || [ "$codice" = "403" ]; } && [ "$me_ok" = 1 ]; then
  chiudi sicurezza "SchieraXI: accesso" "Il login dell'app e' di nuovo attivo."
fi

# ---- disco: oltre l'80% di uso
pct=$(df --output=pcent / 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "$pct" ]; then
  if [ "$pct" -gt 80 ]; then
    apri disco "SchieraXI: disco" "Il disco e' pieno al ${pct}% (limite 80%)." 4 warning
  else
    chiudi disco "SchieraXI: disco" "Il disco e' tornato sotto l'80% (${pct}%)."
  fi
fi

# ---- memoria: meno del 10% disponibile
tot=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null)
disp=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null)
if [ -n "$tot" ] && [ -n "$disp" ] && [ "$tot" -gt 0 ]; then
  libera=$(( disp * 100 / tot ))
  if [ "$libera" -lt 10 ]; then
    apri memoria "SchieraXI: memoria" "Memoria quasi finita: solo il ${libera}% disponibile." 4 warning
  else
    chiudi memoria "SchieraXI: memoria" "La memoria e' tornata sopra il 10% (${libera}% libero)."
  fi
fi

# ---- certificato: scade tra meno di 14 giorni (1209600 secondi), letto dal sito pubblico
cert=""
if [ -z "${CONTROLLO_SENZA_CERTIFICATO:-}" ]; then     # solo per le prove (niente rete)
  cert=$(echo | timeout 15 openssl s_client -connect "$HOST:443" -servername "$HOST" 2>/dev/null \
    | openssl x509 -noout -enddate -checkend 1209600 2>/dev/null)
fi
if printf '%s' "$cert" | grep -q 'will expire'; then
  fine=$(printf '%s' "$cert" | sed -n 's/^notAfter=//p')
  apri certificato "SchieraXI: certificato" "Il certificato scade il ${fine}: meno di 14 giorni. Rinnovarlo (Let's Encrypt, certbot)." 4 warning
elif printf '%s' "$cert" | grep -q 'will not expire'; then
  chiudi certificato "SchieraXI: certificato" "Il certificato e' di nuovo valido a lungo."
fi

date '+%F %T' > "$dir/ultimo-giro"
exit 0
