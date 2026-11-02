"""Note sugli infortuni delle fonti: tradotte in inglese con un vocabolario, mai inventate (se non si riconosce, resta l'italiano)."""
import pytest
from fastapi.testclient import TestClient

from fanta import note_infortuni as ni, server


@pytest.mark.parametrize("it,en", [
    ("tracheite, da valutare contro il Sassuolo", "Tracheitis, to be assessed against Sassuolo"),
    ("risentimento muscolare al polpaccio destro, rientro da metà novembre", "Muscle strain in the right calf, return from mid-November"),
    ("problema muscolare al bicipite femorale della coscia destra, rientro dalla metà di novembre",
     "Muscle problem in the hamstring of the right thigh, return from mid-November"),
    ("lombalgia, out a Roma", "Lower back pain, out at Roma"),
    ("rottura di tibia e perone gamba sinistra, rientro da dicembre", "Fractured tibia and fibula in the left leg, return from December"),
    ("lesione di primo grado al bicipite femorale destro, tentativo di rientro dalla prima metà di novembre",
     "First-degree injury in the right hamstring, attempted return from the first half of November"),
    ("schiacciamento di un nervo al piede, in dubbio convocazione contro l'Atalanta", "Pinched nerve in the foot, call-up in doubt against Atalanta"),
    ("lesione miotendinea del retto femorale sinistro con lesione parziale del tendine, rientro da fine marzo",
     "Myotendinous injury in the left rectus femoris with partial injury in the tendon, return from late March"),
    ("noie fisiche, da valutare contro l'Inter", "Physical trouble, to be assessed against Inter"),
    ("risentimento ai flessori della coscia sinistra, da valutare convocazione a Venezia",
     "Strain in the flexors of the left thigh, call-up to be assessed at Venezia"),
    ("problema all'anca sinistra, contro il Bologna", "Problem in the left hip, against Bologna"),
])
def test_note_tradotte(it, en):
    assert ni.traduci(it) == en


@pytest.mark.parametrize("nota", [
    "tendinopatia inguaribile, rientro da metà novembre",          # parola sconosciuta: resta com'è
    "problema alla caviglia, tornerà quando vorrà",                # pezzo sconosciuto
    "contusione al ginocchio, in forte dubbio dal 1' a Frosinone",
    "", "   ", None, "x" * 400,
])
def test_nota_sconosciuta_resta_italiana(nota):
    assert ni.traduci(nota) == nota


def test_ogni_nota_vera_o_si_traduce_o_resta_uguale():
    # nessuna parola italiana a metà: un risultato tradotto non contiene i pezzi tipici dell'italiano
    for nota in ["problema alla spalla destra, rientro da metà novembre", "frattura a un dito del piede, rientro inizio novembre",
                 "distrazione di basso grado dei muscoli flessori della gamba sinistra, da valutare convocazione per Firenze"]:
        t = ni.traduci(nota)
        assert t != nota and not any(p in t.split() for p in ("della", "del", "alla", "al", "rientro", "problema"))


def test_traduci_dati_tocca_solo_note_e_motivi():
    dati = {"giocatori": [{"nome": "Rossi", "nota": "lombalgia, out a Roma", "motivi": ["infortunato", "lombalgia, out a Roma", "rigorista"]},
                          {"nome": "Bianchi", "nota": None, "motivi": ["titolare al 85%"]},
                          {"nome": "Verdi", "nota": "boh", "motivi": ["boh"]}],
            "nota": "lombalgia, out a Roma", "altro": "lombalgia, out a Roma"}
    out = ni.traduci_dati(dati)
    assert out["giocatori"][0] == {"nome": "Rossi", "nota": "Lower back pain, out at Roma", "motivi": ["infortunato", "Lower back pain, out at Roma", "rigorista"]}
    assert out["giocatori"][1] == dati["giocatori"][1] and out["giocatori"][2] == dati["giocatori"][2]
    assert out["nota"] == "Lower back pain, out at Roma" and out["altro"] == "lombalgia, out a Roma"
    assert dati["nota"] == "lombalgia, out a Roma"                                  # l'originale non si tocca


