"""Limiti dei valori delle regole (#881, parte B: punti 5 e 6 del collaudo del 25/11/2026).

5. I limiti dei pulsanti − e + non valevano per i numeri scritti a mano e il server accettava valori assurdi: gol dell'attaccante
   −4, autogol +3, difensori minimi del modificatore 9 (nessun modulo li ha), e via API assist 99, panchina 0, modificatore acceso
   senza fasce, fasce ripetute; i pulsanti arrivavano a valori che il server rifiutava (14 cambi, 0 portieri). Ora i limiti stanno
   in un posto solo, `fanta/web/limiti-regole.json`: li usa il server quando salva e la pagina Regole per i pulsanti e i campi.
6. Gli errori avevano sigle e nomi interni («rosa deve indicare quanti P, D, C, A», «panchina.max_sostituzioni: al massimo 10»)
   ed erano in italiano anche con la web in inglese. Ora sono frasi semplici, ognuna con la sua traduzione nel catalogo.
Il punto 4 (un campo svuotato si salvava come 0) è della pagina: tests/browser/test_limiti_pagina_regole.py.
I limiti nuovi valgono solo per ciò che cambia con il salvataggio delle regole (PUT /api/regole, con le regole salvate): una lega
salvata prima con valori ora fuori dai limiti continua a funzionare (eccezione delle partite rinviate, scadenza, backup).
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
    "modificatore_difesa.min_difensori": (3, 5),             # nessun modulo ha 6 difensori
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
    """Tutti i problemi di queste regole salvate dalla pagina Regole sopra quelle di partenza (i valori cambiati hanno i limiti
    nuovi), senza alzare errori."""
    return regole._da_dict(Regole, dati).problemi(salvate=Regole())


# ---------------------------------------------------------------- i valori assurdi del collaudo
ASSURDI = [
    ({"bonus__gol__A": -4}, "il bonus per il gol dell'attaccante deve essere tra 0 e 20"),
    ({"bonus__autogol": 3}, "il malus per l'autogol deve essere tra −20 e 0"),
    ({"modificatore_difesa__min_difensori": 9}, "i difensori minimi del modificatore difesa devono essere tra 3 e 5"),
    ({"modificatore_difesa__min_difensori": 6}, "i difensori minimi del modificatore difesa devono essere tra 3 e 5"),
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
        regole.da_dict(tre_e_quattro, salvate=Regole())
    assert "nessun modulo ammesso ha almeno 5 difensori: il modificatore difesa non si applicherebbe mai" in str(e.value)
    assert _problemi(_con(tre_e_quattro, modificatore_difesa__min_difensori=4)) == []
    assert _problemi(_con(tre_e_quattro, modificatore_difesa__attivo=False)) == []    # spento non conta


# Tipi sbagliati (revisione di #886): «3,5» portieri o «500,5» crediti passavano la pagina e il server rispondeva «rosa.P deve
# essere un numero intero», con il nome interno e in italiano anche con la web in inglese.
TIPI = [
    ({"rosa__P": 3.5}, "«Portieri della rosa» deve essere un numero intero"),
    ({"crediti_iniziali": 500.5}, "«Crediti iniziali» deve essere un numero intero"),
    ({"panchina__max_sostituzioni": 2.5}, "«Cambi massimi» deve essere un numero intero"),
    ({"modificatore_difesa__min_difensori": 3.5}, "«Difensori minimi del modificatore difesa» deve essere un numero intero"),
    ({"bonus__assist": "tre"}, "«Assist» deve essere un numero"),
    ({"bonus__gol__P": None}, "«Gol di un portiere» deve essere un numero"),
    ({"modificatore_difesa__attivo": "sì"}, "«Modificatore difesa attivo» deve essere sì o no"),
    ({"nome_lega": 3}, "«Nome della lega» deve essere un testo"),
    ({"rosa": [3, 8, 8, 6]}, "la rosa deve indicare quanti portieri, difensori, centrocampisti e attaccanti"),
    ({"moduli": "3-4-3"}, "i moduli devono essere scritti come 3-4-3"),
    ({"modificatore_difesa__soglie": [[6]]}, "ogni fascia del modificatore difesa deve avere una media e un bonus"),
]


@pytest.mark.parametrize("cambi, frase", TIPI)
def test_i_tipi_sbagliati_si_dicono_con_il_nome_del_campo(client, cambi, frase):
    prima = client.get("/api/regole").json()
    r = client.put("/api/regole", json=_con(prima, **cambi))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == f"Regole non valide:\n- {frase}", r.json()


def test_i_messaggi_non_hanno_sigle_ne_nomi_interni():
    """Nessun messaggio dei limiti nomina un campo come nel file («panchina.max_sostituzioni», «bonus.gol») o i ruoli con le
    sigle («P, D, C, A»)."""
    base = asdict(Regole())
    messaggi = []
    for cambi, _ in ASSURDI + TIPI:
        messaggi += _problemi(_con(base, **cambi))
    for chiave, (minimo, _massimo) in SCELTI.items():
        messaggi += _problemi_con(chiave, minimo - 1)
    messaggi += _problemi(_con(base, rosa={"P": 3}))           # rosa senza tutti i ruoli
    messaggi += _problemi(_con(base, fonte_voto="giornale", panchina__tipo="mista", partite_rinviate="boh"))
    assert messaggi
    for m in messaggi:
        assert not re.search(r"[a-z]\.[a-z]|_|\bP, D, C, A\b|\[|\{", m), m


# ---------------------------------------------------------------- un posto solo per i limiti
def test_i_limiti_sono_quelli_scelti_e_stanno_in_un_file_solo():
    """Il file che legge la pagina Regole è lo stesso con cui controlla il server."""
    dal_file = json.loads(FILE_LIMITI.read_text(encoding="utf-8"))
    assert {k: (v["min"], v["max"]) for k, v in dal_file.items()} == SCELTI
    assert regole.LIMITI == dal_file
    # i limiti di prima (fuori dalla pagina Regole e per i valori che non cambiano) ci sono per ogni campo e non sono più stretti
    assert set(regole.LIMITI_LARGHI) == set(regole.LIMITI)
    for k, v in regole.LIMITI.items():
        assert regole.LIMITI_LARGHI[k]["min"] <= v["min"] and v["max"] <= regole.LIMITI_LARGHI[k]["max"], k


def test_la_pagina_legge_i_limiti_dal_server(client):
    """La web li chiede a /limiti-regole.json, lo stesso server che controlla le regole."""
    r = client.get("/limiti-regole.json")
    assert r.status_code == 200 and r.json() == regole.LIMITI


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


def _tipo_sbagliato(base: dict, chiave: str) -> dict:
    """Le regole `base` con un valore di tipo sbagliato (una lista) al campo `chiave` (un nome di regole.NOMI_CAMPI)."""
    if chiave.startswith("panchina.posti."):
        base = _con(base, panchina__posti={"P": 2, "D": 3, "C": 3, "A": 3}, panchina__numero=11)
    return _con(base, **{chiave.replace(".", "__"): [1]})


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
    assert _problemi(estremi) == []


VECCHIE = {"bonus__gol__A": -4, "bonus__autogol": 3, "panchina__numero": 0, "modificatore_difesa__attivo": True,
           "modificatore_difesa__min_difensori": 2, "modificatore_difesa__soglie": []}


def test_le_regole_salvate_fuori_dai_limiti_nuovi_si_leggono_ancora(tmp_path):
    """Una lega salvata prima, con valori ora fuori dai limiti, si apre ancora (la pagina Regole la mostra e la si corregge)."""
    f = tmp_path / "regole.json"
    f.write_text(json.dumps(_con(asdict(Regole()), **VECCHIE)), encoding="utf-8")
    lette = regole.carica(f)
    assert lette.bonus.gol["A"] == -4 and lette.panchina.numero == 0


@pytest.fixture
def lega_vecchia(client, tmp_path):
    """Il client con una lega salvata prima dei limiti nuovi (valori dentro i limiti di prima, fuori da quelli nuovi)."""
    (tmp_path / "regole.json").write_text(json.dumps(_con(asdict(Regole()), **VECCHIE)), encoding="utf-8")
    return client


def test_con_una_lega_salvata_prima_l_eccezione_delle_partite_rinviate_si_salva(lega_vecchia):
    """Revisione di #886: «Voto d'ufficio» per una giornata, dalla Formazione, non deve fallire per un bonus fuori dai limiti
    nuovi che non c'entra."""
    r = lega_vecchia.put("/api/regole/rinvio", json={"giornata": 12, "modo": "voto_ufficio"})
    assert r.status_code == 200, r.text
    assert lega_vecchia.get("/api/regole").json()["bonus"]["autogol"] == 3          # il resto resta com'era


