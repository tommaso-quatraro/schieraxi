"""Valori fuori misura (#663), dalla caccia ai difetti del 12/11/2026.

1. `PUT /api/regole` accettava numeri finiti ma enormi (un bonus gol di 1e308, crediti iniziali negativi o di 10^30, un minimo di
   difensori di 10^30): risposta 200, poi Formazione, Oggi, Rosa e widget rispondevano 400 finché le regole non si correggevano.
   Ora le regole si rifiutano (400) con un messaggio che dice il campo e l'intervallo, e quelle salvate non cambiano.
2. Numeri enormi o negativi nei percorsi (`/api/giocatore/-99999999999999999999`, gli id di invito e di utente
   dell'amministratore) davano 500: sqlite non sa cercare oltre i 64 bit. Ora 422, come le rotte con `giornata`.
   Il test che trova da solo le rotte prova ogni parametro intero di percorso e di query: una rotta nuova che con un numero
   enorme dà 500 lo fa fallire."""
import contextlib
import json
import typing
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from fanta import account, archivio, regole, server
from fanta.regole import Regole
from fanta.regole import salva as salva_regole

from test_account_http import PASSWORD, _tutte_le_rotte

ENORME = 10 ** 20


# ---------------------------------------------------------------- regole
@pytest.fixture
def client(tmp_path, monkeypatch):
    salva_regole(Regole(), tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server.scelte, "FILE_SCELTE", tmp_path / "scelte.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    return TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)


def _con(dati: dict, chiave: str, valore) -> dict:
    """Le regole `dati` con un valore cambiato (chiave puntata, es. "bonus.gol.P")."""
    nuove = json.loads(json.dumps(dati))
    nodo = nuove
    *strada, ultima = chiave.split(".")
    for k in strada:
        nodo = nodo[k]
    nodo[ultima] = valore
    return nuove


@pytest.mark.parametrize("chiave, valore, parole", [
    ("bonus.gol.P", 1e308, ["gol del portiere", "tra -100 e 100"]),
    ("crediti_iniziali", -1, ["crediti iniziali", "tra 0 e 100.000"]),
    ("crediti_iniziali", 10 ** 30, ["crediti iniziali", "tra 0 e 100.000"]),
    ("modificatore_difesa.min_difensori", 10 ** 30, ["difensori", "tra 0 e 10"]),
])
def test_regole_fuori_misura_400_chiaro_e_regole_invariate(client, chiave, valore, parole):
    prima = client.get("/api/regole").json()
    r = client.put("/api/regole", json=_con(prima, chiave, valore))
    assert r.status_code == 400, r.text
    corpo = r.json()
    assert "id_errore" not in corpo, corpo                  # un messaggio scritto apposta, non «La richiesta non è valida»
    for p in parole:
        assert p in corpo["detail"], corpo["detail"]
    assert client.get("/api/regole").json() == prima


# I limiti di ogni numero (chiave, minimo, massimo, parole del messaggio). Larghi: la web e l'iPhone stanno molto più stretti.
LIMITI = [
    ("bonus.gol.P", -100, 100, "gol del portiere"),
    ("bonus.gol.D", -100, 100, "gol del difensore"),
    ("bonus.gol.C", -100, 100, "gol del centrocampista"),
    ("bonus.gol.A", -100, 100, "gol dell'attaccante"),
    ("bonus.rigore_segnato", -100, 100, "rigore segnato"),
    ("bonus.assist", -100, 100, "assist"),
    ("bonus.rigore_parato", -100, 100, "rigore parato"),
    ("bonus.rigore_sbagliato", -100, 100, "rigore sbagliato"),
    ("bonus.autogol", -100, 100, "autogol"),
    ("bonus.gol_subito_portiere", -100, 100, "gol subito dal portiere"),
    ("bonus.portiere_imbattuto", -100, 100, "portiere imbattuto"),
    ("bonus.ammonizione", -100, 100, "ammonizione"),
    ("bonus.espulsione", -100, 100, "espulsione"),
    ("bonus.mvp", -100, 100, "migliore in campo"),
    ("voto_senza_sostituto", 0, 10, "senza sostituto"),
    ("crediti_iniziali", 0, 100_000, "crediti iniziali"),
    ("modificatore_difesa.min_difensori", 0, 10, "difensori"),
    ("fattore_campo", -100, 100, "fattore campo"),
    ("soglia_primo_gol", 0, 200, "primo gol"),
    ("ampiezza_fascia_gol", 0, 100, "fasce dei gol"),
]


@pytest.mark.parametrize("chiave, minimo, massimo, parole", LIMITI)
def test_ogni_numero_ha_i_suoi_limiti(chiave, minimo, massimo, parole):
    base = json.loads(json.dumps(asdict(Regole())))
    for buono in (minimo, massimo):
        assert regole.da_dict(_con(base, chiave, buono)).problemi() == [], (chiave, buono)
    for fuori in (minimo - 1, massimo + 1, ENORME, -ENORME):
        with pytest.raises(ValueError) as e:
            regole.da_dict(_con(base, chiave, fuori))
        assert type(e.value) is ValueError                     # 400, non 422 dei tetti di misura
        assert parole in str(e.value) and f"tra {minimo:,} e {massimo:,}".replace(",", ".") in str(e.value), str(e.value)


def test_fasce_del_modificatore_limitate():
    base = json.loads(json.dumps(asdict(Regole())))
    assert regole.da_dict(_con(base, "modificatore_difesa.soglie", [[0, -100], [10, 100]])).problemi() == []
    for soglie, parole in (([[10.5, 1]], "la media di ogni fascia"), ([[-1, 1]], "la media di ogni fascia"),
                           ([[6, 101]], "il bonus di ogni fascia"), ([[6, -1e308]], "il bonus di ogni fascia")):
        with pytest.raises(ValueError, match=parole):
            regole.da_dict(_con(base, "modificatore_difesa.soglie", soglie))


def test_regole_vere_dentro_i_limiti():
    """Le regole di partenza, la lega d'esempio e i valori estremi che la web e l'iPhone lasciano scegliere passano."""
    assert Regole().problemi() == []
    esempio = regole.carica(Path(__file__).resolve().parent.parent / "lega" / "esempio" / "regole.json")
    assert esempio.problemi() == []
    base = json.loads(json.dumps(asdict(Regole())))
    estremi = {"bonus.gol.P": 20, "bonus.assist": 20, "bonus.ammonizione": -20, "crediti_iniziali": 5000,
               "voto_senza_sostituto": 10, "modificatore_difesa.min_difensori": 6,
               "modificatore_difesa.soglie": [[4, 0], [9, 20]]}
    for chiave, valore in estremi.items():
        base = _con(base, chiave, valore)
    assert regole.da_dict(base).problemi() == []


def test_regole_salvate_prima_dei_limiti_si_leggono_ancora(tmp_path):
    """Come per i tetti di misura: un file salvato prima si legge (la schermata Regole lo mostra e lo si corregge), ma non si
    salva di nuovo così."""
    f = tmp_path / "regole.json"
    f.write_text(json.dumps(_con(asdict(Regole()), "bonus.gol.P", 1e308)), encoding="utf-8")
    vecchie = regole.carica(f)
    assert vecchie.bonus.gol["P"] == 1e308
    with pytest.raises(ValueError, match="gol del portiere"):
        regole.salva(vecchie, tmp_path / "nuove.json")


# ---------------------------------------------------------------- numeri nei percorsi
@pytest.fixture
def amministratore(multiutente, dati_isolati):
    """Un amministratore con la sessione aperta (vede anche le rotte /api/admin/...)."""
    with contextlib.closing(account.apri()) as db:
        invito = account.crea_invito(db, "capo", True)
    c = TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)
    r = c.post("/api/account/registra", json={"nome_utente": "capo", "password": PASSWORD, "invito": invito})
    assert r.status_code == 200, r.text
    return c


