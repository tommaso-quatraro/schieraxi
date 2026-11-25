"""Riconoscimento del regolamento incollato da Leghe (testo di esempio verosimile, il formato vero può differire)."""
import random
import re
import time
from pathlib import Path

import pytest

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
    v = _per_chiave(regole_testo.interpreta("Panchina libera, senza vincoli di ruolo\nCrediti iniziali: 500\nCrediti residui alla giornata 3"))
    assert v["panchina.tipo"] == "libera" and v["crediti_iniziali"] == 500


def test_intervalli_e_negazioni_non_creano_valori_sbagliati():
    r = regole_testo.interpreta("Modificatore difesa attivo\nMedia 6-6,5: +1\nMedia difensori minimo 6,5\nNon sono ammessi i moduli 5-2-3, 3-3-4")
    v = _per_chiave(r)
    assert "modificatore_difesa.soglie" not in v and "modificatore_difesa.min_difensori" not in v and "moduli" not in v
    assert any("6-6,5" in x for x in r["non_riconosciute"])


def test_modificatore_disattivato_e_testo_vuoto():
    v = _per_chiave(regole_testo.interpreta("Modificatore difesa: non attivo"))
    assert v["modificatore_difesa.attivo"] is False
    assert regole_testo.interpreta("") == {"modifiche": [], "non_riconosciute": [], "da_controllare": []}


def test_posti_della_panchina_dal_testo():
    v = _per_chiave(regole_testo.interpreta("Panchina: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti"))
    assert v["panchina.posti"] == {"P": 2, "D": 3, "C": 3, "A": 3} and v["panchina.numero"] == 11


# ---------------------------------------------------------------- negazioni con parole in mezzo (#655)
# Frasi inventate, scritte nei modi in cui si trovano nei regolamenti: «non» con «è», «sono», «mai», «si» in mezzo.
CAMBIO_MODULO_NEGATO = [
    "Cambio modulo: non è consentito",
    "Il cambio di modulo non è ammesso",
    "Le sostituzioni sono al massimo 5 e non è consentito il cambio modulo",
    "Non è consentito il cambio modulo",
    "Cambi di modulo: non sono ammessi",
    "Cambi di modulo non sono consentiti",
    "Cambio modulo: non previsto",
    "Cambio modulo: non possibile",
    "Cambio modulo: non utilizzato",
    "Cambio modulo non permesso",
    "Cambio modulo non attivo",
    "Il cambio di modulo non è mai consentito",
    "Il cambio modulo non viene applicato",
    "Il cambio modulo non può essere attivato",
    "Cambio modulo: non si può",
    "Cambio di modulo: non e' consentito",
    "CAMBIO MODULO: NON È AMMESSO",
    "Non è consentito, in nessun caso, il cambio modulo",
]


@pytest.mark.parametrize("riga", CAMBIO_MODULO_NEGATO)
def test_cambio_modulo_negato_anche_con_parole_in_mezzo(riga):
    assert _per_chiave(regole_testo.interpreta(riga))["panchina.cambio_modulo"] is False


MODIFICATORE_NEGATO = [
    "Modificatore difesa: non è attivo",
    "Il modificatore difesa non è previsto",
    "I modificatori di difesa non sono attivi",
    "Modificatore di difesa non utilizzato",
    "Modificatore difesa: non viene applicato",
    "Il modificatore della difesa non si applica",
    "Modificatore difesa: non è in uso",
    "Il modificatore difesa non è stato attivato",
    "Modificatore difesa: non c'è",
    "Modificatore difesa, non attivo",
]


@pytest.mark.parametrize("riga", MODIFICATORE_NEGATO)
def test_modificatore_negato_anche_con_parole_in_mezzo(riga):
    assert _per_chiave(regole_testo.interpreta(riga))["modificatore_difesa.attivo"] is False


MODULI_NEGATI = [
    "Non è ammesso il modulo 5-4-1",
    "Il modulo 5-4-1 non è consentito",
    "Il modulo 3-3-4 non è utilizzabile",
    "Formazione con modulo 4-4-2 non permessa",
    "Il 5-4-1 non va bene come modulo",
    "Moduli: 3-4-3, 4-4-2, 4-3-3 (il 5-4-1 non si può usare)",
    "I moduli 5-4-1 e 3-3-4 non sono validi",
]


@pytest.mark.parametrize("riga", MODULI_NEGATI)
def test_moduli_con_un_non_restano_da_controllare(riga):
    r = regole_testo.interpreta(riga)
    assert "moduli" not in _per_chiave(r)
    assert r["non_riconosciute"] == [riga]


PANCHINA_NEGATA = [
    "Panchina non libera",
    "Panchina: non è libera",
    "Panchina di 7 giocatori, non libera",
    "Panchina non per ruolo",
    "La panchina non è fissa",
    "Le riserve non sono libere",
]


@pytest.mark.parametrize("riga", PANCHINA_NEGATA)
def test_tipo_di_panchina_negato_non_si_riconosce(riga):
    assert "panchina.tipo" not in _per_chiave(regole_testo.interpreta(riga))


@pytest.mark.parametrize("riga", ["La panchina non è vincolata al ruolo", "Panchina: le riserve non sono vincolate al ruolo"])
def test_panchina_non_vincolata_al_ruolo_anche_con_il_verbo_e_libera(riga):
    assert _per_chiave(regole_testo.interpreta(riga))["panchina.tipo"] == "libera"


@pytest.mark.parametrize("riga, chiave", [
    ("Le riserve non sono ammesse oltre la terza e il cambio modulo è consentito", "panchina.cambio_modulo"),
    ("Il cambio modulo non è, in nessun caso, consentito", "panchina.cambio_modulo"),
    ("Cambio modulo: non", "panchina.cambio_modulo"),
    ("Cambio modulo: non attivo; cambio modulo consentito in coppa", "panchina.cambio_modulo"),
    ("Modificatore difesa: non in questa lega", "modificatore_difesa.attivo"),
])
def test_riga_dubbia_non_propone_niente(riga, chiave):
    """Un «sì» e un «non» per la stessa regola, o un «non» senza la parola che nega: la riga non si riconosce."""
    assert chiave not in _per_chiave(regole_testo.interpreta(riga))


