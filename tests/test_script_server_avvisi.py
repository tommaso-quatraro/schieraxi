"""Avvisi degli script del server e copia notturna dell'archivio (#607).

- aggiorna.sh: lo stato dei guasti è per passo di `python -m fanta aggiorna` (listone, voti, probabili, Understat...), un file per
  passo in ~/.cache/fantacalcio/passi. Avviso con il nome del passo alla seconda volta di fila, poi al massimo uno ogni 24 ore
  finché dura, e «funziona di nuovo» quando torna (se il guasto era stato segnalato). Un passo rotto da giorni non copre più il
  guasto di un altro, come succedeva con il contatore unico.
  L'uscita del finto Python è quella VERA di fanta/aggiorna.py (passi finti, niente rete): se cambia il formato delle righe
  «non riuscito», queste prove se ne accorgono.
- backup-dati.sh: l'archivio delle statistiche (dati/fanta.sqlite) va nella copia notturna, preso con l'API di backup di SQLite a
  servizio acceso, e il ripristino di docs/RIPRISTINO-SERVER.md (pacchetto estratto nella cartella dell'app) lo rimette.
Case finte in cartelle temporanee, finti curl, date e flock: niente server vero, niente rete."""
import contextlib
import json
import os
import shutil
import sqlite3
import tarfile

import pytest

from test_script_server import BASH, _casa_aggiorna, _lancia, _lancia_backup_dati, _msys, _rimuovi, _scrivi, _stub, con_bash

ADESSO = 1_800_000_000          # secondi: l'orologio finto di `date +%s`
ORA = 3600
PASSI_FINTI = ("listone", "calendario", "voti", "probabili", "understat")
INTERROTTO = ("Traceback (most recent call last):\nsqlite3.OperationalError: database is locked\n", 1)


def _uscita_aggiorna(cartella, rotti=(), spenti=()):
    """Le righe vere di `python -m fanta aggiorna` e la sua uscita: i passi in `rotti` alzano un errore, le fonti in `spenti` sono
    spente, gli altri passi riescono senza scaricare niente. Archivio in `cartella`."""
    from fanta import aggiorna, archivio, fonti_attive, funzioni
    vero = archivio.apri
    righe = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(archivio, "apri", lambda: vero(cartella / "fanta.sqlite"))
        mp.setattr(fonti_attive, "acceso", lambda fonte, percorso=None: fonte not in spenti)
        mp.setattr(funzioni, "acceso", lambda nome, *a, **k: False)                # fonti «in ombra» spente
        for nome in PASSI_FINTI:
            def passo(self, *a, _nome=nome, **k):
                if _nome in rotti:
                    raise ConnectionError("la fonte non risponde")
            mp.setattr(aggiorna.Aggiornamento, nome, passo)
        errori = aggiorna.esegui(scrivi=righe.append)
    return "\n".join(righe) + "\n", 1 if errori else 0


@pytest.fixture
def casa(tmp_path):
    """La casa del server con aggiorna.sh, un finto Python che per `fanta aggiorna` stampa l'uscita preparata, un finto curl che
    annota gli avvisi (il JSON mandato a ntfy) e un finto `date +%s` (l'ora del giro)."""
    uscita, esito, orologio = tmp_path / "uscita.txt", tmp_path / "esito.txt", tmp_path / "orologio.txt"
    app, bin_, _ = _casa_aggiorna(tmp_path, f'if [ "$*" = "-m fanta aggiorna" ]; then cat "{_msys(uscita)}"; '
                                            f'exit "$(cat "{_msys(esito)}")"; fi\nexit 0')
    avvisi = tmp_path / "avvisi.txt"
    _stub(bin_, "curl", f'while [ $# -gt 0 ]; do [ "$1" = "-d" ] && printf "%s\\n" "$2" >> "{_msys(avvisi)}"; shift; done\nexit 0')
    _stub(bin_, "date", f'if [ "${{1:-}}" = "+%s" ]; then cat "{_msys(orologio)}"; exit 0; fi\nexec /usr/bin/date "$@"')
    _scrivi(tmp_path, "canale", "canale-di-prova")
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": _msys(tmp_path / "casa"),
           "SCHIERAXI_CANALE": _msys(tmp_path / "canale")}

    class Casa:
        stato = tmp_path / "casa" / ".cache" / "fantacalcio"
        passi = stato / "passi"

        def giro(self, rotti=(), spenti=(), ora=0.0, uscita_pronta=None):
            """Un giro di aggiorna.sh all'ora `ora` (ore dopo ADESSO). `uscita_pronta`: (testo, uscita) di `fanta aggiorna` al posto
            di quella vera. Restituisce i testi degli avvisi mandati in quel giro."""
            testo, rc = uscita_pronta or _uscita_aggiorna(tmp_path / "archivio", rotti, spenti)
            uscita.write_text(testo, encoding="utf-8", newline="\n")
            esito.write_text(str(rc), encoding="utf-8")
            orologio.write_text(str(ADESSO + int(ora * ORA)), encoding="utf-8")
            prima = avvisi.read_text(encoding="utf-8").splitlines() if avvisi.exists() else []
            # se bash si pianta (vedi _lancia) casa e avvisi tornano com'erano prima del giro: il giro ripetuto conta una volta sola
            foto = tmp_path / "foto-casa"
            if foto.exists():
                _rimuovi(foto)
            shutil.copytree(tmp_path / "casa", foto)

            def ripristina():
                _rimuovi(tmp_path / "casa")
                shutil.copytree(foto, tmp_path / "casa")
                avvisi.write_text("".join(f"{riga}\n" for riga in prima), encoding="utf-8")
            r = _lancia([BASH, (app / "script" / "server" / "aggiorna.sh").as_posix()], env=env, ripristina=ripristina)
            assert r.returncode == 0, r.stderr
            dopo = avvisi.read_text(encoding="utf-8").splitlines() if avvisi.exists() else []
            mandati = [json.loads(riga) for riga in dopo[len(prima):]]
            assert all(m["topic"] == "canale-di-prova" and m["title"] == "Fantacalcio" for m in mandati), mandati
            return [m["message"] for m in mandati]

        def log(self):
            return (app / "dati" / "aggiorna.log").read_text(encoding="utf-8")

    return Casa()


