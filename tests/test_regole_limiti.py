"""Limiti dei valori delle regole (#881, parte B: punti 5 e 6 del collaudo del 25/11/2026).

5. I limiti dei pulsanti − e + non valevano per i numeri scritti a mano e il server accettava valori assurdi: gol dell'attaccante
   −4, autogol +3, difensori minimi del modificatore 9 (nessun modulo li ha), e via API assist 99, panchina 0, modificatore acceso
   senza fasce, fasce ripetute; i pulsanti arrivavano a valori che il server rifiutava (14 cambi, 0 portieri). Ora i limiti stanno
   in un posto solo, `fanta/web/limiti-regole.json`: li usa il server quando salva e la pagina Regole per i pulsanti e i campi.
6. Gli errori avevano sigle e nomi interni («rosa deve indicare quanti P, D, C, A», «panchina.max_sostituzioni: al massimo 10»)
   ed erano in italiano anche con la web in inglese. Ora sono frasi semplici, ognuna con la sua traduzione nel catalogo.
Il punto 4 (un campo svuotato si salvava come 0) è della pagina: tests/browser/test_regole_limiti.py.
"""
import json
import re
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fanta import archivio, regole, server
from fanta.regole import Regole
from fanta.regole import salva as salva_regole

import codice_web

FILE_LIMITI = server.WEB / "limiti-regole.json"
TESTI_JS = codice_web.leggi("testi.js")

