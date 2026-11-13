"""Solo due avvisi, con un interruttore unico (#676).

Il server manda soltanto:
- il promemoria prima della scadenza (un'ora e un quarto d'ora prima), se la formazione non è a posto (vedi test_promemoria_messa.py);
- l'avviso quando cambia la formazione da schierare: un titolare diventa fuori (infortunato, squalificato, in panchina, non
  convocato) e la consigliata lo toglie, oppure, nell'ora prima della scadenza, la consigliata vale almeno un punto atteso in più.
Gli altri (cambi delle probabili, giocatori seguiti, riepilogo della giornata, reparto scoperto, «formazione pronta») non partono
più: il riepilogo è già in testa alla Formazione a giornata finita, il reparto scoperto è una riga di «Da fare».
Le scelte per avviso salvate dagli utenti (anche dall'iPhone) restano nel file e la rotta le legge e le scrive come prima, ma il
server non le usa più: decide l'interruttore unico (gli avvisi arrivano a chi li ha accesi su un dispositivo). Restano le ore
tranquille e la lingua. Il tetto per giornata resta: due avvisi «cambia la formazione», un promemoria per finestra; «cambia un
titolare» (titolo suo, fuori da quel tetto) parte una volta per ogni titolare che diventa fuori.
Orari simulati (`adesso` passato come argomento), archivio in memoria, notifiche finte."""
# ruff: noqa: F811  (le fixture importate da altri file di test arrivano come parametri con lo stesso nome: è il modo di pytest)
from datetime import datetime

from fanta import __main__ as cli
from fanta import avvisi_utenti, consigli, notifiche, scelte
from fanta.regole import Regole

from test_avviso_scadenza import BASE, ROSE, _cambi_ha_visto, _giro, m, ore  # noqa: F401  (m = fixture)
from test_avvisi_utenti import mondo, nuovo, registro  # noqa: F401  (fixture)
from test_notifiche import ST
from test_server import client  # noqa: F401  (fixture: un solo utente, senza account)

SPENTE = {"cambi": False, "promemoria_60": False, "promemoria_15": False, "riepilogo": False, "copertura": False, "avviso_prima": 0}


def _registro():
    mandati = []
    return mandati, lambda titolo, testo, priorita=3, tag="x", **k: mandati.append((titolo, testo)) or True


def _cambi(m, tmp_path, quando, manda, opz=None, file_scelte=None):
    return notifiche.cambi(m.db, Regole(), ROSE, quando, tmp_path / "cambi.json", manda, opz if opz is not None else {},
                           file_scelte=file_scelte or tmp_path / "scelte.json", file_promemoria=tmp_path / "prom.json")


# ---------------------------------------------------------------- le vecchie scelte per avviso non contano più
def test_il_promemoria_parte_anche_con_le_vecchie_scelte_spente(m, tmp_path):
    mandati, manda = _registro()
    for quando in (ore(17, 35), ore(18, 20)):
        assert len(notifiche.promemoria(m.db, Regole(), ROSE, quando, tmp_path / "p.json", manda, SPENTE, tmp_path / "s.json")) == 1
    assert [t for t, _ in mandati] == ["SchieraXI · formazione tra un'ora", "SchieraXI · ultimi minuti per la formazione"]


def test_l_avviso_prima_della_scadenza_ha_sempre_la_sua_ora(m, tmp_path):
    """Un'ora prima della scadenza, qualunque fosse `avviso_prima` (0 = spento, 30, 90): il valore resta nel file, il server no."""
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    _giro(m, tmp_path, ore(16, 0), {"avviso_prima": 90})
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert _giro(m, tmp_path, ore(17, 20), {"avviso_prima": 90}) == ([], [])             # 70 minuti: non ancora
    righe, mandati = _giro(m, tmp_path, ore(17, 50), {"avviso_prima": 0})                 # spento nel file: parte lo stesso
    assert len(mandati) == 1 and mandati[0][1].startswith("Castoldi è infortunato: metti Bonvicini (+2,5 punti attesi).")


