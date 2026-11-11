#!/bin/bash
# registri.sh - da includere negli script del server che scrivono i loro registri (log) in una cartella che scrive anche il servizio
# (dati/ dell'app, ~/.cache): QUI=$(cd "$(dirname "$0")" && pwd); . "$QUI/registri.sh" || exit 1
# Gli script dei cron girano fuori dal recinto del servizio: non devono mai scrivere, ruotare o cambiare i permessi passando da un
# collegamento simbolico messo in quelle cartelle, che li porterebbe a scrivere altrove (per esempio sul codice o sulle chiavi).
#   registri_sicuri FILE...    esce con 1 se uno dei file e' un collegamento simbolico; altrimenti 0. Si chiama all'inizio.
#                              Lo dice sullo standard error e, se c'e' logger, anche nel journal (i cron buttano l'uscita).
#   ruota_registro FILE N      tiene le ultime N righe. Il file di lavoro (FILE.<numero del processo>) si crea con noclobber
#                              (set -C: apertura esclusiva, rifiuta un file o un collegamento gia' presente con quel nome) e poi
#                              prende il posto del registro con mv (che sostituisce il nome, non segue un collegamento).
#   permessi_registri CARTELLA chmod 600 sui *.log della cartella che sono file veri (i collegamenti si saltano).

registri_sicuri() {
  local f messaggio
  for f in "$@"; do
    if [ -L "$f" ]; then
      messaggio="$(basename "$0"): $f e' un collegamento simbolico: non scrivo niente"
      echo "$messaggio" >&2
      if command -v logger >/dev/null 2>&1; then logger -t schieraxi -- "$messaggio" 2>/dev/null; fi
      return 1
    fi
  done
  return 0
}

ruota_registro() {
  local file=$1 righe=$2 lavoro
  registri_sicuri "$file" || return 1
  [ -f "$file" ] || return 0
  lavoro="$file.$$"
  if ! ( set -C; tail -n "$righe" -- "$file" > "$lavoro" ) 2>/dev/null; then
    echo "$(basename "$0"): non riesco a creare $lavoro (c'e' gia'?): registro non ruotato" >&2
    return 1
  fi
  mv -f -- "$lavoro" "$file"
}

permessi_registri() {
  local f
  for f in "$1"/*.log; do
    if [ -f "$f" ] && [ ! -L "$f" ]; then chmod 600 "$f"; fi
  done
  return 0
}
