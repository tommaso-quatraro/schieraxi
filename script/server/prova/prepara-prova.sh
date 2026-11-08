#!/bin/bash
# prepara-prova.sh - Una volta, a mano, come utente del server (script/server/prova/LEGGIMI.md, passo 4.3): prepara l'ambiente di prova
# in ~/schieraxi-prova, una seconda copia dell'app con dati inventati. Cosa fa, in ordine (ogni passo solo se manca: rilanciato riprende
# da dove si era fermato e non cambia quello che c'e' gia'):
#   1. controlla che ci siano la produzione (~/fantacalcio con il suo ambiente Python), il clone ~/schieraxi-src e una versione verificata
#      dalla produzione (~/.cache/fantacalcio/verificato, altrimenti ultimo-rilascio). Se manca qualcosa non scrive niente;
#   2. codice di quella versione (fanta, tests, script, requirements*: le stesse cose che installa aggiorna-app.sh) e la lega d'esempio
#      (lega/esempio, squadre inventate). Mai la lega vera, mai i dati della produzione;
#   3. ambiente Python nuovo con lo stesso Python della produzione e solo le versioni e gli hash di requirements.txt (pip --require-hashes);
#   4. cartella dati (700) e dati/ambiente.env (600) da ambiente-prova.env.esempio: posta, lavori periodici e fonti spenti;
#   5. prima copia dell'archivio delle statistiche (copia-archivio-prova.sh: produzione solo letta, senza gli esiti della sentinella);
#   6. stato degli aggiornamenti della prova (~/.cache/schieraxi-prova): ultimo-rilascio e verificato = la versione del passo 2, cosi'
#      aggiorna-app.sh con SCHIERAXI_ISTANZA=prova controlla le firme da li' in avanti.
# Non tocca mai ~/fantacalcio, ~/.cache/fantacalcio, servizi, nginx, sudo e crontab: quelli sono i passi 4.4-4.8, a mano.
# Opzione --prova: dice cosa farebbe e non scrive niente.
# Variabile per le prove: SCHIERAXI_SRC (cartella del clone).
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i messaggi con accenti restano giusti
export GIT_TERMINAL_PROMPT=0
PROVA=0
[ "${1:-}" = --prova ] && PROVA=1
PRODUZIONE="$HOME/fantacalcio"                       # solo letta
STATO_PRODUZIONE="$HOME/.cache/fantacalcio"          # solo letta
SRC="${SCHIERAXI_SRC:-$HOME/schieraxi-src}"
DEST="$HOME/schieraxi-prova"
STATO="$HOME/.cache/schieraxi-prova"
PEZZI="fanta tests script requirements.txt requirements-dev.txt lega/esempio"

dico() { if [ "$PROVA" = 1 ]; then echo "[prova] $*"; else echo "$*"; fi; }
ferma() { echo "NON preparo: $*" >&2; exit 1; }
nel_clone() { (cd "$SRC" && git "$@"); }

# 1. controlli (solo letture)
[ -x "$PRODUZIONE/.venv/bin/python" ] || ferma "manca l'ambiente Python della produzione ($PRODUZIONE/.venv/bin/python)"
python_base=$(readlink -f "$PRODUZIONE/.venv/bin/python") || ferma "non trovo il Python della produzione"
[ -d "$SRC/.git" ] || ferma "manca il clone $SRC (lo crea aggiorna-app.sh della produzione)"
commit=$(cat "$STATO_PRODUZIONE/verificato" 2>/dev/null)
[ -n "$commit" ] || commit=$(cat "$STATO_PRODUZIONE/ultimo-rilascio" 2>/dev/null)
[ -n "$commit" ] || ferma "la produzione non ha ancora una versione verificata ($STATO_PRODUZIONE/verificato)"
commit=$(nel_clone rev-parse -q --verify "$commit^{commit}") || ferma "la versione verificata dalla produzione non c'e' nel clone $SRC"
for p in $PEZZI script/server/prova; do
  nel_clone cat-file -e "$commit:$p" 2>/dev/null || ferma "la versione ${commit:0:7} non contiene $p"
done
dico "ambiente di prova in $DEST, versione ${commit:0:7} (l'ultima verificata dalla produzione), Python $python_base"

