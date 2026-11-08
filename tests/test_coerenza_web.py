"""Web e iPhone uguali (docs/COERENZA-WEB-IPHONE.md, pacchetto 1 della web): numero della giornata della lega, partita
«INT @ MIL · sab 31 20:45», celle «@ MIL» / «vs MIL», «in trasferta contro», stati della partita con le parole del vocabolario,
cognome senza iniziale sul campo, «Ho schierato la consigliata»."""
import json
import re
import shutil
import subprocess

import pytest

import codice_web

APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")
IT, EN = TESTI.split("\n  en: {", 1)


def _testo(blocco: str, chiave: str) -> str:
    return re.search(rf'"{re.escape(chiave)}": "([^"]*)"', blocco).group(1)


def test_giornata_della_lega_dappertutto():
    """Il numero della giornata: dal 5/11/2026 (#299) lega e Serie A insieme, «Giornata 8 · 11ª di Serie A», sempre da `nomeGiornata`.
    I controlli di ogni schermata stanno in tests/test_giornate_lega_serie_a.py; qui resta il nome del file dell'immagine."""
    assert "function nomeGiornata(lega, serieA) {" in APP
    assert "formazione-giornata-${f.giornata_lega || f.giornata}.png" in APP  # immagine da condividere: nome del file corto


def test_partita_nelle_righe_e_nelle_celle():
    assert 'const vsAt = x => `<span aria-hidden="true">${x.in_casa ? "vs" : "@"} ${sigla(x.avversario)}</span>' in APP
    assert "const partitaRiga = x => `${sigla(x.squadra)} ${vsAt(x)}`;" in APP
    assert "const partitaBreve = x => `${partitaRiga(x)} · ${quando(x.data_partita)}`;" in APP
    # per i lettori di schermo la frase intera, «in trasferta contro Genoa», dentro vsAt; mai «GEN fuori» (#453)
    assert APP.count('t(x.in_casa ? "formazione.voce_casa" : "formazione.voce_fuori", { avv: nomeClub(x.avversario) })') == 1
    assert "giocatore.casa" not in APP and "giocatore.fuori" not in APP
    assert APP.count('<span class="cella d${p.difficolta}">${vsAt(p)}</span>') == 2           # calendario e prossime partite
    assert "${sigla(x.squadra)} – ${sigla(x.avversario)}" not in APP


def test_parole_del_vocabolario():
    assert _testo(IT, "mercato.partita_fuori") == "{g} · in trasferta contro {avv} · {quando}"      # {g} = nomeGiornata
    assert "fuori contro" not in TESTI
    attesi = {"oggi.st_senza_voto": "Senza voto", "oggi.st_attesa_voti": "Voto in arrivo", "oggi.st_in_corso": "Partita in corso",
              "oggi.st_rinviata": "Rinviata", "oggi.st_da_giocare": "Da giocare"}
    for chiave, testo in attesi.items():
        assert _testo(IT, chiave) == testo, chiave
        assert _testo(IT, "tit." + chiave.split(".", 1)[1]) == testo                       # stesse parole in Oggi e Formazione
        assert _testo(EN, chiave) == _testo(EN, "tit." + chiave.split(".", 1)[1])
    assert _testo(IT, "diario.ho_schierato_questa") == "Ho schierato la consigliata"


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_sul_campo_il_cognome_senza_iniziale():
    riga = next(r for r in APP.splitlines() if r.startswith("const cognome = x =>"))
    nomi = ["Rossi L.", "Carlos Augusto", "Martinez L.", "Zambo Anguissa", "De Ketelaere", "Chalobah T.", "Gonzalez Ni."]
    r = subprocess.run([NODE, "-e", riga + f"console.log(JSON.stringify({json.dumps(nomi)}.map(n => cognome({{nome: n}}))))"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["Rossi", "Carlos Augusto", "Martinez", "Zambo Anguissa", "De Ketelaere", "Chalobah", "Gonzalez"]
    pedina = APP[APP.index("function pedina("):APP.index("// Legenda del campo")]
    assert "${esc(cognome(x))}" in pedina


def test_seguiti_un_solo_nome():
    for blocco in (IT, EN):
        valori = re.findall(r'"(?:mercato|lega)\.[a-z_.]*osserv[a-z_.]*": "([^"]*)"', blocco)
        assert valori and not [v for v in valori if re.search(r"(?i)osserv|watch", v)], valori
    assert _testo(IT, "mercato.osserva") == "☆ Segui" and _testo(IT, "mercato.osservato") == "★ Seguito"
    assert _testo(IT, "lega.voce_osservati") == "Seguiti"                   # menu e sezioni di Squadra (#458: stessa chiave)
    assert _testo(EN, "mercato.osserva") == "☆ Follow" and _testo(EN, "lega.voce_osservati") == "Following"


def test_plurale_del_bonus_nelle_regole():
    assert _testo(IT, "regole.media_bonus.one").endswith("{b} punto") and _testo(IT, "regole.media_bonus.other").endswith("{b} punti")
    assert '"regole.media_bonus"' not in TESTI
    assert 'tp("regole.media_bonus", Math.abs(b),' in APP          # 1 = «punto», 3,5 = «punti» (Intl.PluralRules), senza arrotondare


def test_crediti_non_salvati_e_ripeti_password_come_iphone():
    assert _testo(IT, "lega.crediti_non_salvati") == "Ci sono crediti scritti e non ancora salvati."
    assert 'id="crediti-non-salvati" role="status" hidden' in APP and 'c.addEventListener("input", segnaModifiche)' in APP
    assert _testo(IT, "account.ripeti_password") == "Ripeti la nuova password"
    assert _testo(IT, "account.password_diverse") == "Le due password non coincidono."
    assert 'campo("acc-ripeti", t("account.ripeti_password")' in APP
    assert 'if (valore("#acc-nuova") !== valore("#acc-ripeti")) {' in APP          # niente richiesta al server se non coincidono


def test_lo_stato_del_giocatore_lo_scrive_il_server():
    """`etichetta` del server (fanta/etichette.py): il web mostra il suo testo con il colore del tono in Formazione, scheda, Rosa,
    Seguiti, Oggi in corso e avvisi di Oggi; le parole composte in JS restano solo come ripiego quando `etichetta` manca."""
    assert 'const CLASSE_TONO = { positivo: "", attenzione: "arancio", negativo: "rossa", neutro: "neutra" };' in APP
    pill = APP[APP.index("function pillTitolarita(x) {"):APP.index("function pillRipiego(x) {")]
    # testoEtichetta protegge il testo come esc e lo divide al «·» per andare a capo (test_etichette_intere_web.py)
    assert "if (etichettaPronta(x)) return" in pill and "testoEtichetta(x.etichetta.testo)" in pill
    assert "!(pronta && motivoDiStato(m))" in APP                                 # niente «infortunato» due volte
    assert 'etichettaPronta(x) ? x.etichetta.testo : t(STATO_PARTITA' in APP     # campo e righe a partita iniziata
    assert 'etichettaPronta(pr) ? esc(pr.etichetta.testo)' in APP                 # scheda
    assert 'if (etichettaPronta(g)) return' in APP                                # Oggi in corso
    assert "const testo = pronta ? esc(a.etichetta.testo)" in APP                # avvisi di Oggi
