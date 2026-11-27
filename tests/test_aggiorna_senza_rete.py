"""«Aggiorna i dati» con le fonti che non rispondono (collaudo d'insieme del 26/11/2026).

1. Un giro in cui nessuna richiesta arriva non rende freschi i dati: prima il passo «voti», che non aveva niente da scaricare,
   risultava riuscito, la riga generale prendeva l'ora di adesso, Giornate diceva «dati del …» di adesso e spariva l'avviso «I dati
   non si aggiornano da 30 giorni». Ora l'ora si scrive solo se almeno un passo ha scaricato davvero qualcosa.
2. Chi preme «Aggiorna i dati» legge una frase per fonte («Fantacalcio.it non risponde: riprova più tardi.»), non l'errore tecnico
   («ProxyError: HTTPSConnectionPool…»), che resta negli errori della corsa (registro, Stato dei dati).

La rete è quella vera di `rete.scarica`, con le pause a zero e la sessione finta: nessuna richiesta esce dal computer. Archivi
temporanei, dati inventati."""
import json
from datetime import datetime

import pytest
import requests

from fanta import aggiorna, archivio, da_fare, fonti_attive, funzioni
# `stato_dati.riepilogo` importa la sentinella solo quando serve: importata qui, la fixture di conftest ne sposta il file in una
# cartella temporanea (lanciato da solo, il test aprirebbe `dati/sentinella.json` del repository)
from fanta import sentinella  # noqa: F401

ADESSO = "2026-11-26T18:38:00"
UN_MESE_FA = "2026-10-27T21:03:00"
CONTROLLI_VERI = aggiorna.Aggiornamento.controlli


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


class _Pagina:
    """Una risposta buona di una fonte (vuota: i passi finti non la leggono)."""
    status_code = 200
    text = ""
    content = b""

    def raise_for_status(self):
        pass


class _Rotta:
    """Una risposta di una fonte con un codice d'errore (`raise_for_status` come in requests)."""

    def __init__(self, codice: int):
        self.status_code = codice

    def raise_for_status(self):
        raise requests.HTTPError(f"{self.status_code} Client Error", response=self)


def _rete(monkeypatch, risponde=True):
    """`rete.scarica` vera, senza pause. `risponde`: True = ogni pagina arriva; False = ogni richiesta cade come con un proxy che
    non risponde (l'errore del collaudo); un numero = la fonte risponde con quel codice."""
    monkeypatch.setattr(aggiorna.rete, "PAUSA", 0)

    def get(url, **_):
        if risponde is True:
            return _Pagina()
        if risponde is False:
            raise requests.exceptions.ProxyError(f"HTTPSConnectionPool(host='fonte.invalid', port=443): Max retries exceeded "
                                                 f"with url: {url} (Caused by ProxyError('Unable to connect to proxy'))")
        return _Rotta(risponde)
    monkeypatch.setattr(aggiorna.rete._sessione, "get", get)


def _passi(monkeypatch, rotti: dict | None = None):
    """esegui() con i passi delle fonti finti: ognuno chiede una pagina con `rete.scarica`, come i veri. «voti» è quello vero:
    l'archivio non ha partite giocate, quindi non ha niente da scaricare e non chiede niente. `rotti`: passo -> eccezione che il
    passo alza dopo aver letto la pagina (una pagina cambiata)."""
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    monkeypatch.setattr(funzioni, "acceso", lambda nome: True)
    rotti = rotti or {}

    def passo(metodo):
        def fai(self):
            aggiorna.rete.scarica(f"https://fonte.invalid/{metodo}")
            if metodo in rotti:
                raise rotti[metodo]
        return fai
    for metodo in ("listone", "calendario", "probabili", "understat", "dati_extra"):
        monkeypatch.setattr(aggiorna.Aggiornamento, metodo, passo(metodo))
    monkeypatch.setattr(aggiorna.Aggiornamento, "controlli", lambda self: None)


def _giro(db, monkeypatch, ora=ADESSO) -> aggiorna.Aggiornamento:
    monkeypatch.setattr(aggiorna, "_ora", lambda: ora)
    a = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None)
    a.esegui()
    return a


def _ultimo(db) -> str | None:
    r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
    return r[0] if r else None


