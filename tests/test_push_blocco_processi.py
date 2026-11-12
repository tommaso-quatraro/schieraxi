"""Le iscrizioni alle notifiche (`push.json`) protette anche tra processi diversi (#547).

Il processo dei promemoria toglie le iscrizioni scadute mentre il server ne registra una nuova: con un blocco valido solo dentro
un processo, uno dei due poteva leggere il file prima che l'altro lo riscrivesse e poi scriverci sopra (iscrizione persa o
iscrizione tolta che rinasce). Qui un secondo processo vero si ferma a metà, dopo aver letto e prima di scrivere: in quel
momento questo processo non deve poter scrivere. Nessuna attesa a tempo: i due processi si danno il via con una riga;
il timer serve solo a non lasciare il test appeso se il figlio si blocca.
Dati inventati (indirizzi IP pubblici di esempio, niente rete) e cartelle temporanee.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from fanta import contesto, percorsi, push
from fanta.blocco import BloccoFile

from test_cancellazione_account import ambiente, elimina, nuovo_utente, sola_lettura_che_non_risponde  # noqa: F401 (fixture e aiuti)

RADICE = Path(__file__).resolve().parent.parent
CHIAVI = {"p256dh": "P" * 40, "auth": "A" * 20}
A, B, C, D = ({"endpoint": f"https://8.8.8.8/push/{n}", "keys": CHIAVI} for n in "abcd")
OCCUPATO = "Un'altra operazione sulle notifiche è ancora in corso: riprova fra qualche secondo"

# Il secondo processo: fa l'operazione chiesta, ma subito dopo aver letto push.json scrive «letto» e aspetta il «via».
FIGLIO = r"""
import json, sys
from pathlib import Path
from fanta import push
file, operazione, endpoint = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
vera = push.iscrizioni
def iscrizioni_ferma(percorso=None):
    lista = vera(percorso)
    print("letto", flush=True)
    sys.stdin.readline()
    return lista
push.iscrizioni = iscrizioni_ferma
if operazione == "togli":
    push.togli(endpoint, file)
elif operazione == "tieni_solo":
    push.tieni_solo(endpoint, file)
else:
    push.iscrivi({"endpoint": endpoint, "keys": {"p256dh": "P" * 40, "auth": "A" * 20}}, file)