# ---------------------------------------------------------------- i cambi: solo quando cambia la formazione da schierare
def test_i_cambi_delle_probabili_da_soli_non_avvisano_piu(m, tmp_path):
    """Un giocatore fuori dalla consigliata va in panchina, un titolare diventa in dubbio o diffidato: la consigliata non cambia,
    quindi niente avviso (prima: «cambi nelle probabili»)."""
    mandati, manda = _registro()
    assert _cambi(m, tmp_path, ore(9, 0), manda) == []                                  # primo controllo: si ricorda lo stato
    m.cambia("v1", stato={13: "panchina", 14: "infortunato"})
    m.prev.loc[9, "dubbio"] = True
    assert _cambi(m, tmp_path, ore(10, 0), manda) == [] and mandati == []


def test_un_titolare_fuori_che_cambia_la_consigliata_avvisa_con_il_motivo(m, tmp_path):
    """Senza una formazione salvata conta la consigliata: Castoldi si fa male, la consigliata mette Bonvicini. Un avviso, con il
    motivo e la scadenza, anche con le vecchie scelte spente; una volta sola."""
    mandati, manda = _registro()
    _cambi(m, tmp_path, ore(9, 0), manda, SPENTE)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"})
    righe = _cambi(m, tmp_path, ore(10, 0), manda, SPENTE)
    assert mandati == [("SchieraXI · cambia un titolare",
                        "Castoldi è infortunato: metti Bonvicini. La formazione si chiude il 28/10 alle 18:30.")]
    assert righe == [mandati[0][1]]
    assert _cambi(m, tmp_path, ore(10, 30), manda, SPENTE) == [] and len(mandati) == 1


def test_e_passa_al_modulo_nuovo(m, tmp_path):
    mandati, manda = _registro()
    _cambi(m, tmp_path, ore(9, 0), manda)
    m.cambia("v1", esce=8, entra=12, stato={8: "squalificato"}, modulo="4-2-4")       # un centrocampista per un attaccante
    _cambi(m, tmp_path, ore(10, 0), manda)
    assert mandati[0][1].startswith("Sartano è squalificato: metti Bonvicini e passa al 4-2-4.")


def test_la_consigliata_che_cambia_senza_titolari_fuori_non_avvisa_lontano_dalla_scadenza(m, tmp_path):
    """Un punto atteso in più lontano dalla scadenza: la Formazione lo mostra, l'avviso no (lo dice l'avviso dell'ultima ora)."""
    mandati, manda = _registro()
    _cambi(m, tmp_path, ore(9, 0), manda)
    m.cambia("v1", esce=8, entra=14, bonus={14: 1.5})
    assert _cambi(m, tmp_path, ore(10, 0), manda) == [] and mandati == []


def test_se_con_la_rosa_non_si_forma_piu_una_squadra_lo_dice(m, tmp_path, monkeypatch):
    mandati, manda = _registro()
    _cambi(m, tmp_path, ore(9, 0), manda)
    m.cambia("v1", stato={1: "squalificato"})

    def impossibile(*a, **k):
        raise ValueError("nessun portiere disponibile")
    monkeypatch.setattr(consigli, "formazione", impossibile)
    _cambi(m, tmp_path, ore(10, 0), manda)
    assert mandati == [("SchieraXI · cambia un titolare",
                        "Ferraglia è squalificato: con la tua rosa non si forma più una squadra. La formazione si chiude il 28/10 alle 18:30.")]


