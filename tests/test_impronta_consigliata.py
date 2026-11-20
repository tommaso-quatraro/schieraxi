"""La consigliata già mostrata si ritrova con un'impronta fatta solo di ciò che cambia il calcolo (#780): rosa della squadra, moduli,
panchina, bonus, fonte del voto, modificatore, voto di chi resta senza sostituto e regola dei rinvii di quella giornata.
Prima l'impronta conteneva anche il nome della squadra e tutte le regole (nome della lega, aste, rinvii di ogni giornata...):
cambiando uno di quei campi la consigliata ripartiva da zero, anche a giornata iniziata. Rosa e numeri inventati."""
import hashlib
import json
from dataclasses import replace
from datetime import timedelta

from fanta import consigli, lega
from test_consigliata_stabile import (GIORNATA, PRIMA_PARTITA, SOLO_442, ST, _ids, _prev, _rose,  # noqa: F401
                                      _schede_semplici, _squadra, mondo)

DOPO_LA_SCADENZA = PRIMA_PARTITA + timedelta(minutes=1)


def _nuove_dopo_la_scadenza() -> object:
    """Probabili cambiate dopo la scadenza: da sola la migliore metterebbe l'8 al posto del 7 infortunato."""
    return _prev({8: {"mu": 9.0}, 7: {"stato": "infortunato", "p_voto": 0.0}})


def _panchina(f: dict) -> list[int]:
    return [g["id"] for g in f["panchina"]]


def _chiave_vecchia(stagione: str, giornata: int, s: lega.Squadra, regole, simulazioni: int = 600) -> str:
    """La chiave delle versioni di prima di #780, copiata (non importata da `consigli`): nome della squadra e regole intere."""
    testo = json.dumps([stagione, int(giornata), s.nome, sorted(g.id for g in s.giocatori if g.id is not None), repr(regole),
                        simulazioni], ensure_ascii=False)
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()[:32]


def _salvata_dalla_versione_di_prima(s: lega.Squadra, regole) -> dict:
    """La voce appena ricordata rimessa sotto la chiave vecchia, con un utente, come l'avrebbe lasciata la versione di prima; poi
    il servizio riparte con quella nuova (memoria vuota)."""
    (voce,) = json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8")).values()
    voce |= {"utenti": [5], "proprie": [5]}
    consigli.FILE_CONSIGLIATE.write_text(json.dumps({_chiave_vecchia(ST, GIORNATA, s, regole): voce}), encoding="utf-8")
    consigli._cache.clear()
    return voce


# ---------------------------------------------------------------- l'impronta
def test_l_impronta_non_cambia_con_cio_che_non_tocca_il_calcolo():
    s = _squadra()
    base = consigli._impronta(ST, GIORNATA, s, SOLO_442, 600)
    uguali = {
        "nome della lega": replace(SOLO_442, nome_lega="Nome nuovo della lega"),
        "scadenza": replace(SOLO_442, scadenza_minuti=30),
        "prima giornata": replace(SOLO_442, prima_giornata_lega=3),
        "rinvio di un'altra giornata": replace(SOLO_442, rinvii_giornate={f"{ST}/{GIORNATA + 1}": "senza_voto"}),
        "voto d'ufficio senza voto d'ufficio": replace(SOLO_442, voto_ufficio_rinviate=5.0),
        "crediti": replace(SOLO_442, crediti_iniziali=800),
        "rimborso": replace(SOLO_442, rimborso_svincolo=1.0),
        "giocatori per ruolo": replace(SOLO_442, rosa={"P": 3, "D": 8, "C": 8, "A": 7}),
        "asta": replace(SOLO_442, asta_estiva={"dal": "2026-09-01", "al": None}),
        "finestre": replace(SOLO_442, finestre_scambio=[]),
        "testa a testa": replace(SOLO_442, fattore_campo=2.0, soglia_primo_gol=70.0, ampiezza_fascia_gol=5.0),
        "aggiornamenti vicino alla scadenza": replace(SOLO_442, aggiornamenti_vicino_scadenza=False),
        # la web manda 6 per 6.0, e le fasce del modificatore restano come arrivano: stesso calcolo, stessa impronta
        "numeri senza decimali": replace(SOLO_442, voto_senza_sostituto=None, modificatore_difesa=replace(
            SOLO_442.modificatore_difesa, soglie=[[6, 1], [6.5, 3], [7, 6]])),
    }
    for cosa, regole in uguali.items():
        assert consigli._impronta(ST, GIORNATA, s, regole, 600) == base, cosa
    rinominata = _squadra()
    rinominata.nome = "Nome Nuovo"
    assert consigli._impronta(ST, GIORNATA, rinominata, SOLO_442, 600) == base


