"""Panchina scelta dal sistema quando sono salvati 11 giocatori senza panchina (web e iPhone salvano solo gli 11): il riepilogo di
Oggi la sceglie con i numeri della rosa alla scadenza (#794); il Diario la sceglieva con i numeri rifatti dopo, senza le probabili.
Il totale poteva cambiare quando la giornata entrava nel Diario, e «X è entrato» contraddire quello visto in diretta. Ora tutti e
due usano i numeri della scadenza, se ci sono (`diario.panchina_alla_scadenza`). Dati finti: le fixture del Diario di
test_diario.py (tutti prendono 6, l'attaccante 25 prende 9; numeri rifatti: «gioca 90%», fantavoto atteso 5,5 + id × 0,05)."""
import pytest

from fanta import diario, fasi, scelte
from fanta.regole import Regole

from test_diario import CON_IL_25, RUOLI, ST, _salva, finto, vero  # noqa: F401  (fixture del Diario con dati finti)

ALLORA = [1, 7, 8, 9, 16, 17, 18, 19, 22, 23, 24]           # la consigliata mostrata prima della scadenza: altri 11


def _numero(i: int) -> dict:
    """I numeri di un giocatore alla scadenza: come quelli rifatti, ma il difensore 7 era dato al 95% con 8 di fantavoto atteso
    (le probabili lo davano titolare). Con i numeri rifatti la panchina non ha difensori."""
    return {"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.95 if i == 7 else 0.9, "fv_atteso": 8.0 if i == 7 else 5.5 + i * 0.05}


@pytest.fixture
def giornata_2(vero, monkeypatch):  # noqa: F811 (fixture importata)
    """Giornata 2: la copia alla scadenza (istantanea e numeri di tutta la rosa), i tuoi 11 salvati senza panchina, il difensore 4
    senza voto e il 7 con 8. Oggi conta i voti come il Diario finto (il voto è il fantavoto)."""
    monkeypatch.setattr(diario.ic, "misure", lambda f: None)
    monkeypatch.setattr(fasi, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    f = {"giornata": 2, "modulo": "3-4-3", "punteggio_atteso": 70.0, "livelli": [], "titolari": [_numero(i) for i in ALLORA],
         "panchina": [_numero(i) for i in (2, 10, 11, 12, 13, 20, 21)], "schede": {str(i): _numero(i) for i in range(1, 26)}}
    assert diario.salva_istantanea(f, ST, vero.file)
    scelte.salva(ST, 2, CON_IL_25, "3-4-3", vero.scelte)
    voti = vero.dati.voti
    vero.dati.voti = voti[~((voti["giornata"] == 2) & (voti["calciatore_id"] == 4))].copy()
    vero.dati.voti.loc[(vero.dati.voti["giornata"] == 2) & (vero.dati.voti["calciatore_id"] == 7), "voto_red"] = 8.0
    vero.db.execute(f"DELETE FROM voti WHERE stagione = '{ST}' AND giornata = 2 AND calciatore_id = 4")
    vero.db.execute(f"UPDATE voti SET voto_red = 8.0 WHERE stagione = '{ST}' AND giornata = 2 AND calciatore_id = 7")
    return vero


def test_il_diario_sceglie_la_panchina_con_i_numeri_della_scadenza_come_oggi(giornata_2):
    """Oggi, prima che il Diario calcoli la giornata, fa entrare il 7 al posto del 4: 71 punti. Il Diario prima sceglieva la
    panchina con i numeri rifatti, senza difensori: il 4 restava senza sostituto e i punti erano 63."""
    v = giornata_2
    oggi = fasi.blocco_riepilogo(v.db, Regole(), v.rose, ST, 2, v.scelte, v.file)
    assert oggi["nel_diario"] is False and oggi["punti_fatti"] == 71.0
    diario.aggiorna(v.db, Regole(), v.rose, v.file, simulazioni=50, file_scelte=v.scelte)
    voce = diario.carica(v.file)["giornate"][f"{ST}/2"]
    s = voce["schierata"]
    assert [t["id"] for t in s["titolari"]] == CON_IL_25 and s["reale"] == 71.0
    assert [(e["esce"]["id"], e["entra"]["id"]) for e in s["dettaglio"]["entrati"]] == [(4, 7)]
    assert fasi.blocco_riepilogo(v.db, Regole(), v.rose, ST, 2, v.scelte, v.file)["punti_fatti"] == 71.0       # dal Diario: lo stesso


def test_anche_correggi_e_i_punti_rifatti_usano_i_numeri_della_scadenza(giornata_2):
    """«Non è quello che ho schierato» con gli stessi 11 e i punti rifatti quando cambiano i voti: stessa panchina, stesso numero."""
    v = giornata_2
    assert _salva(v, 2, "manuale", CON_IL_25)["schierata"]["reale"] == 71.0
    voti = v.dati.voti
    voti.loc[(voti["giornata"] == 2) & (voti["calciatore_id"] == 25), "voto_red"] = 10.0         # una correzione dei giorni dopo
    assert diario.aggiorna(v.db, Regole(), v.rose, v.file, simulazioni=50, file_scelte=v.scelte) >= 1
    assert diario.carica(v.file)["giornate"][f"{ST}/2"]["schierata"]["reale"] == 72.0


def test_senza_i_numeri_della_scadenza_la_panchina_e_quella_di_sempre(vero):  # noqa: F811 (fixture importata)
    """Nessuna copia alla scadenza: la panchina del sistema con i numeri rifatti, come prima (qui senza difensori: 63 punti)."""
    voti = vero.dati.voti
    vero.dati.voti = voti[~((voti["giornata"] == 2) & (voti["calciatore_id"] == 4))].copy()
    vero.dati.voti.loc[(vero.dati.voti["giornata"] == 2) & (vero.dati.voti["calciatore_id"] == 7), "voto_red"] = 8.0
    scelte.salva(ST, 2, CON_IL_25, "3-4-3", vero.scelte)
    diario.aggiorna(vero.db, Regole(), vero.rose, vero.file, simulazioni=50, file_scelte=vero.scelte)
    assert diario.carica(vero.file)["giornate"][f"{ST}/2"]["schierata"]["reale"] == 63.0
