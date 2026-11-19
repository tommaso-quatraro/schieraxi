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
    # l'avviso dice come si esce dopo il controllo, e non parla di altre versioni in attesa (non ce ne sono)
    assert "--fidati" in s.avvisi()[-1] and "arrivat" not in s.avvisi()[-1]


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


@con_bash
@pytest.mark.parametrize(("salvata", "subito"), [("ieri, forse\n", True), (f"0{ORA_ZERO}\n", False)])
def test_ora_salvata_illeggibile_o_con_lo_zero_davanti(s, salvata, subito):
    """Un'ora dell'ultima installazione illeggibile vale come nessuna (subito). Con uno zero davanti è la stessa ora: bash la
    leggerebbe in base otto, con un errore, e installerebbe subito invece di raggruppare."""
    _scrivi(s.stato, "ultima-installazione", salvata)
    c2 = _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(10)
    assert (s.riavvii() == 1) is subito and (s.ultimo() == c2) is subito


@con_bash
def test_versione_urgente_durante_una_partita_resta_rimandata(s):
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    c3 = _commit(s.lavoro, URGENTE, **{"fanta/__init__.py": "V3"})
    s.esito_libero.write_text("3", encoding="utf-8")                       # partita in corso: l'urgenza salta solo l'intervallo
    s.giro(10)
    assert s.riavvii() == 1 and s.codice() == "V2"
    s.esito_libero.write_text("0", encoding="utf-8")
    s.giro(20)                                                              # l'ora non è passata, ma è urgente
    assert s.riavvii() == 2 and s.ultimo() == c3


@con_bash
def test_ultima_versione_rifiutata_con_una_buona_sotto_resta_fuori_e_l_avviso_lo_dice(s):
    """Scelta (#635): se l'ultima versione viene rifiutata, quelle buone raggruppate sotto non si installano da sole (un ripiego
    automatico su una versione non provata potrebbe alternare due versioni rotte, con un riavvio ogni 10 minuti). L'avviso del
    rifiuto lo dice; entrano con la prossima versione buona."""
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, "Versione 1.6: codice 3, buona", **{"fanta/__init__.py": "V3"})
    s.giro(10)                                                              # raggruppata
    _commit(s.lavoro, "Versione 1.7: codice 4, non parte", **{"fanta/__init__.py": "V4"})
    s.codice_curl.write_text("500", encoding="utf-8")
    s.giro(60)                                                              # si installa la 4, non risponde: si torna alla 2
    s.codice_curl.write_text("200", encoding="utf-8")
    assert s.codice() == "V2" and "la versione arrivata prima" in s.avvisi()[-1]
    s.giro(130)
    assert s.codice() == "V2" and s.riavvii() == 3
    c5 = _commit(s.lavoro, "codice 5, correzione", **{"fanta/__init__.py": "V5"})
    s.giro(140)
    assert s.ultimo() == c5 and s.codice() == "V5" and s.riavvii() == 4


@con_bash
def test_versione_rifiutata_con_sotto_solo_documenti_non_parla_di_versioni_in_attesa(s):
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, "Solo documenti (#60)", **{"docs/d.md": "doc3"})
    _commit(s.lavoro, "Versione 1.6: codice 4, non parte", **{"fanta/__init__.py": "V4"})
    s.codice_curl.write_text("500", encoding="utf-8")
    s.giro(70)
    assert s.codice() == "V2"
    assert "La versione nuova non partiva" in s.avvisi()[-1] and "arrivat" not in s.avvisi()[-1]     # sotto, solo documenti


@con_bash
def test_unione_senza_ancora_il_commit_di_versione_aspetta_il_giro_dopo(s):
    """Il job rilascia crea il commit di versione 10-20 secondi dopo l'unione. Un giro che cade in mezzo non installa l'unione da
    sola (numero di versione e novità vecchi, con il raggruppamento per un'ora): aspetta il giro dopo."""
    _commit(s.lavoro, "Correzione (#50)", **{"fanta/__init__.py": "V2", "fanta/novita.d/correzione.json": "{}"})
    s.giro(10)
    assert s.riavvii() == 0 and _righe(s, "commit di versione")
    (s.lavoro / "fanta" / "novita.d" / "correzione.json").unlink()
    c3 = _commit(s.lavoro, "Versione 1.6: Correzione", **{"fanta/novita.json": "[]"})
    s.giro(20)
    assert s.riavvii() == 1 and s.ultimo() == c3


