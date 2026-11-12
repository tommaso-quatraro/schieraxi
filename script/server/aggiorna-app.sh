#!/bin/bash
# aggiorna-app.sh - Sul server, ogni 10 minuti: se su GitHub (ramo main) c'e' una versione nuova di SchieraXI, la installa da sola.
# Cosa fa, in ordine:
#   1. scarica da GitHub (clone https pubblico, nessuna chiave) e confronta con l'ultima versione installata;
#   1b. controlla le FIRME: ogni commit nuovo di main (linea principale) deve avere la firma di una chiave fidata, quella del file
#      ~/.config/schieraxi/chiavi-firma.asc (fuori dal repository; oggi la chiave con cui GitHub firma le unioni delle PR e il commit
#      di versione del bot). Se una firma manca: non installa, segna "rifiutato" e manda un avviso. Se manca quel file NON installa
#      niente (riga nel log e un avviso la prima volta); per installare senza firme serve l'interruttore SCHIERAXI_SENZA_FIRME=1.
#      Il commit da installare e' la punta del ramo refs/remotes/origin/main, letta con git show-ref --verify (mai un tag con un nome
#      simile). Dettagli e casi limite in script/server/LEGGIMI.md;
#   2. se NON sono cambiate le cartelle del server (fanta, tests, script, requirements*) segna la versione come vista e si ferma:
#      le modifiche a ios/, sito/, docs/ non riavviano l'app e non mandano avvisi;
#   2b. installazioni raggruppate (#635): rimanda durante le partite e nell'ora prima di una scadenza, e se l'ultima installazione
#      riuscita e' di meno di un intervallo fa (predefinito 60 minuti, 0 = subito; SCHIERAXI_INTERVALLO_MINUTI o il file
#      ~/.config/schieraxi/intervallo-minuti). Subito le versioni segnate urgenti dal job rilascia (vedi «Rilasci raggruppati» sotto);
#   3. altrimenti salva una copia della versione attuale (per tornare indietro) e copia la nuova in ~/fantacalcio
#      (codice e script: mai lega/, dati/ e fanta/avatar_tratti.json, mai CLAUDE.md);
#   4. se cambia requirements.txt prepara un ambiente Python nuovo (solo versioni e hash di requirements.txt: pip --require-hashes)
#      e lo scambia con quello in uso solo se tutto e' andato; se pip non riesce resta tutto com'era e riprova ai giri dopo
#      (alla terza volta di fila rinuncia e avvisa); poi riavvia SOLO il servizio fantacalcio e controlla che risponda;
#   5. se non risponde torna alla versione di prima (codice e librerie), non riprova la stessa versione e manda un avviso sul telefono.
# Avvisi sul telefono solo quando qualcosa non va (versione rifiutata, librerie che non si installano, ritorno alla versione di prima,
# chiave delle firme mancante, GitHub che non risponde da tre giri, copia di GitHub o file della versione nuova che non si copiano:
# vedi guasto, al massimo uno al giorno per motivo): un'installazione riuscita resta solo nel registro dati/pubblicazione.log.
# Non parte mentre gira l'aggiornamento dei dati (stesso blocco di aggiorna.sh): ritenta al giro dopo.
# Mentre lavora tiene ~/.cache/fantacalcio/blocco-pubblicazione: lo usano anche pubblica-sito.sh (stesso clone) e promemoria.sh (salute).
# Opzione --prova: dice cosa farebbe e non scrive niente in ~/fantacalcio e in ~/.cache/fantacalcio (non copia, non riavvia).
# Opzione --fidati COMMIT: «questo commit di main l'ho controllato io»: da li' in poi ogni commit deve essere firmato (serve al primo
#   avvio, dopo il passaggio a un repository nuovo o dopo un rifiuto controllato a mano). Non installa: lo fa il giro dopo.
# Il clone ~/schieraxi-src segue il suo "origin", qualunque sia; se manca lo crea da SCHIERAXI_REPO
# (predefinito: https://github.com/tommaso-quatraro/schieraxi.git).
# SCHIERAXI_ISTANZA: vuota (o assente) = la produzione, come sempre. "prova" = l'ambiente di prova (script/server/prova/LEGGIMI.md),
#   che gira con il SUO utente (schieraxi-prova) e la sua casa: cartella ~/app, stato ~/.cache/schieraxi-prova, clone ~/schieraxi-src e
#   blocco suoi, chiave delle firme /etc/schieraxi-prova/chiavi-firma.asc (di root), servizio schieraxi-prova, porta 8001, nessuna
#   attesa della fine delle partite, nessun avviso. Nella casa della produzione (dove c'e' ~/fantacalcio) la prova non parte.
#   Ogni altro valore: esce con 2 senza fare niente.
# Opzione --configurazione: stampa cartella, stato, servizio, porta, attesa delle partite, clone, blocco e chiave dell'istanza ed esce
#   (non scrive niente).
#   Dal crontab dell'utente del server:  */10 * * * * /bin/bash $HOME/fantacalcio/script/server/aggiorna-app.sh >/dev/null 2>&1
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): senza questo Python legge male gli accenti passati dallo script
export GIT_TERMINAL_PROMPT=0     # mai domande di password: il repository e' pubblico
PROVA=0
FIDATI=""
CONFIGURAZIONE=0
case "${1:-}" in
  --prova) PROVA=1 ;;
  --fidati) FIDATI="${2:-}"; [ -n "$FIDATI" ] || { echo "uso: $0 --fidati COMMIT (di solito: origin/main dopo averlo controllato)"; exit 2; } ;;
  --configurazione) CONFIGURAZIONE=1 ;;
