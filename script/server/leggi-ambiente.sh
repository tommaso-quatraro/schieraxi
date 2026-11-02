#!/bin/bash
# leggi-ambiente.sh - da includere negli script del server:  . script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env
# Legge le variabili del servizio SENZA eseguire il file (prima si faceva ". dati/ambiente.env": chi riusciva a scriverci dentro
# faceva girare i suoi comandi). Riga per riga, solo CHIAVE=valore; vale solo un elenco di chiavi (FANTA_* e MAX_UTENTI),
# le altre (PATH, LD_PRELOAD...) si ignorano. Il valore resta com'è: niente $(...), `...`, $VARIABILI né ; eseguiti.
# Si accettano: righe vuote e commenti (#), "export " davanti, virgolette semplici o doppie intorno al valore, fine riga Windows.
# Senza il file non cambia niente.

leggi_ambiente() {
  local file=$1 riga chiave valore
  [ -f "$file" ] || return 0
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
