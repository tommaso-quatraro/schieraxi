"""«Quanto ci abbiamo preso», riga «su tutta la Serie A» (#374, L5 di #165): errore del fantavoto atteso e «gioca N%» di TUTTI i
giocatori della Serie A, presi dal registro delle giornate (fanta/registro_giornate.py), anche quando vanno male. Si mostra da 3
giornate misurate in su; prima «servono ancora N giornate». Il testo lo scrive il server (fanta/frasi.py): web e iPhone uguali.
Solo dati inventati: numeri del registro scritti a mano, archivio in una cartella temporanea, nessun giocatore."""
import html
import json
import shutil
import subprocess
from datetime import datetime

import pytest

from fanta import archivio, diario, precisione, registro_giornate as rg, server
from fanta.frasi import F
import codice_web

ST = "2026-27"


def _fasce(**per_fascia):
    f = [[0, 0.0, 0] for _ in range(10)]
    for k, v in per_fascia.items():
        f[int(k[1:])] = v
    return f


# una giornata misurata: 100 voti, errore del fantavoto atteso più basso di quello della fantamedia; chi davamo al 95% ha giocato 47
# volte su 50, chi davamo al 15% 8 volte su 50
BUONA = {"voti": 100, "sq_modello": 100.0, "sq_fantamedia": 150.0, "presenze": 100, "brier_somma": 10.0,
         "fasce": _fasce(f9=[50, 47.5, 47], f1=[50, 7.5, 8]), "fascia_casi": 20, "fascia_dentro": 16}
# andata male: il fantavoto atteso sbaglia più della fantamedia (radice di 169/144 = 13/12) e chi davamo al 95% ha giocato 6 volte su 10
CATTIVA = {**BUONA, "sq_modello": 169.0, "sq_fantamedia": 144.0, "fasce": _fasce(f9=[50, 47.5, 30], f1=[50, 7.5, 8])}


def _registro(db, misure: list[dict | None], salvate_in_piu: int = 0):
    """Una riga di registro per giornata (dalla 1), misurata con i numeri dati; `None` = giornata senza partite utili.
    `salvate_in_piu` giornate salvate ma non ancora misurate, dopo."""
    for g, m in enumerate(misure, start=1):
        db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, 100, 1)",
                   (ST, g, f"2026-10-{g:02d}T12:00:00"))
        rg.registra_misura(db, ST, g, m, datetime(2026, 10, g, 23))
    for g in range(len(misure) + 1, len(misure) + 1 + salvate_in_piu):
        db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, 100, 1)",
                   (ST, g, f"2026-10-{g:02d}T12:00:00"))
    db.commit()
    return db


@pytest.fixture(autouse=True)
def _registro_acceso(monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRO_GIORNATE", "1")        # conftest lo spegne per tutti i test: qui serve acceso


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "registro.sqlite")
    yield d
    d.close()


# ---------------------------------------------------------------- server: il campo nuovo
def test_registro_vuoto_nessuna_riga(db):
    assert precisione.serie_a(db) is None


def test_due_giornate_servono_ancora(db):
    s = precisione.serie_a(_registro(db, [BUONA, BUONA]))
    assert s["giornate"] == 2 and s["giornate_minime"] == 3 and s["mancano"] == 1
    assert s["testo"] == "Su tutta la Serie A serve ancora 1 giornata per dire quanto ci prendiamo."
    assert s["frase"] == {"chiave": "diario.serie_a_attesa", "param": {"n": 1}}
    assert "errore_fantavoto" not in s and "gioca" not in s                        # niente numeri prima di 3 giornate


def test_una_giornata_servono_ancora_due(db):
    s = precisione.serie_a(_registro(db, [BUONA]))
    assert s["mancano"] == 2 and s["testo"] == "Su tutta la Serie A servono ancora 2 giornate per dire quanto ci prendiamo."


