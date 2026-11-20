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
#   3. altrimenti salva una copia della versione attuale (per tornare indietro); se cambia requirements.txt prepara PRIMA un ambiente
#      Python nuovo (solo versioni e hash di requirements.txt: pip --require-hashes; se pip non riesce non tocca niente e riprova ai giri
#      dopo, alla terza volta di fila rinuncia e avvisa) (#826);
#   4. copia la versione nuova in ~/fantacalcio (codice e script: mai lega/, dati/ e fanta/avatar_tratti.json, mai CLAUDE.md), scambia
#      l'ambiente Python, riavvia SOLO il servizio fantacalcio (sudo -n, processo cambiato: #826) e controlla che risponda e che il
#      database degli account si apra alla versione attesa (#825);
#   5. se non va torna alla versione di prima (codice e librerie), non riprova la stessa versione e manda un avviso sul telefono;
#      ma se intanto il database degli account e' salito di versione tiene la nuova e avvisa (il codice di prima non lo leggerebbe).
# Avvisi sul telefono solo quando qualcosa non va (versione rifiutata, librerie che non si installano, ritorno alla versione di prima,
# chiave delle firme mancante, GitHub che non risponde da tre giri, copia di GitHub o file della versione nuova che non si copiano:
# vedi guasto, al massimo uno al giorno per motivo): un'installazione riuscita resta solo nel registro dati/pubblicazione.log.
# Gli avvisi partono anche nelle ore tranquille; se non partono, una riga nel registro e si riprovano (#826, avvisa_o_riprova).
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
# Gli avvisi dell'installazione ignorano le ore tranquille (#826): dicono che gli aggiornamenti sono fermi o tornati indietro.
avvisa() {   # titolo, testo, priorita (usa il canale delle notifiche dell'app: web o ntfy); esce con 0 solo se l'avviso e' partito
  [ "$ISTANZA" = prova ] && return 0     # la prova non avvisa: gli avvisi vanno al canale della produzione (se resta indietro, lo vede il collaudo)
  ( cd "$DEST" && nice -n 10 .venv/bin/python -c "
import sys
from fanta import notifiche
sys.exit(0 if notifiche.invia(sys.argv[1], sys.argv[2], int(sys.argv[3]), 'package', ignora_silenzio=True) else 1)" "$1" "$2" "$3" ) >/dev/null 2>&1
}
# Fermo per un collegamento: oltre al journal (registri.sh) un avviso sul telefono, una volta sola finche' il collegamento resta.
# Il segno sta in ~/.cache come gli altri stati e si crea con noclobber (mai attraverso un collegamento gia' presente).
SEGNO_COLLEGAMENTO="$STATO/avvisato-collegamento"
if ! registri_sicuri "$LOG" "$LOG.tmp"; then
  if [ "$PROVA" = 0 ] && [ -z "$ISTANZA" ] && mkdir -p "$STATO" && [ ! -L "$SEGNO_COLLEGAMENTO" ] && [ ! -e "$SEGNO_COLLEGAMENTO" ] \
     && ( set -C; : > "$SEGNO_COLLEGAMENTO" ) 2>/dev/null; then
    avvisa "SchieraXI: aggiornamento fermo" "Nella cartella dei dati c'e' un collegamento al posto del registro degli aggiornamenti: l'app non si aggiorna finche' non lo togli." 4 \
      || rm -f "$SEGNO_COLLEGAMENTO"     # non partito (#826): il giro dopo riprova
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
  if [ "$n" -ge "${3:-1}" ] && [ $(( adesso - ultimo )) -ge $(( GIORNO - TOLLERANZA )) ]; then
    if avvisa "SchieraXI: aggiornamento non riuscito" "$2 Dettagli in dati/pubblicazione.log." 4; then ultimo=$adesso
    else log "avviso non partito (guasto $1): riprovo al prossimo giro"; fi
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
    avvisa "SchieraXI: aggiornamenti di nuovo a posto" "Gli aggiornamenti automatici funzionano di nuovo." 3 \
      || { log "avviso «di nuovo a posto» non partito: riprovo"; return 0; }
  fi
  rm -f -- "${file[@]}"
}
TESTO_RETE="Da tre giri di fila non riesco a scaricare da GitHub (rete?): le versioni nuove non arrivano."