# Frasi che si leggevano già bene: la correzione delle negazioni non le cambia.
COME_PRIMA = {
    "Cambio modulo: non consentito": {"panchina.cambio_modulo": False},
    "Cambio modulo consentito": {"panchina.cambio_modulo": True},
    "Il cambio modulo è consentito": {"panchina.cambio_modulo": True},
    "Cambio modulo: sì": {"panchina.cambio_modulo": True},
    "Cambio modulo: no": {"panchina.cambio_modulo": False},
    "Cambio modulo vietato": {"panchina.cambio_modulo": False},
    "Cambio modulo disattivato": {"panchina.cambio_modulo": False},
    "Cambio modulo consentito se il titolare non ha un sostituto nel suo ruolo": {"panchina.cambio_modulo": True},
    "Il cambio modulo è consentito solo se non si superano le 3 sostituzioni":
        {"panchina.max_sostituzioni": 3, "panchina.cambio_modulo": True},
    "Non sono consentite più di 3 sostituzioni, cambio modulo consentito":
        {"panchina.max_sostituzioni": 3, "panchina.cambio_modulo": True},
    "Le riserve non sono ammesse oltre la terza; cambio modulo consentito": {"panchina.cambio_modulo": True},
    "Modificatore difesa": {"modificatore_difesa.attivo": True},
    "Modificatore difesa attivo": {"modificatore_difesa.attivo": True},
    "Modificatore difesa: non attivo": {"modificatore_difesa.attivo": False},
    "Modificatore della difesa: non previsto": {"modificatore_difesa.attivo": False},
    "Modificatore difesa: no": {"modificatore_difesa.attivo": False},
    "Nessun modificatore difesa": {"modificatore_difesa.attivo": False},
    "Modificatore difesa: assente": {"modificatore_difesa.attivo": False},
    "Modificatore difesa disattivato": {"modificatore_difesa.attivo": False},
    "Modificatore difesa (non conta il portiere)": {"modificatore_difesa.attivo": True},
    "Modificatore difesa (non si applica al portiere)": {"modificatore_difesa.attivo": True},
    "Il modificatore della difesa, le riserve non sono consentite": {"modificatore_difesa.attivo": True},
    "Modificatore difesa attivo, non conta il portiere": {"modificatore_difesa.attivo": True},
    "Moduli ammessi: 3-4-3, 4-4-2": {"moduli": ["3-4-3", "4-4-2"]},
    "Moduli ammessi: 343, 352, 433, 442": {"moduli": ["3-4-3", "3-5-2", "4-3-3", "4-4-2"]},
    "Panchina non vincolata al ruolo": {"panchina.tipo": "libera"},
    "Panchina: 7 riserve, non vincolate al ruolo": {"panchina.numero": 7, "panchina.tipo": "libera"},
    "Panchina libera: se un titolare non gioca entra la prima riserva disponibile": {"panchina.tipo": "libera"},
    "Panchina per ruolo: se un titolare non gioca entra la prima riserva del suo ruolo": {"panchina.tipo": "per_ruolo"},
    "Riserve non libere: entrano per ruolo": {"panchina.tipo": "per_ruolo"},
}


@pytest.mark.parametrize("riga", sorted(COME_PRIMA))
def test_frasi_che_si_leggevano_bene_restano_uguali(riga):
    assert _per_chiave(regole_testo.interpreta(riga)) == COME_PRIMA[riga]


# Il «non» di una condizione («quando non è possibile sostituire nel ruolo») dice quando scatta la regola: non la spegne.
# None = nessuna proposta (la regola sta dentro la condizione, o la condizione ha un «no» che non si sa a cosa risponda).
CONDIZIONI = {
    "Il cambio modulo avviene quando non è possibile sostituire il titolare con un giocatore dello stesso ruolo": True,
    "Cambio modulo automatico se il titolare non può essere sostituito nel ruolo": True,
    "Cambio modulo sì quando non si può sostituire nel ruolo": True,
    "Cambio modulo: se non è possibile la sostituzione nello stesso ruolo, si passa a un modulo valido": True,
    "Cambio modulo consentito se il titolare non può essere sostituito nel ruolo": True,
    "Il cambio modulo si applica solo se non è possibile sostituire nel ruolo": True,
    "Cambio modulo consentito quando un titolare non viene utilizzato": True,
    # il «non» della condizione a qualsiasi distanza da «se» o «quando»
    "Il cambio modulo avviene se il titolare rimasto senza voto non può essere sostituito": True,
    "Il cambio modulo avviene quando il giocatore titolare senza voto in pagella non può essere sostituito nel ruolo": True,
    "Cambio modulo automatico se il titolare del ruolo scoperto non può essere sostituito": True,
    "Il cambio modulo è consentito se il titolare non gioca e se non c'è un sostituto": True,
    # un «no» che vale solo in una condizione («non si applica se...») non spegne la regola: nessuna proposta
    "Il cambio modulo non è consentito quando non ci sono riserve": None,
    "Il modificatore difesa non si applica se il portiere non gioca": None,
    "Il modificatore difesa non si applica se in campo ci sono meno di 4 difensori": None,
    "Modificatore difesa: non è attivo quando la difesa non è a 4": None,
    # «se non» come «tranne»
    "Il cambio modulo non è consentito se non quando manca un sostituto del ruolo": None,
    "Il cambio modulo non è previsto, se non per il portiere": None,
    "Cambio modulo vietato se non per infortunio": None,
    "Il modificatore della difesa, se non diversamente stabilito, non si applica": False,
    "In caso di cambio modulo non sono consentite più di 3 sostituzioni": None,
    "Se il titolare non gioca il cambio modulo non è consentito": None,
    # il «3» non lo legge nessuna regola: la riga non propone niente e si controlla (regola dei numeri non spiegati, #884)
    "Modificatore della difesa attivo quando non si usa la difesa a 3": None,
    "Il modificatore difesa si applica se il portiere non prende voto? No": None,
}


@pytest.mark.parametrize("riga", sorted(CONDIZIONI))
def test_il_non_di_una_condizione_non_spegne_la_regola(riga):
    chiave = "modificatore_difesa.attivo" if "modificatore" in riga.lower() else "panchina.cambio_modulo"
    assert _per_chiave(regole_testo.interpreta(riga)).get(chiave) is CONDIZIONI[riga]


# Altri modi di dire sì e no: o il valore giusto, o nessuna proposta (una regola letta male non si applica in silenzio).
ALTRE_FORME = {
    "Moduli: 3-4-3, 4-4-2, 4-3-3 (no 5-4-1)": ("moduli", None),
    "Moduli ammessi 343 442 433, NO 541": ("moduli", None),
    "Moduli ammessi: 3-4-3, 4-4-2 salvo il 5-4-1": ("moduli", None),
    "Modificatore difesa: disabilitato": ("modificatore_difesa.attivo", False),
    "Modificatore difesa: OFF": ("modificatore_difesa.attivo", False),
    "Modificatore difesa: vietato se il titolare non gioca": ("modificatore_difesa.attivo", False),
    "Cambio modulo: OFF": ("panchina.cambio_modulo", False),
    "Cambio modulo disabilitato": ("panchina.cambio_modulo", False),
    "Non è vietato il cambio modulo": ("panchina.cambio_modulo", None),
    "Non c'è nessun modificatore della difesa": ("modificatore_difesa.attivo", False),
    "Modificatore difesa: attivo; modificatore attacco: non attivo": ("modificatore_difesa.attivo", True),
    "Panchina fissa: non si può scegliere l'ordine liberamente": ("panchina.tipo", "per_ruolo"),
    "Panchina libera: no": ("panchina.tipo", None),
    "Panchina libera o per ruolo, a scelta della lega": ("panchina.tipo", None),
    "Panchina: le riserve non sono mai vincolate al ruolo": ("panchina.tipo", "libera"),
}


