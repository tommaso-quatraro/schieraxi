#!/bin/bash
# TEMPORANEO (issue #393): prova che l'ascolto del registro vede l'avviso. Non va unito.
USCITA="${2:-screenshot}"
mkdir -p "$USCITA"
D=$(mktemp -d)
IFS=$'\t' read -r UDID NOME IOS <<< "$(python3 -I "$(dirname "$0")/scegli_simulatore.py" iphone)"
echo "Simulatore: $NOME ($IOS) $UDID"
xcrun simctl boot "$UDID" 2>/dev/null
xcrun simctl bootstatus "$UDID" -b >/dev/null
echo "$(date +%s) avviato"
source "$(dirname "$0")/avvisi.sh"
echo "filtro: $AVVISI_FILTRO"
# A: col tubo semplice (come prima)
( xcrun simctl spawn "$UDID" log stream --level debug --style compact --predicate "$AVVISI_FILTRO" 2>/dev/null \
    | while IFS= read -r riga; do case "$riga" in 20*) date +%s > "$D/A.flag"; echo "$riga" >> "$D/A.log" ;; esac; done ) &
# B: con avvisi.sh (terminale finto)
AVVISI_FLAG="$D/B.flag"
avvisi_avvia "$UDID"
inizio=$(date +%s)
a_visto=0; b_visto=0
for i in $(seq 1 270); do
  if [ -f "$D/A.flag" ] && [ "$a_visto" = 0 ]; then a_visto=$(cat "$D/A.flag"); echo "A (tubo) ha visto l'avviso alle $a_visto, dopo $((a_visto - inizio)) s; ora $(date +%s)"; fi
  b=$(avvisi_ultimo)
  if [ "$b" -gt 0 ] && [ "$b_visto" = 0 ]; then
    b_visto=$b
    echo "B (script) ha visto l'avviso alle $b, dopo $((b - inizio)) s; ora $(date +%s)"
    xcrun simctl io "$UDID" screenshot "$USCITA/p_subito.png" >/dev/null 2>&1
    sleep 12
    xcrun simctl io "$UDID" screenshot "$USCITA/p_dopo12s.png" >/dev/null 2>&1
    echo "foto fatte alle $(date +%s)"
    break
  fi
  sleep 2
done
sleep 5
echo "== A.log"; cat "$D/A.log" 2>/dev/null | cut -c1-200
echo "== B.log"; cat "$D/B.flag.log" 2>/dev/null | cut -c1-200
echo "== verità (log show)"
xcrun simctl spawn "$UDID" log show --last 12m --style compact --predicate 'eventMessage CONTAINS "Posted new Readiness CFU"' 2>&1 | cut -c1-160 | head -5
avvisi_ferma
xcrun simctl shutdown "$UDID" >/dev/null 2>&1
exit 0