ROSE = "Squadra di prova\nP\tSommer\t10\n"


@pytest.mark.parametrize("valore", [ENORME, -ENORME, 2 ** 63, -(2 ** 63) - 1, 2 ** 31, 0, -1])
@pytest.mark.parametrize("metodo, percorso, nome, corpo", [
    ("GET", "/api/giocatore/{}", "calciatore_id", None),
    ("DELETE", "/api/admin/inviti/{}", "invito_id", None),
    ("POST", "/api/admin/utenti/{}/rose", "utente_id", {"testo": ROSE}),
])
def test_id_fuori_misura_422_mai_500(amministratore, metodo, percorso, nome, corpo, valore):
    r = amministratore.request(metodo, percorso.format(valore), json=corpo)
    assert r.status_code == 422, (metodo, percorso, valore, r.status_code, r.text)
    assert nome in r.json()["campi"], r.json()


def test_id_normali_rispondono_come_prima(amministratore):
    assert amministratore.delete("/api/admin/inviti/9999").status_code == 404
    assert amministratore.post("/api/admin/utenti/9999/rose", json={"testo": ROSE}).status_code == 404
    assert amministratore.get(f"/api/giocatore/{server.MAX_ID_CALCIATORE}").status_code != 500


def _intero(annotazione) -> bool:
    return annotazione is int or int in typing.get_args(annotazione)


