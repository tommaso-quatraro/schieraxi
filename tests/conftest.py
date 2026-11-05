import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fanta.listone import Calciatore  # noqa: E402
from fanta.nomi import Indice  # noqa: E402


def _c(id, nome, ruolo, sq, slug):
    return Calciatore(id, nome, ruolo, "", sq, slug, 10, 10, 100)


@pytest.fixture(autouse=True)
def _senza_pianificatore(monkeypatch):
    """Nei test il pianificatore (aggiornamenti schedulati dentro il servizio) resta spento: niente rete per sbaglio."""
    monkeypatch.setenv("FANTA_PIANIFICATORE", "0")
    monkeypatch.setenv("FANTA_COPIA_SCADENZA", "0")          # e niente copie alla scadenza nei file veri della lega


@pytest.fixture(autouse=True)
def _dns_push_finto(monkeypatch):
    """Le iscrizioni push controllano il nome del servizio: nei test niente rete vera, ogni nome vale un indirizzo pubblico."""
    from fanta import push
    push._cache_dns.clear()
    monkeypatch.setattr(push, "_risolvi_host", lambda host: ["93.184.216.34"])


@pytest.fixture(autouse=True)
def _fonti_accese_nei_test(tmp_path, monkeypatch):
    """Gli interruttori delle fonti (fanta/fonti_attive.py) sono accesi nei test, anche nell'esportazione pubblica dove il predefinito
    e' spento; la scelta dell'amministratore sta in un file temporaneo. Le prove sugli interruttori li cambiano da se'."""
    from fanta import fonti_attive
    for k in fonti_attive.FONTI:
        if k != "foto":
            monkeypatch.setenv(f"FANTA_FONTE_{k.upper()}", "1")
    monkeypatch.setattr(fonti_attive, "FILE", tmp_path / "fonti-finte.json")


@pytest.fixture(autouse=True)
def _uso_nei_test(tmp_path, monkeypatch):
    """Il conteggio d'uso (fanta/uso.py) nei test scrive in una cartella temporanea e parte vuoto."""
    from fanta import uso
    monkeypatch.setattr(uso, "FILE", tmp_path / "uso-finto.json")
    monkeypatch.setattr(uso, "_in_memoria", {})
    monkeypatch.setattr(uso, "_ultima_scrittura", 0.0)


@pytest.fixture(autouse=True)
def _funzioni_neutre_nei_test(tmp_path, monkeypatch):
    """Gli interruttori delle funzioni (fanta/funzioni.py) nei test partono come nel codice privato (tutto acceso), anche
    nell'esportazione pubblica; la scelta dell'amministratore sta in un file temporaneo."""
    from fanta import funzioni
    monkeypatch.setattr(funzioni, "VERSIONE_PUBBLICA", False)
    monkeypatch.setattr(funzioni, "FILE", tmp_path / "funzioni-finte.json")
    for k in funzioni.FUNZIONI:
        monkeypatch.delenv(f"FANTA_FUNZIONE_{k.upper()}", raising=False)


@pytest.fixture
def calciatori():
    return [
        _c(1, "Carnesecchi", "P", "ATA", "atalanta"),
        _c(2, "Sommer", "P", "INT", "inter"),
        _c(3, "Bastoni", "D", "INT", "inter"),
        _c(4, "N'Dicka", "D", "ROM", "roma"),
        _c(5, "Laurienté", "C", "SAS", "sassuolo"),
        _c(6, "Thuram K.", "C", "JUV", "juventus"),
        _c(7, "Thuram", "A", "INT", "inter"),
        _c(8, "Esposito Se.", "A", "INT", "inter"),
        _c(9, "Esposito F.P.", "A", "INT", "inter"),
        _c(10, "Martinez L.", "A", "INT", "inter"),
        _c(11, "Martinez Jo.", "P", "INT", "inter"),
        _c(12, "Barella", "C", "INT", "inter"),
        _c(13, "Dimarco", "D", "INT", "inter"),
        _c(14, "Kean", "A", "FIO", "fiorentina"),
        # due omonimi con lo stesso nome, ruoli diversi
        _c(15, "Rossi", "D", "GEN", "genoa"),
        _c(16, "Rossi", "A", "LEC", "lecce"),
        _c(17, "Pellegrini Lu.", "D", "LAZ", "lazio"),
    ]