def test_con_una_lega_salvata_prima_la_scadenza_si_salva(lega_vecchia):
    """La scadenza (in cima a Regole e nel primo avvio) manda le regole salvate con un valore solo cambiato: va."""
    salvate = lega_vecchia.get("/api/regole").json()
    r = lega_vecchia.put("/api/regole", json=salvate | {"scadenza_minuti": 30})
    assert r.status_code == 200, r.text


def test_con_una_lega_salvata_prima_un_valore_cambiato_ha_i_limiti_nuovi(lega_vecchia):
    salvate = lega_vecchia.get("/api/regole").json()
    r = lega_vecchia.put("/api/regole", json=_con(salvate, bonus__autogol=2))
    assert r.status_code == 400 and r.json()["detail"] == "Regole non valide:\n- il malus per l'autogol deve essere tra −20 e 0"
    r = lega_vecchia.put("/api/regole", json=_con(salvate, panchina__numero=12))         # sistemato: va
    assert r.status_code == 200, r.text


def test_il_backup_di_una_lega_salvata_prima_si_ripristina():
    """Il ripristino controlla le regole come prima (tetti e intervalli di #663), non con i limiti della pagina."""
    assert regole.da_dict(_con(asdict(Regole()), **VECCHIE)).bonus.autogol == 3