@pytest.mark.parametrize("riga", sorted(ALTRE_FORME))
def test_altri_modi_di_dire_si_e_no(riga):
    chiave, atteso = ALTRE_FORME[riga]
    r = regole_testo.interpreta(riga)
    assert _per_chiave(r).get(chiave) == atteso and (atteso is not None or chiave != "moduli" or r["non_riconosciute"] == [riga])


# ---------------------------------------------------------------- righe da controllare a mano (#684)
# `da_controllare`: le righe che l'app non ha letto, nell'ordine del testo, ognuna con le regole da impostare a mano. Ci sono le
# righe con numeri non lette (quelle di `non_riconosciute`, che resta per i client di prima) e le righe dubbie anche senza
# numeri: nominano il cambio modulo, il modificatore della difesa o il tipo di panchina senza dirne il valore con sicurezza.
CAMBIO = {"chiave": "panchina.cambio_modulo", "etichetta": "Cambio modulo nelle sostituzioni"}
MODIFICATORE = {"chiave": "modificatore_difesa.attivo", "etichetta": "Modificatore difesa attivo"}
TIPO = {"chiave": "panchina.tipo", "etichetta": "Ordine dei cambi"}


def _dubbie(r):
    """Le righe da controllare che hanno almeno una regola da impostare a mano."""
    return [x["riga"] for x in r["da_controllare"] if x["regole"]]


DUBBIE_SENZA_NUMERI = {
    "Non è vietato il cambio modulo": CAMBIO,
    "Il cambio modulo non è consentito se non quando manca un sostituto": CAMBIO,
    "Il cambio modulo non è consentito quando non ci sono riserve": CAMBIO,
    "Le riserve non sono ammesse oltre la terza e il cambio modulo è consentito": CAMBIO,
    "Cambio modulo: non": CAMBIO,
    "Modificatore difesa: non in questa lega": MODIFICATORE,
    "Il modificatore difesa non si applica se il portiere non gioca": MODIFICATORE,
    "Panchina non libera": TIPO,
    "La panchina non è fissa": TIPO,
    "Panchina libera: no": TIPO,
    "Panchina libera o per ruolo, a scelta della lega": TIPO,
}


@pytest.mark.parametrize("riga", sorted(DUBBIE_SENZA_NUMERI))
def test_riga_dubbia_senza_numeri_e_da_controllare_con_la_sua_regola(riga):
    r = regole_testo.interpreta(riga)
    assert r["da_controllare"] == [{"riga": riga, "regole": [DUBBIE_SENZA_NUMERI[riga]]}]
    assert r["non_riconosciute"] == [] and r["modifiche"] == []


@pytest.mark.parametrize("riga, letto, regola", [
    ("Panchina di 7 giocatori, non libera", {"panchina.numero": 7}, TIPO),
    ("In caso di cambio modulo non sono consentite più di 3 sostituzioni", {"panchina.max_sostituzioni": 3}, CAMBIO),
])
def test_riga_dubbia_letta_in_parte_resta_da_controllare(riga, letto, regola):
    """Il numero si propone; la regola dubbia della stessa riga va impostata a mano: la riga resta da controllare."""
    r = regole_testo.interpreta(riga)
    assert _per_chiave(r) == letto and r["da_controllare"] == [{"riga": riga, "regole": [regola]}]
    assert r["non_riconosciute"] == []


def test_una_riga_con_due_regole_dubbie_le_dice_tutte_e_due():
    riga = "Cambio modulo: non; panchina non libera"
    assert regole_testo.interpreta(riga)["da_controllare"] == [{"riga": riga, "regole": [TIPO, CAMBIO]}]


@pytest.mark.parametrize("riga", [r for r, v in CONDIZIONI.items() if v is None] + PANCHINA_NEGATA
                         + [r for r, (_, v) in ALTRE_FORME.items() if v is None])
def test_ogni_riga_senza_proposta_compare_una_volta_fra_quelle_da_controllare(riga):
    r = regole_testo.interpreta(riga)
    assert [x["riga"] for x in r["da_controllare"]].count(riga) == 1


def test_riga_con_numeri_non_letti_e_dubbia_compare_una_volta_con_la_regola():
    riga = "Il modificatore difesa non si applica se in campo ci sono meno di 4 difensori"
    r = regole_testo.interpreta(riga)
    assert r["non_riconosciute"] == [riga] and r["da_controllare"] == [{"riga": riga, "regole": [MODIFICATORE]}]


def test_riga_con_numeri_non_letti_senza_regole_dubbie():
    r = regole_testo.interpreta("Media 6-6,5: +1")
    assert r["da_controllare"] == [{"riga": "Media 6-6,5: +1", "regole": []}] and r["non_riconosciute"] == ["Media 6-6,5: +1"]


@pytest.mark.parametrize("riga", sorted(COME_PRIMA) + CAMBIO_MODULO_NEGATO + MODIFICATORE_NEGATO + [
    "Panchina: le riserve entrano liberamente", "Panchina: 7 giocatori, no doppioni", "Le riserve non sono ammesse oltre la terza"])
def test_righe_lette_con_sicurezza_o_senza_quelle_regole_non_sono_dubbie(riga):
    assert _dubbie(regole_testo.interpreta(riga)) == []


@pytest.mark.parametrize("riga", ["Riserve libere: no", "Riserve libere: off", "Riserve fisse: no", "Panchina: riserve fisse, no"])
def test_tipo_di_panchina_al_plurale_con_un_no_e_dubbio(riga):
    """Come «Panchina libera: no»: un «no» sul tipo di panchina non dice quale dei due vale, la riga è dubbia, non ignorata."""
    r = regole_testo.interpreta(riga)
    assert "panchina.tipo" not in _per_chiave(r) and r["da_controllare"] == [{"riga": riga, "regole": [TIPO]}]