def test_tre_giornate_riga_con_i_numeri(db):
    s = precisione.serie_a(_registro(db, [BUONA, BUONA, BUONA]))
    assert s["giornate"] == 3 and s["mancano"] == 0 and s["voti"] == 300
    assert s["errore_fantavoto"] == 1.0 and s["errore_fantamedia"] == 1.225       # radice di 300/300 e di 450/300
    assert s["rispetto_fantamedia"] == -18                                        # 1 / 1,2247 − 1 = −18%
    principale = s["gioca"]["gruppi"][s["gioca"]["principale"]]
    assert principale == {"da": 90, "a": 100, "giocatori": 150, "pochi": False, "detto": 95, "giocato": 94}
    assert s["testo"] == ("Su tutta la Serie A, nelle ultime 3 giornate: il fantavoto atteso ha sbagliato il 18% in meno della "
                          "fantamedia; quando diciamo «gioca 95%», ha giocato 9 volte su 10.")
    assert s["frase"]["chiave"] == "diario.serie_a" and s["frase"]["param"]["n"] == 3
    assert s["frase"]["param"]["fv"] == {"chiave": "diario.serie_a_fv_meno", "param": {"pct": 18}}
    assert s["frase"]["param"]["gioca"] == {"chiave": "diario.serie_a_gioca", "param": {"p": 95, "k": 9}}


def test_anche_quando_va_male(db):
    s = precisione.serie_a(_registro(db, [CATTIVA, CATTIVA, CATTIVA]))
    assert s["rispetto_fantamedia"] == 8
    assert s["testo"] == ("Su tutta la Serie A, nelle ultime 3 giornate: il fantavoto atteso ha sbagliato l'8% in più della "
                          "fantamedia; quando diciamo «gioca 95%», ha giocato 6 volte su 10.")


def test_pari_con_la_fantamedia_e_apostrofo(db, tmp_path):
    pari = {**BUONA, "sq_modello": 100.0, "sq_fantamedia": 100.0}
    assert "ha sbagliato quanto la fantamedia;" in precisione.serie_a(_registro(db, [pari] * 3))["testo"]
    otto = archivio.apri(tmp_path / "otto.sqlite")
    meno_otto = {**BUONA, "sq_modello": 84.64, "sq_fantamedia": 100.0}             # radice di 0,8464 = 0,92: −8%
    assert "ha sbagliato l'8% in meno della fantamedia" in precisione.serie_a(_registro(otto, [meno_otto] * 3))["testo"]
    otto.close()


def test_contano_solo_le_giornate_misurate_e_le_ultime_otto(db, tmp_path):
    # salvate ma non misurate e giornate senza partite utili non contano
    s = precisione.serie_a(_registro(db, [BUONA, None, BUONA], salvate_in_piu=2))
    assert s["giornate"] == 2 and s["mancano"] == 1
    tante = archivio.apri(tmp_path / "tante.sqlite")
    s = precisione.serie_a(_registro(tante, [BUONA] * 11))
    assert s["giornate"] == rg.FINESTRA == 8 and "nelle ultime 8 giornate" in s["testo"]
    tante.close()


