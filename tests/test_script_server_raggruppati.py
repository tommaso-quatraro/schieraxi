"""aggiorna-app.sh: installazioni raggruppate (#635).

Le PR si uniscono e hanno la loro versione subito, ma sul server l'installazione si raggruppa: fra due installazioni riuscite almeno
un intervallo (predefinito 60 minuti; sul server variabile SCHIERAXI_INTERVALLO_MINUTI o file ~/.config/schieraxi/intervallo-minuti,
0 = come prima). Alla scadenza si installa l'ultima versione di main, in un colpo solo. Subito: una versione segnata urgente dal job
rilascia (riga «Rilascio: urgente» in un commit nuovo, firmato), l'installazione forzata, la prima volta e con l'orologio tornato
indietro. Il rimando per le partite resta e si somma.
Lo script vero, con il server finto di test_script_server.py (casa, «GitHub» con i commit firmati, finti sudo, curl e flock) e un
orologio finto (`date +%s`)."""
import importlib.util

import pytest

import test_script_server as base
from test_script_server import RADICE, _commit, _msys, _scrivi, _stub, con_bash

server = base.server                       # le fixture del server finto, per nome
chiavi_di_prova = base.chiavi_di_prova

_spec = importlib.util.spec_from_file_location("assegna_versione", RADICE / "script" / "ci" / "assegna_versione.py")
assegna_versione = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(assegna_versione)
URGENTE = f"Versione 1.6: Correzione dei voti\n\n{assegna_versione.RIGA_URGENTE}"     # come lo scrive il job rilascia

ORA_ZERO = 1_800_000_000          # secondi: l'orologio finto parte da qui


@pytest.fixture
def s(server, tmp_path):
    """Il server finto con l'orologio finto: s.giro(minuti) è un giro del cron a ORA_ZERO + minuti."""
    orologio = tmp_path / "orologio.txt"
    _stub(server.bin, "date", f'if [ "${{1:-}}" = "+%s" ]; then cat "{_msys(orologio)}"; exit 0; fi\nexec /usr/bin/date "$@"')

    def giro(minuti, *argomenti, uscita=0, **env):
        orologio.write_text(str(ORA_ZERO + minuti * 60), encoding="utf-8")
        r = server.esegui("aggiorna-app.sh", *argomenti, **env)
        assert r.returncode == uscita, r.stdout + r.stderr
        return r
    server.giro = giro
    server.codice = lambda: (server.app / "fanta" / "__init__.py").read_text(encoding="utf-8")
    server.impostazione = lambda testo: _scrivi(server.casa / ".config" / "schieraxi", "intervallo-minuti", testo)
    return server


def _righe(s, parola):
    return [r for r in s.log().splitlines() if parola in r]


@con_bash
def test_prima_installazione_senza_stato_subito_e_l_intervallo_in_uso_nel_registro(s):
    """Nessuna installazione registrata (il primo giro con questo script): si installa subito, come prima. Il valore in uso si
    legge nel registro dal primo giro, anche senza versioni nuove, e non a ogni giro."""
    c2 = _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    assert s.riavvii() == 1 and s.ultimo() == c2
    s.giro(10)                                                              # niente di nuovo
    [riga] = _righe(s, "intervallo fra due installazioni")
    assert "60 minuti" in riga and "predefinito" in riga


@con_bash
def test_due_versioni_a_venti_minuti_una_sola_installazione_dell_ultima_allo_scadere_dell_ora(s):
    c2 = _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    assert s.riavvii() == 1 and s.ultimo() == c2
    c3 = _commit(s.lavoro, "codice 3", **{"fanta/__init__.py": "V3"})
    s.giro(10)
    s.giro(20)
    c4 = _commit(s.lavoro, "codice 4", **{"fanta/__init__.py": "V4"})
    s.giro(30)
    prima = base._istantanea(s.stato)
    r = s.giro(40, "--prova")
    assert "[prova] rimanderei" in r.stdout and "raggruppate" in r.stdout and c4[:7] in r.stdout
    assert base._istantanea(s.stato) == prima                              # --prova non scrive lo stato
    assert s.riavvii() == 1 and s.ultimo() == c2 and s.codice() == "V2"
    rimandi = _righe(s, "raggruppata")
    assert len(rimandi) == 2 and c3[:7] in rimandi[0] and c4[:7] in rimandi[1]     # una riga per versione, non a ogni giro
    s.giro(60)
    assert s.riavvii() == 2 and s.ultimo() == c4 and s.codice() == "V4"             # l'ultima, in un colpo solo
    assert len(_righe(s, "raggruppata")) == 2