def test_l_impronta_cambia_con_cio_che_cambia_il_calcolo():
    s = _squadra()
    diverse = {
        "di partenza": consigli._impronta(ST, GIORNATA, s, SOLO_442, 600),
        "moduli": consigli._impronta(ST, GIORNATA, s, replace(SOLO_442, moduli=["4-3-3"]), 600),
        "fonte del voto": consigli._impronta(ST, GIORNATA, s, replace(SOLO_442, fonte_voto="statistico"), 600),
        "bonus": consigli._impronta(ST, GIORNATA, s, replace(SOLO_442, bonus=replace(SOLO_442.bonus, assist=2.0)), 600),
        "panchina": consigli._impronta(ST, GIORNATA, s, replace(SOLO_442, panchina=replace(SOLO_442.panchina, numero=9)), 600),
        "modificatore": consigli._impronta(ST, GIORNATA, s, replace(
            SOLO_442, modificatore_difesa=replace(SOLO_442.modificatore_difesa, attivo=True)), 600),
        "senza sostituto": consigli._impronta(ST, GIORNATA, s, replace(SOLO_442, voto_senza_sostituto=4.0), 600),
        "rinvio di questa giornata": consigli._impronta(ST, GIORNATA, s, replace(
            SOLO_442, rinvii_giornate={f"{ST}/{GIORNATA}": "senza_voto"}), 600),
        "voto d'ufficio": consigli._impronta(ST, GIORNATA, s, replace(SOLO_442, partite_rinviate="voto_ufficio"), 600),
        "valore del voto d'ufficio": consigli._impronta(ST, GIORNATA, s, replace(
            SOLO_442, partite_rinviate="voto_ufficio", voto_ufficio_rinviate=5.0), 600),
        "rosa della squadra": consigli._impronta(ST, GIORNATA, _squadra(senza=(25,)), SOLO_442, 600),
        "simulazioni": consigli._impronta(ST, GIORNATA, s, SOLO_442, 200),
        "giornata": consigli._impronta(ST, GIORNATA + 1, s, SOLO_442, 600),
        "stagione": consigli._impronta("2027-28", GIORNATA, s, SOLO_442, 600),
    }
    assert len(set(diverse.values())) == len(diverse), diverse


# ---------------------------------------------------------------- la consigliata mostrata resta (#780)
def test_nome_della_lega_cambiato_dopo_la_scadenza_la_consigliata_resta(mondo):  # noqa: F811
    prima = consigli.formazione(mondo["db"], SOLO_442, _rose())
    mondo["adesso"] = DOPO_LA_SCADENZA
    mondo["prev"], mondo["versione"] = _nuove_dopo_la_scadenza(), "v2"
    assert _ids(consigli.formazione(mondo["db"], SOLO_442, _rose())) == _ids(prima)
    dopo = consigli.formazione(mondo["db"], replace(SOLO_442, nome_lega="Nome nuovo della lega"), _rose())
    assert _ids(dopo) == _ids(prima) and _panchina(dopo) == _panchina(prima)


def test_squadra_rinominata_la_consigliata_resta_dopo_un_ritocco(mondo):  # noqa: F811
    prima = consigli.formazione(mondo["db"], SOLO_442, _rose())
    mondo["prev"], mondo["versione"] = _prev({8: {"mu": 6.4}}), "v2"       # l'8 passa davanti al 7 per meno di un punto
    assert _ids(consigli.formazione(mondo["db"], SOLO_442, _rose())) == _ids(prima)
    s = _squadra()
    s.nome = "Nome Nuovo"
    rinominata = consigli.formazione(mondo["db"], SOLO_442, lega.Rose([s], "Nome Nuovo"))
    assert _ids(rinominata) == _ids(prima)


