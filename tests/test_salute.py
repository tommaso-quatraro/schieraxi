"""Controllo di salute: servizio che non risponde e dati vecchi."""
from datetime import datetime

from fanta import archivio, salute


def test_avvisa_una_volta_e_poi_ogni_12_ore(tmp_path):
    db = archivio.apri(tmp_path / "t.sqlite")
    adesso = datetime(2026, 10, 28, 12, 0)
    db.execute("INSERT INTO aggiornamenti (cosa, quando) VALUES ('aggiornamento', ?)", ("2026-10-28T08:00:00",))
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append(testo) or True    # noqa: E731
    f = tmp_path / "s.json"
    assert salute.controlla(db, adesso, f, manda, lambda: True) == [] and mandati == []          # tutto bene
    assert len(salute.controlla(db, adesso, f, manda, lambda: False)) == 1 and len(mandati) == 1   # servizio giu'
    salute.controlla(db, adesso, f, manda, lambda: False)
    assert len(mandati) == 1                                                                        # non si ripete subito
    salute.controlla(db, datetime(2026, 10, 29, 1, 0), f, manda, lambda: False)
    assert len(mandati) == 2                                                                        # dopo 12 ore si'
    salute.controlla(db, datetime(2026, 10, 29, 1, 5), f, manda, lambda: True)                      # il problema e' passato
    salute.controlla(db, datetime(2026, 10, 29, 1, 10), f, manda, lambda: False)
    assert len(mandati) == 3                                                                        # se torna, si riavvisa subito


def test_dati_vecchi(tmp_path):
    db = archivio.apri(tmp_path / "t.sqlite")
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append(testo) or True    # noqa: E731
    db.execute("INSERT INTO aggiornamenti (cosa, quando) VALUES ('aggiornamento', ?)", ("2026-10-26T08:00:00",))
    p = salute.controlla(db, datetime(2026, 10, 28, 12, 0), tmp_path / "s.json", manda, lambda: True)
    assert len(p) == 1 and "da 52 ore" in p[0] and len(mandati) == 1
    assert salute.controlla(db, datetime(2026, 10, 28, 12, 0), tmp_path / "s2.json", lambda *a, **k: False, lambda: True)       # invio fallito: si riprova


def test_con_gli_account_accesi_un_401_vuol_dire_che_il_servizio_c_e(monkeypatch):
    import io
    import urllib.error

    def finto(codice):
        def apri(indirizzo, timeout=0):
            raise urllib.error.HTTPError(indirizzo, codice, "x", {}, io.BytesIO(b""))
        return apri
    monkeypatch.setattr(salute.urllib.request, "urlopen", finto(401))
    assert salute.servizio_risponde() is True            # lo stato chiede l'accesso: il servizio protegge, quindi vive
    monkeypatch.setattr(salute.urllib.request, "urlopen", finto(500))
    assert salute.servizio_risponde() is False
    monkeypatch.setattr(salute.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("giu")))
    assert salute.servizio_risponde() is False


def test_il_servizio_si_dice_giu_solo_dopo_tre_prove_fallite():
    """Un riavvio dell'app dura qualche secondo: una sola prova fallita non basta per l'allarme (falso allarme del 1/11)."""
    pause = []
    esiti = iter([False, False, True])
    assert salute.servizio_risponde_con_tentativi(lambda: next(esiti), dormi=pause.append) is True
    assert pause == [salute.PAUSA, salute.PAUSA]
    pause.clear()
    prove = []
    assert salute.servizio_risponde_con_tentativi(lambda: prove.append(1) or False, dormi=pause.append) is False
    assert len(prove) == 3 and len(pause) == 2                  # nessuna pausa inutile dopo l'ultima prova
    assert salute.controlla.__defaults__[-1] is salute.servizio_risponde_con_tentativi