# I limiti scelti (#881): gli stessi dei pulsanti della web e dell'iPhone, più larghi dove i pulsanti erano più stretti di una lega
# vera (crediti, panchina), più stretti dove i pulsanti arrivavano a valori che il server rifiutava (0 portieri, 14 cambi).
# I bonus non sono mai negativi, i malus mai positivi.
SCELTI = {
    **{f"bonus.gol.{r}": (0, 20) for r in "PDCA"},
    **{f"bonus.{k}": (0, 20) for k in ("rigore_segnato", "assist", "rigore_parato", "portiere_imbattuto", "mvp")},
    **{f"bonus.{k}": (-20, 0) for k in ("rigore_sbagliato", "autogol", "gol_subito_portiere", "ammonizione", "espulsione")},
    **{f"rosa.{r}": (1, 30) for r in "PDCA"},
    "crediti_iniziali": (0, 100_000),
    "panchina.numero": (1, 30),
    "panchina.max_sostituzioni": (0, 10),
    **{f"panchina.posti.{r}": (0, 10) for r in "PDCA"},
    "voto_senza_sostituto": (0, 10),
    "voto_ufficio_rinviate": (0, 10),
    "modificatore_difesa.min_difensori": (3, 6),
    "modificatore_difesa.soglie.media": (0, 10),
    "modificatore_difesa.soglie.bonus": (0, 20),
    "fattore_campo": (-100, 100),
    "soglia_primo_gol": (0, 200),
    "ampiezza_fascia_gol": (0, 100),
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    salva_regole(Regole(), tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server.scelte, "FILE_SCELTE", tmp_path / "scelte.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    return TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)


def _con(dati: dict, **cambi) -> dict:
    """Le regole `dati` con dei valori cambiati; la chiave è il percorso con «__» al posto del punto (bonus__gol__A=-4)."""
    nuove = json.loads(json.dumps(dati))
    for chiave, valore in cambi.items():
        nodo = nuove
        *strada, ultima = chiave.split("__")
        for k in strada:
            nodo = nodo[k]
        nodo[ultima] = valore
    return nuove


def _problemi(dati: dict) -> list[str]:
    """Tutti i problemi di queste regole (anche quelli che si guardano solo al salvataggio), senza alzare errori."""
    return regole._da_dict(Regole, dati).problemi()


# ---------------------------------------------------------------- i valori assurdi del collaudo
ASSURDI = [
    ({"bonus__gol__A": -4}, "il bonus per il gol dell'attaccante deve essere tra 0 e 20"),
    ({"bonus__autogol": 3}, "il malus per l'autogol deve essere tra −20 e 0"),
    ({"modificatore_difesa__min_difensori": 9}, "i difensori minimi del modificatore difesa devono essere tra 3 e 6"),
    ({"bonus__assist": 99}, "il bonus per l'assist deve essere tra 0 e 20"),
    ({"panchina__numero": 0}, "i giocatori in panchina devono essere tra 1 e 30"),
    ({"modificatore_difesa__attivo": True, "modificatore_difesa__soglie": []},
     "con il modificatore difesa acceso serve almeno una fascia"),
    ({"modificatore_difesa__soglie": [[6, 1], [6.5, 3], [6, 2]]},
     "due fasce del modificatore difesa hanno la stessa media: togline una"),
    ({"panchina__max_sostituzioni": 14}, "i cambi massimi devono essere tra 0 e 10"),
    ({"rosa__P": 0}, "i portieri della rosa devono essere tra 1 e 30"),
]


@pytest.mark.parametrize("cambi, frase", ASSURDI)
def test_i_valori_assurdi_si_rifiutano_con_una_frase_chiara(client, cambi, frase):
    prima = client.get("/api/regole").json()
    r = client.put("/api/regole", json=_con(prima, **cambi))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == f"Regole non valide:\n- {frase}", r.json()
    assert client.get("/api/regole").json() == prima


def test_difensori_minimi_che_nessun_modulo_ammesso_ha():
    """Con il modificatore acceso, almeno un modulo ammesso deve avere i difensori minimi: altrimenti non si applica mai."""
    base = asdict(Regole())
    tre_e_quattro = _con(base, moduli=["3-4-3", "4-4-2", "4-3-3"], modificatore_difesa__attivo=True,
                         modificatore_difesa__min_difensori=5)
    with pytest.raises(regole.RegoleFuoriIntervallo) as e:
        regole.da_dict(tre_e_quattro)
    assert "nessun modulo ammesso ha almeno 5 difensori: il modificatore difesa non si applicherebbe mai" in str(e.value)
    assert regole.da_dict(_con(tre_e_quattro, modificatore_difesa__min_difensori=4)).problemi() == []
    assert regole.da_dict(_con(tre_e_quattro, modificatore_difesa__attivo=False)).problemi() == []    # spento non conta


def test_i_messaggi_non_hanno_sigle_ne_nomi_interni():
    """Nessun messaggio dei limiti nomina un campo come nel file («panchina.max_sostituzioni», «bonus.gol») o i ruoli con le
    sigle («P, D, C, A»)."""
    base = asdict(Regole())
    messaggi = []
    for cambi, _ in ASSURDI:
        messaggi += _problemi(_con(base, **cambi))
    for chiave, (minimo, _massimo) in SCELTI.items():
        messaggi += _problemi_con(chiave, minimo - 1)
    messaggi += _problemi(_con(base, rosa={"P": 3}))           # rosa senza tutti i ruoli
    assert messaggi
    for m in messaggi:
        assert not re.search(r"[a-z]\.[a-z]|_|\bP, D, C, A\b|\[|\{", m), m


# ---------------------------------------------------------------- un posto solo per i limiti
def test_i_limiti_sono_quelli_scelti_e_stanno_in_un_file_solo():
    """Il file che legge la pagina Regole è lo stesso con cui controlla il server."""
    dal_file = json.loads(FILE_LIMITI.read_text(encoding="utf-8"))
    assert {k: (v["min"], v["max"]) for k, v in dal_file.items()} == SCELTI
    assert regole.LIMITI == dal_file


def _problemi_con(chiave: str, valore) -> list[str]:
    """I problemi delle regole di partenza con un valore cambiato (chiave del file dei limiti), dopo i controlli di tipo."""
    base = asdict(Regole())
    if chiave.startswith("modificatore_difesa.soglie."):
        fascia = [valore, 1] if chiave.endswith(".media") else [6, valore]
        dati = _con(base, modificatore_difesa__soglie=[fascia])
    elif chiave.startswith("panchina.posti."):
        posti = {"P": 2, "D": 3, "C": 3, "A": 3} | {chiave[-1]: valore}
        dati = _con(base, panchina__posti=posti, panchina__numero=sum(posti.values()))
    elif chiave == "voto_senza_sostituto":
        dati = _con(base, voto_senza_sostituto=valore)
    elif chiave in ("rosa.D", "rosa.C", "rosa.A"):        # un modulo che chiede un solo giocatore di quel ruolo
        dati = _con(base, rosa=base["rosa"] | {chiave[-1]: valore}, moduli=[{"D": "1-4-5", "C": "4-1-5", "A": "4-5-1"}[chiave[-1]]])
    else:
        dati = _con(base, **{chiave.replace(".", "__"): valore})
    return _problemi(dati)


def _cifra(n) -> str:
    return ("−" if n < 0 else "") + f"{abs(n):,}".replace(",", ".")


@pytest.mark.parametrize("chiave", sorted(SCELTI))
def test_ogni_limite_vale_quando_si_salva(chiave):
    minimo, massimo = SCELTI[chiave]
    for buono in (minimo, massimo):
        assert _problemi_con(chiave, buono) == [], (chiave, buono)
    for fuori in (minimo - 1, massimo + 1):
        problemi = [p for p in _problemi_con(chiave, fuori) if " tra " in p]          # (0 difensori in rosa: anche i moduli)
        assert len(problemi) == 1 and problemi[0].endswith(f"tra {_cifra(minimo)} e {_cifra(massimo)}"), (chiave, fuori, problemi)


def test_ogni_numero_delle_regole_ha_il_suo_limite():
    """Un numero nuovo nelle regole, mostrato con − e +, deve avere il suo limite nel file (o stare fra quelli che hanno un
    controllo a parte, con un menu nella web)."""
    a_parte = {"rimborso_svincolo", "scadenza_minuti", "prima_giornata_lega"}

    def numeri(dati, prefisso=""):
        for k, v in dati.items():
            if isinstance(v, dict):
                yield from numeri(v, f"{prefisso}{k}.")
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                yield prefisso + k

    tutti = set(numeri(asdict(Regole()) | {"voto_senza_sostituto": 4, "panchina": asdict(Regole().panchina)
                                            | {"posti": {"P": 2, "D": 3, "C": 3, "A": 3}}}))
    tutti |= {"modificatore_difesa.soglie.media", "modificatore_difesa.soglie.bonus"}
    assert tutti - a_parte == set(regole.LIMITI)


# ---------------------------------------------------------------- le leghe di prima non si rompono
def test_le_regole_valide_di_prima_restano_valide():
    """Le regole di partenza, la lega d'esempio e i valori estremi che la web e l'iPhone lasciavano scegliere (dentro i limiti
    del server di prima) passano ancora."""
    assert Regole().problemi() == []
    esempio = regole.carica(Path(__file__).resolve().parent.parent / "lega" / "esempio" / "regole.json")
    assert esempio.problemi() == []
    estremi = _con(asdict(Regole()), bonus__gol__P=20, bonus__assist=20, bonus__ammonizione=-20, bonus__mvp=0, crediti_iniziali=5000,
                   voto_senza_sostituto=10, panchina__numero=14, panchina__max_sostituzioni=10,
                   modificatore_difesa__attivo=True, modificatore_difesa__min_difensori=5,
                   modificatore_difesa__soglie=[[4, 0], [9, 20]], rosa={"P": 1, "D": 20, "C": 20, "A": 20})
    assert regole.da_dict(estremi).problemi() == []


def test_le_regole_salvate_fuori_dai_limiti_nuovi_si_leggono_ancora(tmp_path):
    """Una lega salvata prima, con valori che ora non si salvano più, si apre ancora (la pagina Regole la mostra e la si corregge);
    per salvarla di nuovo va riportata nei limiti."""
    f = tmp_path / "regole.json"
    vecchie = _con(asdict(Regole()), bonus__gol__A=-4, bonus__autogol=3, panchina__numero=0, modificatore_difesa__attivo=True,
                   modificatore_difesa__min_difensori=2, modificatore_difesa__soglie=[])
    f.write_text(json.dumps(vecchie), encoding="utf-8")
    lette = regole.carica(f)
    assert lette.bonus.gol["A"] == -4 and lette.panchina.numero == 0
    with pytest.raises(regole.RegoleFuoriIntervallo):
        regole.salva(lette, tmp_path / "nuove.json")


# ---------------------------------------------------------------- tradotti
def _in_inglese(messaggi: list[str]) -> list[str]:
    prova = TESTI_JS + """
    LINGUA = "en";
    console.log(JSON.stringify(JSON.parse(String.raw`MESSAGGI`).map(traduciErrore)));
    """
    r = subprocess.run(["node", "-"], input=prova.replace("MESSAGGI", json.dumps(messaggi)), capture_output=True,
                       encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


ITALIANO = re.compile(r"\b(deve|devono|essere|della|delle|del|dei|il|la|le|tra|non|serve|nessun|regole)\b", re.I)


def test_con_la_web_in_inglese_gli_errori_delle_regole_sono_in_inglese(client):
    """Ogni messaggio dei limiti e dei valori assurdi, anche più di uno nella stessa risposta, arriva in inglese."""
    base = asdict(Regole())
    righe = [f for _, f in ASSURDI] + [p for k, (m, _) in SCELTI.items() for p in _problemi_con(k, m - 1)]
    righe += _problemi(_con(base, rosa={"P": 3}))
    righe += _problemi(_con(base, moduli=[]))
    righe += _problemi(_con(base, moduli=["3-4-3", "3-4-3"]))
    righe += _problemi(_con(base, rosa={"P": 3, "D": 2, "C": 8, "A": 6}))
    righe += _problemi(_con(base, panchina__posti={"P": 1, "D": 1, "C": 1, "A": 1}))
    righe += _problemi(_con(base, moduli=["3-4-3"], modificatore_difesa__attivo=True, modificatore_difesa__min_difensori=4))
    vera = client.put("/api/regole", json=_con(client.get("/api/regole").json(), bonus__assist=99, bonus__autogol=3)).json()["detail"]
    tradotti = _in_inglese([f"Regole non valide:\n- {r}" for r in righe] + [vera])
    for italiano, inglese in zip(righe, tradotti[:-1]):
        assert inglese.startswith("Invalid rules:\n- "), (italiano, inglese)
        assert not ITALIANO.search(inglese), (italiano, inglese)
    assert tradotti[-1] == ("Invalid rules:\n- the assist bonus must be between 0 and 20\n"
                            "- the own goal malus must be between −20 and 0"), tradotti[-1]