def test_con_la_formazione_salvata_parla_il_cambio_pronto_anche_con_i_cambi_spenti(tmp_path, monkeypatch):
    from test_cambio_pronto import ADESSO, CON_CASTRO, ROSE as ROSE_CP, _db as _db_cp, _scena
    _, mandati, manda = _scena(monkeypatch)
    fs = tmp_path / "s.json"
    scelte.salva(ST, 9, CON_CASTRO, "4-4-2", fs, da="web")
    notifiche.cambi(_db_cp(), Regole(), ROSE_CP, ADESSO, tmp_path / "n.json", manda, SPENTE, file_scelte=fs)
    assert len(mandati) == 1 and mandati[0][0] == "SchieraXI · cambio pronto"


def test_nell_ultima_ora_lo_stesso_cambio_arriva_una_volta_sola(m, tmp_path):
    mandati, manda = _registro()
    _cambi(m, tmp_path, ore(16, 0), manda)
    _giro(m, tmp_path, ore(16, 0))
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    righe = _cambi(m, tmp_path, ore(17, 45), manda)                                     # parte prima l'avviso dell'ultima ora
    assert [t for t, _ in mandati] == ["SchieraXI · cambia la formazione consigliata"] and len(righe) == 1
    assert "(+2,5 punti attesi)" in mandati[0][1]
    assert _giro(m, tmp_path, ore(17, 50)) == ([], []) and _cambi(m, tmp_path, ore(18, 0), manda) == []
    assert len(mandati) == 1


def test_nelle_ore_tranquille_l_avviso_aspetta(m, tmp_path):
    mandati, manda = _registro()
    _cambi(m, tmp_path, ore(9, 0), manda)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"})
    assert notifiche.cambi(m.db, Regole(), ROSE, ore(10, 0), tmp_path / "cambi.json", lambda *a, **k: False, {},
                           file_scelte=tmp_path / "scelte.json", file_promemoria=tmp_path / "prom.json") == []
    assert len(_cambi(m, tmp_path, ore(11, 0), manda)) == 1 and len(mandati) == 1        # al giro dopo parte


def test_ogni_titolare_che_diventa_fuori_si_dice_una_volta_con_un_titolo_suo(m, tmp_path):
    """L'avviso del giro dei cambi ha un titolo diverso da «cambia la formazione» e non entra nel suo tetto di due per giornata:
    parte una volta per ogni titolare che diventa fuori (revisione della #693)."""
    mandati, manda = _registro()
    _cambi(m, tmp_path, ore(9, 0), manda)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"})
    _cambi(m, tmp_path, ore(10, 0), manda)
    m.cambia("v2", esce=10, entra=14, stato={10: "squalificato"})
    _cambi(m, tmp_path, ore(11, 0), manda)
    m.cambia("v3", esce=9, entra=13, stato={9: "panchina"})
    _cambi(m, tmp_path, ore(12, 0), manda)
    assert [t for t, _ in mandati] == ["SchieraXI · cambia un titolare"] * 3
    assert [x.split(":")[0] for _, x in mandati] == ["Castoldi è infortunato", "Kerani è squalificato", "Lombrici parte dalla panchina"]
    assert _cambi(m, tmp_path, ore(13, 0), manda) == [] and len(mandati) == 3          # la stessa notizia non si ripete


def test_chi_era_gia_fuori_quando_e_stata_mostrata_non_fa_partire_l_avviso(m, tmp_path):
    """Castoldi era già in panchina al primo controllo e la consigliata lo teneva; più tardi la consigliata lo toglie per i punti
    attesi: non è un titolare «diventato» fuori, quindi niente avviso (lontano dalla scadenza lo dice la Formazione)."""
    mandati, manda = _registro()
    m.prev.at[11, "stato"] = "panchina"
    _cambi(m, tmp_path, ore(9, 0), manda)
    m.cambia("v1", esce=11, entra=12, bonus={12: 1.5})
    assert _cambi(m, tmp_path, ore(10, 0), manda) == [] and mandati == []