def test_registro_spento_niente_attesa(db, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRO_GIORNATE", "0")
    assert precisione.serie_a(_registro(db, [BUONA, BUONA])) is None              # spento non arriverebbe mai a 3: niente «servono ancora»


def test_registro_spento_i_numeri_che_ci_sono_restano(db, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRO_GIORNATE", "0")
    assert precisione.serie_a(_registro(db, [BUONA] * 3))["mancano"] == 0


def test_archivio_illeggibile_niente_riga(tmp_path):
    rotto = archivio.apri(tmp_path / "rotto.sqlite")
    rotto.execute("DROP TABLE registro_giornate")
    assert precisione.serie_a(rotto) is None                                     # il Diario non si rompe per la riga in più
    rotto.close()


def test_frase_si_rifa_dal_json(db):
    from fanta import frasi
    s = precisione.serie_a(_registro(db, [BUONA] * 3))
    assert frasi.da_json(s["frase"]) == s["testo"]
    assert F("diario.serie_a_fv_pari") == "il fantavoto atteso ha sbagliato quanto la fantamedia"


def test_niente_dati_personali_nella_riga(db):
    testo = json.dumps(precisione.serie_a(_registro(db, [BUONA] * 3)))
    assert '"id"' not in testo and "calciatore" not in testo and "nome" not in testo


# ---------------------------------------------------------------- la rotta del Diario
def test_la_rotta_del_diario_ha_la_riga_della_serie_a(dati_isolati, tmp_path):
    from fastapi.testclient import TestClient
    voce = {"stagione": ST, "giornata": 5, "consigliata": {"atteso": 70.0, "reale": 72.0, "titolari": []}, "schierata": None,
            "giocatori": [{"id": 1, "p_voto": 0.9, "fv_atteso": 6.0, "fv": 7.0}]}
    diario.FILE.parent.mkdir(parents=True, exist_ok=True)
    diario.FILE.write_text(json.dumps({"giornate": {f"{ST}/5": voce}}), encoding="utf-8")
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.get("/api/diario").json()["precisione"]["serie_a"] is None            # registro vuoto: niente riga
    reg = archivio.apri(tmp_path / "archivio-finto" / "fanta.sqlite")
    _registro(reg, [BUONA] * 3)
    reg.close()
    p = c.get("/api/diario").json()["precisione"]
    assert p["giornate"] == 1 and p["serie_a"]["giornate"] == 3 and p["serie_a"]["testo"].startswith("Su tutta la Serie A, nelle ultime 3")


# ---------------------------------------------------------------- web: la riga nella carta, stesse parole del server
APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")


def _funzione(nome: str) -> str:
    inizio = APP.index(f"function {nome}(")
    return APP[inizio:APP.index("\n}\n", inizio) + 3]


def _carte(lingua: str, *precisioni: dict) -> list[str]:
    al_percento = next(r for r in APP.splitlines() if r.startswith("const alPercento = "))
    elidi = next(r for r in APP.splitlines() if r.startswith("const elidiOrdinali = "))
    prova = (TESTI + "\nconst virgola = x => (LINGUA === 'it' ? String(x).replace('.', ',') : String(x));\n" + al_percento + "\n" + elidi + "\n"
             + _funzione("esc") + _funzione("nomeGiornata") + _funzione("cartaPrecisione") + f"""
    LINGUA = "{lingua}";
    console.log(JSON.stringify({json.dumps(list(precisioni))}.map(cartaPrecisione)));
    """)
    r = subprocess.run(["node", "-"], input=prova, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _voce(g):
    return {"stagione": ST, "giornata": g, "giornata_lega": g - 3, "consigliata": {"atteso": 70.0, "reale": 72.0, "titolari": []},
            "schierata": None, "giocatori": [{"id": i, "p_voto": 0.95, "fv_atteso": 6.0, "fv": 6.5} for i in range(1, 6)]}


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
@pytest.mark.parametrize("lingua", ["it", "en"])
def test_web_mostra_la_riga_con_le_parole_del_server(lingua, tmp_path):
    base = precisione.riassunto([_voce(4), _voce(5)])
    db2, db3 = archivio.apri(tmp_path / "due.sqlite"), archivio.apri(tmp_path / "tre.sqlite")
    due = base | {"serie_a": precisione.serie_a(_registro(db2, [BUONA, BUONA]))}
    tre = base | {"serie_a": precisione.serie_a(_registro(db3, [CATTIVA] * 3))}
    db2.close()
    db3.close()
    senza, con_null, html_due, html_tre = _carte(lingua, base, base | {"serie_a": None}, due, tre)
    assert "qp-serie-a" not in senza and "qp-serie-a" not in con_null                    # server vecchio o registro vuoto: niente riga
    for h in (html_due, html_tre):
        assert h.count("qp-serie-a") == 1
        assert "undefined" not in h and "NaN" not in h and "frase.diario" not in h and "null" not in h
    testo = lambda h: html.unescape(h.split('qp-serie-a">', 1)[1].split("</div>", 1)[0])    # noqa: E731
    if lingua == "it":                                                                   # in italiano: il testo del server, uguale
        assert testo(html_due) == due["serie_a"]["testo"]
        assert testo(html_tre) == tre["serie_a"]["testo"]
    else:
        assert testo(html_due) == "Across the whole Serie A we need 1 more matchday to tell how accurate we are."
        assert testo(html_tre) == ("Across the whole Serie A, over the last 3 matchdays: the expected fantasy score erred 8% more than "
                                   "the fantasy average; when we say “plays 95%”, they played 6 times out of 10.")