esac
INIZIO=$(date +%s)     # l'ora d'inizio del giro, in secondi: conta per l'intervallo fra due installazioni (#635)
SRC="${SCHIERAXI_SRC:-$HOME/schieraxi-src}"     # cartella della copia di GitHub (per le prove si puo cambiare)
ISTANZA="${SCHIERAXI_ISTANZA:-}"
case "$ISTANZA" in
  "")    DEST="$HOME/fantacalcio"; STATO="$HOME/.cache/fantacalcio";    SERVIZIO=fantacalcio;     PORTA=8000; ATTENDE_PARTITE=1
         CHIAVI_DI_SOLITO="$HOME/.config/schieraxi/chiavi-firma.asc" ;;
  prova) DEST="$HOME/app";         STATO="$HOME/.cache/schieraxi-prova"; SERVIZIO=schieraxi-prova; PORTA=8001; ATTENDE_PARTITE=0
         CHIAVI_DI_SOLITO=/etc/schieraxi-prova/chiavi-firma.asc     # di root: nella sua casa la prova la potrebbe cambiare
         if [ -e "$HOME/fantacalcio" ]; then      # qui userebbe il clone della produzione con un altro blocco
           echo "Questa e' la casa della produzione: l'ambiente di prova gira con il suo utente, schieraxi-prova. Non faccio niente." >&2
           exit 2
         fi ;;
  *) echo "SCHIERAXI_ISTANZA sconosciuta: vuota per la produzione oppure prova (script/server/prova/LEGGIMI.md). Non faccio niente." >&2
     exit 2 ;;
esac
# Il blocco della pubblicazione va con il clone: chi usa lo stesso clone usa lo stesso blocco (un solo git fetch e una sola verifica
# delle firme, che lavora in .git/verifica-firme, alla volta). Produzione: ~/.cache/fantacalcio/blocco-pubblicazione, lo stesso di
# pubblica-sito.sh, promemoria.sh e sentinella.sh. La prova ha la sua casa, quindi clone suo e blocco suo: niente in comune.
BLOCCO="$STATO/blocco-pubblicazione"
CHIAVI="${SCHIERAXI_CHIAVI:-$CHIAVI_DI_SOLITO}"     # chiavi fidate per le firme: FUORI dal repository (e, per la prova, fuori dalla sua casa)
# Intervallo minimo fra due installazioni riuscite, in minuti (#635): variabile SCHIERAXI_INTERVALLO_MINUTI, altrimenti il file
# ~/.config/schieraxi/intervallo-minuti (un numero), altrimenti 60. Da 0 (ogni versione subito, come prima) a 1440: un altro valore
# vale 60 e lo si dice nel registro. L'ambiente di prova installa sempre subito: serve al collaudo automatico.
if [ "$ISTANZA" = prova ]; then
  INTERVALLO=0; DA_DOVE="ambiente di prova: ogni versione subito"