def _rotto(nome, giri):
    return f"Aggiornamento dati: «{nome}» non riesce da {giri} giri di fila."


def _di_nuovo(nome):
    return f"Aggiornamento dati: «{nome}» funziona di nuovo."


# ---------------------------------------------------------------- aggiorna.sh: un guasto per passo

@con_bash
def test_una_fonte_rotta_da_tanti_giri_non_copre_il_guasto_di_un_altra(casa):
    """Come sul server il 12/11/2026: una fonte rotta da giorni (contatore unico a 41) zittiva ogni altro guasto."""
    _scrivi(casa.stato, "errori", "41")                    # il contatore unico di prima: non conta più e si toglie
    assert casa.giro(rotti={"understat"}, ora=0) == []
    assert casa.giro(rotti={"understat"}, ora=4) == [_rotto("Understat", 2)]
    for ora in (9, 13, 21):
        assert casa.giro(rotti={"understat"}, ora=ora) == []
    assert casa.giro(rotti={"understat", "probabili"}, ora=24) == []           # probabili: prima volta
    assert casa.giro(rotti={"understat", "probabili"}, ora=26) == [_rotto("probabili", 2)]
    assert not (casa.stato / "errori").exists()
    assert sorted(p.name for p in casa.passi.iterdir()) == ["Understat", "probabili"]
    assert "«probabili»: non riuscito (giri di fila: 2)" in casa.log()


@con_bash
def test_lo_stesso_guasto_avvisa_al_massimo_una_volta_ogni_24_ore(casa):
    esiti = {ora: casa.giro(rotti={"voti"}, ora=ora) for ora in (0, 4, 9, 13, 24, 27.9, 28, 32)}
    assert esiti == {0: [], 4: [_rotto("voti", 2)], 9: [], 13: [], 24: [], 27.9: [],
                     28: [_rotto("voti", 7)],             # 24 ore dopo l'avviso di prima
                     32: []}


@con_bash
def test_un_passo_che_torna_a_funzionare_lo_dice_una_volta(casa):
    casa.giro(rotti={"probabili"}, ora=0)
    assert casa.giro(rotti={"probabili"}, ora=4) == [_rotto("probabili", 2)]
    assert casa.giro(ora=9) == [_di_nuovo("probabili")]
    assert "«probabili»: di nuovo a posto (giri non riusciti di fila: 2)" in casa.log()
    assert casa.giro(ora=13) == []
    assert not list(casa.passi.iterdir())
    # un errore solo, mai segnalato: torna a posto con una riga nel registro e nessun avviso
    assert casa.giro(rotti={"voti"}, ora=17) == [] and casa.giro(ora=21) == []
    assert "«voti»: di nuovo a posto (giri non riusciti di fila: 1)" in casa.log()


@con_bash
def test_giro_interrotto_o_fonte_spenta_non_dicono_che_un_passo_funziona(casa):
    casa.giro(rotti={"understat"}, ora=0)
    assert casa.giro(rotti={"understat"}, ora=4) == [_rotto("Understat", 2)]
    # il comando si ferma prima dei passi: non sa niente di Understat, conta solo il guasto di tutto l'aggiornamento
    assert casa.giro(uscita_pronta=INTERROTTO, ora=9) == []
    assert casa.giro(uscita_pronta=INTERROTTO, ora=13) == \
        ["Aggiornamento dati non riuscito da 2 giri di fila: dettagli in dati/aggiorna.log."]
    assert (casa.passi / "Understat").exists()
    # di nuovo in fondo, con Understat spenta a mano: l'aggiornamento è tornato, Understat non è «di nuovo a posto», solo spenta
    assert casa.giro(spenti={"understat"}, ora=17) == ["Aggiornamento dati di nuovo riuscito."]
    assert "«Understat»: spento, non si controlla più" in casa.log()
    assert not list(casa.passi.iterdir())