# Avvisi che si mandano una volta sola (versione rifiutata, ritorno indietro...): lo stato e' gia' scritto, quindi il giro dopo non
# ripasserebbe di qui (#826). Se non partono (servizio degli avvisi che non risponde) una riga nel registro e l'avviso resta in
# $STATO/avvisi-da-mandare, un file per avviso (ora in secondi, priorita, titolo, testo); ogni giro, prima di tutto il resto, li
# riprova: mandato, si toglie con una riga nel registro; dopo un giorno si rinuncia, con una riga nel registro.
DA_MANDARE="$STATO/avvisi-da-mandare"
avvisa_o_riprova() {   # titolo, testo, priorita
  [ "$PROVA" = 1 ] && return 0
  avvisa "$1" "$2" "$3" && return 0
  log "avviso non partito («$1»): lo riprovo ai prossimi giri"
  { mkdir -p "$DA_MANDARE" && [ ! -L "$DA_MANDARE" ]; } || return 1
  printf '%s\n%s\n%s\n%s\n' "$(date +%s)" "$3" "$1" "$2" > "$DA_MANDARE/$(date +%s)-$$-$RANDOM"
  return 1
}
riprova_avvisi() {
  [ "$PROVA" = 1 ] && return 0
  { [ -d "$DA_MANDARE" ] && [ ! -L "$DA_MANDARE" ]; } || return 0
  local f quando priorita titolo testo
  for f in "$DA_MANDARE"/*; do
    { [ -f "$f" ] && [ ! -L "$f" ]; } || continue
    quando=""; priorita=""; titolo=""
    { read -r quando; read -r priorita; read -r titolo; testo=$(cat); } < "$f"
    [[ $quando =~ ^[0-9]{1,12}$ ]] || quando=0
    [[ $priorita =~ ^[1-5]$ ]] || priorita=4
    if avvisa "$titolo" "$testo" "$priorita"; then
      log "avviso mandato al nuovo tentativo: «$titolo»"; rm -f "$f"
    elif [ $(( $(date +%s) - quando )) -ge "$GIORNO" ]; then
      log "avviso «$titolo» non partito per un giorno intero: rinuncio"; rm -f "$f"
    fi
  done
}
riprova_avvisi

# Riavvio del servizio (#826): sudo -n (mai una domanda di password: senza la regola di sudo il comando fallisce subito) e processo
# principale (MainPID, da systemctl show, che non chiede permessi) diverso da prima. Esce con 1 se il riavvio non e' riuscito, con
# una riga nel registro: risponderebbe ancora il processo vecchio, con il codice di prima. Un processo 0 (o illeggibile) dopo il
# riavvio non e' un guasto del riavvio: e' la versione nuova che muore all'avvio (systemd la rilancia), e lo dice il controllo dopo.
pid_servizio() { systemctl show -p MainPID --value "$SERVIZIO" 2>/dev/null | tr -cd '0-9'; }
riavvia() {
  local prima dopo
  prima=$(pid_servizio)
  if ! sudo -n systemctl restart "$SERVIZIO" 2>>"$ERR"; then
    log "riavvio di $SERVIZIO non riuscito (sudo -n systemctl restart: manca la regola di sudo o il servizio non parte)"
    return 1
  fi
  dopo=$(pid_servizio)
  if [ -n "$dopo" ] && [ "$dopo" != 0 ] && [ "$dopo" = "$prima" ]; then
    log "riavvio di $SERVIZIO non riuscito: il processo del servizio non e' cambiato (prima ${prima:-nessuno}, dopo ${dopo:-nessuno})"
    return 1
  fi
}
TESTO_RIAVVIO="Non riesco a riavviare il servizio (regola di sudo o systemd): resta la versione di prima e riprovo al prossimo giro."

# Database degli account (#825). /api/account/me risponde 401 senza sessione prima di leggere il database: il servizio «risponde»
# anche con una migrazione che sui dati veri non riesce. Per questo:
# - versione_db: la versione del database (PRAGMA user_version) letta in sola lettura con il solo Python di base, senza importare
#   fanta, quindi con qualunque versione installata e senza migrare niente. Stampa un numero, «nessuno» se il file non c'e', niente
#   se non si legge. Si legge prima dell'installazione (anche nel segno installazione-in-corso) e prima di tornare indietro: se e'
#   salita, il codice di prima rifiuterebbe il database («versione piu' nuova dell'app») e si tiene la versione nuova;
# - controlla_account: dopo il riavvio, con il codice appena installato, apre davvero il database (con le migrazioni, come la prima
#   richiesta del servizio) e lo confronta con le migrazioni attese: fanta/salute.py, controlla_database_account (nome fisso: lo
#   chiama questo script, che e' quello della versione di prima). La sua frase finisce in ESITO_ACCOUNT. Una versione senza quella
#   funzione (per esempio il revert di #825) si installa lo stesso, con la riga nel registro: come momento-libero, un controllo che
#   manca non deve fermare gli aggiornamenti (ne' un ritorno indietro d'emergenza).
#   Il percorso e' quello del servizio: FANTA_DATI_UTENTI se c'e' (dall'ambiente del servizio), altrimenti dati/ della cartella.
ambiente_servizio() { . "$QUI/leggi-ambiente.sh" && leggi_ambiente dati/ambiente.env 2>/dev/null; }
versione_db() {
  ( cd "$DEST" && ambiente_servizio && timeout -k 5 60 nice -n 10 .venv/bin/python -c "
import os, sqlite3, sys
from pathlib import Path
p = Path(os.environ.get('FANTA_DATI_UTENTI') or 'dati') / 'account.sqlite'
if not p.exists():
    print('nessuno')
    sys.exit(0)
db = sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True, timeout=15)
print(db.execute('PRAGMA user_version').fetchone()[0])" 2>>"$ERR" )
}
salita() { [[ ${1:-} =~ ^[0-9]{1,9}$ ]] && [[ ${2:-} =~ ^[0-9]{1,9}$ ]] && [ "$2" -gt "$1" ]; }     # versione di prima, di adesso
controlla_account() {
  local rc
  ESITO_ACCOUNT=$(cd "$DEST" && ambiente_servizio && timeout -k 5 "${SCHIERAXI_TIMEOUT_ACCOUNT:-90}" nice -n 10 .venv/bin/python -c "
import sys
from fanta import salute
controlla = getattr(salute, 'controlla_database_account', None)
if controlla is None:
    print('controllo del database degli account assente in questa versione: non controllo')
    sys.exit(0)
ok, testo = controlla()
print(testo)
sys.exit(0 if ok else 1)" 2>&1)
  rc=$?
  ESITO_ACCOUNT=$(printf '%s' "$ESITO_ACCOUNT" | tr '\r\n' '  ' | tail -c 400)
  return "$rc"
}
TESTO_TENUTA="Va controllato il server: script/server/LEGGIMI.md, «Versione tenuta dopo una migrazione». Dettagli in dati/pubblicazione.log."

# La richiesta d'emergenza resta finche' un'installazione non riesce (#647): l'avviso di un rifiuto lo dice
ancora_subito() {
  [ -e "$STATO/installa-subito" ] && printf ' La richiesta di installare subito resta attiva: la prossima versione si installa appena arriva, anche durante una partita.'
  return 0
}
# Installazione interrotta (#647). Mentre i file nuovi non hanno superato l'installazione c'e' il segno installazione-in-corso: «file
# <commit>», poi «ambiente <commit>» appena prima dello scambio degli ambienti Python. Se c'e' all'inizio di un giro, il giro che l'ha
# scritto si e' fermato a meta' (server spento, processo ucciso): un giro ancora vivo terrebbe il blocco preso qui sopra e questo non
# sarebbe partito. Si rimettono subito file e ambiente della versione di prima dalla copia di sicurezza (mai rifatta mentre c'e' il
# segno), si riavvia il servizio e si avvisa (uno al giorno, come gli altri guasti); poi il giro continua e la versione nuova si riprova.
# La stessa versione interrotta una seconda volta (stato in interrotta) diventa rifiutata: niente ciclo di installazioni a meta'.
# Senza copia di sicurezza (o rovinata) non si installa niente: l'avviso rimanda al LEGGIMI, che dice come ripartire a mano.
copia="$STATO/versione-precedente.tar.gz"
A_META="$STATO/installazione-in-corso"
TESTO_SENZA_COPIA="Un aggiornamento si era fermato a metà e non riesco a rimettere la versione di prima dalla copia di sicurezza: gli aggiornamenti sono fermi. Come ripartire: script/server/LEGGIMI.md, «Aggiornamento interrotto senza copia di sicurezza»."
if [ -e "$A_META" ]; then
  stadio=""; interrotto=""; db_meta=""
  read -r stadio interrotto db_meta _ < "$A_META" 2>/dev/null
  if [ "$PROVA" = 1 ]; then
    log "un'installazione di prima (${interrotto:0:7}) si e' fermata a meta': rimetterei la versione di prima dalla copia di sicurezza"
  elif db_ora=$(versione_db) && salita "$db_meta" "$db_ora"; then
    # la versione nuova ha gia' migrato il database degli account (#825): il codice di prima non lo saprebbe leggere. Niente ritorno
    # indietro: si toglie il segno e questo giro reinstalla la versione di main (ultimo-rilascio e' ancora quello di prima)
    log "l'installazione di prima (${interrotto:0:7}) non era finita, ma il database degli account e' gia' passato dalla versione $db_meta alla $db_ora: non rimetto la versione di prima, che non lo saprebbe leggere; reinstallo la versione nuova"
    rm -f "$A_META" "$STATO/interrotta"
    # per questo giro: la copia di sicurezza non si rifa' dai file lasciati a meta' e la versione «di prima» del database resta
    # quella di prima della migrazione, cosi' se anche la reinstallazione non va si tiene la nuova invece di tornare a una copia
    DB_PRIMA_ORIGINALE=$db_meta
    avvisa_o_riprova "SchieraXI: aggiornamento da controllare" "Un aggiornamento si era fermato a metà dopo aver già aggiornato il database degli account: non ho rimesso la versione di prima, che non saprebbe leggerlo, e reinstallo quella nuova.$(ancora_subito) $TESTO_TENUTA" 4
  else
    log "l'installazione di prima (${interrotto:0:7}) non era finita (server spento o processo fermato?): rimetto la versione di prima dalla copia di sicurezza"
    rimessa=0
    if [ -s "$copia" ] && tar xzf "$copia" -C "$DEST"; then
      if [ "$stadio" = ambiente ] && [ -d "$DEST/.venv.precedente" ]; then
        rm -rf "$DEST/.venv.scartata"
        mv "$DEST/.venv" "$DEST/.venv.scartata" && mv "$DEST/.venv.precedente" "$DEST/.venv" && rm -rf "$DEST/.venv.scartata"
      fi
      [ -e "$DEST/.venv" ] || { [ -d "$DEST/.venv.precedente" ] && mv "$DEST/.venv.precedente" "$DEST/.venv"; }
      rm -rf "$DEST/.venv.nuova"
      [ -x "$DEST/.venv/bin/python" ] && rimessa=1
    fi
    if [ "$rimessa" = 0 ]; then
      log "non riesco a rimettere la versione di prima dalla copia di sicurezza (manca o e' rovinata): non installo niente, controlla $DEST (script/server/LEGGIMI.md)"
      guasto copia-sicurezza "$TESTO_SENZA_COPIA"
      fine; exit 1
    fi
    rm -f "$A_META"
    if riavvia; then log "versione di prima rimessa e servizio riavviato"
    else log "versione di prima rimessa, ma il servizio non si e' riavviato"; guasto riavvio "$TESTO_RIAVVIO"; fi
    if [ -n "$interrotto" ] && [ "$(cat "$STATO/interrotta" 2>/dev/null)" = "$interrotto" ]; then
      log "versione ${interrotto:0:7} interrotta due volte: non la riprovo"
      echo "$interrotto" > "$STATO/rifiutato"; rm -f "$STATO/interrotta" "$STATO/attesa-versione"
      avvisa_o_riprova "SchieraXI: aggiornamento annullato" "La versione nuova si è interrotta due volte a metà dell'installazione: ho rimesso quella di prima e non la riprovo.$(ancora_subito) Dettagli in dati/pubblicazione.log." 4
    else
      [ -n "$interrotto" ] && echo "$interrotto" > "$STATO/interrotta"
    fi
    guasto interrotta "Un aggiornamento si era fermato a metà: ho rimesso la versione di prima."
  fi
fi

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
# Versione rifiutata con altre sotto, arrivate prima e non ancora installate (con il raggruppamento capita piu' spesso, #635): non si
# installano da sole, perche' un ripiego automatico su una versione mai provata potrebbe alternare due versioni rotte con un riavvio a
# ogni giro. Entrano con la prossima versione buona (o con --fidati, per le firme). L'avviso del rifiuto lo dice se sotto c'e' una
# versione che si sarebbe potuta installare da sola: l'ultimo commit (linea principale, sotto quello rifiutato) senza novita' in attesa
# in fanta/novita.d. Le unioni sopra quel commit sono numerate dal commit di versione rifiutato, quindi sono la versione rotta (#647).
# Se fra l'ultima installata e quel commit cambiano le cartelle del server (non per i soli documenti; anche una modifica rimasta senza
# commit di versione) l'avviso lo dice, contando le versioni vere quando ci sono: i commit «Versione 1.2: ...» del job rilascia.
anche_prima() {
  local n c fino=""
  { [ -n "$ultimo" ] && git cat-file -e "$ultimo^{commit}" 2>/dev/null && git cat-file -e "$nuovo^1" 2>/dev/null; } || return 0
  for c in $(git rev-list --first-parent --max-count=500 "$ultimo..$nuovo^1" 2>/dev/null); do
    git ls-tree --name-only "$c" fanta/novita.d/ 2>/dev/null | grep -q '\.json$' || { fino=$c; break; }
  done
  [ -n "$fino" ] || return 0
  # shellcheck disable=SC2086
  git diff --quiet "$ultimo" "$fino" -- $CARTELLE 2>/dev/null && return 0
  n=$(git log --first-parent --format=%s "$ultimo..$fino" 2>/dev/null | grep -cE '^Versione [0-9]+\.[0-9]+[,:]')
  if ! [[ $n =~ ^[0-9]+$ ]] || [ "$n" = 0 ]; then
    printf ' Anche le modifiche arrivate prima, in attesa, non sono installate: entrano con la prossima versione buona.'
  elif [ "$n" = 1 ]; then
    printf ' Anche la versione arrivata prima, in attesa, non è installata: entra con la prossima versione buona.'
  else
    printf ' Anche le %s versioni arrivate prima, in attesa, non sono installate: entrano con la prossima versione buona.' "$n"
  fi
  return 0
}
# Firme: dall'ultimo commit verificato (o, la prima volta, dall'ultimo installato) fino a quello nuovo, tutti firmati da una chiave fidata
if [ -s "$CHIAVI" ]; then
  base=$(cat "$STATO/verificato" 2>/dev/null)
  [ -n "$base" ] || base="$ultimo"
  if ! verifica_catena "$base" "$nuovo" "$CHIAVI"; then
    log "versione ${nuovo:0:7} NON installata: $MOTIVO_FIRMA"
    if [ "$PROVA" = 0 ]; then
      echo "$nuovo" > "$STATO/rifiutato"; rm -f "$STATO/attesa-versione"
      avvisa_o_riprova "SchieraXI: aggiornamento bloccato" "Su GitHub c'è una versione senza la firma attesa: non l'ho installata.$(anche_prima)$(ancora_subito) Motivo in dati/pubblicazione.log. Se dopo il controllo va bene: aggiorna-app.sh --fidati origin/main (script/server/LEGGIMI.md, «Casi limite»)." 4
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
    [ -e "$STATO/senza-chiave" ] || avvisa_o_riprova "SchieraXI: aggiornamenti fermi" "Manca la chiave per controllare le firme: non installo le versioni nuove. Dettagli in dati/pubblicazione.log." 4
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
  [ "$PROVA" = 1 ] || { echo "$nuovo" > "$STATO/rifiutato"; rm -f "$STATO/attesa-versione"; }
  guasto cartelle "Su GitHub c'è una versione senza tutte le cartelle del server: non l'ho installata.$(anche_prima)$(ancora_subito)"
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

# Installazione forzata, a mano: SCHIERAXI_INSTALLA_SUBITO=1 oppure il file installa-subito (si cancella da solo a installazione
# riuscita: se non riesce, la richiesta resta per i giri dopo, #647)
installa_subito=0
if [ "${SCHIERAXI_INSTALLA_SUBITO:-0}" = 1 ] || [ -e "$STATO/installa-subito" ]; then installa_subito=1; fi

# Unione arrivata, commit di versione non ancora (#635): il job rilascia lo crea 10-20 secondi dopo l'unione. Se in main c'e' ancora
# una novita' senza numero (fanta/novita.d/*.json) si aspetta il giro dopo: l'unione da sola avrebbe numero di versione e novita'
# vecchi fino all'installazione seguente (con il raggruppamento, fino a un'ora). Al massimo mezz'ora, contata dal primo giro che ha
# aspettato (stato in attesa-versione: l'ora di quel giro, in secondi), non dall'ora dei commit: un'unione nuova non la fa ripartire.
# Poi (job rilascia fermo?) si installa lo stesso, con un avviso e una riga nel registro (una sola: «scaduta», secondo campo dello
# stato); «di nuovo a posto» quando main non ha piu' novita' senza numero. L'installazione forzata non aspetta. Lo stato si toglie
# dopo l'installazione, quando una versione e' rifiutata (#647) o quando le novita' senza numero non ci sono piu'.
if [ "$installa_subito" = 0 ] && [[ $INIZIO =~ ^[0-9]{1,12}$ ]] \
   && git ls-tree --name-only "$nuovo" fanta/novita.d/ 2>/dev/null | grep -q '\.json$'; then
  inizio_attesa=""; scaduta=""
  [ -f "$STATO/attesa-versione" ] && read -r inizio_attesa scaduta _ < "$STATO/attesa-versione"
  if ! [[ $inizio_attesa =~ ^[0-9]{1,12}$ ]] || [ $(( 10#$inizio_attesa )) -gt $(( 10#$INIZIO )) ]; then
    inizio_attesa=$INIZIO; scaduta=""          # primo giro che aspetta (o stato rovinato, o orologio tornato indietro)
    if [ "$PROVA" = 0 ]; then
      echo "$INIZIO" > "$STATO/attesa-versione"
      log "versione ${nuovo:0:7} senza ancora il commit di versione del job rilascia (novita' in attesa): aspetto, al massimo mezz'ora"
    fi
  fi
  attesi=$(( 10#$INIZIO - 10#$inizio_attesa ))
  if [ "$attesi" -lt 1800 ]; then
    [ "$PROVA" = 1 ] && log "aspetterei il commit di versione del job rilascia per ${nuovo:0:7} (in attesa da $(( attesi / 60 )) minuti)"
    fine; exit 0
  fi
  # una riga sola per attesa (#647): se l'installazione poi e' rimandata (partita, intervallo) i giri dopo non la ripetono
  if [ "$PROVA" = 1 ] || [ "$scaduta" != scaduta ]; then
    log "il commit di versione del job rilascia non e' arrivato in $(( attesi / 60 )) minuti (job fermo?): installo lo stesso ${nuovo:0:7}"
    [ "$PROVA" = 1 ] || echo "$inizio_attesa scaduta" > "$STATO/attesa-versione"
  fi
  guasto rilascia "Da mezz'ora il commit di versione non arriva (job rilascia fermo?): installo le versioni senza il loro numero."
elif [ "$PROVA" = 0 ] && ! git ls-tree --name-only "$nuovo" fanta/novita.d/ 2>/dev/null | grep -q '\.json$'; then
  rm -f "$STATO/attesa-versione"
  risolto rilascia
fi

# Mai durante una partita di Serie A ne' nell'ora prima della scadenza della formazione di una lega: il riavvio interromperebbe i
# risultati in diretta e i giri delle probabili. Decide la versione installata (python -m fanta momento-libero, fanta/libero.py):
# 3 = occupato (si rimanda al primo giro libero, una riga nel log per versione); qualunque altro esito (0, comando che non c'e'
# ancora, errore, tempo scaduto) = si installa: un controllo guasto non deve fermare gli aggiornamenti.
# Emergenza: SCHIERAXI_INSTALLA_SUBITO=1 oppure il file ~/.cache/fantacalcio/installa-subito (si cancella a installazione riuscita).
# L'ambiente di prova non aspetta (ATTENDE_PARTITE=0): nessun utente vero lo usa e deve avere ogni versione prima della produzione.
forzata=0
if [ "$ATTENDE_PARTITE" = 0 ]; then
  :
elif [ "$installa_subito" = 1 ]; then
  log "installazione forzata di ${nuovo:0:7}: non controllo commit di versione, partite, scadenze e intervallo fra due installazioni"
  forzata=1
  [ "$PROVA" = 1 ] || rm -f "$STATO/rimandata"
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
  trascorsi=$(( 10#$INIZIO - 10#$ultima_installazione ))     # 10#: uno zero davanti non vuol dire base otto
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
# Copia di sicurezza della versione in uso, per tornare indietro: prende il posto della vecchia solo se e' riuscita tutta. Qui il segno
# installazione-in-corso non c'e' (un giro interrotto e' gia' stato rimesso a posto all'inizio), quindi la cartella dell'app ha una
# versione che ha superato l'installazione. Da qui fino alla fine dell'installazione il segno c'e' (#647), con la versione del
# database degli account di prima (#825; «-» se non si legge).
db_prima=$(versione_db)
if [ -n "${DB_PRIMA_ORIGINALE:-}" ]; then
  log "database degli account alla versione ${db_prima:-non leggibile} (era alla $DB_PRIMA_ORIGINALE prima dell'installazione interrotta): tengo la copia di sicurezza di allora"
  db_prima=$DB_PRIMA_ORIGINALE
else
  case "$db_prima" in
    nessuno) log "database degli account assente (account spenti?): niente da confrontare" ;;
    "") log "database degli account non leggibile in sola lettura: se l'installazione non va, si torna indietro come sempre" ;;
    *) log "database degli account alla versione $db_prima" ;;
  esac
fi
[ -n "$db_prima" ] || db_prima=-
# shellcheck disable=SC2086
if [ -e "$A_META" ] || { [ -z "${DB_PRIMA_ORIGINALE:-}" ] && { ! tar czf "$copia.nuova" -C "$DEST" $CARTELLE 2>/dev/null || ! mv "$copia.nuova" "$copia"; }; }; then
  rm -f "$copia.nuova"; log "copia di sicurezza della versione in uso non riuscita (disco pieno?): non installo"
  guasto copia-file "Non riesco a fare la copia di sicurezza della versione in uso (disco pieno?): resta quella di prima."; fine; exit 1
fi
echo "file $nuovo $db_prima" > "$A_META"
vecchi_req=$(md5sum "$DEST/requirements.txt" 2>/dev/null | cut -d' ' -f1)

prova=$(mktemp -d)
# shellcheck disable=SC2086
if ! git archive "$nuovo" $CARTELLE | tar -x -C "$prova"; then
  log "copia dei file non riuscita"; rm -rf "$prova"; rm -f "$A_META"
  guasto copia-file "Non riesco a copiare i file della versione nuova (disco pieno?): resta quella di prima."; fine; exit 1
fi
# Il file dei tratti dei volti vive solo sul server: se c'e' gia', resta quello (anche se il repository non lo ha piu')
if [ -f "$DEST/fanta/avatar_tratti.json" ]; then
  cp -p "$DEST/fanta/avatar_tratti.json" "$prova/fanta/avatar_tratti.json"
fi

# Librerie cambiate: un ambiente Python NUOVO accanto a quello in uso (.venv.nuova), con le sole versioni e hash di requirements.txt.
# Si prepara PRIMA di toccare i file (#826): mentre pip lavora i processi del cron usano ancora codice e librerie di prima, e se pip
# non riesce non c'e' niente da rimettere (prima restavano i file aggiunti dalla versione nuova). Le cartelle si scambiano solo se
# l'installazione e' riuscita tutta: l'ambiente in uso non resta mai a meta'. Quello di prima resta in .venv.precedente (per tornare
# indietro). Funziona perche' servizio e script usano solo .venv/bin/python (mai i comandi di bin/).
venv_pronta=0
venv_cambiata=0
if [ "$vecchi_req" != "$(md5sum "$prova/requirements.txt" | cut -d' ' -f1)" ]; then
  log "librerie cambiate: preparo un ambiente Python nuovo con le versioni e gli hash di requirements.txt"
  python_base=$(readlink -f "$DEST/.venv/bin/python")
  rm -rf "$DEST/.venv.nuova"
  if "$python_base" -m venv "$DEST/.venv.nuova" >> "$LOG" 2>&1 \
     && "$DEST/.venv.nuova/bin/python" -m pip install -q --require-hashes -r "$prova/requirements.txt" >> "$LOG" 2>&1; then
    rm -f "$STATO/librerie-fallite"
    venv_pronta=1
  else
    # file, ambiente in uso e servizio non sono stati toccati: si butta solo quello che e' stato preparato
    rm -rf "$DEST/.venv.nuova" "$prova"
    rm -f "$A_META"
    # un errore passeggero (rete, PyPI) non deve bloccare la versione per sempre: si riprova ai giri dopo, si rinuncia alla terza volta
    tentativi=1
    if [ "$(cut -d' ' -f1 "$STATO/librerie-fallite" 2>/dev/null)" = "$nuovo" ]; then
      tentativi=$(( $(cut -d' ' -f2 "$STATO/librerie-fallite") + 1 ))
    fi
    echo "$nuovo $tentativi" > "$STATO/librerie-fallite"
    if [ "$tentativi" -ge "${SCHIERAXI_TENTATIVI_LIBRERIE:-3}" ]; then
      log "librerie NON installate per la ${tentativi}a volta di fila: rinuncio a ${nuovo:0:7} (resta la versione di prima)"
      echo "$nuovo" > "$STATO/rifiutato"; rm -f "$STATO/attesa-versione"
      rm -f "$STATO/librerie-fallite"
      avvisa_o_riprova "SchieraXI: aggiornamento annullato" "Le librerie della versione nuova non si installano (provato $tentativi volte): resta quella di prima.$(anche_prima)$(ancora_subito) Dettagli in dati/pubblicazione.log." 4
    else
      log "librerie NON installate (rete, PyPI, hash diverso?): resta la versione di prima, riprovo al prossimo giro (tentativo $tentativi)"
      if [ "$tentativi" = 1 ] && ! avvisa "SchieraXI: aggiornamento rimandato" "Le librerie della versione nuova non si sono installate: riprovo fra 10 minuti." 3; then
        log "avviso «aggiornamento rimandato» non partito (non lo riprovo: vale solo adesso)"
      fi
    fi
    fine; exit 1
  fi
fi

for d in fanta tests script; do
  rm -rf "$DEST/$d.nuovo" && mv "$prova/$d" "$DEST/$d.nuovo" && rm -rf "$DEST/$d" && mv "$DEST/$d.nuovo" "$DEST/$d"
done
cp "$prova"/requirements*.txt "$DEST"/
rm -rf "$prova"
find "$DEST/script" -name '*.sh' -exec sed -i 's/\r$//' {} +

if [ "$venv_pronta" = 1 ]; then
  rm -rf "$DEST/.venv.precedente"
  echo "ambiente $nuovo $db_prima" > "$A_META"     # prima dello scambio: un'interruzione da qui rimette anche l'ambiente di prima
  mv "$DEST/.venv" "$DEST/.venv.precedente" && mv "$DEST/.venv.nuova" "$DEST/.venv" && venv_cambiata=1
  if [ "$venv_cambiata" = 0 ]; then
    # il servizio non e' stato riavviato: si rimettono subito l'ambiente in uso e i file della versione di prima (#647)
    log "scambio degli ambienti Python non riuscito: rimetto la versione di prima"
    [ -e "$DEST/.venv" ] || mv "$DEST/.venv.precedente" "$DEST/.venv"
    rm -rf "$DEST/.venv.nuova"
    if tar xzf "$copia" -C "$DEST" && [ -x "$DEST/.venv/bin/python" ]; then rm -f "$A_META"
    else log "versione di prima non rimessa del tutto: controlla $DEST (il prossimo giro riprova dalla copia di sicurezza)"; fi
    guasto ambienti "Non riesco a scambiare gli ambienti Python della versione nuova: resta quella di prima, va controllato il server."
    fine; exit 1
  fi
fi

riavviato=0
risponde=0
if riavvia; then
  riavviato=1
  for i in $(seq 1 "${SCHIERAXI_ATTESE_AVVIO:-25}"); do
    # 200 con un solo utente; 401 con gli account accesi: in entrambi i casi il servizio risponde
    codice=$(curl -s -m 5 -o /dev/null -w '%{http_code}' -H "X-Fanta: 1" "http://127.0.0.1:$PORTA/api/account/me")
    if [ "$codice" = 200 ] || [ "$codice" = 401 ]; then risponde=1; break; fi
    sleep 1
  done
fi
perche="il servizio NON risponde (ultimo codice HTTP: ${codice:-nessuno})"
[ "$riavviato" = 1 ] || perche="il riavvio del servizio non e' riuscito"
if [ "$risponde" = 1 ] && ! controlla_account; then     # il servizio risponde: ora il database degli account (#825)
  risponde=0; perche="il database degli account non va: $ESITO_ACCOUNT"
fi

if [ "$risponde" = 1 ]; then
  # prima il segno, poi lo stato: un'interruzione fra i due fa solo reinstallare la stessa versione al giro dopo (#647)
  rm -f "$A_META"
  echo "$nuovo" > "$STATO/ultimo-rilascio"
  echo "$INIZIO" > "$STATO/ultima-installazione"     # da qui parte l'intervallo fra due installazioni (#635)
  rm -f "$STATO/attesa-versione" "$STATO/interrotta" "$STATO/riavvio-fallito"
  [ "$installa_subito" = 1 ] && rm -f "$STATO/installa-subito"     # la richiesta d'emergenza e' soddisfatta (#647)
  versione=$(cd "$DEST" && .venv/bin/python -c "import json; print(json.load(open('fanta/novita.json', encoding='utf-8'))[0]['versione'])" 2>/dev/null)
  # solo la riga nel registro, niente avviso: con tante versioni al giorno gli avvisi veri (fallita, rifiutata, tornata indietro) si
  # perdevano tra quelli di routine (#607)
  log "installata ${nuovo:0:7} (versione $versione): il servizio risponde ($ESITO_ACCOUNT)"
  risolto cartelle copia-file ambienti interrotta copia-sicurezza riavvio     # «di nuovo a posto» se un guasto dell'installazione era stato segnalato
elif db_dopo=$(versione_db) && salita "$db_prima" "$db_dopo"; then
  # la versione nuova ha gia' migrato il database degli account (#825): il codice di prima lo rifiuterebbe, con errori per ogni utente
  # collegato. Si tiene la nuova (codice e librerie) e si avvisa; il segno si toglie, se no il giro dopo rimetterebbe la versione di prima
  log "con ${nuovo:0:7} $perche, ma il database degli account e' gia' passato dalla versione $db_prima alla $db_dopo: non torno alla versione di prima, che non lo saprebbe leggere. Resta ${nuovo:0:7}, da controllare a mano"
  rm -f "$A_META"
  echo "$nuovo" > "$STATO/ultimo-rilascio"
  rm -f "$STATO/attesa-versione" "$STATO/interrotta"
  avvisa_o_riprova "SchieraXI: aggiornamento da controllare" "La versione nuova non funziona come dovrebbe, ma ha già aggiornato il database degli account: l'ho lasciata installata, perché quella di prima non saprebbe leggerlo.$(ancora_subito) $TESTO_TENUTA" 4
else
  log "con ${nuovo:0:7} $perche: torno alla versione di prima"
  rimessa=1
  tar xzf "$copia" -C "$DEST" || rimessa=0
  if [ "$venv_cambiata" = 1 ]; then          # anche le librerie di prima
    rm -rf "$DEST/.venv.scartata"
    mv "$DEST/.venv" "$DEST/.venv.scartata" && mv "$DEST/.venv.precedente" "$DEST/.venv" && rm -rf "$DEST/.venv.scartata" || rimessa=0
  fi
  [ "$rimessa" = 1 ] && rm -f "$A_META"     # altrimenti il giro dopo riprova a rimettere la versione di prima (#647)
  riavvia || [ "$riavviato" = 0 ] || guasto riavvio "$TESTO_RIAVVIO"     # la versione di prima rimessa, ma il servizio no
  if [ "$riavviato" = 0 ]; then
    # guasto del server, non della versione (#826): non si scrive «rifiutato» e il giro dopo riprova, al massimo tre giri per versione
    # (stato in riavvio-fallito: «commit volte»), poi si rinuncia come per le librerie: ogni giro rifa' copia, file e librerie
    volte=1
    if [ "$(cut -d' ' -f1 "$STATO/riavvio-fallito" 2>/dev/null)" = "$nuovo" ]; then
      volte=$(cut -d' ' -f2 "$STATO/riavvio-fallito" 2>/dev/null); [[ $volte =~ ^[0-9]{1,6}$ ]] || volte=0
      volte=$(( volte + 1 ))
    fi
    if [ "$volte" -ge "${SCHIERAXI_TENTATIVI_RIAVVIO:-3}" ]; then
      log "riavvio non riuscito per la ${volte}a volta di fila con ${nuovo:0:7}: non la riprovo (resta la versione di prima)"
      echo "$nuovo" > "$STATO/rifiutato"; rm -f "$STATO/attesa-versione" "$STATO/riavvio-fallito"
      avvisa_o_riprova "SchieraXI: aggiornamento annullato" "Non riesco a riavviare il servizio da $volte giri di fila: resta la versione di prima e non riprovo questa (la prossima versione sì). Va controllata la regola di sudo (script/server/LEGGIMI.md).$(ancora_subito) Dettagli in dati/pubblicazione.log." 4
    else
      echo "$nuovo $volte" > "$STATO/riavvio-fallito"
    fi
    guasto riavvio "$TESTO_RIAVVIO"
    fine; exit 0
  fi
  echo "$nuovo" > "$STATO/rifiutato"; rm -f "$STATO/attesa-versione"
  sleep "${SCHIERAXI_PAUSA_DOPO_RITORNO:-5}"
  avvisa_o_riprova "SchieraXI: aggiornamento annullato" "La versione nuova non partiva: sono tornato a quella di prima.$(anche_prima)$(ancora_subito) Dettagli in dati/pubblicazione.log." 4
fi
fine
exit 0