def _consigliata_senza_castro(monkeypatch, prev):
    """La consigliata finta della rosa di test_cambio_pronto: Castro (1) se gioca, altrimenti Bonny (2), con gli altri dieci."""
    from test_cambio_pronto import ALTRI
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {"modulo": "4-4-2", "punteggio_atteso": 70.0, "titolari": [
        {"id": i} for i in [*ALTRI, 1 if prev.at[1, "stato"] not in notifiche.MOTIVI_FUORI else 2]]})


def test_con_la_formazione_salvata_parla_solo_il_cambio_pronto(tmp_path, monkeypatch):
    """Con una formazione salvata che si può schierare conta lei: quando la consigliata toglie Castro arriva «cambio pronto»,
    non anche «cambia un titolare» (che è per chi non ha salvato niente)."""
    from test_cambio_pronto import ADESSO, CON_CASTRO, ROSE as ROSE_CP, _db as _db_cp, _scena
    prev, mandati, manda = _scena(monkeypatch, stato="titolare")
    _consigliata_senza_castro(monkeypatch, prev)
    fs, stato, db = tmp_path / "s.json", tmp_path / "n.json", _db_cp()
    scelte.salva(ST, 9, CON_CASTRO, "4-4-2", fs, da="web")
    notifiche.cambi(db, Regole(), ROSE_CP, ADESSO, stato, manda, {}, file_scelte=fs)       # primo controllo: memorizza
    prev.loc[1, "stato"] = "infortunato"
    notifiche.cambi(db, Regole(), ROSE_CP, ADESSO, stato, manda, {}, file_scelte=fs)
    assert [t for t, _, _ in mandati] == ["SchieraXI · cambio pronto"]


def test_se_parte_cambia_un_titolare_e_il_cambio_pronto_no_quello_riprova_da_solo(tmp_path, monkeypatch):
    """Nello stesso giro due avvisi: «cambia un titolare» (Castro è fuori, entra Bonny) parte, il «cambio pronto» su Bonny, che parte
    dalla panchina, no (invio fallito). Lo stato si salva: al giro dopo riprova solo il «cambio pronto», l'altro non si ripete."""
    from test_cambio_pronto import ADESSO, ROSE as ROSE_CP, _db as _db_cp, _scena
    from fanta import da_fare
    prev, mandati, manda = _scena(monkeypatch, stato="titolare")
    _consigliata_senza_castro(monkeypatch, prev)
    voce_bonny = {"giocatore": {"id": 2, "nome": "Bonny"}, "alternativa": {"id": 12, "nome": "Tosi", "ruolo": "A", "punti_attesi": 6.0}}
    monkeypatch.setattr(da_fare, "_dubbi", lambda *a, **k: [voce_bonny])
    fs, stato, db = tmp_path / "s.json", tmp_path / "n.json", _db_cp()
    notifiche.cambi(db, Regole(), ROSE_CP, ADESSO, stato, manda, {}, file_scelte=fs)       # primo controllo: memorizza
    prev.loc[1, "stato"], prev.loc[2, "stato"] = "infortunato", "panchina"
    senza_pronto = lambda titolo, *a, **k: "cambio pronto" not in str(titolo) and manda(titolo, *a, **k)     # noqa: E731
    notifiche.cambi(db, Regole(), ROSE_CP, ADESSO, stato, senza_pronto, {}, file_scelte=fs)
    assert [t for t, _, _ in mandati] == ["SchieraXI · cambia un titolare"]
    notifiche.cambi(db, Regole(), ROSE_CP, ADESSO, stato, manda, {}, file_scelte=fs)
    assert [t for t, _, _ in mandati] == ["SchieraXI · cambia un titolare", "SchieraXI · cambio pronto"]
    notifiche.cambi(db, Regole(), ROSE_CP, ADESSO, stato, manda, {}, file_scelte=fs)
    assert len(mandati) == 2