@con_bash
def test_nomi_strani_nelle_righe_restano_dentro_la_cartella_e_non_rompono_l_avviso(casa):
    """Il nome del passo viene dall'uscita del comando: nel nome del file di stato e nell'avviso restano solo lettere, cifre, spazi
    e trattini (niente percorsi, niente virgolette che romperebbero il JSON mandato a ntfy)."""
    strana = ('  ! ../../x "a": non riuscito (ValueError: no)\nFatto: 1 richieste, 1 passi non riusciti\n', 1)
    assert casa.giro(uscita_pronta=strana, ora=0) == []
    assert casa.giro(uscita_pronta=strana, ora=4) == [_rotto("x a", 2)]
    assert [p.name for p in casa.passi.iterdir()] == ["x-a"]
    assert not (casa.stato.parent.parent / "x").exists()


# ---------------------------------------------------------------- backup-dati.sh: l'archivio delle statistiche nella copia

def _servizio_con_dati(app):
    """L'archivio come lo tiene aperto il servizio (modo WAL), con una riga storica e una del registro ancora nel file -wal."""
    from fanta import archivio
    servizio = archivio.apri(app / "dati" / "fanta.sqlite")
    servizio.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) "
                     "VALUES ('2024-25', 30, '2025-03-30T14:50:00', 1, 1)")
    servizio.execute("INSERT INTO aggiornamenti (cosa, quando) VALUES ('dati di una fonte chiusa', '2025-04-01T10:00:00')")
    servizio.commit()
    assert (app / "dati" / "fanta.sqlite-wal").stat().st_size > 0       # i dati confermati sono ancora nel -wal
    return servizio


@con_bash
def test_backup_dati_mette_l_archivio_nella_copia_e_il_ripristino_lo_rimette(tmp_path):
    from fanta import registro_copia
    app = tmp_path / "app"
    _scrivi(app, "dati/scelte.json", "SCELTE")
    servizio = _servizio_con_dati(app)
    try:
        r, dest, _ = _lancia_backup_dati(tmp_path, app)              # a servizio acceso
    finally:
        servizio.close()
    assert r.returncode == 0, r.stderr
    [pacchetto] = dest.glob("dati-*.tar.gz")
    # ripristino come in docs/RIPRISTINO-SERVER.md, passo 2: il pacchetto estratto nella cartella dell'app nuova
    nuova = tmp_path / "nuova"
    with tarfile.open(pacchetto) as t:
        nomi = t.getnames()
        assert [n for n in nomi if "fanta.sqlite" in n] == ["./dati/fanta.sqlite"], nomi      # un file solo, senza -wal
        t.extractall(nuova, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    copia = nuova / "dati" / "fanta.sqlite"
    with contextlib.closing(sqlite3.connect(copia.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"          # si apre da solo, senza file di appoggio
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert db.execute("SELECT quando FROM aggiornamenti WHERE cosa = 'dati di una fonte chiusa'").fetchall() == \
            [("2025-04-01T10:00:00",)]
        assert db.execute("SELECT stagione, giornata FROM registro_giornate").fetchall() == [("2024-25", 30)]
    # passo 5: il registro è già nell'archivio rimesso, l'importazione non aggiunge niente
    esito = registro_copia.importa(nuova / "dati" / "registro-giornate.json", copia)
    assert esito["registro_giornate"] == (0, 1)


@con_bash
def test_backup_dati_se_la_copia_dell_archivio_non_riesce_niente_pacchetto(tmp_path):
    """Come per il registro: niente copia quella notte (e niente rotazione: restano le copie di prima), una riga nel registro."""
    import sys
    app = tmp_path / "app"
    _scrivi(app, "dati/scelte.json", "SCELTE")
    _servizio_con_dati(app).close()
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    # il Python vero, tranne la copia dell'archivio (python -c ... dati/fanta.sqlite), che non riesce
    _stub(bin_, "python-finto", 'case "$*" in "-c "*dati/fanta.sqlite*) echo "disco pieno" >&2; exit 1;; esac\n'
                                f'exec "{_msys(sys.executable)}" "$@"')
    r, dest, cache = _lancia_backup_dati(tmp_path, app, python="python-finto")
    assert r.returncode == 1
    assert not list(dest.glob("dati-*.tar.gz"))
    assert "copia dell'archivio delle statistiche non riuscita: disco pieno" in (cache / "backup-dati.log").read_text(encoding="utf-8")
