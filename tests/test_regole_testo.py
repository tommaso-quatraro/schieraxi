"""Riconoscimento del regolamento incollato da Leghe (testo di esempio verosimile, il formato vero può differire)."""
from fanta import regole_testo

ESEMPIO = """
Bonus e malus
Gol segnato +3
Assist +1
Rigore segnato +3
Rigore parato +3
Rigore sbagliato -3
Autogol -2
Gol subito dal portiere -1
Portiere imbattuto +1
Ammonizione -0,5
Espulsione -1
Moduli ammessi: 3-4-3, 3-5-2, 4-3-3, 4-4-2, 4-5-1, 5-3-2, 5-4-1
Panchina: 7 giocatori, panchina per ruolo
Sostituzioni massime: 3
Cambio modulo consentito
Modificatore difesa attivo
Difensori minimi 4
Media 6 : +1
Media 6,5 : +3
Media 7 : +6
Crediti iniziali: 500
Portieri 3
Difensori 8
Centrocampisti 8
Attaccanti 6
Il campionato inizia il 24 agosto 2026
"""


def _per_chiave(r):
    return {m["chiave"]: m["valore"] for m in r["modifiche"]}


def test_riconosce_bonus_con_il_segno_giusto():
    v = _per_chiave(regole_testo.interpreta(ESEMPIO))
    assert v["bonus.gol.A"] == 3 and v["bonus.gol.P"] == 3
    assert v["bonus.assist"] == 1 and v["bonus.rigore_parato"] == 3
    assert v["bonus.rigore_sbagliato"] == -3 and v["bonus.autogol"] == -2 and v["bonus.gol_subito_portiere"] == -1
    assert v["bonus.ammonizione"] == -0.5 and v["bonus.espulsione"] == -1 and v["bonus.portiere_imbattuto"] == 1


def test_riconosce_moduli_panchina_modificatore_e_rosa():
    v = _per_chiave(regole_testo.interpreta(ESEMPIO))
    assert v["moduli"] == ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"]
    assert v["panchina.numero"] == 7 and v["panchina.tipo"] == "per_ruolo" and v["panchina.max_sostituzioni"] == 3
    assert v["panchina.cambio_modulo"] is True
    assert v["modificatore_difesa.attivo"] is True and v["modificatore_difesa.min_difensori"] == 4
    assert v["modificatore_difesa.soglie"] == [[6, 1], [6.5, 3], [7, 6]]
    assert v["crediti_iniziali"] == 500
    assert (v["rosa.P"], v["rosa.D"], v["rosa.C"], v["rosa.A"]) == (3, 8, 8, 6)


def test_ogni_valore_porta_la_riga_di_origine():
    r = regole_testo.interpreta(ESEMPIO)
    assist = next(m for m in r["modifiche"] if m["chiave"] == "bonus.assist")
    assert assist["riga"] == "Assist +1"


def test_gol_per_ruolo_e_righe_non_riconosciute():
    r = regole_testo.interpreta("Gol del portiere: 6\nGol del difensore 5\nGol dell'attaccante: 3\nTelefono assistenza 081 123456")
    v = _per_chiave(r)
    assert v["bonus.gol.P"] == 6 and v["bonus.gol.D"] == 5 and v["bonus.gol.A"] == 3 and "bonus.gol.C" not in v
    assert "bonus.assist" not in v                       # "assistenza" non è un assist
    assert any("telefono" in x.lower() for x in r["non_riconosciute"])


def test_gol_con_piu_ruoli_nella_stessa_riga():
    v = _per_chiave(regole_testo.interpreta("Gol: portiere 6, difensore 5, centrocampista 4, attaccante 3"))
    assert (v["bonus.gol.P"], v["bonus.gol.D"], v["bonus.gol.C"], v["bonus.gol.A"]) == (6, 5, 4, 3)


def test_imbattuto_non_e_gol_subito_e_assist_da_gol_non_e_gol():
    v = _per_chiave(regole_testo.interpreta("Portiere imbattuto (nessun gol subito): +1\nGol subito: -1\nAssist da gol: +1"))
    assert v["bonus.portiere_imbattuto"] == 1 and v["bonus.gol_subito_portiere"] == -1 and v["bonus.assist"] == 1
    assert not any(k.startswith("bonus.gol.") for k in v)


def test_panchina_libera_e_crediti_non_confusi():
    v = _per_chiave(regole_testo.interpreta("Panchina libera, senza vincoli di ruolo\nCrediti iniziali: 500 per 8 squadre\nCrediti residui alla giornata 3"))
    assert v["panchina.tipo"] == "libera" and v["crediti_iniziali"] == 500


def test_intervalli_e_negazioni_non_creano_valori_sbagliati():
    r = regole_testo.interpreta("Modificatore difesa attivo\nMedia 6-6,5: +1\nMedia difensori minimo 6,5\nNon sono ammessi i moduli 5-2-3, 3-3-4")
    v = _per_chiave(r)
    assert "modificatore_difesa.soglie" not in v and "modificatore_difesa.min_difensori" not in v and "moduli" not in v
    assert any("6-6,5" in x for x in r["non_riconosciute"])


def test_modificatore_disattivato_e_testo_vuoto():
    v = _per_chiave(regole_testo.interpreta("Modificatore difesa: non attivo"))
    assert v["modificatore_difesa.attivo"] is False
    assert regole_testo.interpreta("") == {"modifiche": [], "non_riconosciute": []}


def test_posti_della_panchina_dal_testo():
    v = _per_chiave(regole_testo.interpreta("Panchina: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti"))
    assert v["panchina.posti"] == {"P": 2, "D": 3, "C": 3, "A": 3} and v["panchina.numero"] == 11