# 2. codice e lega d'esempio
mancano=""
for p in $PEZZI; do [ -e "$DEST/$p" ] || mancano="$mancano $p"; done
if [ -z "$mancano" ]; then
  dico "codice e lega d'esempio: ci sono gia' (il codice lo aggiorna aggiorna-app.sh con SCHIERAXI_ISTANZA=prova)"
elif [ "$PROVA" = 1 ]; then
  dico "metterei in $DEST:$mancano (versione ${commit:0:7}; niente ios, sito, docs, lega vera, dati)"
else
  tmp=$(mktemp -d) || ferma "non riesco a creare una cartella temporanea"
  # shellcheck disable=SC2086
  if ! nel_clone archive "$commit" $mancano | tar -x -C "$tmp"; then
    rm -rf "$tmp"; ferma "estrazione del codice non riuscita"
  fi
  mkdir -p "$DEST/lega"
  for p in $mancano; do
    mv "$tmp/$p" "$DEST/$p" || { rm -rf "$tmp"; ferma "non riesco a mettere $p in $DEST"; }
  done
  rm -rf "$tmp"
  find "$DEST/script" -name '*.sh' -exec sed -i 's/\r$//' {} +
  dico "messo in $DEST:$mancano"
fi

# 3. ambiente Python
if [ -x "$DEST/.venv/bin/python" ]; then
  dico "ambiente Python: c'e' gia' ($DEST/.venv)"
elif [ "$PROVA" = 1 ]; then
  dico "creerei $DEST/.venv con $python_base e pip install --require-hashes -r requirements.txt (qualche minuto)"
else
  dico "preparo l'ambiente Python (pip install --require-hashes -r requirements.txt): qualche minuto"
  rm -rf "${DEST:?}/.venv.nuova"
  if "$python_base" -m venv "$DEST/.venv.nuova" \
     && "$DEST/.venv.nuova/bin/python" -m pip install -q --require-hashes -r "$DEST/requirements.txt"; then
    mv "$DEST/.venv.nuova" "$DEST/.venv" || ferma "non riesco a mettere al suo posto $DEST/.venv"
  else
    rm -rf "${DEST:?}/.venv.nuova"
    ferma "librerie non installate (rete, PyPI?): rilancia lo script, riprende da qui"
  fi
fi

# 4. dati e variabili d'ambiente
if [ "$PROVA" = 1 ]; then
  [ -d "$DEST/dati" ] || dico "creerei $DEST/dati (permessi 700)"
  if [ -f "$DEST/dati/ambiente.env" ]; then dico "ambiente.env: c'e' gia', resta com'e'"
  else dico "creerei $DEST/dati/ambiente.env da ambiente-prova.env.esempio (permessi 600)"; fi
else
  mkdir -p "$DEST/dati" && chmod 700 "$DEST/dati"
  if [ -f "$DEST/dati/ambiente.env" ]; then
    dico "ambiente.env: c'e' gia', resta com'e'"
  else
    (umask 077 && cp "$DEST/script/server/prova/ambiente-prova.env.esempio" "$DEST/dati/ambiente.env") \
      || ferma "non riesco a creare $DEST/dati/ambiente.env"
    dico "creato $DEST/dati/ambiente.env (posta, lavori periodici e fonti spenti)"
  fi
fi

# 5. archivio delle statistiche
if [ -f "$DEST/dati/fanta.sqlite" ]; then
  dico "archivio delle statistiche: c'e' gia' (lo rifa' ogni notte copia-archivio-prova.sh)"
elif [ "$PROVA" = 1 ]; then
  dico "copierei $PRODUZIONE/dati/fanta.sqlite in $DEST/dati/fanta.sqlite (produzione solo letta, senza gli esiti della sentinella)"
else
  bash "$DEST/script/server/prova/copia-archivio-prova.sh" \
    || ferma "prima copia dell'archivio non riuscita (motivo qui sopra): rilancia lo script, riprende da qui"
fi

# 6. stato degli aggiornamenti della prova
if [ "$PROVA" = 1 ]; then
  dico "scriverei in $STATO ultimo-rilascio e verificato = ${commit:0:7} (solo se mancano)"
else
  mkdir -p "$STATO"
  for f in ultimo-rilascio verificato; do
    [ -s "$STATO/$f" ] || echo "$commit" > "$STATO/$f"
  done
  dico "fatto. Prossimo passo: il servizio (script/server/prova/LEGGIMI.md, passo 4.4)"
fi
exit 0
