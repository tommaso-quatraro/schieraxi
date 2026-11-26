#!/bin/bash
# verifica-firme.sh - Si include (source) da aggiorna-app.sh: i commit nuovi di main hanno la firma di una chiave fidata?
# La chiave fidata sta FUORI dal repository, sul server (predefinito ~/.config/schieraxi/chiavi-firma.asc): chi riesce a scrivere
# su main non puo' cambiarla. Oggi e' la chiave pubblica con cui GitHub firma i commit che crea lui (le unioni "squash" delle PR
# e il commit di versione del job rilascia, creato via API): copia di riferimento in script/server/chiavi/github-web-flow.asc.
#
# verifica_catena BASE NUOVO CHIAVI
#   0 se BASE e' un antenato di NUOVO, NUOVO sta nella storia del ramo main di origin (refs/remotes/origin/main, letto con
#   git show-ref --verify; con aggiorna-app.sh NUOVO e' gia' la punta del ramo, il controllo serve a chi la usa con altri commit) e ogni
#   commit della linea principale (--first-parent) dopo BASE, fino a NUOVO compreso, ha una firma valida di una chiave del file CHIAVI;
#   altrimenti 1 e il motivo in MOTIVO_FIRMA. Si lancia dalla radice del clone.
#   Una firma scaduta, revocata, di un'altra chiave, o un commit senza firma: rifiutato. Anche un commit firmato che non sta su main.

_togli_casa_firme() {   # toglie il portachiavi temporaneo e le trap che lo toglievano all'uscita
  rm -rf "$_CASA_FIRME"
  _CASA_FIRME=""
  trap - EXIT HUP INT TERM
}

verifica_catena() {
  local base="$1" nuovo="$2" chiavi="$3" casa c out main
  MOTIVO_FIRMA=""
  if [ -z "$base" ] || ! git cat-file -e "$base^{commit}" 2>/dev/null; then
    MOTIVO_FIRMA="non trovo la versione di partenza '${base:0:7}' (repository nuovo?): controlla e poi usa --fidati"
    return 1
  fi
  if ! git merge-base --is-ancestor "$base" "$nuovo" 2>/dev/null; then
    MOTIVO_FIRMA="main non discende piu' da ${base:0:7}: storia riscritta (force-push?)"
    return 1
  fi
  # il ramo per nome intero con show-ref --verify, che non cerca altri nomi (un tag con un nome simile non prende il suo posto)
  if ! main=$(git show-ref --verify -s refs/remotes/origin/main 2>/dev/null); then
    MOTIVO_FIRMA="il ramo origin/main non esiste nel clone: non installo"
    return 1
  fi
  if ! git merge-base --is-ancestor "$nuovo" "$main" 2>/dev/null; then
    MOTIVO_FIRMA="il commit ${nuovo:0:7} non e' nella storia di main (refs/remotes/origin/main): non lo installo"
    return 1
  fi
  if ! command -v gpg >/dev/null 2>&1; then
    MOTIVO_FIRMA="manca il programma gpg (sudo apt install gnupg)"
    return 1
  fi
  # portachiavi usa e getta con le sole chiavi fidate (percorso relativo: funziona anche con il gpg di Git per Windows nelle prove).
  # Uno nuovo per ogni processo (mktemp -d, 700): un --prova lanciato mentre gira l'aggiornamento non cancella il portachiavi
  # dell'altro, che altrimenti rifiuterebbe una versione buona. Si toglie alla fine, anche se lo script si ferma a meta' (trap).
  casa=$(mktemp -d .git/verifica-firme.XXXXXX) || { MOTIVO_FIRMA="non riesco a creare il portachiavi temporaneo in .git"; return 1; }
  _CASA_FIRME="$casa"
  trap 'rm -rf "$_CASA_FIRME"' EXIT
  trap 'rm -rf "$_CASA_FIRME"; exit 1' HUP INT TERM
  GNUPGHOME="$casa" gpg --batch --no-autostart --quiet --import "$chiavi" >/dev/null 2>&1
  if ! GNUPGHOME="$casa" gpg --batch --no-autostart --list-keys --with-colons 2>/dev/null | grep -q '^pub'; then
    _togli_casa_firme
    MOTIVO_FIRMA="la chiave fidata $chiavi non si legge"
    return 1
  fi
  for c in $(git rev-list --first-parent "$base..$nuovo"); do
    # gpg.program fisso: nessuna impostazione del clone puo' sostituire il programma che controlla le firme
    out=$(GNUPGHOME="$casa" git -c gpg.program=gpg verify-commit --raw "$c" 2>&1)
    if [ $? -ne 0 ] || ! printf '%s\n' "$out" | grep -q '^\[GNUPG:\] GOODSIG ' || ! printf '%s\n' "$out" | grep -q '^\[GNUPG:\] VALIDSIG '; then
      _togli_casa_firme
      MOTIVO_FIRMA="il commit ${c:0:7} non ha una firma valida di una chiave fidata"
      return 1
    fi
  done
  _togli_casa_firme
  return 0
}