@con_bash
def test_rilascia_fermo_mezz_ora_dal_primo_giro_che_aspetta_anche_con_altre_unioni(s, monkeypatch):
    """Job rilascia fermo: la novità resta in main e arrivano altre unioni. La mezz'ora si conta dal primo giro che ha aspettato, non
    dall'ora dell'ultimo commit (anche nel futuro): un'unione nuova non la fa ripartire. Poi si installa lo stesso, con un avviso;
    quando il commit di versione arriva, «di nuovo a posto»."""
    env = {"SCHIERAXI_INTERVALLO_MINUTI": "0"}
    _commit(s.lavoro, "Correzione (#50)", **{"fanta/__init__.py": "V2", "fanta/novita.d/correzione.json": "{}"})
    s.giro(10, **env)
    s.giro(20, **env)
    monkeypatch.setenv("GIT_COMMITTER_DATE", f"@{ORA_ZERO + 90 * 60} +0000")           # orologio di chi committa avanti
    _commit(s.lavoro, "Altra unione (#51)", **{"docs/d.md": "doc"})
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    s.giro(30, **env)
    assert s.riavvii() == 0 and len(_righe(s, "commit di versione")) == 1 and not _righe(s, "installo lo stesso")
    c4 = _commit(s.lavoro, "Ancora un'unione (#52)", **{"docs/d.md": "doc 2"})
    s.giro(40, **env)                                                       # mezz'ora dal giro delle 10
    assert s.riavvii() == 1 and s.ultimo() == c4 and _righe(s, "installo lo stesso")
    assert len(s.avvisi()) == 1 and "rilascia" in s.avvisi()[0]
    (s.lavoro / "fanta" / "novita.d" / "correzione.json").unlink()
    c5 = _commit(s.lavoro, "Versione 1.6: Correzione", **{"fanta/novita.json": "[]"})
    s.giro(50, **env)
    assert s.riavvii() == 2 and s.ultimo() == c5
    assert len(s.avvisi()) == 2 and "di nuovo" in s.avvisi()[1]


@con_bash
@pytest.mark.parametrize("come", ["file", "variabile"])
def test_installazione_forzata_non_aspetta_il_commit_di_versione(s, come, monkeypatch):
    """La leva d'emergenza deve funzionare anche se il job rilascia è fermo (unione appena arrivata, novità in attesa)."""
    env = {"SCHIERAXI_INSTALLA_SUBITO": "1"} if come == "variabile" else {}
    if come == "file":
        (s.stato / "installa-subito").write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_COMMITTER_DATE", f"@{ORA_ZERO + 5 * 60} +0000")            # unione di cinque minuti prima
    c2 = _commit(s.lavoro, "Correzione urgente (#50)", **{"fanta/__init__.py": "V2", "fanta/novita.d/correzione.json": "{}"})
    s.giro(10, **env)
    assert s.riavvii() == 1 and s.ultimo() == c2 and not (s.stato / "installa-subito").exists()


# ---------------------------------------------------------------- rifiniture (#647)

@con_bash
@pytest.mark.parametrize("perche", ["partita", "intervallo"])
def test_rilascia_fermo_e_installazione_rimandata_installo_lo_stesso_una_volta_sola(s, perche):
    """#647, 1: finita la mezz'ora di attesa del commit di versione, se l'installazione è rimandata (partita o intervallo) i giri dopo
    non riscrivono «installo lo stesso» senza installare: la riga è una, l'installazione arriva al primo giro libero."""
    env = {"SCHIERAXI_INTERVALLO_MINUTI": "0"} if perche == "partita" else {}
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0, **env)
    assert s.riavvii() == 1
    c3 = _commit(s.lavoro, "Correzione (#50)", **{"fanta/__init__.py": "V3", "fanta/novita.d/correzione.json": "{}"})
    s.giro(10, **env)                                                       # aspetta il commit di versione
    if perche == "partita":
        s.esito_libero.write_text("3", encoding="utf-8")
    s.giro(40, **env)                                                       # mezz'ora passata, ma rimandata
    s.giro(50, **env)
    assert s.riavvii() == 1 and s.codice() == "V2"
    assert len(_righe(s, "installo lo stesso")) == 1
    s.esito_libero.write_text("0", encoding="utf-8")
    s.giro(60, **env)
    assert s.riavvii() == 2 and s.ultimo() == c3 and s.codice() == "V3"
    assert len(_righe(s, "installo lo stesso")) == 1