# ---------------------------------------------------------------- 1. l'ora dell'aggiornamento
def test_un_giro_senza_rete_non_rende_freschi_i_dati_anche_se_voti_riesce(db, monkeypatch):
    archivio.segna(db, "aggiornamento", UN_MESE_FA, "[]")
    db.commit()
    _rete(monkeypatch, risponde=False)
    _passi(monkeypatch)
    a = _giro(db, monkeypatch)
    assert "voti" in a.riusciti                          # niente da scaricare: il passo va, ma non ha portato niente di nuovo
    assert _ultimo(db) == UN_MESE_FA, "un giro senza nessuna pagina scaricata ha dato ai dati l'ora di adesso"
    errori = json.loads(db.execute("SELECT dettaglio FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()[0])
    assert errori == a.errori and any("ProxyError" in e for e in errori)        # gli errori di adesso restano visibili
    voce = da_fare._dati_vecchi(db, datetime.fromisoformat(ADESSO))
    assert voce is not None and voce["giorni"] == 29, voce                       # e l'avviso «I dati non si aggiornano» resta


def test_un_giro_che_scarica_qualcosa_rende_freschi_i_dati(db, monkeypatch):
    archivio.segna(db, "aggiornamento", UN_MESE_FA, "[]")
    db.commit()
    _rete(monkeypatch, risponde=True)
    _passi(monkeypatch)
    a = _giro(db, monkeypatch)
    assert a.errori == []
    assert _ultimo(db) == ADESSO
    assert da_fare._dati_vecchi(db, datetime.fromisoformat(ADESSO)) is None


def test_basta_un_passo_che_scarica_davvero(db, monkeypatch):
    """Fantacalcio.it giù e Understat che risponde: i dati di Understat sono nuovi, l'ora avanza."""
    archivio.segna(db, "aggiornamento", UN_MESE_FA, "[]")
    db.commit()
    _rete(monkeypatch, risponde=True)
    _passi(monkeypatch, rotti={m: requests.ConnectionError("giù") for m in ("listone", "calendario", "probabili", "dati_extra")})
    _giro(db, monkeypatch)
    assert _ultimo(db) == ADESSO


def test_un_passo_riuscito_con_la_copia_di_oggi_non_conta_come_scaricato(db, monkeypatch):
    """Il listone si scarica una volta al giorno: con la copia di oggi il passo riesce senza chiedere niente. Se nient'altro
    arriva, i dati non sono più freschi di prima."""
    archivio.segna(db, "aggiornamento", UN_MESE_FA, "[]")
    db.commit()
    _rete(monkeypatch, risponde=False)
    _passi(monkeypatch)
    monkeypatch.setattr(aggiorna.Aggiornamento, "listone", lambda self: None)
    a = _giro(db, monkeypatch)
    assert {"listone", "voti"} <= set(a.riusciti)
    assert _ultimo(db) == UN_MESE_FA


def test_le_pagine_della_diretta_in_un_altro_thread_non_contano(db, monkeypatch):
    """Revisione della #956: nel server la diretta scarica da un altro thread anche mentre gira «Aggiorna i dati». Una sua pagina
    arrivata durante il passo «voti» (riuscito senza chiedere niente) non rende freschi i dati: `rete.arrivate_qui` conta per
    thread. La fonte della diretta risponde, quelle dell'aggiornamento no."""
    import threading
    archivio.segna(db, "aggiornamento", UN_MESE_FA, "[]")
    db.commit()
    monkeypatch.setattr(aggiorna.rete, "PAUSA", 0)

    def get(url, **_):
        if "diretta" in url:
            return _Pagina()
        raise requests.exceptions.ProxyError(f"Unable to connect to proxy: {url}")
    monkeypatch.setattr(aggiorna.rete._sessione, "get", get)
    _passi(monkeypatch)
    arrivate = []

    def voti(self):                                   # come «voti» senza giornate nuove, mentre la diretta scarica
        diretta = threading.Thread(target=lambda: arrivate.append(aggiorna.rete.scarica("https://diretta.invalid/partite")))
        diretta.start()
        diretta.join()
    monkeypatch.setattr(aggiorna.Aggiornamento, "voti", voti)
    a = _giro(db, monkeypatch)
    assert len(arrivate) == 1, "la pagina della diretta non è arrivata: la prova non prova niente"
    assert a.riusciti and a.scaricati == [], (a.riusciti, a.scaricati)
    assert _ultimo(db) == UN_MESE_FA


# ---------------------------------------------------------------- 2. le frasi per chi ha premuto «Aggiorna i dati»
def test_senza_rete_una_frase_sola_con_le_fonti_che_non_rispondono(db, monkeypatch):
    _rete(monkeypatch, risponde=False)
    _passi(monkeypatch)
    a = _giro(db, monkeypatch)
    frasi = a.per_utente()
    assert frasi == ["Fantacalcio.it, Understat e football-data.co.uk non rispondono: riprova più tardi."], frasi
    assert frasi[0].chiave == "aggiorna.non_rispondono"
    assert all("Error" not in f and "HTTPS" not in f for f in frasi)
    assert any("ProxyError" in e for e in a.errori)       # il dettaglio tecnico resta negli errori della corsa


def test_una_fonte_sola_che_non_risponde(db, monkeypatch):
    _rete(monkeypatch, risponde=True)
    _passi(monkeypatch, rotti={"understat": requests.exceptions.ConnectTimeout("scaduto")})
    frasi = _giro(db, monkeypatch).per_utente()
    assert frasi == ["Understat non risponde: riprova più tardi."], frasi
    assert frasi[0].json() == {"chiave": "aggiorna.non_risponde", "param": {"fonte": "Understat"}}


def test_una_fonte_che_risponde_con_un_errore_del_server_non_risponde(db, monkeypatch):
    """`rete.scarica` dopo tre risposte 503 alza un HTTPError senza risposta: per chi legge la fonte non risponde."""
    _rete(monkeypatch, risponde=503)
    _passi(monkeypatch)
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: nome == "understat")
    assert _giro(db, monkeypatch).per_utente() == ["Understat non risponde: riprova più tardi."]


def test_una_pagina_cambiata_o_sparita_dice_dove_guardare(db, monkeypatch):
    _rete(monkeypatch, risponde=True)
    _passi(monkeypatch, rotti={"calendario": ValueError("giornata 3: trovate 0 partite invece di 10"),
                               "probabili": requests.HTTPError("404 Client Error", response=_Rotta(404))})
    frasi = _giro(db, monkeypatch).per_utente()
    assert frasi == ["Una parte dei dati di Fantacalcio.it non si è aggiornata: il dettaglio è in Stato dei dati."], frasi


def test_fonte_che_non_risponde_e_controlli_storti_insieme(db, monkeypatch):
    """I controlli veri del giro, con un controllo che conta come errore («gol_dei_voti») storto."""
    _rete(monkeypatch, risponde=True)
    _passi(monkeypatch, rotti={"listone": requests.ConnectionError("giù")})
    monkeypatch.setattr(aggiorna.Aggiornamento, "controlli", CONTROLLI_VERI)
    monkeypatch.setattr(aggiorna.controlli, "esegui", lambda db: [
        {"stagione": "2026-27", "nome": "gol_dei_voti", "esito": "errore", "dettaglio": "g3: 1 partita con i gol diversi"},
        {"stagione": "2026-27", "nome": "partite_senza_statistiche", "esito": "avviso", "dettaglio": "g3: 10"}])
    frasi = _giro(db, monkeypatch).per_utente()
    assert frasi == ["Fantacalcio.it non risponde: riprova più tardi.",
                     "I controlli sui dati hanno trovato un problema: il dettaglio è in Stato dei dati."], frasi


def test_tutto_a_posto_nessuna_frase(db, monkeypatch):
    _rete(monkeypatch, risponde=True)
    _passi(monkeypatch)
    assert _giro(db, monkeypatch).per_utente() == []


def test_esegui_riempie_le_frasi_per_chi_le_chiede(tmp_path, monkeypatch):
    """`aggiorna.esegui` (quello che chiama il server) dà gli errori tecnici come sempre e, se gli si passa `per_utente`, ci
    mette le frasi."""
    apri = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: apri(tmp_path / "e.sqlite"))
    _rete(monkeypatch, risponde=False)
    _passi(monkeypatch)
    frasi: list = []
    errori = aggiorna.esegui(scrivi=lambda _: None, per_utente=frasi)
    assert errori and any("ProxyError" in e for e in errori)
    assert frasi == ["Fantacalcio.it, Understat e football-data.co.uk non rispondono: riprova più tardi."]