# Il tipo di panchina al plurale si legge come al singolare: stessa proposta, o stessa riga dubbia.
SINGOLARE_PLURALE = [
    ("Panchina libera", "Riserve libere", "libera"),
    ("La riserva è libera", "Le riserve sono libere", "libera"),
    ("Panchina fissa", "Riserve fisse", "per_ruolo"),
    ("La panchina è fissa", "Le panchine sono fisse", "per_ruolo"),
    ("Riserva non libera: entra per ruolo", "Riserve non libere: entrano per ruolo", "per_ruolo"),
    ("Panchina non fissa: riserva libera", "Riserve non fisse: libere", "libera"),
    ("Panchina libera: no", "Riserve libere: no", None),
    ("Panchina non libera", "Riserve non libere", None),
    ("La panchina non è fissa", "Le riserve non sono fisse", None),
]


@pytest.mark.parametrize("singolare, plurale, atteso", SINGOLARE_PLURALE)
def test_tipo_di_panchina_al_plurale_come_al_singolare(singolare, plurale, atteso):
    s, p = regole_testo.interpreta(singolare), regole_testo.interpreta(plurale)
    assert _per_chiave(s).get("panchina.tipo") == atteso and _per_chiave(p).get("panchina.tipo") == atteso
    assert bool(_dubbie(s)) is bool(_dubbie(p)) is (atteso is None)


# «nessun» dice no solo subito prima del nome della regola («Nessun cambio modulo», «Non c'è nessun modificatore della difesa»),
# in «in nessun caso» e da solo («Cambio modulo: nessuno»). Dentro una condizione dice quando scatta la regola, come un «non».
# Altrove non si sa a cosa risponda («nessun divieto» vuol dire sì): la riga è da controllare, senza proposta.
NESSUNO = {
    "Nessun cambio modulo": ("panchina.cambio_modulo", False),
    "Nessun cambio di modulo consentito": ("panchina.cambio_modulo", False),
    "Cambio modulo: nessuno": ("panchina.cambio_modulo", False),
    "Cambio modulo consentito in nessun caso": ("panchina.cambio_modulo", False),
    "Nessun modificatore difesa": ("modificatore_difesa.attivo", False),
    "Modificatore difesa: nessuno": ("modificatore_difesa.attivo", False),
    "Cambio modulo consentito se non c'è nessun sostituto nel ruolo": ("panchina.cambio_modulo", True),
    "Il cambio modulo avviene quando nessun giocatore della panchina può sostituire il titolare": ("panchina.cambio_modulo", True),
    "Modificatore della difesa attivo quando nessun difensore resta senza voto": ("modificatore_difesa.attivo", True),
    # un no che vale solo in un caso, come «non è consentito quando non ci sono riserve»: nessuna proposta
    "Nessun cambio modulo quando non ci sono riserve": ("panchina.cambio_modulo", None),
    "Nessun cambio modulo se il titolare gioca": ("panchina.cambio_modulo", None),
    # «nessun» davanti ad altro: su main molte davano sì (giusto); un no qui salverebbe la regola al contrario
    "Nessun divieto di cambio modulo": ("panchina.cambio_modulo", None),
    "Cambio modulo: nessun divieto": ("panchina.cambio_modulo", None),
    "Cambio modulo consentito: nessun divieto": ("panchina.cambio_modulo", None),
    "Nessun impedimento al cambio modulo": ("panchina.cambio_modulo", None),
    "Cambio modulo: nessun ostacolo": ("panchina.cambio_modulo", None),
    "Nessun problema per il cambio modulo": ("panchina.cambio_modulo", None),
    "Nessun tetto al cambio modulo": ("panchina.cambio_modulo", None),
    "Cambio modulo: nessun obbligo": ("panchina.cambio_modulo", None),
    "Cambio modulo: nessuna condizione": ("panchina.cambio_modulo", None),
    "Non c'è nessun divieto al cambio modulo": ("panchina.cambio_modulo", None),
    "Cambio modulo: nessun limite": ("panchina.cambio_modulo", None),
    "Cambio modulo consentito senza nessuna eccezione": ("panchina.cambio_modulo", None),
    "Nessuna sostituzione con cambio modulo": ("panchina.cambio_modulo", None),
    "Modificatore difesa attivo con nessun difensore sotto il 6": ("modificatore_difesa.attivo", None),
    # «in nessun caso» con un altro «nessun» (doppia negazione): non è un no sicuro
    "Nessun divieto di cambio modulo in nessun caso": ("panchina.cambio_modulo", None),
    "Cambio modulo: nessun divieto in nessun caso": ("panchina.cambio_modulo", None),
    "Non c'è nessun divieto al cambio modulo in nessun caso": ("panchina.cambio_modulo", None),
    "Nessun cambio modulo in nessun caso": ("panchina.cambio_modulo", False),
    "Il cambio modulo non è consentito senza nessuna eccezione": ("panchina.cambio_modulo", False),
    # un no detto con altre parole resta no anche con un «nessun» accanto (su main era già no)
    "Cambio modulo vietato senza nessuna eccezione": ("panchina.cambio_modulo", False),
    "Modificatore difesa assente senza nessuna eccezione": ("modificatore_difesa.attivo", False),
    "Modificatore difesa: no senza nessuna eccezione": ("modificatore_difesa.attivo", False),
}


@pytest.mark.parametrize("riga", sorted(NESSUNO))
def test_nessun_dice_no_solo_prima_della_regola(riga):
    chiave, atteso = NESSUNO[riga]
    r = regole_testo.interpreta(riga)
    assert _per_chiave(r).get(chiave) is atteso
    if atteso is None:                              # senza proposta: la riga è fra quelle da controllare, con la sua regola
        assert any(x["riga"] == riga and chiave in [g["chiave"] for g in x["regole"]] for x in r["da_controllare"])


def test_righe_da_controllare_nell_ordine_del_testo():
    """Righe con numeri non lette e righe dubbie mescolate come nel testo incollato, non un elenco dopo l'altro."""
    r = regole_testo.interpreta(ESEMPIO + "\nPanchina non libera\nMedia 6-6,5: +1\nNon è vietato il cambio modulo")
    assert [x["riga"] for x in r["da_controllare"]] == [
        "Il campionato inizia il 24 agosto 2026", "Panchina non libera", "Media 6-6,5: +1", "Non è vietato il cambio modulo"]
    assert r["non_riconosciute"] == ["Il campionato inizia il 24 agosto 2026", "Media 6-6,5: +1"]


def test_righe_dubbie_al_massimo_30_oltre_a_quelle_con_numeri():
    testo = "Telefono 081 1234\n" * 30 + "Cambio modulo: non\n" * 40
    r = regole_testo.interpreta(testo)
    assert len(r["non_riconosciute"]) == 30 and len(r["da_controllare"]) == 60 and len(_dubbie(r)) == 30