@con_bash
def test_dopo_una_versione_rifiutata_la_successiva_aspetta_di_nuovo_il_commit_di_versione(s):
    """#647, 2: una versione rifiutata (qui: installata a forza, non risponde, si torna indietro) non lascia l'attesa del commit di
    versione: la versione dopo aspetta il suo commit di versione e non parte un avviso «rilascia fermo» non vero."""
    env = {"SCHIERAXI_INTERVALLO_MINUTI": "0"}
    c2 = _commit(s.lavoro, "Correzione (#50)", **{"fanta/__init__.py": "V2", "fanta/novita.d/correzione.json": "{}"})
    s.giro(10, **env)                                                       # aspetta il commit di versione
    s.codice_curl.write_text("500", encoding="utf-8")
    s.giro(20, SCHIERAXI_INSTALLA_SUBITO="1", **env)                        # forzata, non risponde: si torna indietro
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2 and s.codice() == "V1"
    assert not (s.stato / "attesa-versione").exists()
    s.codice_curl.write_text("200", encoding="utf-8")
    _commit(s.lavoro, "Altra correzione (#51)", **{"fanta/__init__.py": "V3", "fanta/novita.d/altra.json": "{}"})
    s.giro(45, **env)                                                       # 35 minuti dal primo giro che aveva aspettato
    assert s.riavvii() == 2 and s.codice() == "V1"
    assert len(_righe(s, "senza ancora il commit di versione")) == 2 and not _righe(s, "installo lo stesso")
    assert not [a for a in s.avvisi() if "rilascia" in a]


@con_bash
def test_installazione_forzata_non_riuscita_resta_richiesta_fino_a_quella_riuscita(s):
    """#647, 3: il file installa-subito si toglie solo a installazione riuscita. Se le librerie non si installano, al giro dopo la
    richiesta c'è ancora: si installa anche durante la partita."""
    s.esito_libero.write_text("3", encoding="utf-8")                       # partita in corso
    (s.stato / "installa-subito").write_text("", encoding="utf-8")
    s.esito_pip.write_text("1", encoding="utf-8")
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    s.giro(0, uscita=1)
    assert s.riavvii() == 0 and s.codice() == "V1"
    assert (s.stato / "installa-subito").exists()
    s.esito_pip.write_text("0", encoding="utf-8")
    s.giro(10)
    assert s.riavvii() == 1 and s.ultimo() == c2 and s.codice() == "V2"
    assert not (s.stato / "installa-subito").exists()


@con_bash
def test_versione_rifiutata_con_sotto_una_modifica_al_server_senza_commit_di_versione_l_avviso_la_nomina(s):
    """#647, 4: sotto la versione rifiutata c'è una modifica al server rimasta senza commit di versione (job rilascia saltato): non
    è installata e l'avviso lo dice. Conta il confronto delle cartelle del server, non i soli commit «Versione …»."""
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, "Correzione (#61)", **{"fanta/__init__.py": "V3"})
    s.giro(10)                                                              # raggruppata
    _commit(s.lavoro, "Versione 1.6: codice 4, non parte", **{"fanta/__init__.py": "V4"})
    s.codice_curl.write_text("500", encoding="utf-8")
    s.giro(70)
    assert s.codice() == "V2"
    assert "La versione nuova non partiva" in s.avvisi()[-1] and "arrivat" in s.avvisi()[-1]


@con_bash
def test_versione_rifiutata_l_unione_che_numera_non_e_una_modifica_arrivata_prima(s):
    """Revisione di #647: il rilascio di tutti i giorni è un'unione con codice e novità, poi il commit di versione che tocca solo le
    novità. Se quella versione è rifiutata, l'unione che numera è la versione rotta, non «una modifica arrivata prima»."""
    _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0)
    _commit(s.lavoro, "Correzione (#62)", **{"fanta/__init__.py": "V3", "fanta/novita.d/correzione.json": "{}"})
    (s.lavoro / "fanta" / "novita.d" / "correzione.json").unlink()
    _commit(s.lavoro, "Versione 1.6: Correzione", **{"fanta/novita.json": "[]"})
    s.codice_curl.write_text("500", encoding="utf-8")
    s.giro(70)
    assert s.codice() == "V2"
    assert "La versione nuova non partiva" in s.avvisi()[-1]
    assert "arrivat" not in s.avvisi()[-1] and "partita" not in s.avvisi()[-1]


