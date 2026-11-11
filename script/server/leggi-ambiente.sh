#!/bin/bash
# leggi-ambiente.sh - da includere negli script del server:  . script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env
# Legge le variabili del servizio SENZA eseguire il file (prima si faceva ". dati/ambiente.env": chi riusciva a scriverci dentro
# faceva girare i suoi comandi). Riga per riga, solo CHIAVE=valore; vale solo un elenco di chiavi (FANTA_* e MAX_UTENTI),
# le altre (PATH, LD_PRELOAD...) si ignorano. Il valore resta com'è: niente $(...), `...`, $VARIABILI né ; eseguiti.
# Si accettano: righe vuote e commenti (#), "export " davanti, virgolette semplici o doppie intorno al valore, fine riga Windows.
# Senza il file non cambia niente.
# Dove sta il file: prima /etc/schieraxi/fantacalcio.env (di root, 640 root:<gruppo del servizio>: il servizio lo legge e non lo
# scrive; e' lo stesso che systemd da' al servizio, script/server/ambiente.conf.esempio). Se non c'e' (o non si legge), il file
# indicato come argomento, di solito dati/ambiente.env, il posto di prima: vale ancora, ma con un avviso, perche' la cartella dati
# la scrive il servizio (docs/RIPRISTINO-SERVER.md, «Spostare le variabili del servizio»).
# SCHIERAXI_AMBIENTE cambia il file di root (per le prove).
AMBIENTE_SERVIZIO="${SCHIERAXI_AMBIENTE:-/etc/schieraxi/fantacalcio.env}"

leggi_ambiente() {
  local file=$AMBIENTE_SERVIZIO riga chiave valore
  if [ ! -f "$file" ] || [ ! -r "$file" ]; then
    [ -f "$file" ] && echo "avviso: $file c'e' ma non si legge (permessi? 640 root:<gruppo del servizio>)" >&2
    file=${1:-}
    [ -n "$file" ] && [ -f "$file" ] || return 0
    echo "avviso: le variabili del servizio stanno ancora in $file: vanno spostate in $AMBIENTE_SERVIZIO (docs/RIPRISTINO-SERVER.md)" >&2
  fi
  while IFS= read -r riga || [ -n "$riga" ]; do
    riga=${riga%$'\r'}
    riga=${riga#"${riga%%[![:space:]]*}"}                       # spazi a sinistra
    case $riga in ''|'#'*) continue ;; esac
    riga=${riga#export }
    case $riga in *=*) ;; *) continue ;; esac
    chiave=${riga%%=*}
    valore=${riga#*=}
    [[ $chiave =~ ^(FANTA_[A-Z0-9_]+|MAX_UTENTI)$ ]] || continue
    if [[ $valore =~ ^\"(.*)\"$ ]] || [[ $valore =~ ^\'(.*)\'$ ]]; then
      valore=${BASH_REMATCH[1]}
    fi
    export "$chiave=$valore"
  done < "$file"
}