@pytest.mark.parametrize("risponde, nuovi", [(False, False), (True, True)])
def test_esegui_dice_se_sono_arrivati_dati_nuovi(tmp_path, monkeypatch, risponde, nuovi):
    """Collaudo del 27/11: con tutte le fonti giù «Aggiorna i dati» diceva «Aggiornato, ma con problemi», ma non era arrivato
    niente. `aggiorna.esegui` riempie `esito["dati_nuovi"]` con la stessa regola che decide se l'ora dei dati cambia (almeno un
    passo ha scaricato qualcosa), così il server può dirlo."""
    apri = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: apri(tmp_path / "e.sqlite"))
    monkeypatch.setattr(aggiorna, "_ora", lambda: ADESSO)
    _rete(monkeypatch, risponde=risponde)
    _passi(monkeypatch)
    esito: dict = {}
    aggiorna.esegui(scrivi=lambda _: None, esito=esito)
    assert esito == {"dati_nuovi": nuovi}
    d = apri(tmp_path / "e.sqlite")
    try:
        assert (_ultimo(d) == ADESSO) is nuovi, "`dati_nuovi` e l'ora dei dati devono dire la stessa cosa"
    finally:
        d.close()


# ---------------------------------------------------------------- 3. Stato dei dati dopo il giro
def test_stato_dei_dati_dopo_un_giro_senza_rete_dice_frasi_semplici(db, monkeypatch):
    """Collaudo della web in inglese del 27/11/2026: dopo «Aggiorna i dati» con il proxy giù, Stato dei dati mostrava «Non riuscito
    alle 18:38 del 26/11: ProxyError: HTTPSConnectionPool(…)» per ogni passo e lo stesso muro di testo nella riga generale, con i
    nomi «listone», «calendario» in italiano. Ora ogni passo dice quale fonte non risponde, la riga generale quali passi non sono
    riusciti, tutto con la frase da tradurre (`errori_frasi`); il dettaglio tecnico resta negli errori della corsa."""
    from fanta import stato_dati
    _rete(monkeypatch, risponde=False)
    _passi(monkeypatch)
    a = _giro(db, monkeypatch)
    assert any("ProxyError" in e for e in a.errori)
    voci = {v["cosa"]: v for v in stato_dati.riepilogo(db, "2026-27", adesso=datetime.fromisoformat(ADESSO))["aggiornamenti"]}
    assert voci["listone"]["errori"] == ["Non riuscito gio 26 nov alle 18:38: Fantacalcio.it non risponde."]
    assert voci["understat"]["errori"] == ["Non riuscito gio 26 nov alle 18:38: Understat non risponde."]
    assert voci["dati-extra"]["errori"] == ["Non riuscito gio 26 nov alle 18:38: football-data.co.uk non risponde."]
    assert voci["aggiornamento"]["errori"] == [
        "Non riusciti: Listone e quotazioni, Calendario, Probabili formazioni, Statistiche avanzate, Statistiche di squadra."]
    for v in voci.values():
        assert len(v["errori_frasi"]) == len(v["errori"]) and all(v["errori_frasi"]), v
        assert not any(p in e for e in v["errori"] for p in ("Error", "HTTPS", "fonte.invalid", "mai riuscito")), v["errori"]