print("fatto", flush=True)
"""


def indirizzi(file: Path) -> list[str]:
    return [s["endpoint"] for s in push.iscrizioni(file)]


@pytest.mark.parametrize("operazione, endpoint, restano", [
    ("togli", B["endpoint"], [A, C]),               # il promemoria toglie un'iscrizione scaduta
    ("tieni_solo", A["endpoint"], [A, C]),          # cambio di password: resta solo il dispositivo che l'ha chiesto
    ("iscrivi", D["endpoint"], [A, B, D, C]),       # un'altra iscrizione nello stesso momento
])
def test_un_altro_processo_a_meta_scrittura_ferma_l_iscrizione(tmp_path, monkeypatch, operazione, endpoint, restano):
    file = tmp_path / "utente" / "push.json"
    file.parent.mkdir()
    file.write_text(json.dumps([A, B]), encoding="utf-8")
    figlio = subprocess.Popen([sys.executable, "-c", FIGLIO, str(file), operazione, endpoint], cwd=RADICE, text=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              env={**os.environ, "PYTHONPATH": str(RADICE), "FANTA_DATI_UTENTI": str(tmp_path / "account")})
    guardia = threading.Timer(60, figlio.kill)       # solo se il figlio resta appeso: il test non deve bloccare la suite
    guardia.start()
    try:
        assert figlio.stdout.readline().strip() == "letto"         # l'altro processo ha letto e non ha ancora scritto
        monkeypatch.setattr(push, "ATTESA_BLOCCO", 0, raising=False)
        with pytest.raises(TimeoutError):            # il file è occupato dall'altro processo: qui non si scrive niente
            push.iscrivi(C, file)
        figlio.stdin.write("via\n")
        figlio.stdin.flush()
        assert figlio.stdout.readline().strip() == "fatto"
        assert figlio.wait() == 0
    finally:
        guardia.cancel()
        if figlio.poll() is None:
            figlio.kill()
            figlio.wait()
        figlio.stdin.close()
        figlio.stdout.close()
    monkeypatch.setattr(push, "ATTESA_BLOCCO", 10)
    push.iscrivi(C, file)                            # finito l'altro, l'iscrizione entra e non cancella il suo lavoro
    assert indirizzi(file) == [s["endpoint"] for s in restano]


def test_invio_col_file_occupato_lascia_la_scaduta_al_prossimo_giro(tmp_path, monkeypatch):
    """Se un altro processo tiene push.json oltre il tempo massimo, l'avviso è già partito: l'iscrizione scaduta resta (si
    toglie al prossimo invio), in push.log ne resta traccia e il giro degli avvisi non si ferma con un errore."""
    import pywebpush

    class Risposta:
        status_code = 410

    def scaduta(**_):
        raise pywebpush.WebPushException("gone", response=Risposta())
    file = tmp_path / "push.json"
    file.write_text(json.dumps([A]), encoding="utf-8")
    monkeypatch.setattr(push, "FILE_ISCRIZIONI", file)          # push.log accanto, nella cartella temporanea
    monkeypatch.setattr("pywebpush.webpush", scaduta)
    monkeypatch.setattr(push, "ATTESA_BLOCCO", 0, raising=False)
    with BloccoFile(file.with_name("push.json.lock")):           # come se lo tenesse l'altro processo
        assert push.invia("Promemoria", "Schiera la formazione", percorso=file, file_chiavi=tmp_path / "vapid.json") == 0
    assert indirizzi(file) == [A["endpoint"]]
    assert "non tolta" in (tmp_path / "push.log").read_text(encoding="utf-8")


def test_togliere_senza_cartella_non_la_crea(tmp_path):
    """Togliere iscrizioni da una cartella che non c'è (account eliminato, utente che non ha mai salvato niente): niente da
    togliere, e il file del blocco non fa nascere la cartella."""
    file = tmp_path / "utente" / "push.json"
    assert push.togli(A["endpoint"], file) == []
    assert push.tieni_solo(None, file) == []
    assert not file.parent.exists()


def test_iscrizioni_dopo_la_cancellazione_non_ricreano_la_cartella(ambiente):  # noqa: F811
    """Il giro degli avvisi e un'iscrizione partita prima dell'eliminazione dell'account: né il file del blocco né le iscrizioni
    fanno rinascere la cartella dell'utente."""
    c, uid = nuovo_utente("marco")
    ctx = contesto.Contesto.per_utente(uid)
    elimina(c)
    assert push.tieni_solo(None, ctx.iscrizioni_push) == []
    with pytest.raises(push.NonPiuValida):           # la sessione si è chiusa mentre si controllava il nome: niente scritto
        push.iscrivi(A, ctx.iscrizioni_push, ancora_valida=lambda: False)
    assert not ctx.cartella.exists()
    with pytest.raises(push.NonPiuValida):           # anche senza controllo della sessione: l'account non c'è più
        push.iscrivi(A, ctx.iscrizioni_push)
    assert not ctx.cartella.exists()


def test_iscrizione_di_un_account_eliminato_col_database_che_non_risponde_non_lascia_la_cartella(ambiente, monkeypatch):  # noqa: F811
    """Account eliminato e database degli account che non risponde: non si sa se l'account c'è, quindi «riprova» e niente
    scritto, nemmeno il file del blocco in una cartella rinata."""
    c, uid = nuovo_utente("marco")
    ctx = contesto.Contesto.per_utente(uid)
    elimina(c)
    sola_lettura_che_non_risponde(monkeypatch)
    with pytest.raises(percorsi.DatabaseAccountNonRisponde):
        push.iscrivi(A, ctx.iscrizioni_push)
    assert not ctx.cartella.exists()


def test_iscrizioni_col_file_occupato_rispondono_riprova(ambiente, monkeypatch):  # noqa: F811
    """push.json tenuto da un altro processo oltre il tempo massimo: attivare o spegnere le notifiche risponde «riprova» (503)
    con una frase chiara, non con l'errore generico del server, e non scrive niente."""
    c, uid = nuovo_utente("marco")
    file = contesto.Contesto.per_utente(uid).iscrizioni_push
    monkeypatch.setattr(push, "ATTESA_BLOCCO", 0, raising=False)
    with BloccoFile(file.with_name("push.json.lock")):           # come se lo tenesse il processo dei promemoria
        r = c.post("/api/push/iscrivi", json=A)
        assert r.status_code == 503 and r.json()["detail"] == OCCUPATO
        r = c.post("/api/push/disiscrivi", json={"endpoint": A["endpoint"]})
        assert r.status_code == 503 and r.json()["detail"] == OCCUPATO
    assert indirizzi(file) == []
    assert c.post("/api/push/iscrivi", json=A).status_code == 200            # libero: entra
    assert indirizzi(file) == [A["endpoint"]]