@pytest.fixture
def listone_in_archivio(tmp_path, monkeypatch, calciatori):
    """I giocatori finti di `calciatori` nella tabella `calciatori` di un archivio temporaneo (lo stesso percorso di `dati_isolati`),
    e il server che legge quello. Serve alle rotte che accettano solo codici del listone (per esempio i Seguiti)."""
    from fanta import archivio, server
    percorso = tmp_path / "archivio-finto" / "fanta.sqlite"
    db = archivio.apri(percorso)
    db.executemany("INSERT OR REPLACE INTO calciatori(id, nome, ruolo, squadra, squadra_slug, quotazione) VALUES (?, ?, ?, ?, ?, ?)",
                   [(c.id, c.nome, c.ruolo, c.squadra, c.squadra_slug, c.quotazione) for c in calciatori])
    db.commit()
    db.close()
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(percorso))
    return {c.id for c in calciatori}


@pytest.fixture
def indice(calciatori):
    return Indice(calciatori)


class Orologio:
    """Il tempo dei limiti di tentativi, che i test fanno scorrere a mano."""
    t = 1000.0


@pytest.fixture(autouse=True)
def _registri_in_cartella_finta(tmp_path, monkeypatch):
    """Il registro degli errori (errori.log) sta accanto ai dati degli account: nei test sempre in una cartella temporanea."""
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "registri-finti"))


def pytest_configure(config):
    config.addinivalue_line("markers", "percorsi_veri: non sostituire i percorsi dei dati personali con quelli finti")


@pytest.fixture(autouse=True)
def _dati_personali_in_cartella_finta(request, tmp_path, monkeypatch):
    """Scelte, osservati, diario e affidabilità non devono mai leggere i file veri di `dati/` (scelte importate, giornate vere):
    un test che non indica il file esplicito userebbe i dati dell'utente e darebbe esiti diversi da PC a PC."""
    if request.node.get_closest_marker("percorsi_veri"):      # solo per chi controlla i percorsi di sempre (nessun file viene letto)
        return
    from fanta import affidabilita, diario, osservati, scelte
    d = tmp_path / "dati-personali-finti"
    for modulo, nome, file in ((scelte, "FILE_SCELTE", "scelte.json"), (osservati, "FILE_OSSERVATI", "osservati.json"),
                               (diario, "FILE", "diario.json"), (affidabilita, "FILE", "affidabilita.json")):
        monkeypatch.setattr(modulo, nome, d / file)
    from fanta import immagini                                # stemmi e maglie: mai nella cartella della lega (anche quella di esempio)
    monkeypatch.setattr(immagini, "CARTELLA", d / "immagini")


@pytest.fixture(autouse=True)
def _consigliate_in_cartella_finta(tmp_path, monkeypatch):
    """Le consigliate già mostrate (`consigli.FILE_CONSIGLIATE`) mai nel file vero di `dati/`: ogni test parte senza, e quella
    ricordata da un test non cambia la consigliata di un altro."""
    from fanta import consigli
    monkeypatch.setattr(consigli, "FILE_CONSIGLIATE", tmp_path / "consigliate-finte.json")


@pytest.fixture
def multiutente(tmp_path, monkeypatch):
    """Modalità multiutente accesa su una cartella temporanea (la vera `dati/` non si tocca), con password veloci da calcolare
    e limiti nuovi (il database dei limiti sta nella cartella temporanea). FANTA_PROXY=1: l'indirizzo di chi chiede si legge da X-Forwarded-For, così i test lo scelgono loro."""
    from fanta import account
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "utenti-prova"))
    monkeypatch.setenv("FANTA_PROXY", "1")
    monkeypatch.delenv("MAX_UTENTI", raising=False)
    monkeypatch.setattr(account, "COSTO", {"n": 2 ** 4, "r": 8, "p": 1})
    orologio = Orologio()
    orologio.t = 1000.0
    monkeypatch.setattr(account, "_orologio", lambda: orologio.t)
    yield orologio