# ---------------------------------------------------------------- 4. gli errori nel registro
@pytest.mark.parametrize("errore, atteso", [
    ("voti: HTTPError: 404 Client Error: Not Found for url: https://fonte.invalid/voti?chiave=a&g=12#parte",
     "voti: HTTPError: 404 Client Error: Not Found for url: https://fonte.invalid/voti"),
    # i proxy e le connessioni cadute scrivono solo il percorso dopo «url:» (revisione della #975)
    ("listone: ProxyError: HTTPSConnectionPool(host='fonte.invalid', port=443): Max retries exceeded with url: /voti/12?chiave=a "
     "(Caused by ProxyError('Unable to connect to proxy'))",
     "listone: ProxyError: HTTPSConnectionPool(host='fonte.invalid', port=443): Max retries exceeded with url: /voti/12 "
     "(Caused by ProxyError('Unable to connect to proxy'))"),
    ("calendario: ConnectionError: Max retries exceeded with URL: fonte.invalid/calendario?stagione=2026#x (giù)",
     "calendario: ConnectionError: Max retries exceeded with URL: fonte.invalid/calendario (giù)"),
    ("probabili: ValueError: la pagina è cambiata? 3 righe invece di 20", "probabili: ValueError: la pagina è cambiata? 3 righe invece di 20"),
])
def test_per_il_registro_toglie_i_parametri_degli_indirizzi(errore, atteso):
    """Nel registro gli errori della corsa senza quello che segue «?» o «#» negli indirizzi (può portare chiavi): sia negli indirizzi
    interi sia nel percorso dopo «url:» dei messaggi di requests; un «?» nel testo resta."""
    assert aggiorna.per_il_registro(errore) == atteso
    assert len(aggiorna.per_il_registro("x" * 500)) == 300 and len(aggiorna.per_il_registro("x" * 1500, massimo=1000)) == 1000