# ---------------------------------------------------------------- testi costruiti male: la lettura resta veloce
N = 10_000
# Una riga di circa N caratteri per ogni forma che faceva lavorare le espressioni regolari in tempo quadratico (lunghe file di spazi,
# di cifre o di parole ripetute dopo una parola chiave).
CATTIVI = {
    "spazi dopo gol": "gol:" + " " * N + "x",
    "spazi dopo i ruoli del gol": "gol portieri difensori centrocampisti attaccanti" + " " * N + "x",
    "spazi dopo un ruolo": "portieri" + " " * N + "x",
    "spazi nel modificatore": "modificatore difesa\nmedia" + " " * N + "x",
    "parola rigore ripetuta": "rigor" * (N // 5),
    "parola portiere ripetuta": "portier" * (N // 7),
    "parola difensore ripetuta": "modificatore difesa\n" + "difensor" * (N // 8),
    "parola minimo ripetuta": "modificatore difesa\n" + "minim" * (N // 5),
    "parola segnato ripetuta": "gol x" + " " * 50 + "segnat" * (N // 6),
    "parola panchina ripetuta": "panchin" * (N // 7),
    "parola massimo ripetuta": "sostituzioni " + "massim" * (N // 6),
    "parola vincolata ripetuta": "panchina " + "vincolat" * (N // 8),
    "cifre prima delle sostituzioni": "sostituzioni " + "1" * N + "x",
    "cifre prima della panchina": "panchina x" + "1" * N + "x",
    "segni e spazi": "assist " + "- " * (N // 2),
    "lettere che si allungano": "gol: " + "ﷺ" * (N // 2),
    "parola non ripetuta": "cambio modulo " + "non " * (N // 4),
    "negazioni ripetute": "modificatore difesa " + "non e consentito " * (N // 17),
    "negazioni di panchina ripetute": "panchina " + "non e libera, " * (N // 14),
    "spazi dopo non": "panchina libera, cambio modulo non" + " " * N + "x",
    "cambio modulo in tanti pezzi": "cambio modulo, " * (N // 15) + "non e consentito",
    "modificatore in tanti pezzi": "modificatore difesa; " * (N // 21) + "attivo",
    "condizioni ripetute": "cambio modulo consentito " + "quando se non " * (N // 14),
    "parola nessun ripetuta": "cambio modulo consentito se " + "nessun " * (N // 7),
    "nessun e limite ripetuti": "nessun cambio modulo " + "nessun limite " * (N // 14),
    "negazioni del punteggio ripetute": "assist " + "non e il nessun " * (N // 16),
    "squadra composta ripetuta": "3 portieri, squadra " + "e la squadra " * (N // 13) + "composta",
}


@pytest.mark.parametrize("nome", sorted(CATTIVI))
def test_testo_costruito_male_si_legge_in_tempo_lineare(nome, monkeypatch):
    """Il riconoscimento non deve fermare il server: anche una riga lunga e fatta apposta si legge in pochi millesimi."""
    monkeypatch.setattr(regole_testo, "MAX_RIGA", 10**6, raising=False)     # senza il tetto per riga: conta solo la velocità
    inizio = time.perf_counter()
    regole_testo.interpreta(CATTIVI[nome])
    assert time.perf_counter() - inizio < 0.2, nome


def test_il_testo_piu_lungo_permesso_si_legge_in_fretta():
    """Con i tetti veri: il testo più lungo che si può mandare, fatto di righe lunghe al massimo e costruite male."""
    riga = "gol portieri difensori centrocampisti attaccanti" + " " * (regole_testo.MAX_RIGA - 49) + "x"
    testo = "\n".join([riga] * (regole_testo.MAX_TESTO // (len(riga) + 1)))
    assert len(testo) <= regole_testo.MAX_TESTO
    inizio = time.perf_counter()
    regole_testo.interpreta(testo)
    assert time.perf_counter() - inizio < 0.6


@pytest.mark.parametrize("cifre", [1900, 5000])
def test_numeri_lunghissimi_non_sono_valori_e_non_fanno_errori(cifre, monkeypatch):
    monkeypatch.setattr(regole_testo, "MAX_RIGA", 10**6, raising=False)
    r = regole_testo.interpreta("\n".join(f"{riga} {'9' * cifre}" for riga in (
        "Panchina:", "Sostituzioni massime", "Crediti iniziali", "Assist +", "Gol: portiere 3, difensore")))
    assert _per_chiave(r) == {"bonus.gol.P": 3}


def test_testo_troppo_lungo_errore_chiaro():
    regole_testo.interpreta("Assist +1\n" * (regole_testo.MAX_TESTO // 10))            # al limite: si legge
    with pytest.raises(regole_testo.TestoTroppoLungo, match="regolamento è troppo lungo"):
        regole_testo.interpreta("Assist +1\n" * (regole_testo.MAX_TESTO // 10 + 1))


def test_riga_troppo_lunga_errore_chiaro():
    regole_testo.interpreta("Assist +1 " + "x" * (regole_testo.MAX_RIGA - 10))          # al limite: si legge
    with pytest.raises(regole_testo.TestoTroppoLungo, match="riga del regolamento è troppo lunga"):
        regole_testo.interpreta("Gol +3\nAssist +1 " + "x" * (regole_testo.MAX_RIGA - 9))


VECCHIO_NUM = r"[+\-−–]?\s*\d+(?:[.,]\d+)?"          # l'espressione di prima, per confronto: deve trovare gli stessi numeri
VECCHIO_RUOLO = r"(portier\w*|difensor\w*|centrocamp\w*|attaccant\w*)\s*[:=]?\s*(\d{1,2})\b"


def test_stessi_numeri_di_prima_su_testi_brevi_a_caso():
    """Su testi brevi (dove la vecchia espressione era veloce) i numeri trovati e il loro valore restano identici."""
    caso = random.Random(480)
    alfabeto = " \t-+12345.,:=ax"            # il testo arriva già normalizzato: «−» e «–» sono diventati «-»
    pezzi = ["portieri", "difensore", "centrocampisti", "attaccante", "portier", " ", "  ", "\t", ":", "=", "3", "12", "123", "x", "-", ","]
    for _ in range(20_000):
        s = "".join(caso.choice(alfabeto) for _ in range(caso.randint(0, 14)))
        nuovi = [regole_testo._numero(x) for x in re.findall(regole_testo.NUM, s)]
        vecchi = [regole_testo._numero(x) for x in re.findall(VECCHIO_NUM, s)]
        assert nuovi == vecchi, repr(s)
        s = "".join(caso.choice(pezzi) for _ in range(caso.randint(0, 6)))
        if max(map(len, re.findall(r"\w+", s)), default=0) > 25:      # parole vere: dopo la radice al massimo 20 lettere
            continue
        m_nuovo, m_vecchio = re.search(regole_testo.RUOLO_ROSA, s), re.search(VECCHIO_RUOLO, s)
        assert (m_nuovo and m_nuovo.groups()) == (m_vecchio and m_vecchio.groups()), repr(s)


# ---------------------------------------------------------------- regolamento incollato: gol, rosa, titoli, righe lette in parte (#881)
# Il testo di un regolamento inventato (tests/dati), scritto come quelli veri: titoli con il numero dell'articolo, una riga di rosa
# con tutti i ruoli, il gol con l'eccezione del portiere fra parentesi.
REGOLAMENTO_INVENTATO = (Path(__file__).parent / "dati" / "regolamento_inventato.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("riga", [
    "Gol segnato: +3 punti (il gol del portiere vale +5)",
    "Gol: +3 (portiere +5)",
    "Gol: 3 punti; portiere: 5 punti",
])
def test_gol_con_l_eccezione_di_un_ruolo_vale_per_tutti_gli_altri(riga):
    """Il primo numero è il gol di tutti i ruoli, quello dopo il ruolo citato vale solo per quel ruolo."""
    v = _per_chiave(regole_testo.interpreta(riga))
    assert (v["bonus.gol.P"], v["bonus.gol.D"], v["bonus.gol.C"], v["bonus.gol.A"]) == (5, 3, 3, 3)


def test_gol_con_due_numeri_prima_del_ruolo_non_si_indovina():
    """«3 punti, 5 per il portiere»: non si sa quale numero vada al portiere, la riga resta da controllare senza proposte."""
    riga = "Gol: 3 punti, 5 per il portiere"
    r = regole_testo.interpreta(riga)
    assert not any(k.startswith("bonus.gol.") for k in _per_chiave(r))
    assert [x["riga"] for x in r["da_controllare"]] == [riga]


@pytest.mark.parametrize("riga, attesa", [
    ("Rosa: portieri 3, difensori 9, centrocampisti 9, attaccanti 5", (3, 9, 9, 5)),
    ("Portieri 3 difensori 8 centrocampisti 8 attaccanti 6", (3, 8, 8, 6)),
    ("Ogni squadra è composta da 3 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti.", (3, 8, 8, 6)),
])
def test_la_rosa_su_una_riga_si_legge_tutta(riga, attesa):
    r = regole_testo.interpreta(riga)
    v = _per_chiave(r)
    assert (v["rosa.P"], v["rosa.D"], v["rosa.C"], v["rosa.A"]) == attesa
    assert r["da_controllare"] == [] and r["non_riconosciute"] == []


@pytest.mark.parametrize("riga", [
    "Assist: +1 (assist da fermo +0,5)",
    "Rosa: portieri 3, difensori 9 (10 nelle leghe a 12 squadre)",
    "Modificatore difesa attivo con almeno 4 difensori",
])
def test_riga_letta_solo_in_parte_non_propone_niente_e_va_controllata(riga):
    """Una riga propone valori solo se ogni suo numero è letto da una proposta: con un numero rimasto fuori non si propone niente
    e la riga va fra quelle da controllare (decisione del coordinatore sulla #884)."""
    r = regole_testo.interpreta(riga)
    assert _per_chiave(r) == {}
    assert r["da_controllare"] == [{"riga": riga, "regole": []}] and r["non_riconosciute"] == [riga]


@pytest.mark.parametrize("riga", [
    "ART. 2 - PUNTEGGI", "Art. 4 – Formazione e panchina", "Articolo 3: modificatore", "Capitolo 1", "2) Rosa", "3. Panchina",
    "REGOLAMENTO LEGA DEGLI ESEMPI INVENTATI 2026/27", "Stagione 2026-2027",
])
def test_i_titoli_non_sono_righe_da_controllare(riga):
    """Il numero dell'articolo o la stagione non sono valori di regola: un titolo senza altri numeri non si controlla a mano."""
    r = regole_testo.interpreta(riga)
    assert r["da_controllare"] == [] and r["non_riconosciute"] == []


@pytest.mark.parametrize("riga, letto", [
    ("1. Assist: +1", {"bonus.assist": 1}),
    ("2. Crediti iniziali: 500", {"crediti_iniziali": 500}),
    ("Art. 5 - Sostituzioni massime: 3", {"panchina.max_sostituzioni": 3}),
])
def test_il_numero_del_titolo_non_si_legge_come_valore(riga, letto):
    r = regole_testo.interpreta(riga)
    assert _per_chiave(r) == letto and r["da_controllare"] == []


def test_regolamento_inventato_con_titoli_rosa_e_gol():
    r = regole_testo.interpreta(REGOLAMENTO_INVENTATO)
    v = _per_chiave(r)
    assert (v["rosa.P"], v["rosa.D"], v["rosa.C"], v["rosa.A"]) == (3, 9, 9, 5)
    assert (v["bonus.gol.P"], v["bonus.gol.D"], v["bonus.gol.C"], v["bonus.gol.A"]) == (5, 3, 3, 3)
    assert [x["riga"] for x in r["da_controllare"]] == ["Assist: +1 (assist da fermo +0,5)"]


# Revisione della #884: righe che si leggevano male. Meglio una riga da controllare a mano che un valore sbagliato.
def _solo_da_controllare(riga, chiavi=None):
    r = regole_testo.interpreta(riga)
    proposte = _per_chiave(r)
    assert (not proposte) if chiavi is None else not any(k.startswith(chiavi) for k in proposte), proposte
    assert [x["riga"] for x in r["da_controllare"]] == [riga]


@pytest.mark.parametrize("riga", ["(+3) Gol segnato", "(-1) Espulsione", "(+1) Assist"])
def test_il_valore_fra_parentesi_in_testa_non_e_il_numero_di_un_elenco(riga):
    """«(+3)» in testa alla riga è il valore, non il numero dell'elenco come «3)»: la riga non si svuota e resta da controllare."""
    _solo_da_controllare(riga)


@pytest.mark.parametrize("riga", [
    "La formazione titolare è composta da 1 portiere, 4 difensori, 4 centrocampisti e 2 attaccanti",
    "Il modulo base è composto da 4 difensori, 4 centrocampisti e 2 attaccanti",
    "Moduli: difensori 3-5, centrocampisti 3-5, attaccanti 1-3",
])
def test_formazione_e_moduli_non_sono_la_rosa(riga):
    _solo_da_controllare(riga, "rosa.")


def test_la_squadra_composta_da_e_la_rosa():
    v = _per_chiave(regole_testo.interpreta("La squadra è composta da 3 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti"))
    assert (v["rosa.P"], v["rosa.D"], v["rosa.C"], v["rosa.A"]) == (3, 8, 8, 6)


@pytest.mark.parametrize("riga", [
    "Gol: +3 (anche per il portiere)",
    "Gol segnato: +3 (doppio per il portiere)",
    "Gol segnato: +3 punti, compreso il portiere",
])
def test_gol_con_un_numero_prima_del_ruolo_e_nessuno_dopo_non_si_indovina(riga):
    """Il portiere citato dopo l'unico numero può essere un'eccezione, un'aggiunta o un multiplo: la riga si controlla a mano."""
    _solo_da_controllare(riga, "bonus.gol.")


@pytest.mark.parametrize("riga, chiave", [
    ("L'assist non dà bonus, il gol vale 3", "bonus.assist"),
    ("Nessun malus per l'autogol, ammonizione -0,5", "bonus.autogol"),
    ("Nessun bonus per il gol del portiere, gli altri +3", "bonus.gol."),
])
def test_una_regola_negata_non_prende_il_numero_di_un_altra(riga, chiave):
    _solo_da_controllare(riga, chiave)


def test_i_crediti_si_leggono_subito_prima_o_dopo_la_parola():
    assert _per_chiave(regole_testo.interpreta("Crediti iniziali: 500"))["crediti_iniziali"] == 500
    assert _per_chiave(regole_testo.interpreta("Si parte con 500 crediti"))["crediti_iniziali"] == 500


# ---------------------------------------------------------------- corpus delle revisioni (#881, PR #884)
# Tutte le righe viste dai revisori, con il risultato atteso: le proposte (vuoto = nessuna) e se la riga va fra quelle da
# controllare a mano. La regola: una proposta solo quando la riga è inequivocabile; nel dubbio nessuna proposta e la riga si
# controlla. Una riga che dà un valore sicuro ma ha anche numeri non letti propone quel valore e va controllata.
def _gol(p, d, c, a):
    return {"bonus.gol.P": p, "bonus.gol.D": d, "bonus.gol.C": c, "bonus.gol.A": a}


def _rosa(p, d, c, a):
    return {"rosa.P": p, "rosa.D": d, "rosa.C": c, "rosa.A": a}


CORPUS = {
    # titoli e numeri d'elenco
    "2. Crediti iniziali: 500": ({"crediti_iniziali": 500}, False),
    "2.1 Crediti iniziali: 500": ({}, True),
    "2.1. Crediti iniziali: 500": ({"crediti_iniziali": 500}, False),
    "- 2. Crediti iniziali: 500": ({"crediti_iniziali": 500}, False),
    "Art. 3: il gol vale 3 punti": ({}, True),
    "Art. 3 - Gol: +3": (_gol(3, 3, 3, 3), False),
    "Art.4 Assist +1": ({"bonus.assist": 1}, False),
    "3) Panchina: 7 giocatori": ({"panchina.numero": 7}, False),
    "3) Gol: +3": (_gol(3, 3, 3, 3), False),
    "(+3) Gol segnato": ({}, True),
    "(-1) Espulsione": ({}, True),
    "(+1) Assist": ({}, True),
    "(3) Gol segnato": ({}, True),
    "+3 Gol segnato": ({}, True),
    "1) +1 assist": ({}, True),
    "[2] Rosa": ({}, False),
    "Cap. 2 - Ammonizione -0,5": ({"bonus.ammonizione": -0.5}, False),
    "Stagione 2026/27: crediti iniziali 1000": ({"crediti_iniziali": 1000}, False),
    # crediti: il numero subito prima di «crediti», altrimenti il primo dopo
    "Ogni squadra ha a disposizione 500 crediti per acquistare 25 giocatori": ({}, True),
    "Si parte con 1000 crediti, piu' 50 per ogni giornata vinta": ({}, True),
    "Budget iniziale: 500 crediti (minimo 1 per giocatore)": ({}, True),
    "Ogni allenatore parte con 300 crediti": ({"crediti_iniziali": 300}, False),
    # gol
    "Gol segnato: +3 (doppio per il portiere)": ({}, True),
    "Gol segnato: +3 punti, compreso il portiere": ({}, True),
    "Gol: +3 (anche per il portiere)": ({}, True),
    "Gol: +3 (il portiere non ha bonus in piu')": ({}, True),
    "Gol del portiere: +5": ({"bonus.gol.P": 5}, False),
    "Gol: 3 punti (difensore 4,5)": (_gol(3, 4.5, 3, 3), False),
    "Gol segnato: +3; se segna il portiere +5": (_gol(5, 3, 3, 3), False),
    "Gol: +3 (+5 se segna il portiere)": ({}, True),
    "Gol: +3, portiere +5, difensore +4": ({}, True),
    "Gol: attaccante 3, centrocampista 3,5, difensore 4, portiere 5": (_gol(5, 4, 3.5, 3), False),
    "Gol segnato: +3, senza distinzione di ruolo": (_gol(3, 3, 3, 3), False),
    "Gol segnato, senza contare i rigori: +3": ({}, True),
    "Non e' previsto il bonus per il gol del portiere": ({}, True),
    "Nessun bonus per il gol del portiere, gli altri +3": ({}, True),
    # rosa: il numero prima del ruolo solo con «rosa» o «squadra … composta»; un totale diverso dalla somma è un dubbio
    "Rosa di 25 giocatori: 3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti": (_rosa(3, 8, 8, 6), False),
    "La rosa e' composta da 25 giocatori: 3 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti": (_rosa(3, 8, 8, 6), False),
    "Rosa di 26 giocatori: 3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti": ({}, True),
    "La formazione titolare e' composta da 1 portiere, 4 difensori, 4 centrocampisti e 2 attaccanti": ({}, True),
    "Ogni formazione e' composta da 11 giocatori: 1 portiere, 4 difensori, 4 centrocampisti, 2 attaccanti": ({}, True),
    "Il modulo base e' composto da 4 difensori, 4 centrocampisti e 2 attaccanti": ({}, True),
    "Moduli: difensori 3-5, centrocampisti 3-5, attaccanti 1-3": ({}, True),
    "Ogni squadra deve avere almeno 1 portiere in panchina": ({}, True),
    "Ogni squadra puo' sostituire 1 portiere infortunato durante l'anno": ({}, True),
    "Ogni squadra scende in campo con 1 portiere, 4 difensori, 3 centrocampisti e 3 attaccanti": ({}, True),
    "Squadre da 25: 3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti": ({}, True),
    # panchina e cambi
    "Panchina di 12 giocatori: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti": ({}, True),
    "Panchina di 11 giocatori: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti":
        ({"panchina.posti": {"P": 2, "D": 3, "C": 3, "A": 3}, "panchina.numero": 11}, False),
    "Mercato di riparazione: ogni squadra puo' cambiare al massimo 2 difensori": ({}, True),
    # bonus e malus, con i «non» e i «senza» che negano davvero e quelli che fanno parte del nome della regola
    "Portiere imbattuto: +1 (se gioca 90 minuti)": ({}, True),
    "Ammonizione: -0,5 (doppia ammonizione: espulsione -1)": ({}, True),
    "Nessun bonus per l'assist": ({}, True),
    "Assist: nessun bonus": ({}, True),
    "L'assist non da' bonus, il gol vale 3": ({}, True),
    "Nessun malus per l'autogol, ammonizione -0,5": ({"bonus.ammonizione": -0.5}, True),
    "Rigore non realizzato, -3": ({"bonus.rigore_sbagliato": -3}, False),
    "Rigore sbagliato o non segnato, -3": ({"bonus.rigore_sbagliato": -3}, False),
    "Clean sheet (portiere senza gol subiti), +1": ({"bonus.portiere_imbattuto": 1}, False),
    "Portiere imbattuto, senza subire gol: +1": ({"bonus.portiere_imbattuto": 1}, False),
    "Autogol: -2, nessun bonus per l'assist": ({"bonus.autogol": -2}, True),
    "Assist: +1, nessun bonus per l'assist da fermo": ({"bonus.assist": 1}, False),
    "Nessun bonus per l'assist, gol +3": ({}, True),
    "Ammonizione, anche senza giocare: -0,5": ({"bonus.ammonizione": -0.5}, False),
    "Espulsione (non cumulabile), -1": ({"bonus.espulsione": -1}, False),
    "Assist, non da calcio piazzato: +1": ({"bonus.assist": 1}, False),
    "Migliore in campo, se non espulso: +1": ({"bonus.mvp": 1}, False),
    # quarto giro: ogni numero della riga deve essere letto da una proposta (anche ripetuto, anche col segno), altrimenti la
    # riga non propone niente; la forma «ruolo numero» solo su righe di rosa; altre negazioni del punteggio
    "Crediti iniziali: 500 per 8 squadre": ({}, True),
    "Crediti iniziali: 500 (rilancio minimo 1 credito)": ({}, True),
    "Crediti iniziali: 500 (600 crediti con 8 squadre)": ({}, True),
    "Budget: 500; chi entra a meta' stagione parte con 300 crediti": ({}, True),
    "L'autogol non viene penalizzato, ammonizione -0,5": ({"bonus.ammonizione": -0.5}, True),
    "Autogol: nessuna penalita'; espulsione -1": ({"bonus.espulsione": -1}, True),
    "Autogol: non penalizza, ammonizione -0,5": ({"bonus.ammonizione": -0.5}, True),
    "Autogol senza malus, espulsione -1": ({"bonus.espulsione": -1}, True),
    "In campo: portiere 1, difensori 4, centrocampisti 3, attaccanti 3": ({}, True),
    "Gol decisivo per la vittoria: +1, gol segnato: +3": ({}, True),
    "Assist da fermo: +0,5; assist su azione: +1": ({}, True),
    "Gol segnato dal portiere: +5, dagli altri ruoli +3": ({}, True),
    "Gol: +3 punti (+1 se su punizione)": ({}, True),
    "Gol: +3 (+3 su punizione)": ({}, True),
    "Riserve: 7 (massimo 5 cambi)": ({"panchina.numero": 7, "panchina.max_sostituzioni": 5}, False),
    "Rosa: 25 giocatori (3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti)": (_rosa(3, 8, 8, 6), False),
    "Rosa: 3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti; massimo 3 giocatori della stessa squadra": ({}, True),
    "Rosa: portieri 3, difensori 8, centrocampisti 8, attaccanti 6, extracomunitari 2": ({}, True),
    "Ammonizione: nessun malus se seguita da espulsione, altrimenti -0,5": ({}, True),
    "Assist: 0 punti (nessun bonus)": ({"bonus.assist": 0}, False),
    "Zero punti per l'assist, +3 per il gol": ({}, True),
    "Gol: +3; nessun punto in piu' per il portiere": ({}, True),
    "Panchina: 7 giocatori, almeno 1 portiere": ({}, True),
    "Sostituzioni: al massimo 3, anche fuori ruolo": ({"panchina.max_sostituzioni": 3}, False),
    "Cambio modulo non consentito; massimo 3 cambi": ({"panchina.max_sostituzioni": 3, "panchina.cambio_modulo": False}, False),
    "La squadra e' composta da 25 calciatori: 3 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti": (_rosa(3, 8, 8, 6), False),
    "Porta inviolata: +1 (gol subito: -1)": ({}, True),
    "Migliore in campo: +1; peggiore in campo: -1": ({}, True),
}


@pytest.mark.parametrize("riga", list(CORPUS))
def test_corpus_delle_revisioni(riga):
    proposte, da_controllare = CORPUS[riga]
    r = regole_testo.interpreta(riga)
    assert _per_chiave(r) == proposte
    assert (riga in [x["riga"] for x in r["da_controllare"]]) is da_controllare


@pytest.mark.parametrize("riga, regola", [
    ("Nessun bonus per l'assist", "bonus.assist"), ("Assist: nessun bonus", "bonus.assist"),
    ("Autogol: -2, nessun bonus per l'assist", "bonus.assist"), ("Nessun malus per l'autogol, ammonizione -0,5", "bonus.autogol"),
    ("Non e' previsto il bonus per il gol del portiere", "bonus.gol.P"),
])
def test_una_regola_negata_senza_valore_si_imposta_a_mano(riga, regola):
    """«Nessun bonus per l'assist» dice un valore che la riga non scrive: va controllata con la regola da impostare."""
    r = regole_testo.interpreta(riga)
    assert regola in [g["chiave"] for x in r["da_controllare"] for g in x["regole"]]


@pytest.mark.parametrize("posti_salvati", [None, {"P": 2, "D": 3, "C": 3, "A": 3}])
def test_la_panchina_diversa_dalla_somma_dei_posti_letti_non_si_applica(posti_salvati):
    """I posti per ruolo letti nel testo fissano la panchina alla loro somma (11): «La panchina è di 12» non si salverebbe."""
    from fanta.regole import Regole
    attuali = Regole()
    attuali.panchina.posti, attuali.panchina.numero = posti_salvati, 11 if posti_salvati else 7
    r = regole_testo.interpreta("Riserve: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti\nLa panchina è di 12 giocatori",
                                attuali)
    assert _per_chiave(r) == {"panchina.posti": {"P": 2, "D": 3, "C": 3, "A": 3}}
    [na] = r["non_applicabili"]
    assert (na["chiave"], na["valore"], na["motivo_frase"]["chiave"]) == ("panchina.numero", 12, "regole.panchina_somma_posti")
    assert "11" in na["motivo"]