else
  FILE_INTERVALLO="$HOME/.config/schieraxi/intervallo-minuti"
  if [ -n "${SCHIERAXI_INTERVALLO_MINUTI:-}" ]; then INTERVALLO=$SCHIERAXI_INTERVALLO_MINUTI; DA_DOVE=SCHIERAXI_INTERVALLO_MINUTI
  elif [ -f "$FILE_INTERVALLO" ]; then INTERVALLO=$(tr -d ' \r\n' < "$FILE_INTERVALLO" 2>/dev/null); DA_DOVE=$FILE_INTERVALLO
  else INTERVALLO=60; DA_DOVE=predefinito; fi
  if [[ $INTERVALLO =~ ^[0-9]{1,4}$ ]] && [ $(( 10#$INTERVALLO )) -le 1440 ]; then
    INTERVALLO=$(( 10#$INTERVALLO ))
  else
    DA_DOVE="valore non valido in $DA_DOVE: '${INTERVALLO:0:20}', vale il predefinito"; INTERVALLO=60
  fi
fi
RIGA_URGENTE="Rilascio: urgente"     # la scrive il job rilascia nel commit di versione (script/ci/assegna_versione.py, RIGA_URGENTE)
if [ "$CONFIGURAZIONE" = 1 ]; then
  printf 'DEST=%s\nSTATO=%s\nSERVIZIO=%s\nPORTA=%s\nATTENDE_PARTITE=%s\nSRC=%s\nBLOCCO=%s\nCHIAVI=%s\n' \
    "$DEST" "$STATO" "$SERVIZIO" "$PORTA" "$ATTENDE_PARTITE" "$SRC" "$BLOCCO" "$CHIAVI"
  exit 0
fi
if [ "$ISTANZA" = prova ]; then
  if [ ! -x "$DEST/.venv/bin/python" ]; then
    echo "ambiente di prova non preparato ($DEST/.venv/bin/python manca): prima script/server/prova/prepara-prova.sh" >&2
    exit 0
  fi
fi
QUI=$(cd "$(dirname "$0")" && pwd)     # la cartella di questo script (prima di ogni cd)
. "$QUI/registri.sh" || exit 1
LOG="$DEST/dati/pubblicazione.log"
# la cartella dati la scrive anche il servizio (produzione o prova): un collegamento simbolico al posto del log farebbe scrivere
# questo script (che gira fuori dal recinto del servizio) da un'altra parte, per esempio sul codice. Non scrive e non installa niente.
avvisa() {   # titolo, testo, priorita (usa il canale delle notifiche dell'app: web o ntfy); esce con 0 solo se l'avviso e' partito
  [ "$ISTANZA" = prova ] && return 0     # la prova non avvisa: gli avvisi vanno al canale della produzione (se resta indietro, lo vede il collaudo)
  ( cd "$DEST" && nice -n 10 .venv/bin/python -c "
import sys
from fanta import notifiche
sys.exit(0 if notifiche.invia(sys.argv[1], sys.argv[2], int(sys.argv[3]), 'package') else 1)" "$1" "$2" "$3" ) >/dev/null 2>&1
}
# Fermo per un collegamento: oltre al journal (registri.sh) un avviso sul telefono, una volta sola finche' il collegamento resta.
# Il segno sta in ~/.cache come gli altri stati e si crea con noclobber (mai attraverso un collegamento gia' presente).
SEGNO_COLLEGAMENTO="$STATO/avvisato-collegamento"
if ! registri_sicuri "$LOG" "$LOG.tmp"; then
  if [ "$PROVA" = 0 ] && [ -z "$ISTANZA" ] && mkdir -p "$STATO" && [ ! -L "$SEGNO_COLLEGAMENTO" ] && [ ! -e "$SEGNO_COLLEGAMENTO" ] \
     && ( set -C; : > "$SEGNO_COLLEGAMENTO" ) 2>/dev/null; then
    avvisa "SchieraXI: aggiornamento fermo" "Nella cartella dei dati c'e' un collegamento al posto del registro degli aggiornamenti: l'app non si aggiorna finche' non lo togli." 4
  fi
  exit 1
fi
[ "$PROVA" = 1 ] || rm -f "$SEGNO_COLLEGAMENTO"
ERR="$LOG"; [ "${1:-}" = "--prova" ] && ERR=/dev/null
REPO="${SCHIERAXI_REPO:-https://github.com/tommaso-quatraro/schieraxi.git}"
CARTELLE="fanta tests script requirements.txt requirements-dev.txt"     # le sole cose che finiscono sul server
. "$QUI/verifica-firme.sh"

if [ "$PROVA" = 0 ]; then
  mkdir -p "$STATO" "$DEST/dati"
  # blocco-pubblicazione e' condiviso: pubblica-sito.sh lo prende per il suo git fetch sullo stesso clone e promemoria.sh (controllo di
  # salute) lo aspetta, cosi' non vede l'app "spenta" mentre questo script la riavvia. Si aspetta al massimo un minuto chi lo tiene.
  exec 7>>"$BLOCCO"
  flock -w "${SCHIERAXI_ATTESA_BLOCCO:-60}" 7 || { [ -n "$FIDATI" ] && echo "c'e' un aggiornamento in corso: riprova fra un minuto"; exit 0; }
  exec 9>>"$STATO/blocco"
  flock -n 9 || { [ -n "$FIDATI" ] && echo "c'e' un aggiornamento in corso: riprova fra un minuto"; exit 0; }
  (umask 077; : >> "$LOG"); chmod 600 "$LOG"     # il log di pubblicazione lo legge solo l'utente del server
fi

log() {
  if [ "$PROVA" = 1 ]; then echo "[prova] $*"; else echo "$(date '+%F %T') $*" >> "$LOG"; fi
  [ -n "$FIDATI" ] && echo "$*"
  return 0
}
fine() { [ "$PROVA" = 1 ] && return 0; ruota_registro "$LOG" 300 2>/dev/null; }

# Guasti che fermano gli aggiornamenti senza un avviso loro (rete, copia di GitHub, versione senza le cartelle, file della versione
# nuova, ambienti Python): oltre alla riga nel registro, un avviso con il motivo, al massimo uno al giorno per motivo (meno un'ora di
# tolleranza), e «di nuovo a posto» quando passa, solo se era stato segnalato (#607). Stato in $STATO/guasto-<motivo>: «volte di fila,
# ora dell'ultimo avviso in secondi»; l'ora si segna e il file si toglie solo se l'avviso e' partito. La rete si segnala alla terza
# volta di fila: un fetch andato male una volta non e' un guasto.
GIORNO=86400
TOLLERANZA=3600
guasto() {   # motivo, testo dell'avviso, volte di fila prima dell'avviso (di solito 1)
  [ "$PROVA" = 1 ] && return 0
  local f="$STATO/guasto-$1" n=0 ultimo=0 resto adesso
  { mkdir -p "$STATO" && [ ! -L "$f" ]; } || return 0
  if [ -f "$f" ]; then read -r n ultimo resto < "$f"; fi
  [[ $n =~ ^[0-9]{1,9}$ ]] || n=0
  [[ $ultimo =~ ^[0-9]{1,12}$ ]] || ultimo=0
  n=$(( n + 1 )); adesso=$(date +%s)
  if [ "$n" -ge "${3:-1}" ] && [ $(( adesso - ultimo )) -ge $(( GIORNO - TOLLERANZA )) ] \
     && avvisa "SchieraXI: aggiornamento non riuscito" "$2 Dettagli in dati/pubblicazione.log." 4; then
    ultimo=$adesso
  fi
  echo "$n $ultimo" > "$f"
}
risolto() {   # motivi tornati a posto
  [ "$PROVA" = 1 ] && return 0
  local m f n ultimo resto segnalati=""
  local -a file=()
  for m in "$@"; do
    f="$STATO/guasto-$m"
    { [ -f "$f" ] && [ ! -L "$f" ]; } || continue
    n=0; ultimo=0; read -r n ultimo resto < "$f"
    file+=("$f")
    if [[ $ultimo =~ ^[1-9][0-9]*$ ]]; then segnalati="${segnalati:+$segnalati, }$m"; fi
  done
  [ ${#file[@]} -gt 0 ] || return 0
  if [ -n "$segnalati" ]; then
    log "di nuovo a posto: $segnalati"
    avvisa "SchieraXI: aggiornamenti di nuovo a posto" "Gli aggiornamenti automatici funzionano di nuovo." 3 || return 0
  fi
  rm -f -- "${file[@]}"
}
TESTO_RETE="Da tre giri di fila non riesco a scaricare da GitHub (rete?): le versioni nuove non arrivano."

if [ ! -d "$SRC/.git" ]; then
  if [ "$PROVA" = 1 ]; then log "manca la copia di GitHub in $SRC: la creerei da $REPO"; exit 0; fi
  timeout -k 5 "${SCHIERAXI_TIMEOUT_GIT:-120}" git clone -q "$REPO" "$SRC" 2>>"$ERR"; rc=$?
  [ "$rc" = 124 ] && { log "git clone interrotto dopo ${SCHIERAXI_TIMEOUT_GIT:-120}s: la rete e' bloccata, riprovo al prossimo giro"; guasto rete "$TESTO_RETE" 3; fine; exit 1; }
  [ "$rc" = 0 ] || { log "clone da GitHub non riuscito (rete?)"; guasto rete "$TESTO_RETE" 3; fine; exit 1; }
fi
cd "$SRC" || { log "manca la copia di GitHub in $SRC"; guasto copia-github "Manca la copia di GitHub sul server: le versioni nuove non arrivano."; exit 1; }
timeout -k 5 "${SCHIERAXI_TIMEOUT_GIT:-120}" git fetch -q origin main 2>>"$ERR"; rc=$?
[ "$rc" = 124 ] && { log "git fetch interrotto dopo ${SCHIERAXI_TIMEOUT_GIT:-120}s: la rete e' bloccata, riprovo al prossimo giro"; guasto rete "$TESTO_RETE" 3; fine; exit 0; }
[ "$rc" = 0 ] || { log "git fetch non riuscito (rete?)"; guasto rete "$TESTO_RETE" 3; fine; exit 0; }
# Il ramo con il nome intero, letto con show-ref --verify che non cerca altri nomi: con rev-parse (anche col nome intero, se il ramo
# manca) git proverebbe altri posti e un tag con lo stesso nome prenderebbe il suo posto
nuovo=$(git show-ref --verify -s refs/remotes/origin/main 2>/dev/null) && nuovo=$(git rev-parse -q --verify "$nuovo^{commit}") \
  || { log "il ramo origin/main non esiste nel clone $SRC: non installo"
       guasto copia-github "Nella copia di GitHub sul server manca il ramo main: le versioni nuove non arrivano."; fine; exit 1; }
risolto rete copia-github          # GitHub risponde e il ramo c'e'
if [ -n "$FIDATI" ]; then
  quale="$FIDATI"; [ "$FIDATI" = origin/main ] && quale="$nuovo"     # "--fidati origin/main" vuol dire il ramo, anche qui
  fidato=$(git rev-parse -q --verify "$quale^{commit}") && git merge-base --is-ancestor "$fidato" "$nuovo" \
    || { log "--fidati: '$FIDATI' non e' un commit di origin/main"; fine; exit 1; }
  echo "$fidato" > "$STATO/verificato"
  rm -f "$STATO/rifiutato"
  log "fidato a mano ${fidato:0:7}: da qui in poi ogni commit nuovo di main deve essere firmato; l'installazione la fa il prossimo giro"
  fine; exit 0
fi
# L'intervallo in uso nel registro: al primo giro e quando cambia (stato in intervallo-letto)
DESCRIZIONE_INTERVALLO="intervallo fra due installazioni: $INTERVALLO minuti ($DA_DOVE)"
if [ "$PROVA" = 1 ]; then
  log "$DESCRIZIONE_INTERVALLO"
elif [ "$(cat "$STATO/intervallo-letto" 2>/dev/null)" != "$DESCRIZIONE_INTERVALLO" ]; then
  log "$DESCRIZIONE_INTERVALLO"
  echo "$DESCRIZIONE_INTERVALLO" > "$STATO/intervallo-letto"
fi
ultimo=$(cat "$STATO/ultimo-rilascio" 2>/dev/null)
if [ "$nuovo" = "$ultimo" ] || [ "$nuovo" = "$(cat "$STATO/rifiutato" 2>/dev/null)" ]; then
  [ "$PROVA" = 1 ] && log "niente di nuovo: ${nuovo:0:7} e' gia' visto"
  exit 0
fi
# Firme: dall'ultimo commit verificato (o, la prima volta, dall'ultimo installato) fino a quello nuovo, tutti firmati da una chiave fidata
if [ -s "$CHIAVI" ]; then
  base=$(cat "$STATO/verificato" 2>/dev/null)
  [ -n "$base" ] || base="$ultimo"
  if ! verifica_catena "$base" "$nuovo" "$CHIAVI"; then
    log "versione ${nuovo:0:7} NON installata: $MOTIVO_FIRMA"
    if [ "$PROVA" = 0 ]; then
      echo "$nuovo" > "$STATO/rifiutato"
      avvisa "SchieraXI: aggiornamento bloccato" "Su GitHub c'è una versione senza la firma attesa: non l'ho installata. Motivo in dati/pubblicazione.log." 4
    fi
    fine; exit 1
  fi
  if [ "$PROVA" = 1 ]; then log "firme a posto da ${base:0:7} a ${nuovo:0:7}"; else echo "$nuovo" > "$STATO/verificato"; fi
  [ "$PROVA" = 1 ] || rm -f "$STATO/senza-chiave"
elif [ "${SCHIERAXI_SENZA_FIRME:-0}" = 1 ]; then
  log "verifica delle firme SPENTA a mano (SCHIERAXI_SENZA_FIRME=1): installo ${nuovo:0:7} senza controllare le firme"
else
  # Senza chiave fidata non si installa niente (un file sparito non deve spegnere la verifica). Una riga nel log e un avviso solo la
  # prima volta per versione (stato in senza-chiave); niente "rifiutato": appena la chiave torna, la stessa versione si installa.
  if [ "$PROVA" = 1 ] || [ "$(cat "$STATO/senza-chiave" 2>/dev/null)" != "$nuovo" ]; then
    log "versione ${nuovo:0:7} NON installata: manca la chiave fidata $CHIAVI (vedi script/server/LEGGIMI.md; per installare senza firme: SCHIERAXI_SENZA_FIRME=1)"
  fi
  if [ "$PROVA" = 0 ]; then
    [ -e "$STATO/senza-chiave" ] || avvisa "SchieraXI: aggiornamenti fermi" "Manca la chiave per controllare le firme: non installo le versioni nuove. Dettagli in dati/pubblicazione.log." 4
    echo "$nuovo" > "$STATO/senza-chiave"
  fi
  fine; exit 1
fi
# Le cartelle del server devono esserci tutte nella versione nuova: se manca qualcosa non si installa niente
# (e quella versione non si riprova a ogni giro; la prossima, con un altro numero, si).
mancanti=""
for c in $CARTELLE; do git cat-file -e "$nuovo:$c" 2>/dev/null || mancanti="$mancanti $c"; done
if [ -n "$mancanti" ]; then
  log "la versione ${nuovo:0:7} non contiene:$mancanti : non installo"
  [ "$PROVA" = 1 ] || echo "$nuovo" > "$STATO/rifiutato"
  guasto cartelle "Su GitHub c'è una versione senza tutte le cartelle del server: non l'ho installata."
  fine; exit 1
fi

# Cambiato qualcosa che riguarda il server? Se l'ultima versione installata non esiste nel clone (storia diversa) conta come "cambiato".
cambiato=1
if [ -n "$ultimo" ] && git cat-file -e "$ultimo^{commit}" 2>/dev/null; then
  # shellcheck disable=SC2086
  git diff --quiet "$ultimo" "$nuovo" -- $CARTELLE && cambiato=0
fi
if [ "$cambiato" = 0 ]; then
  log "versione ${nuovo:0:7}: cambiano solo cose che non riguardano il server (ios, sito, docs...): non installo"
  [ "$PROVA" = 1 ] || echo "$nuovo" > "$STATO/ultimo-rilascio"
  fine; exit 0
fi

# Mai durante una partita di Serie A ne' nell'ora prima della scadenza della formazione di una lega: il riavvio interromperebbe i
# risultati in diretta e i giri delle probabili. Decide la versione installata (python -m fanta momento-libero, fanta/libero.py):
# 3 = occupato (si rimanda al primo giro libero, una riga nel log per versione); qualunque altro esito (0, comando che non c'e'
# ancora, errore, tempo scaduto) = si installa: un controllo guasto non deve fermare gli aggiornamenti.
# Emergenza: SCHIERAXI_INSTALLA_SUBITO=1 oppure il file ~/.cache/fantacalcio/installa-subito (si cancella da solo dopo l'uso).
# L'ambiente di prova non aspetta (ATTENDE_PARTITE=0): nessun utente vero lo usa e deve avere ogni versione prima della produzione.
forzata=0
if [ "$ATTENDE_PARTITE" = 0 ]; then
  :
elif [ "${SCHIERAXI_INSTALLA_SUBITO:-0}" = 1 ] || [ -e "$STATO/installa-subito" ]; then
  log "installazione forzata di ${nuovo:0:7}: non controllo partite, scadenze e intervallo fra due installazioni"
  forzata=1
  [ "$PROVA" = 1 ] || rm -f "$STATO/installa-subito" "$STATO/rimandata"
else
  motivo=$(cd "$DEST" && . "$QUI/leggi-ambiente.sh" && leggi_ambiente dati/ambiente.env &&
           timeout -k 5 "${SCHIERAXI_TIMEOUT_LIBERO:-60}" nice -n 10 .venv/bin/python -m fanta momento-libero 2>>"$ERR")
  rc=$?
  if [ "$rc" = 3 ]; then
    if [ "$PROVA" = 1 ]; then
      log "rimanderei ${nuovo:0:7}: $motivo"
    elif [ "$(cat "$STATO/rimandata" 2>/dev/null)" != "$nuovo" ]; then
      log "rimandata: partite in corso ($motivo); installo ${nuovo:0:7} al primo giro libero"
      echo "$nuovo" > "$STATO/rimandata"
    fi
    fine; exit 0
  fi
  if [ "$PROVA" = 0 ] && [ -e "$STATO/rimandata" ]; then
    log "fine del rimando: momento libero"
    rm -f "$STATO/rimandata"
  fi
fi

# Rilasci raggruppati (#635): fra due installazioni riuscite almeno INTERVALLO minuti. Prima si rimanda (una riga nel registro per
# versione, stato in raggruppata); alla scadenza si installa l'ultima versione di main, in un colpo solo. Conta l'inizio del giro
# dell'ultima installazione riuscita (ultima-installazione, in secondi): un'installazione non riuscita non lo cambia. Un minuto di
# margine: i giri del cron non partono tutti allo stesso secondo. Si somma al rimando per le partite qui sopra. Subito, senza aspettare:
# - una versione urgente: fra i commit nuovi (dall'ultimo installato, linea principale) c'e' la riga intera «Rilascio: urgente», che
#   il job rilascia mette nel commit di versione quando una PR ha l'etichetta P1 o urgente. Si legge qui, dopo la verifica delle firme;
# - l'installazione forzata (qui sopra) e l'ambiente di prova (INTERVALLO 0);
# - nessuna installazione registrata (la prima volta) o l'orologio del server indietro rispetto all'ultima (non si aspetta per sempre).
aspetta=0
ultima_installazione=$(cat "$STATO/ultima-installazione" 2>/dev/null)
if [ "$INTERVALLO" -gt 0 ] && [ "$forzata" = 0 ] && [[ $ultima_installazione =~ ^[0-9]{1,12}$ ]] && [[ $INIZIO =~ ^[0-9]{1,12}$ ]]; then
  trascorsi=$(( INIZIO - ultima_installazione ))
  if [ "$trascorsi" -lt 0 ]; then
    log "l'orologio del server e' indietro rispetto all'ultima installazione: non aspetto l'intervallo"
  elif [ "$trascorsi" -lt $(( INTERVALLO * 60 - 60 )) ]; then
    aspetta=1
  fi
fi
if [ "$aspetta" = 1 ] && [ -n "$ultimo" ] && git cat-file -e "$ultimo^{commit}" 2>/dev/null \
   && git log --first-parent --format=%B "$ultimo..$nuovo" | tr -d '\r' | grep -qxF "$RIGA_URGENTE"; then
  log "versione urgente fra i commit nuovi: installo ${nuovo:0:7} subito, senza aspettare l'intervallo"
  aspetta=0
fi
if [ "$aspetta" = 1 ]; then
  if [ "$PROVA" = 1 ]; then
    log "rimanderei ${nuovo:0:7}: installazioni raggruppate, l'ultima $(( trascorsi / 60 )) minuti fa (intervallo $INTERVALLO minuti)"
  elif [ "$(cat "$STATO/raggruppata" 2>/dev/null)" != "$nuovo" ]; then
    log "raggruppata: ultima installazione $(( trascorsi / 60 )) minuti fa, intervallo $INTERVALLO minuti; installo ${nuovo:0:7} (o la versione piu' nuova di allora) fra circa $(( INTERVALLO - trascorsi / 60 )) minuti"
    echo "$nuovo" > "$STATO/raggruppata"
  fi
  fine; exit 0
fi
if [ "$PROVA" = 0 ] && [ -e "$STATO/raggruppata" ]; then
  log "fine del raggruppamento"
  rm -f "$STATO/raggruppata"
fi

if [ "$PROVA" = 1 ]; then
  log "installerei ${nuovo:0:7}; file cambiati rispetto a '${ultimo:0:7}':"
  if [ -n "$ultimo" ] && git cat-file -e "$ultimo^{commit}" 2>/dev/null; then
    # shellcheck disable=SC2086
    git diff --name-only "$ultimo" "$nuovo" -- $CARTELLE | head -n 30
  else
    echo "[prova] (versione di prima sconosciuta: conta come tutto cambiato)"
  fi
  exit 0
fi

log "versione nuova ${nuovo:0:7}: la installo"
copia="$STATO/versione-precedente.tar.gz"
# shellcheck disable=SC2086
tar czf "$copia" -C "$DEST" $CARTELLE 2>/dev/null
vecchi_req=$(md5sum "$DEST/requirements.txt" 2>/dev/null | cut -d' ' -f1)

prova=$(mktemp -d)
# shellcheck disable=SC2086
if ! git archive "$nuovo" $CARTELLE | tar -x -C "$prova"; then
  log "copia dei file non riuscita"; rm -rf "$prova"
  guasto copia-file "Non riesco a copiare i file della versione nuova (disco pieno?): resta quella di prima."; fine; exit 1
fi
# Il file dei tratti dei volti vive solo sul server: se c'e' gia', resta quello (anche se il repository non lo ha piu')
if [ -f "$DEST/fanta/avatar_tratti.json" ]; then
  cp -p "$DEST/fanta/avatar_tratti.json" "$prova/fanta/avatar_tratti.json"
fi
for d in fanta tests script; do
  rm -rf "$DEST/$d.nuovo" && mv "$prova/$d" "$DEST/$d.nuovo" && rm -rf "$DEST/$d" && mv "$DEST/$d.nuovo" "$DEST/$d"
done
cp "$prova"/requirements*.txt "$DEST"/
rm -rf "$prova"
find "$DEST/script" -name '*.sh' -exec sed -i 's/\r$//' {} +

# Librerie cambiate: un ambiente Python NUOVO accanto a quello in uso (.venv.nuova), con le sole versioni e hash di requirements.txt.
# Si scambiano le cartelle solo se l'installazione e' riuscita tutta: l'ambiente in uso non resta mai a meta'. Quello di prima resta
# in .venv.precedente (per tornare indietro). Funziona perche' servizio e script usano solo .venv/bin/python (mai i comandi di bin/).
venv_cambiata=0
if [ "$vecchi_req" != "$(md5sum "$DEST/requirements.txt" | cut -d' ' -f1)" ]; then
  log "librerie cambiate: preparo un ambiente Python nuovo con le versioni e gli hash di requirements.txt"
  python_base=$(readlink -f "$DEST/.venv/bin/python")
  rm -rf "$DEST/.venv.nuova"
  if "$python_base" -m venv "$DEST/.venv.nuova" >> "$LOG" 2>&1 \
     && "$DEST/.venv.nuova/bin/python" -m pip install -q --require-hashes -r "$DEST/requirements.txt" >> "$LOG" 2>&1; then
    rm -f "$STATO/librerie-fallite"
    rm -rf "$DEST/.venv.precedente"
    mv "$DEST/.venv" "$DEST/.venv.precedente" && mv "$DEST/.venv.nuova" "$DEST/.venv" && venv_cambiata=1
    [ "$venv_cambiata" = 1 ] || { log "scambio degli ambienti Python non riuscito: controlla $DEST/.venv"
                                  guasto ambienti "Non riesco a scambiare gli ambienti Python della versione nuova: va controllato il server."
                                  fine; exit 1; }
  else
    # il servizio non e' stato riavviato e il suo ambiente non e' stato toccato: si rimettono solo i file della versione di prima
    rm -rf "$DEST/.venv.nuova"
    tar xzf "$copia" -C "$DEST"
    # un errore passeggero (rete, PyPI) non deve bloccare la versione per sempre: si riprova ai giri dopo, si rinuncia alla terza volta
    tentativi=1
    if [ "$(cut -d' ' -f1 "$STATO/librerie-fallite" 2>/dev/null)" = "$nuovo" ]; then
      tentativi=$(( $(cut -d' ' -f2 "$STATO/librerie-fallite") + 1 ))
    fi
    echo "$nuovo $tentativi" > "$STATO/librerie-fallite"
    if [ "$tentativi" -ge "${SCHIERAXI_TENTATIVI_LIBRERIE:-3}" ]; then
      log "librerie NON installate per la ${tentativi}a volta di fila: rinuncio a ${nuovo:0:7} (resta la versione di prima)"
      echo "$nuovo" > "$STATO/rifiutato"
      rm -f "$STATO/librerie-fallite"
      avvisa "SchieraXI: aggiornamento annullato" "Le librerie della versione nuova non si installano (provato $tentativi volte): resta quella di prima. Dettagli in dati/pubblicazione.log." 4
    else
      log "librerie NON installate (rete, PyPI, hash diverso?): resta la versione di prima, riprovo al prossimo giro (tentativo $tentativi)"
      [ "$tentativi" = 1 ] && avvisa "SchieraXI: aggiornamento rimandato" "Le librerie della versione nuova non si sono installate: riprovo fra 10 minuti." 3
    fi
    fine; exit 1
  fi
fi

sudo systemctl restart "$SERVIZIO"
risponde=0
for i in $(seq 1 "${SCHIERAXI_ATTESE_AVVIO:-25}"); do
  # 200 con un solo utente; 401 con gli account accesi: in entrambi i casi il servizio risponde
  codice=$(curl -s -m 5 -o /dev/null -w '%{http_code}' -H "X-Fanta: 1" "http://127.0.0.1:$PORTA/api/account/me")
  if [ "$codice" = 200 ] || [ "$codice" = 401 ]; then risponde=1; break; fi
  sleep 1
done

if [ "$risponde" = 1 ]; then
  echo "$nuovo" > "$STATO/ultimo-rilascio"
  echo "$INIZIO" > "$STATO/ultima-installazione"     # da qui parte l'intervallo fra due installazioni (#635)
  versione=$(cd "$DEST" && .venv/bin/python -c "import json; print(json.load(open('fanta/novita.json', encoding='utf-8'))[0]['versione'])" 2>/dev/null)
  # solo la riga nel registro, niente avviso: con tante versioni al giorno gli avvisi veri (fallita, rifiutata, tornata indietro) si
  # perdevano tra quelli di routine (#607)
  log "installata ${nuovo:0:7} (versione $versione): il servizio risponde"
  risolto cartelle copia-file ambienti           # «di nuovo a posto» se un guasto dell'installazione era stato segnalato
else
  log "il servizio NON risponde con ${nuovo:0:7} (ultimo codice HTTP: ${codice:-nessuno}): torno alla versione di prima"
  tar xzf "$copia" -C "$DEST"
  if [ "$venv_cambiata" = 1 ]; then          # anche le librerie di prima
    rm -rf "$DEST/.venv.scartata"
    mv "$DEST/.venv" "$DEST/.venv.scartata" && mv "$DEST/.venv.precedente" "$DEST/.venv" && rm -rf "$DEST/.venv.scartata"
  fi
  sudo systemctl restart "$SERVIZIO"
  echo "$nuovo" > "$STATO/rifiutato"
  sleep "${SCHIERAXI_PAUSA_DOPO_RITORNO:-5}"
  avvisa "SchieraXI: aggiornamento annullato" "La versione nuova non partiva: sono tornato a quella di prima. Dettagli in dati/pubblicazione.log." 4
fi
fine
exit 0