@con_bash
@pytest.mark.parametrize("come", ["file", "variabile"])
def test_intervallo_zero_come_prima(s, come):
    """0 = ogni versione subito. Dal file sul server, o dalla variabile, che vale più del file."""
    if come == "file":
        s.impostazione("0\n")
        env = {}
    else:
        s.impostazione("60\n")
        env = {"SCHIERAXI_INTERVALLO_MINUTI": "0"}
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0, **env)
    c3 = _commit(s.lavoro, "codice 3", **{"fanta/__init__.py": "V3"})
    s.giro(10, **env)
    assert s.riavvii() == 2 and s.ultimo() == c3
    assert not _righe(s, "raggruppata")
    [riga] = _righe(s, "intervallo fra due installazioni")
    assert "0 minuti" in riga


@con_bash
def test_valore_non_valido_vale_il_predefinito_e_lo_dice(s):
    s.impostazione("un'ora\n")
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, "codice 3", **{"fanta/__init__.py": "V3"})
    s.giro(10)
    assert s.riavvii() == 1 and len(_righe(s, "raggruppata")) == 1
    [riga] = _righe(s, "intervallo fra due installazioni")
    assert "60 minuti" in riga and "non valido" in riga


@con_bash
def test_versione_urgente_subito_anche_con_altri_commit_dopo(s):
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, URGENTE, **{"fanta/__init__.py": "V3"})
    c4 = _commit(s.lavoro, "Solo documenti (#41)", **{"docs/d.md": "doc4"})
    s.giro(10)
    assert s.riavvii() == 2 and s.ultimo() == c4 and s.codice() == "V3"
    assert _righe(s, "urgente") and not _righe(s, "raggruppata")


@con_bash
def test_il_segno_urgente_vale_solo_come_riga_intera(s):
    """Il titolo di una PR finisce nel titolo del commit di unione: «Rilascio: urgente (#40)» non è il segno del rilascio."""
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, f"{assegna_versione.RIGA_URGENTE} (#40)", **{"fanta/__init__.py": "V3"})
    s.giro(10)
    assert s.riavvii() == 1 and len(_righe(s, "raggruppata")) == 1


@con_bash
def test_il_segno_urgente_in_un_commit_senza_firma_non_installa(s):
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    c3 = _commit(s.lavoro, URGENTE, _firma=False, **{"fanta/__init__.py": "MALIGNO"})
    s.giro(10, uscita=1)
    assert s.riavvii() == 1 and s.codice() == "V2"
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c3


@con_bash
def test_partite_e_intervallo_si_sommano_senza_perdere_versioni(s):
    """La partita finisce dentro l'intervallo: si aspetta ancora l'ora. L'ora scade durante un'altra partita: si aspetta la fine."""
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, "codice 3", **{"fanta/__init__.py": "V3"})
    s.esito_libero.write_text("3", encoding="utf-8")                       # partita in corso
    s.giro(10)
    s.esito_libero.write_text("0", encoding="utf-8")                       # finita, ma l'ora non è passata
    s.giro(30)
    assert s.riavvii() == 1 and s.codice() == "V2"
    c4 = _commit(s.lavoro, "codice 4", **{"fanta/__init__.py": "V4"})
    s.esito_libero.write_text("3", encoding="utf-8")                       # l'ora scade durante un'altra partita
    s.giro(60)
    assert s.riavvii() == 1 and c4[:7] in _righe(s, "rimandata: partite in corso")[-1]
    s.esito_libero.write_text("0", encoding="utf-8")
    s.giro(70)
    assert s.riavvii() == 2 and s.ultimo() == c4 and s.codice() == "V4"


@con_bash
def test_orologio_tornato_indietro_non_blocca_gli_aggiornamenti(s):
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    c3 = _commit(s.lavoro, "codice 3", **{"fanta/__init__.py": "V3"})
    s.giro(-120)                                                            # due ore indietro: non si aspetta fino a domani
    assert s.riavvii() == 2 and s.ultimo() == c3
    c4 = _commit(s.lavoro, "codice 4", **{"fanta/__init__.py": "V4"})
    s.giro(-110)                                                            # l'intervallo riparte dall'ora nuova
    assert s.riavvii() == 2
    s.giro(-60)
    assert s.riavvii() == 3 and s.ultimo() == c4


@con_bash
def test_installazione_non_riuscita_non_fa_partire_l_intervallo(s):
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, "codice 3", **{"fanta/__init__.py": "V3"})
    s.codice_curl.write_text("500", encoding="utf-8")                      # il servizio non risponde: si torna indietro
    s.giro(70)
    assert s.riavvii() == 3 and s.codice() == "V2"
    s.codice_curl.write_text("200", encoding="utf-8")
    c4 = _commit(s.lavoro, "codice 4", **{"fanta/__init__.py": "V4"})
    s.giro(80)                                                              # l'ultima riuscita resta quella dell'ora zero
    assert s.riavvii() == 4 and s.ultimo() == c4


@con_bash
def test_installazione_forzata_non_aspetta_l_intervallo(s):
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    c3 = _commit(s.lavoro, "codice 3", **{"fanta/__init__.py": "V3"})
    (s.stato / "installa-subito").write_text("", encoding="utf-8")
    s.giro(10)
    assert s.riavvii() == 2 and s.ultimo() == c3 and not (s.stato / "installa-subito").exists()
