#!/bin/bash
# pubblica-sito.sh - Sul server, ogni 5 minuti: tiene /var/www/schieraxi-sito uguale alla cartella sito/ del ramo main
# (dal clone ~/schieraxi-src, quello che usa anche aggiorna-app.sh: per questo prende il suo stesso blocco). nginx serve il sito da quella cartella: non serve ricaricarlo.
#   - Se la cartella e' una cartella normale, aggiorna i file al suo interno (aggiunge, sostituisce, toglie quelli spariti;
#     sposta fuori dalla cartella servita un eventuale .git (la vecchia copia); non tocca .well-known; permessi 755/644).
#   - Se e' un link simbolico, crea una cartella nuova accanto (<cartella>-<versione>) e sposta il link in un colpo solo.
#   - Se sito/ non e' cambiato dall'ultima volta, non fa niente.
# Variabili per le prove: SCHIERAXI_SITO_DIR (dove si pubblica), SCHIERAXI_SRC (clone), SCHIERAXI_SENZA_FETCH=1.
#   Dal crontab dell'utente del server:  */5 * * * * /bin/bash $HOME/fantacalcio/script/server/pubblica-sito.sh >/dev/null 2>&1
set -u
SRC="${SCHIERAXI_SRC:-$HOME/schieraxi-src}"
SITO="${SCHIERAXI_SITO_DIR:-/var/www/schieraxi-sito}"
STATO="${FANTA_CACHE:-$HOME/.cache/fantacalcio}"
mkdir -p "$STATO"
exec 5>"$STATO/blocco-sito"
flock -n 5 || exit 0
LOG="$STATO/pubblica-sito.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"; }

export GIT_TERMINAL_PROMPT=0
cd "$SRC" 2>/dev/null || { log "manca il clone $SRC"; exit 1; }
# Il clone e' lo stesso di aggiorna-app.sh, che parte nello stesso minuto: due git fetch insieme si bloccano a vicenda (i "git fetch
# non riuscito" del 1/11). Si usa il suo stesso blocco (attesa massima 2 minuti, poi si riprova al giro dopo senza scrivere niente)
# e, per gli errori di rete veri, il fetch si riprova una seconda volta dopo 10 secondi.
exec 6>"$STATO/blocco-pubblicazione"
flock -w "${SCHIERAXI_ATTESA_BLOCCO:-120}" 6 || exit 0
if [ "${SCHIERAXI_SENZA_FETCH:-0}" != 1 ]; then
  # ogni fetch ha un tempo massimo: se la rete si pianta non si tiene il blocco condiviso per sempre
  TG="${SCHIERAXI_TIMEOUT_GIT:-120}"
  timeout -k 5 "$TG" git fetch -q origin main 2>/dev/null; rc=$?
  if [ "$rc" != 0 ]; then
    sleep "${SCHIERAXI_PAUSA_FETCH:-10}"
    timeout -k 5 "$TG" git fetch -q origin main 2>/dev/null; rc=$?
  fi
  [ "$rc" = 124 ] && { log "git fetch interrotto dopo ${TG}s (due volte): la rete e' bloccata"; exit 0; }
  [ "$rc" = 0 ] || { log "git fetch non riuscito due volte (rete?)"; exit 0; }
fi
albero=$(git rev-parse -q --verify "origin/main:sito") || { log "in origin/main non c'e' la cartella sito/"; exit 0; }
[ "$albero" = "$(cat "$STATO/ultimo-sito" 2>/dev/null)" ] && [ -e "$SITO" ] && exit 0

nuovo=$(mktemp -d "$STATO/sito.XXXXXX") || exit 1
trap 'rm -rf "$nuovo"' EXIT
git archive origin/main sito | tar -x -C "$nuovo" --strip-components=1 || { log "estrazione di sito/ non riuscita"; exit 1; }
exec 6>&-     # i file sono estratti: il clone non serve piu', aggiorna-app.sh puo' partire
[ -f "$nuovo/index.html" ] || { log "sito/ senza index.html: non pubblico"; exit 1; }
find "$nuovo" -name CNAME -delete
# Permessi: mktemp crea la cartella con 700 e tar rispetta l'umask di chi lancia lo script (cron: spesso 077). Senza questo passo la
# copia diventerebbe illeggibile per nginx (403). Cartelle 755, file 644, prima della copia e di nuovo dopo.
permessi() { find "$1" -path "$1/.git" -prune -o -type d -exec chmod 755 {} + ; find "$1" -path "$1/.git" -prune -o -type f -exec chmod 644 {} + ; }
permessi "$nuovo"

if [ -L "$SITO" ]; then
  cartella="$SITO-${albero:0:8}"
  rm -rf "$cartella" && mkdir -p "$cartella" && cp -a "$nuovo"/. "$cartella"/ || { log "copia non riuscita"; exit 1; }
  # file che non vengono da sito/ ma servono al server (per esempio .well-known) passano nella cartella nuova
  vecchia=$(readlink -f "$SITO")
  [ -d "$vecchia/.well-known" ] && [ ! -e "$cartella/.well-known" ] && cp -a "$vecchia/.well-known" "$cartella/"
  permessi "$cartella"
  ln -sfn "$cartella" "$SITO.nuovo" && mv -T "$SITO.nuovo" "$SITO" || { log "cambio del link non riuscito"; exit 1; }
  # le cartelle vecchie (tranne le ultime 3) si tolgono
  ls -1dt "$SITO"-???????? 2>/dev/null | tail -n +4 | while IFS= read -r v; do rm -rf -- "$v"; done
else
  mkdir -p "$SITO"
  cp -a "$nuovo"/. "$SITO"/ || { log "copia non riuscita"; exit 1; }
  # toglie i file che nel sito nuovo non ci sono piu' (senza toccare .git e .well-known)
  ( cd "$nuovo" && find . -type f | sort ) > "$STATO/sito-nuovo.lista"
  ( cd "$SITO" && find . \( -path ./.git -o -path ./.well-known \) -prune -o -type f -print | sort ) > "$STATO/sito-attuale.lista"
  comm -13 "$STATO/sito-nuovo.lista" "$STATO/sito-attuale.lista" | while IFS= read -r f; do rm -f -- "$SITO/$f"; done
  rm -f "$STATO/sito-nuovo.lista" "$STATO/sito-attuale.lista"
  chmod 755 "$SITO"; permessi "$SITO"
  # la vecchia copia git (il sito era un clone) esce dalla cartella servita al primo giro riuscito: nginx non deve poterla mostrare.
  # Resta in $STATO/sito-vecchio-git per tornare indietro: git --git-dir=<quella> --work-tree=<cartella del sito> checkout -f
  if [ -e "$SITO/.git" ]; then
    dove="$STATO/sito-vecchio-git"; [ -e "$dove" ] && dove="$dove.$(date +%s)"
    mv "$SITO/.git" "$dove" 2>/dev/null && log "vecchia copia .git tolta dalla cartella servita (ora in $dove)"
  fi
  # se il .git e' ancora li' non si segna il sito come pubblicato: si riprova al giro dopo
  if [ -e "$SITO/.git" ]; then
    log "ATTENZIONE: non riesco a togliere $SITO/.git dalla cartella servita: riprovo al prossimo giro (e bloccarlo in nginx)"
    exit 1
  fi
fi
echo "$albero" > "$STATO/ultimo-sito"
log "sito pubblicato (${albero:0:8})"
exit 0