@con_bash
def test_installazione_forzata_tornata_indietro_l_avviso_dice_che_la_richiesta_resta_attiva(s):
    """Revisione di #647: installa-subito resta finché un'installazione non riesce. L'avviso del rifiuto lo dice: la prossima
    versione si installa subito, anche durante una partita."""
    (s.stato / "installa-subito").write_text("", encoding="utf-8")
    c2 = _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.codice_curl.write_text("500", encoding="utf-8")
    s.giro(0)
    assert s.codice() == "V1" and (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2
    assert (s.stato / "installa-subito").exists()
    assert "La versione nuova non partiva" in s.avvisi()[-1] and "anche durante una partita" in s.avvisi()[-1]


SCAMBIO_CHE_NON_RIESCE = 'case "$*" in *".venv.nuova "*"/.venv") exit 1;; esac\nexec /usr/bin/mv "$@"'


@con_bash
def test_scambio_degli_ambienti_non_riuscito_rimette_subito_la_versione_di_prima(s):
    """Revisione di #647: se l'ambiente Python nuovo non prende il posto di quello in uso, codice e ambiente tornano subito quelli di
    prima. Al giro dopo la copia di sicurezza è quella della versione di prima: un ritorno indietro riporta davvero lì."""
    _stub(s.bin, "mv", SCAMBIO_CHE_NON_RIESCE)
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    s.giro(0, uscita=1)
    assert s.riavvii() == 0 and s.codice() == "V1" and base._venv(s) == "vecchia"
    assert (s.app / "requirements.txt").read_text(encoding="utf-8") == "r1"
    assert len(s.avvisi()) == 1 and "ambienti Python" in s.avvisi()[0]
    (s.bin / "mv").unlink()
    s.codice_curl.write_text("500", encoding="utf-8")                      # si riprova, la versione nuova non parte
    s.giro(10)
    assert s.codice() == "V1" and base._venv(s) == "vecchia"
    assert (s.app / "requirements.txt").read_text(encoding="utf-8") == "r1"
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2


@con_bash
def test_installazione_rimasta_a_meta_non_sovrascrive_la_copia_di_sicurezza(s):
    """Revisione di #647: se un'installazione si ferma a metà (qui: lo scambio non riesce e neanche il ripristino), il giro dopo
    rimette la versione di prima dalla copia di sicurezza invece di rifarla con il codice mai provato."""
    _stub(s.bin, "mv", SCAMBIO_CHE_NON_RIESCE)
    _stub(s.bin, "tar", 'case "${1:-}" in xzf) exit 1;; esac\nexec /usr/bin/tar "$@"')
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    s.giro(0, uscita=1)
    assert s.riavvii() == 0 and base._venv(s) == "vecchia"
    (s.bin / "mv").unlink()
    (s.bin / "tar").unlink()
    s.codice_curl.write_text("500", encoding="utf-8")
    s.giro(10)
    assert s.codice() == "V1" and base._venv(s) == "vecchia"
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2
    assert _righe(s, "non era finita")


@con_bash
def test_installazione_interrotta_il_giro_dopo_rimette_subito_la_versione_di_prima(s):
    """Revisione di #647: un giro fermato a metà (qui: ucciso subito dopo il riavvio, con il codice e l'ambiente Python nuovi già al
    loro posto). Il giro dopo rimette subito codice e ambiente di prima dalla copia di sicurezza, lo scrive e avvisa; la copia
    resta quella buona, quindi anche un altro ritorno indietro porta alla versione di prima."""
    sudo_normale = f'echo "sudo $*" >> "{base._msys(s.chiamate)}"'
    _stub(s.bin, "sudo", sudo_normale + '\nkill -9 "$PPID"')                # il giro muore dopo il riavvio
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode != 0 and s.codice() == "V2" and base._venv(s) == "nuova"
    assert (s.stato / "installazione-in-corso").exists()
    _stub(s.bin, "sudo", sudo_normale)
    s.codice_curl.write_text("500", encoding="utf-8")                      # la reinstallazione non parte: si torna indietro
    s.giro(10)
    assert s.codice() == "V1" and base._venv(s) == "vecchia"
    assert (s.app / "requirements.txt").read_text(encoding="utf-8") == "r1"
    assert not (s.stato / "installazione-in-corso").exists()
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2
    assert _righe(s, "non era finita") and any("a metà" in a for a in s.avvisi())


def _sudo(s, poi=""):
    """Il finto sudo del server, con un comando in più dopo l'annotazione (per esempio: il giro muore qui)."""
    _stub(s.bin, "sudo", f'echo "sudo $*" >> "{base._msys(s.chiamate)}"' + (f"\n{poi}" if poi else ""))


@con_bash
def test_interruzione_a_installazione_riuscita_non_lascia_la_versione_vecchia_segnata_come_installata(s):
    """Seconda revisione di #647: il segno si toglie prima di scrivere ultimo-rilascio. Un giro che muore proprio lì non deve lasciare
    il codice di prima con lo stato «installata la nuova» (il giro dopo non la riproverebbe più)."""
    segno = s.casa / "ucciso-una-volta"
    _stub(s.bin, "rm", f'case "$*" in *installazione-in-corso*) [ -e "{base._msys(segno)}" ] || '
                       f'{{ : > "{base._msys(segno)}"; kill -9 "$PPID"; exit 1; }};; esac\nexec /usr/bin/rm "$@"')     # ucciso: il segno resta
    c2 = _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode != 0 and segno.exists() and (s.stato / "installazione-in-corso").exists()
    s.giro(10)
    assert s.ultimo() == c2 and s.codice() == "V2"


@con_bash
def test_interruzione_subito_dopo_lo_scambio_degli_ambienti_rimette_anche_l_ambiente_di_prima(s):
    """Seconda revisione di #647: il segno dice «ambiente» prima dello scambio. Un giro che muore appena scambiati gli ambienti non
    lascia il codice di prima con l'ambiente Python nuovo."""
    _stub(s.bin, "mv", '/usr/bin/mv "$@"; rc=$?\ncase "$*" in *".venv.nuova "*"/.venv") kill -9 "$PPID"; sleep 5;; esac\nexit $rc')
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode != 0 and base._venv(s) == "nuova"
    (s.bin / "mv").unlink()
    s.codice_curl.write_text("500", encoding="utf-8")                      # la reinstallazione non parte: si torna indietro
    s.giro(10)
    assert s.codice() == "V1" and base._venv(s) == "vecchia"
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2


LEGGIMI_INTERROTTA = "Aggiornamento interrotto senza copia di sicurezza"


@con_bash
def test_installazione_interrotta_senza_copia_di_sicurezza_dice_come_ripartire(s):
    """Seconda revisione di #647: segno presente ma copia di sicurezza mancante. Non si installa niente; l'avviso (uno al giorno) dice
    dove leggere come ripartire, e il LEGGIMI ha i comandi. Tolto il segno a mano, gli aggiornamenti ripartono."""
    _scrivi(s.stato, "installazione-in-corso", f"file {s.c1}\n")
    c2 = _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    s.giro(0, uscita=1)
    assert s.riavvii() == 0 and s.codice() == "V1"
    assert len(s.avvisi()) == 1 and LEGGIMI_INTERROTTA in s.avvisi()[0]
    leggimi = (base.SCRIPT / "LEGGIMI.md").read_text(encoding="utf-8")
    assert LEGGIMI_INTERROTTA in leggimi and "git archive" in leggimi and "rm ~/.cache/fantacalcio/installazione-in-corso" in leggimi
    s.giro(10, uscita=1)
    assert len(s.avvisi()) == 1                                            # uno al giorno
    (s.stato / "installazione-in-corso").unlink()
    s.giro(20)
    assert s.ultimo() == c2 and "di nuovo a posto" in s.avvisi()[-1]


@con_bash
def test_versione_interrotta_due_volte_non_si_riprova_piu_neanche_con_installa_subito(s):
    """Seconda revisione di #647: il segno ricorda il commit. La stessa versione interrotta per la seconda volta, dopo il ripristino,
    è rifiutata con un avviso; l'avviso «si era fermato a metà» resta uno al giorno."""
    _sudo(s, f'grep -q V2 "{base._msys(s.app / "fanta" / "__init__.py")}" && {{ kill -9 "$PPID"; sleep 5; }}')
    c2 = _commit(s.lavoro, "codice 2", **{"fanta/__init__.py": "V2"})
    for _ in range(2):                                                      # due giri muoiono con la versione nuova al suo posto
        assert s.esegui("aggiorna-app.sh").returncode != 0
    assert c2 in (s.stato / "installazione-in-corso").read_text(encoding="utf-8")
    s.giro(20)
    assert s.codice() == "V1" and (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2
    assert any("interrotta due volte" in a for a in s.avvisi())
    assert len([a for a in s.avvisi() if "si era fermato a metà" in a]) == 1
    riavvii = s.riavvii()
    (s.stato / "installa-subito").write_text("", encoding="utf-8")
    s.giro(30)
    assert s.codice() == "V1" and s.riavvii() == riavvii