@pytest.fixture
def dati_isolati(tmp_path, monkeypatch):
    """Se per un errore una rotta risultasse aperta, il test non deve poter toccare i dati veri né fare cose vere (aggiornamenti,
    avvisi): tutti i file personali vanno in una cartella temporanea e le azioni verso l'esterno sono spente."""
    from fanta import affidabilita, archivio, avvisi, diario, immagini, notifiche, osservati, push, scelte, server
    d = tmp_path / "dati-finti"
    for modulo, nome, percorso in ((server, "FILE_REGOLE", d / "regole.json"), (server, "FILE_ROSE", d / "rose.json"),
                                   (server, "FILE_MOVIMENTI", d / "movimenti.json"), (server, "FILE_ICONA", d / "icona.json"),
                                   (server, "RADICE", d), (scelte, "FILE_SCELTE", d / "scelte.json"),
                                   (osservati, "FILE_OSSERVATI", d / "osservati.json"), (diario, "FILE", d / "diario.json"),
                                   (affidabilita, "FILE", d / "affidabilita.json"),
                                   (immagini, "CARTELLA", d / "immagini"), (push, "FILE_VAPID", d / "vapid.json"),
                                   (push, "FILE_ISCRIZIONI", d / "push.json"), (notifiche, "FILE_IMPOSTAZIONI", d / "avvisi.json"),
                                   (notifiche, "FILE_STATO", d / "n.json"), (notifiche, "FILE_PROMEMORIA", d / "p.json"),
                                   (notifiche, "FILE_RIEPILOGO", d / "r.json"), (avvisi, "FILE_STATO", d / "a.json")):
        monkeypatch.setattr(modulo, nome, percorso)
    try:                                           # nella versione pubblica il modulo delle foto non c'è
        from fanta import foto
        monkeypatch.setattr(foto, "CARTELLA", d / "foto")
    except ImportError:
        pass
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "archivio-finto" / "fanta.sqlite"))     # archivio vuoto, non quello vero
    monkeypatch.setattr(server.aggiorna, "esegui", lambda **k: [])
    monkeypatch.setattr(server, "_scalda", lambda *a, **k: None)
    monkeypatch.setattr(server, "_versione_dati", lambda: None)
    monkeypatch.setattr(notifiche, "_invia_ntfy", lambda *a, **k: False)
    monkeypatch.setattr(push, "invia", lambda *a, **k: 0)
    return d


@pytest.fixture(autouse=True)
def _ricerche_gia_contate_azzerate():
    """Le richieste già contate oggi si ricordano in memoria (vedi limiti.conta): ogni test riparte da zero."""
    from fanta import limiti
    limiti._gia_contate.clear()
    yield
    limiti._gia_contate.clear()


NODE_ITALIANO = str(Path(__file__).resolve().parent / "node_italiano.cjs")


@pytest.fixture(autouse=True)
def _node_in_italiano(monkeypatch):
    """I test del codice web girano con Node, che prende navigator.language dalla lingua del sistema (inglese sui server
    di GitHub, italiano sul PC): l'app sceglierebbe l'inglese. Ogni Node lanciato dai test precarica node_italiano.cjs."""
    vero = subprocess.run

    def run(args, *a, **k):
        if isinstance(args, (list, tuple)) and args and os.path.basename(str(args[0])).lower() in ("node", "node.exe"):
            args = [args[0], "--require", NODE_ITALIANO, *args[1:]]
        return vero(args, *a, **k)

    monkeypatch.setattr(subprocess, "run", run)
