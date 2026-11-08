#!/bin/bash
# prepara-prova.sh - Una volta, a mano, con l'utente della PROVA (schieraxi-prova, casa /srv/schieraxi-prova; script/server/prova/LEGGIMI.md,
# passo 4.5): prepara l'ambiente di prova in ~/app, una seconda copia dell'app con dati inventati.
#   Uso:  prepara-prova.sh [--prova] COMMIT        (COMMIT = l'ultima versione verificata dalla produzione: cat ~/.cache/fantacalcio/verificato,
#                                                  letta da chi lancia lo script con l'utente della produzione)
# Cosa fa, in ordine (ogni passo solo se manca: rilanciato riprende da dove si era fermato e non cambia quello che c'e' gia'):
#   1. controlli: non e' la casa della produzione, COMMIT ha la forma giusta, il Python c'e', nessun collegamento simbolico al posto dei
#      file che scrive. Clone del codice SUO (~/schieraxi-src, dal repository pubblico): se manca lo crea. COMMIT deve stare nella storia
#      di main. Se qualcosa non torna non scrive niente (al massimo il clone);
#   2. codice di COMMIT (fanta, tests, script, requirements*: le stesse cose che installa aggiorna-app.sh) e la lega d'esempio
#      (lega/esempio, squadre inventate). Mai la lega vera, mai i dati della produzione (la prova non li puo' leggere);
#   3. ambiente Python nuovo con SCHIERAXI_PYTHON (lo stesso Python della produzione) e solo le versioni e gli hash di
#      requirements.txt (pip --require-hashes);
#   4. cartella dati (700) e dati/ambiente.env (600) da ambiente-prova.env.esempio: posta, lavori periodici e fonti spenti;
#   5. prima copia dell'archivio delle statistiche dalla cartella di scambio (copia-archivio-prova.sh): la produzione ce la mette con
#      esporta-archivio-prova.sh (passo 4.4). Se manca si ferma qui;
#   6. stato degli aggiornamenti della prova (~/.cache/schieraxi-prova): ultimo-rilascio e verificato = COMMIT, cosi' aggiorna-app.sh
#      con SCHIERAXI_ISTANZA=prova controlla le firme da li' in avanti.
# Non tocca mai servizi, nginx, sudo e crontab: quelli sono passi a mano.
# Opzione --prova: dice cosa farebbe e non scrive niente.
# Variabili: SCHIERAXI_PYTHON (Python per l'ambiente, predefinito python3), SCHIERAXI_SCAMBIO, SCHIERAXI_REPO, SCHIERAXI_SRC (per le prove).
set -u
export PYTHONUTF8=1     # il server può avere la lingua it_IT (Latin-1): i messaggi con accenti restano giusti
export GIT_TERMINAL_PROMPT=0
PROVA=0
if [ "${1:-}" = --prova ]; then PROVA=1; shift; fi
VERSIONE="${1:-}"
SRC="${SCHIERAXI_SRC:-$HOME/schieraxi-src}"
REPO="${SCHIERAXI_REPO:-https://github.com/tommaso-quatraro/schieraxi.git}"
PY="${SCHIERAXI_PYTHON:-python3}"
SCAMBIO="${SCHIERAXI_SCAMBIO:-/srv/schieraxi-scambio}"
DEST="$HOME/app"
STATO="$HOME/.cache/schieraxi-prova"
PEZZI="fanta tests script requirements.txt requirements-dev.txt lega/esempio"

dico() { if [ "$PROVA" = 1 ]; then echo "[prova] $*"; else echo "$*"; fi; }
ferma() { echo "NON preparo: $*" >&2; exit 1; }
nel_clone() { (cd "$SRC" && git "$@"); }

# 1. controlli
[ -e "$HOME/fantacalcio" ] && ferma "questa e' la casa della produzione: lo script gira con l'utente della prova, schieraxi-prova"
[[ $VERSIONE =~ ^[0-9a-f]{7,40}$ ]] \
  || ferma "manca la versione da installare. Uso: prepara-prova.sh [--prova] COMMIT, con COMMIT = cat ~/.cache/fantacalcio/verificato della produzione"
python_base=$(command -v "$PY") || ferma "non trovo il Python $PY (SCHIERAXI_PYTHON)"
python_base=$(readlink -f "$python_base")
for f in "$DEST/dati/ambiente.env" "$DEST/dati/copia-archivio.log" "$DEST/dati/copia-archivio.log.tmp" "$DEST/dati/fanta.sqlite"; do
  [ -L "$f" ] && ferma "$f e' un collegamento simbolico"
done
commit="$VERSIONE"
if [ ! -d "$SRC/.git" ]; then
  if [ "$PROVA" = 1 ]; then
    dico "creerei il clone $SRC da $REPO e controllerei che ${VERSIONE:0:7} sia nella storia di main"
  else
    timeout -k 5 "${SCHIERAXI_TIMEOUT_GIT:-300}" git clone -q "$REPO" "$SRC" || ferma "clone di $REPO non riuscito (rete?)"
  fi
fi
if [ -d "$SRC/.git" ]; then
  if ! commit=$(nel_clone rev-parse -q --verify "$VERSIONE^{commit}"); then
    [ "$PROVA" = 1 ] || timeout -k 5 "${SCHIERAXI_TIMEOUT_GIT:-300}" bash -c 'cd "$1" && git fetch -q origin main' _ "$SRC"
    commit=$(nel_clone rev-parse -q --verify "$VERSIONE^{commit}") || ferma "la versione ${VERSIONE:0:7} non c'e' nel clone $SRC"
  fi
  main=$(nel_clone show-ref --verify -s refs/remotes/origin/main) || ferma "il ramo origin/main non c'e' nel clone $SRC"
  nel_clone merge-base --is-ancestor "$commit" "$main" || ferma "la versione ${commit:0:7} non e' nella storia di main"
  for p in $PEZZI script/server/prova; do
    nel_clone cat-file -e "$commit:$p" 2>/dev/null || ferma "la versione ${commit:0:7} non contiene $p"
  done
fi
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

# 5. archivio delle statistiche, dalla cartella di scambio
if [ -f "$DEST/dati/fanta.sqlite" ]; then
  dico "archivio delle statistiche: c'e' gia' (lo rifa' ogni notte copia-archivio-prova.sh)"
elif [ "$PROVA" = 1 ]; then
  dico "copierei $SCAMBIO/fanta.sqlite (la copia della produzione, senza gli esiti della sentinella) in $DEST/dati/fanta.sqlite"
elif [ ! -f "$SCAMBIO/fanta.sqlite" ]; then
  ferma "manca la copia della produzione in $SCAMBIO: prima esporta-archivio-prova.sh con l'utente della produzione (passo 4.4), poi rilancia"
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
  dico "fatto. Prossimo passo: il servizio (script/server/prova/LEGGIMI.md, passo 4.6)"
fi
exit 0