@pytest.fixture
def cliente(monkeypatch, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    if not any(getattr(r, "path", "") == "/api/_prova_note" for r in server.app.routes):
        def _prova_note():
            return {"avvisi": [{"nome": f"G{i}", "nota": "risentimento muscolare al polpaccio destro, rientro da metà novembre",
                                "motivi": ["infortunato", "risentimento muscolare al polpaccio destro, rientro da metà novembre"]} for i in range(30)]}
        server.app.add_api_route("/api/_prova_note", _prova_note, methods=["GET"])
        server.app.router.routes.insert(0, server.app.router.routes.pop())          # prima del montaggio dei file statici
    return TestClient(server.app)


def test_rotta_in_inglese_con_compressione_e_senza(cliente):
    it = cliente.get("/api/_prova_note")
    assert it.json()["avvisi"][0]["nota"].startswith("risentimento muscolare")             # senza lingua: invariato
    for kw in ({"params": {"lingua": "en"}}, {"headers": {"Accept-Language": "en-US,en;q=0.9"}},
               {"headers": {"Accept-Language": "en", "Accept-Encoding": "identity"}}):
        r = cliente.get("/api/_prova_note", **kw)
        assert r.status_code == 200 and "Accept-Language" in r.headers["vary"]
        a = r.json()["avvisi"][0]
        assert a["nota"] == "Muscle strain in the right calf, return from mid-November"
        assert a["motivi"] == ["infortunato", a["nota"]] and len(r.json()["avvisi"]) == 30
    assert cliente.get("/api/_prova_note?lingua=it", headers={"Accept-Language": "en"}).json() == it.json()


NOTA = "risentimento muscolare al polpaccio destro, rientro da metà novembre"


@pytest.fixture
def cliente_etag(cliente):
    """Rotte di prova: una con ETag come le vere (calcolato sui dati italiani, 304 con If-None-Match), una da scaricare."""
    from fastapi import Request
    from fastapi.responses import JSONResponse, Response
    from fanta import versioni

    if not any(getattr(r, "path", "") == "/api/_prova_etag" for r in server.app.routes):
        def _prova_etag(request: Request):
            corpo = {"nota": NOTA, "motivi": [NOTA]}
            etag = versioni.etag_dati(corpo)
            if request.headers.get("if-none-match") == etag:
                return Response(status_code=304, headers={"ETag": etag})
            return JSONResponse(corpo, headers={"ETag": etag})

        def _prova_scarica():
            return JSONResponse({"nota": NOTA}, headers={"Content-Disposition": 'attachment; filename="b.json"'})
        server.app.add_api_route("/api/_prova_etag", _prova_etag, methods=["GET"])
        server.app.add_api_route("/api/_prova_scarica", _prova_scarica, methods=["GET"])
        for _ in range(2):
            server.app.router.routes.insert(0, server.app.router.routes.pop())
    return cliente


def test_etag_diverso_per_inglese_e_if_none_match(cliente_etag):
    c = cliente_etag
    it = c.get("/api/_prova_etag")
    en = c.get("/api/_prova_etag", headers={"Accept-Language": "en"})
    assert it.headers["etag"] != en.headers["etag"] and en.headers["etag"].endswith('-en"')
    # l'ETag preso dalla risposta italiana, in inglese, non dà 304 con le note vecchie
    r = c.get("/api/_prova_etag", headers={"Accept-Language": "en", "If-None-Match": it.headers["etag"]})
    assert r.status_code == 200 and r.json()["nota"].startswith("Muscle strain")
    # quello inglese in inglese: 304; in italiano: 200
    r = c.get("/api/_prova_etag", headers={"Accept-Language": "en", "If-None-Match": en.headers["etag"]})
    assert r.status_code == 304 and r.content == b"" and "Accept-Language" in r.headers["vary"]
    assert c.get("/api/_prova_etag", headers={"If-None-Match": en.headers["etag"]}).status_code == 200
    assert c.get("/api/_prova_etag", headers={"If-None-Match": it.headers["etag"]}).status_code == 304


def test_vary_sulle_risposte_italiane(cliente, monkeypatch):
    assert "Accept-Language" in cliente.get("/api/_prova_note").headers["vary"]
    monkeypatch.setattr(server, "RISPOSTE_PER_PERSONA", ("/api/_prova_note",))
    v = cliente.get("/api/_prova_note", headers={"Accept-Encoding": "gzip"}).headers["vary"]
    assert all(x in v for x in ("Authorization", "Cookie", "Accept-Language", "Accept-Encoding"))


def test_accoda_vary_senza_perdere_e_senza_doppioni():
    from fastapi.responses import Response
    r = Response(headers={"Vary": "Accept-Encoding, accept-language"})
    server._accoda_vary(r, "Authorization, Accept-Language")
    assert r.headers["vary"] == "Accept-Encoding, accept-language, Authorization"


def test_download_non_si_riscrive(cliente_etag):
    r = cliente_etag.get("/api/_prova_scarica", headers={"Accept-Language": "en"})
    assert r.json()["nota"] == NOTA


def test_errore_di_traduzione_lascia_la_risposta(cliente, monkeypatch):
    def rotto(_):
        raise RuntimeError("boom")
    monkeypatch.setattr(ni, "traduci_dati", rotto)
    r = cliente.get("/api/_prova_note", headers={"Accept-Language": "en"})
    assert r.status_code == 200 and r.json()["avvisi"][0]["nota"] == NOTA


def test_traduci_ha_la_cache():
    ni.traduci.cache_clear()
    ni.traduci(NOTA), ni.traduci(NOTA)
    assert ni.traduci.cache_info().hits == 1


@pytest.mark.parametrize("nota", ["frattura Qualcosa", "Frattura Qualcosa, rientro da novembre", "lombalgia, Boh"])
def test_maiuscole_sconosciute_non_fanno_testi_misti(nota):
    assert ni.traduci(nota) == nota


def test_maiuscole_solo_come_nome_di_squadra():
    assert ni.traduci("lombalgia, out contro il Sassuolo") == "Lower back pain, out against Sassuolo"
    assert ni.traduci("distorsione, da valutare convocazione per Hellas Verona").endswith("for Hellas Verona")