# «Cambiato» non dipende dall'ordine (ricontrollo di #886): la pagina manda le fasce ordinate per media e i moduli nell'ordine dei
# suoi pulsanti, che possono essere diversi da quelli del file salvato.
def _salva_vecchie(client, tmp_path, **cambi) -> dict:
    (tmp_path / "regole.json").write_text(json.dumps(_con(asdict(Regole()), **cambi)), encoding="utf-8")
    return client.get("/api/regole").json()


def test_moduli_riordinati_non_sono_cambiati(client, tmp_path):
    """Lega di prima: modificatore acceso con almeno 4 difensori e solo moduli a 3 difensori (non si applica mai)."""
    salvate = _salva_vecchie(client, tmp_path, moduli=["3-4-3", "3-5-2"], modificatore_difesa__attivo=True,
                             modificatore_difesa__min_difensori=4)
    assert client.put("/api/regole", json=salvate).status_code == 200                                          # uguali
    r = client.put("/api/regole", json=_con(salvate, moduli=["3-5-2", "3-4-3"]))                                 # riordinati
    assert r.status_code == 200, r.text
    r = client.put("/api/regole", json=_con(salvate, moduli=["3-4-3", "3-6-1"]))                                 # cambiati
    assert r.status_code == 400 and "nessun modulo ammesso ha almeno 4 difensori" in r.json()["detail"], r.text


@pytest.mark.parametrize("fasce, riordinate, cambiate, frase", [
    # un bonus negativo, ammesso prima, fuori dai limiti della pagina
    ([[6.5, 3], [6, -1]], [[6, -1], [6.5, 3]], [[6, -1], [6.5, 4]],
     "il bonus di ogni fascia del modificatore difesa deve essere tra 0 e 20"),
    # due fasce con la stessa media, salvate via API prima di #881
    ([[6, 2], [6, 1]], [[6, 1], [6, 2]], [[6, 1], [6, 3]], "due fasce del modificatore difesa hanno la stessa media: togline una"),
])
def test_fasce_riordinate_non_sono_cambiate(client, tmp_path, fasce, riordinate, cambiate, frase):
    salvate = _salva_vecchie(client, tmp_path, modificatore_difesa__attivo=True, modificatore_difesa__soglie=fasce)
    assert client.put("/api/regole", json=salvate).status_code == 200
    r = client.put("/api/regole", json=_con(salvate, modificatore_difesa__soglie=riordinate))
    assert r.status_code == 200, r.text
    r = client.put("/api/regole", json=_con(salvate, modificatore_difesa__soglie=cambiate))
    assert r.status_code == 400 and frase in r.json()["detail"], r.text


def test_posti_fissi_riordinati_non_sono_cambiati(client, tmp_path):
    """12 portieri in panchina, ammessi prima (fino a 30), fuori dai limiti della pagina (fino a 10)."""
    salvate = _salva_vecchie(client, tmp_path, panchina__posti={"P": 12, "D": 3, "C": 3, "A": 3}, panchina__numero=21)
    assert client.put("/api/regole", json=salvate).status_code == 200
    r = client.put("/api/regole", json=_con(salvate, panchina__posti={"A": 3, "C": 3, "D": 3, "P": 12}))
    assert r.status_code == 200, r.text
    r = client.put("/api/regole", json=_con(salvate, panchina__posti={"P": 11, "D": 3, "C": 3, "A": 3}, panchina__numero=20))
    assert r.status_code == 400 and "i posti in panchina per i portieri devono essere tra 0 e 10" in r.json()["detail"], r.text


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
    righe = [f for _, f in ASSURDI + TIPI] + [p for k, (m, _) in SCELTI.items() for p in _problemi_con(k, m - 1)]
    righe += _problemi(_con(base, fonte_voto="giornale", panchina__tipo="mista", partite_rinviate="boh"))
    righe += _problemi(_con(base, rimborso_svincolo=2)) + _problemi(_con(base, rimborso_svincolo="metà"))
    righe += [p for k in regole.NOMI_CAMPI for p in _problemi(_tipo_sbagliato(base, k))]
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