def _parametri(dipendenza):
    """I parametri di percorso e di query di una rotta, anche quelli delle sue dipendenze."""
    yield from ((p, "percorso") for p in dipendenza.path_params)
    yield from ((p, "query") for p in dipendenza.query_params)
    for d in dipendenza.dependencies:
        yield from _parametri(d)


def _parametri_interi() -> list[tuple[str, str, str, str, APIRoute]]:
    """(metodo, percorso, nome, dove, rotta) per ogni parametro intero di percorso o di query, anche nei router inclusi."""
    trovati = []
    for prefisso, r in _tutte_le_rotte(server.app.routes):
        if isinstance(r, APIRoute):
            for metodo in sorted(r.methods - {"HEAD"}):
                trovati += [(metodo, prefisso + r.path, p.name, dove, r) for p, dove in _parametri(r.dependant)
                            if _intero(p.field_info.annotation)]
    return trovati


# Valori buoni per gli altri parametri obbligatori e per i corpi: così un 422, se arriva, è per il numero provato.
ALTRI = {"a": 1, "b": 2, "con": "Altra", "do": "1", "ricevo": "2"}
CORPI = {("POST", "/api/admin/utenti/{utente_id}/rose"): {"testo": ROSE}}


def test_i_parametri_interi_si_trovano_tutti():
    trovati = {(m, p, n) for m, p, n, _, _ in _parametri_interi()}
    assert {("GET", "/api/giocatore/{calciatore_id}", "calciatore_id"), ("DELETE", "/api/admin/inviti/{invito_id}", "invito_id"),
            ("POST", "/api/admin/utenti/{utente_id}/rose", "utente_id"), ("GET", "/api/formazione", "giornata"),
            ("GET", "/api/oggi", "certificato_giorni")} <= trovati


@pytest.mark.parametrize("valore", [ENORME, -ENORME])
def test_ogni_parametro_intero_mai_500(amministratore, valore):
    rotti = []
    for metodo, percorso, nome, _, rotta in _parametri_interi():
        valori = {p.name: ALTRI.get(p.name, 1) for p, _ in _parametri(rotta.dependant)} | {nome: valore}
        indirizzo = percorso.format(**{p.name: valori[p.name] for p in rotta.dependant.path_params})
        query = {p.name: valori[p.name] for p, d in _parametri(rotta.dependant)
                 if d == "query" and (p.field_info.is_required() or p.name == nome)}
        richiede_corpo = any(p.field_info.is_required() for p in rotta.dependant.body_params)
        assert not richiede_corpo or (metodo, percorso) in CORPI, f"aggiungi a CORPI un corpo valido per {metodo} {percorso}"
        r = amministratore.request(metodo, indirizzo, params=query, json=CORPI.get((metodo, percorso)))
        # un 422 deve parlare del numero provato: se parla d'altro, manca un valore in ALTRI e il numero non è stato provato
        if r.status_code == 500 or (r.status_code == 422 and nome not in r.json().get("campi", [nome])):
            rotti.append(f"{metodo} {percorso} {nome}: {r.status_code} {r.text[:200]}")
    assert not rotti, "\n".join(rotti)
