"""Riconoscimento del regolamento incollato da Leghe (testo di esempio verosimile, il formato vero può differire)."""
import random
import re
import time

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
    "Il cambio modulo non è consentito quando non ci sono riserve": False,
    "In caso di cambio modulo non sono consentite più di 3 sostituzioni": None,
    "Se il titolare non gioca il cambio modulo non è consentito": None,
    "Modificatore della difesa attivo quando non si usa la difesa a 3": True,
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
