"""Squadra rinominata nell'app (PUT /api/squadre/nome): reimportazione da Leghe con il nome vecchio, stemma e maglia al sicuro,
nomi strani, immagini private e orfane. Dati finti in cartelle temporanee."""
from fanta import immagini, lega, server

from test_etag import mondo  # noqa: F401 (fixture)
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

ROSE = "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"
ROSE_DOPO = "Mia\nP\tSommer\t10\nD\tBastoni\t15\nAltra\nA\tKean\t30\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40


def _squadre(a):
    return {s["nome"]: s for s in a.get("/api/squadre").json()}


def _stemma(a, squadra):
    return a.post("/api/squadre/immagine", params={"squadra": squadra, "tipo": "stemma"}, files={"file": ("s.png", PNG, "image/png")})


def test_reimportare_con_il_nome_di_leghe_aggiorna_la_squadra_rinominata(mondo):
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    assert a.put("/api/squadre/nome", json={"nome": "Mia", "nuovo": "I Lupi"}).status_code == 200
    # su Leghe la squadra si chiama ancora «Mia»: anteprima e importazione normale (senza sostituisci_tutto)
    ant = a.post("/api/rose/anteprima", json={"testo": ROSE_DOPO}).json()
    assert {s["nome"] for s in ant["squadre"]} == {"I Lupi", "Altra"} and ant["mia_squadra"] == "I Lupi"
    assert a.post("/api/rose/testo", json={"testo": ROSE_DOPO}).status_code == 200
    sq = _squadre(a)
    assert set(sq) == {"I Lupi", "Altra"} and sq["I Lupi"]["mia"] and sq["I Lupi"]["giocatori"] == 2
    # si riconosce anche alla volta dopo, e tornare al nome di Leghe toglie il ricordo
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    assert set(_squadre(a)) == {"I Lupi", "Altra"}
    assert a.put("/api/squadre/nome", json={"nome": "I Lupi", "nuovo": "Mia"}).status_code == 200
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    assert set(_squadre(a)) == {"Mia", "Altra"}


def test_nomi_rinominati_non_tocca_una_squadra_che_ha_davvero_quel_nome():
    class Letta:
        def __init__(self, nome):
            self.nome = nome
    prima = lega.Rose([lega.Squadra("I Lupi", nome_importato="Mia"), lega.Squadra("Mia")])
    lette = [Letta("Mia"), Letta("Altra")]
    lega.nomi_rinominati(lette, prima)
    assert [x.nome for x in lette] == ["Mia", "Altra"]
    assert lega.da_dict({"squadre": [{"nome": "X", "giocatori": []}]}).squadre[0].nome_importato is None      # file vecchi


def test_se_il_salvataggio_fallisce_stemma_e_maglia_tornano_indietro(mondo, monkeypatch):
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE})
    assert _stemma(a, "Mia").status_code == 200
    def rotto(*_a, **_k):
        raise OSError("disco pieno")
    with monkeypatch.context() as m:
        m.setattr(server.lega, "salva", rotto)
        assert a.put("/api/squadre/nome", json={"nome": "Mia", "nuovo": "I Lupi"}).status_code == 500
    sq = _squadre(a)
    assert set(sq) == {"Mia", "Altra"} and sq["Mia"]["immagini"]["stemma"]


def test_nomi_lunghissimi_e_di_soli_simboli(mondo, tmp_path):
    assert len(immagini.slug("㎯" * 60)) <= immagini.MAX_SLUG
    assert immagini.percorso("x" * 400, "stemma", tmp_path) is None          # mai un errore del disco
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE})
    r = a.put("/api/squadre/nome", json={"nome": "Mia", "nuovo": "㎯" * 60})
    assert r.status_code == 200 and a.get("/api/squadre").status_code == 200
    assert _stemma(a, "㎯" * 60).status_code == 200 and _squadre(a)["㎯" * 60]["immagini"]["stemma"]
    # due nomi di soli simboli: non è «c'è già una squadra con questo nome», ma si confonderebbero stemma e maglia
    assert a.put("/api/squadre/nome", json={"nome": "㎯" * 60, "nuovo": "★★★"}).status_code == 200
    r = a.put("/api/squadre/nome", json={"nome": "Altra", "nuovo": "☆☆"})
    assert r.status_code == 409 and "si confonde con «★★★»" in r.json()["detail"]


def test_immagini_private_e_orfane_non_ereditate(mondo):
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE})
    assert _stemma(a, "Altra").status_code == 200
    r = a.get("/api/squadre/immagine", params={"squadra": "Altra", "tipo": "stemma"})
    assert r.status_code == 200 and r.headers["cache-control"].startswith("private")
    # «Altra» sparisce (sostituisci tutto); una squadra nuova con lo stesso nome non ne eredita lo stemma
    assert a.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\n", "sostituisci_tutto": True}).status_code == 200
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    assert not _squadre(a)["Altra"]["immagini"]["stemma"]


def test_pulisci_tiene_le_immagini_in_attesa_e_quelle_delle_squadre(tmp_path):
    for nome in ("lupi-stemma.png", "orsi-maglia.jpg", "_in-attesa.png", "altro.txt"):
        (tmp_path / nome).write_bytes(b"x")
    assert immagini.pulisci(["Lupi"], tmp_path) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["_in-attesa.png", "altro.txt", "lupi-stemma.png"]