def test_rinvio_di_un_altra_giornata_la_consigliata_resta_dopo_un_ritocco(mondo):  # noqa: F811
    prima = consigli.formazione(mondo["db"], SOLO_442, _rose())
    mondo["prev"], mondo["versione"] = _prev({8: {"mu": 6.4}}), "v2"
    con_rinvio = replace(SOLO_442, rinvii_giornate={f"{ST}/{GIORNATA + 1}": "voto_ufficio"})
    assert _ids(consigli.formazione(mondo["db"], con_rinvio, _rose())) == _ids(prima)


# ---------------------------------------------------------------- al rilascio: le voci salvate con la chiave vecchia
def test_voce_della_versione_di_prima_si_ritrova_a_giornata_iniziata(mondo):  # noqa: F811
    """Rilascio a giornata iniziata: la consigliata congelata alla scadenza era salvata con la chiave vecchia. Non riparte da zero."""
    prima = consigli.formazione(mondo["db"], SOLO_442, _rose())
    _salvata_dalla_versione_di_prima(_squadra(), SOLO_442)
    mondo["adesso"] = DOPO_LA_SCADENZA
    mondo["prev"], mondo["versione"] = _nuove_dopo_la_scadenza(), "v2"
    dopo = consigli.formazione(mondo["db"], SOLO_442, _rose())
    assert _ids(dopo) == _ids(prima) and _panchina(dopo) == _panchina(prima)


def test_voce_della_versione_di_prima_passa_alla_chiave_nuova(mondo):  # noqa: F811
    """Ritrovata con la chiave vecchia, la voce passa a quella nuova così com'è (quando, utenti, proprie): poi un cambio del nome
    della lega, che cambia la chiave vecchia, non la perde più."""
    prima = consigli.formazione(mondo["db"], SOLO_442, _rose())
    voce = _salvata_dalla_versione_di_prima(_squadra(), SOLO_442)
    mondo["adesso"] = DOPO_LA_SCADENZA
    mondo["prev"], mondo["versione"] = _nuove_dopo_la_scadenza(), "v2"
    consigli.formazione(mondo["db"], SOLO_442, _rose())                     # la prima lettura dopo il rilascio
    tutte = json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8"))
    assert tutte == {consigli._impronta(ST, GIORNATA, _squadra(), SOLO_442, 600): voce}
    dopo = consigli.formazione(mondo["db"], replace(SOLO_442, nome_lega="Nome nuovo della lega"), _rose())
    assert _ids(dopo) == _ids(prima) and _panchina(dopo) == _panchina(prima)


def test_la_voce_con_la_chiave_nuova_vince_su_quella_vecchia(mondo):  # noqa: F811
    """Tutte e due nel file (la nuova scritta dopo il rilascio): vale la nuova, e lo spostamento non la sovrascrive."""
    consigli.formazione(mondo["db"], SOLO_442, _rose())
    nuova = json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8"))
    (chiave,) = nuova
    assert nuova[chiave]["titolari"][0] == 1
    vecchia = _chiave_vecchia(ST, GIORNATA, _squadra(), SOLO_442)
    altra = dict(nuova[chiave], titolari=[2] + nuova[chiave]["titolari"][1:])          # un altro portiere: si vedrebbe
    consigli.FILE_CONSIGLIATE.write_text(json.dumps(nuova | {vecchia: altra}), encoding="utf-8")
    assert consigli._sposta_voci({vecchia: chiave}) == 0
    assert json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8")) == nuova | {vecchia: altra}
    consigli._cache.clear()
    mondo["adesso"] = DOPO_LA_SCADENZA                                     # dopo la scadenza resta quella ricordata, com'è
    dopo = consigli.formazione(mondo["db"], SOLO_442, _rose())
    assert 1 in _ids(dopo) and 2 not in _ids(dopo)