# ---------------------------------------------------------------- con gli account: l'interruttore unico decide
def test_con_le_vecchie_scelte_spente_arrivano_i_due_avvisi(mondo, registro):
    ctx = nuovo("amico1", (1, "Castro"))
    notifiche.salva_impostazioni(SPENTE, ctx.impostazioni_avvisi)
    assert notifiche.impostazioni(ctx.impostazioni_avvisi)["promemoria_60"] is False       # nel file restano, la rotta le legge
    esiti, errori = avvisi_utenti.esegui("promemoria", mondo.db, datetime(2026, 10, 28, 17, 35))
    assert errori == {} and len(esiti["amico1"]) == 1
    assert [t for _, t, _ in registro.web] == ["SchieraXI · formazione tra un'ora"]


def test_riepilogo_e_formazione_pronta_non_partono_piu(mondo, registro, capsys):
    nuovo("amico1", (1, "Castro"))
    assert set(avvisi_utenti.FUNZIONI) == {"cambi", "promemoria"}
    cli.cmd_avviso(None)                                                                # «formazione pronta»: 30 ore prima
    cli.cmd_riepilogo(None)
    assert registro.web == [] and registro.ntfy == [] and capsys.readouterr().out == ""


def test_nel_giro_dei_cambi_niente_reparto_scoperto(mondo, registro, monkeypatch):
    from fanta import copertura
    nuovo("amico1", (1, "Castro"))
    monkeypatch.setattr(copertura, "analizza", lambda *a, **k: {"reparti": [{"ruolo": "P", "livello": copertura.SCOPERTO,
                                                                             "testo": "Portieri: nessuno disponibile"}]})
    avvisi_utenti.esegui("cambi", mondo.db, datetime(2026, 10, 27, 9, 0))
    assert registro.web == []


# ---------------------------------------------------------------- un solo utente
def test_un_solo_utente_niente_riepilogo_ne_formazione_pronta(client, monkeypatch, capsys):
    """Gli script del server lanciano ancora `avviso` e `riepilogo`: escono subito, senza scrivere niente (lo script manda su ntfy
    quello che `avviso` stampa), anche quando sarebbe il momento di «formazione pronta»."""
    from fanta import avvisi
    inviati = []
    monkeypatch.setattr(notifiche, "invia", lambda *a, **k: inviati.append(a) or True)
    monkeypatch.setattr(avvisi, "da_mandare", lambda *a, **k: {"titolo": "SchieraXI", "testo": "pronta", "scadenza": ore(18, 30)},
                        raising=False)
    cli.cmd_avviso(type("A", (), {"prova": False})())
    cli.cmd_riepilogo(None)
    assert inviati == [] and capsys.readouterr().out == ""


def test_un_osservato_lasciato_libero_non_avvisa_piu(client, monkeypatch):
    from fanta import osservati, server
    inviati = []
    monkeypatch.setattr(notifiche, "invia", lambda *a, **k: inviati.append(a) or True)
    monkeypatch.setattr(osservati, "leggi", lambda *a, **k: [7])
    monkeypatch.setattr(server.movimenti, "differenze", lambda prima, nuove: {
        "tagliati": [{"squadra": "Real Esempio", "giocatori": [{"id": 7, "nome": "Bonny", "ruolo": "A"}]}], "testo": ""})
    assert client.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\n"}).status_code == 200
    assert inviati == []


def test_la_rotta_degli_avvisi_risponde_come_prima(client):
    """Le scelte per avviso si leggono e si scrivono come prima (l'iPhone di oggi le usa): nessun campo tolto."""
    r = client.put("/api/avvisi", json={"promemoria_15": False, "riepilogo": False, "avviso_prima": 30})
    assert r.status_code == 200
    imp = client.get("/api/avvisi").json()["impostazioni"]
    assert imp["promemoria_15"] is False and imp["riepilogo"] is False and imp["avviso_prima"] == 30
    assert {"cambi", "promemoria_60", "copertura", "app_nativa", "silenzio", "silenzio_da", "silenzio_a", "lingua"} <= set(imp)
