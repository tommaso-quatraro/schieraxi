"""Isolamento tra utenti per le rotte di stemma/maglia da indirizzo web, rimozione e condivisione dal telefono."""
from fanta import limiti, server

from test_account_http import cliente
from test_isolamento import PNG, due, esegui_tutto, scritture  # noqa: F401  (due è una fixture)


def test_immagini_da_indirizzo_e_condivise_sono_per_utente(due, monkeypatch):  # noqa: F811
    monkeypatch.setattr(limiti, "PAUSA_IMMAGINI_URL", 0)
    monkeypatch.setattr(server.scarica_immagine, "scarica", lambda url, **k: (PNG + b"DA-URL-DI-A", ".png"))
    (ca, _), (cb, _) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    esegui_tutto(cb, scritture("B"))
    corpo = {"squadra": "Real Esempio A", "tipo": "maglia", "url": "https://img.example.com/m.png"}
    r = ca.post("/api/squadre/immagine/da-url", json=corpo)
    assert r.status_code == 200 and r.json()["immagini"]["maglia"] is True
    assert ca.get("/api/squadre/immagine", params={"squadra": "Real Esempio A", "tipo": "maglia"}).content.endswith(b"DA-URL-DI-A")
    assert cb.get("/api/squadre/immagine", params={"squadra": "Real Esempio A", "tipo": "maglia"}).status_code in (404, 400)
    assert [s["immagini"]["maglia"] for s in cb.get("/api/squadre").json()] == [False, False]
    assert cb.post("/api/squadre/immagine/da-url", json=corpo).status_code == 404            # la squadra di A, per B, non esiste
    # condivisione dal telefono: l'immagine in attesa di A non si vede da B
    f = {"immagine": ("foto.png", PNG + b"CONDIVISA-DI-A", "image/png")}
    assert ca.post(server.PERCORSO_CONDIVISIONE, files=f, follow_redirects=False).status_code == 303
    assert ca.get("/api/squadre/immagine/in-attesa").content.endswith(b"CONDIVISA-DI-A")
    assert cb.get("/api/squadre/immagine/in-attesa").status_code == 404
    assert cb.delete("/api/squadre/immagine/in-attesa").status_code == 200
    assert ca.get("/api/squadre/immagine/in-attesa").status_code == 200                        # B non ha toccato quella di A
    # B non può togliere l'immagine di A
    assert cb.delete("/api/squadre/immagine", params={"squadra": "Real Esempio A", "tipo": "maglia"}).status_code == 404
    assert ca.get("/api/squadre/immagine", params={"squadra": "Real Esempio A", "tipo": "maglia"}).status_code == 200
    assert ca.delete("/api/squadre/immagine", params={"squadra": "Real Esempio A", "tipo": "maglia"}).status_code == 200
    # senza accesso: 401 su tutto, anche sulla ricezione dal menu Condividi (che non manda X-Fanta)
    anonimo = cliente()
    for metodo, rotta, argomenti in [("POST", server.PERCORSO_CONDIVISIONE, dict(files=f)), ("GET", "/api/squadre/immagine/in-attesa", {}),
                                     ("DELETE", "/api/squadre/immagine/in-attesa", {}),
                                     ("POST", "/api/squadre/immagine/da-url", dict(json={"squadra": "x", "tipo": "stemma", "url": "https://a.example.com/"}))]:
        assert anonimo.request(metodo, rotta, **argomenti).status_code == 401, (metodo, rotta)
