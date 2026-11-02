"""Gli interruttori da ambiente (repository unico): predefiniti pubblici, profilo del server con le variabili, lega e tratti dei volti."""
import json
import os
import subprocess
import sys
from pathlib import Path

from fanta import avatar

RADICE = Path(__file__).resolve().parent.parent


def esegui(codice: str, **ambiente) -> str:
    """Un processo nuovo: gli interruttori si leggono all'avvio, non a ogni richiesta."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("FANTA_")}
    env.update(ambiente)
    env["PYTHONPATH"] = str(RADICE)
    r = subprocess.run([sys.executable, "-c", codice], cwd=RADICE, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    return r.stdout.strip()


STATO = ("from fanta import fonti_attive as fa, funzioni as fn; "
         "print(fa.PREDEFINITO_ACCESO, fn.VERSIONE_PUBBLICA, fa.acceso('fantacalcio'), fa.acceso('foto'), "
         "fn.predefinito('diario'), fn.predefinito('asta'), fn.predefinito('live'))")


def test_predefiniti_pubblici():
    assert esegui(STATO) == "False True False False False False False"      # fonti spente, funzioni nascoste


def test_profilo_del_server_con_le_variabili():
    out = esegui(STATO, FANTA_FONTI_PREDEFINITO="1", FANTA_PROFILO_FUNZIONI="completo")
    assert out == "True False True False True False True"                    # fonti accese (le foto no), tutto acceso tranne l'asta


def test_valori_strani_restano_pubblici():
    out = esegui(STATO, FANTA_FONTI_PREDEFINITO="si", FANTA_PROFILO_FUNZIONI="boh")
    assert out == "False True False False False False False"


def test_lega_dal_percorso_scelto_e_predefinito(tmp_path):
    assert esegui("from fanta.percorsi import CARTELLA_LEGA as c; print(c)", FANTA_LEGA=str(tmp_path)) == str(tmp_path)
    ora = esegui("from fanta.percorsi import CARTELLA_LEGA as c; print(c)")
    assert Path(ora) in (RADICE / "lega", RADICE / "lega" / "esempio")


def test_la_lega_d_esempio_e_completa_e_si_carica():
    from fanta import lega
    from fanta.regole import carica
    cartella = RADICE / "lega" / "esempio"
    rose = lega.carica(cartella / "rose.json")
    assert len(rose.squadre) == 10 and rose.mia_squadra in {s.nome for s in rose.squadre}
    assert carica(cartella / "regole.json").nome_lega == "Lega d'esempio"


def test_senza_lega_vera_si_usa_l_esempio(tmp_path, monkeypatch):
    """Una copia del progetto senza lega/regole.json (come il repository pubblico) parte con la lega d'esempio."""
    from fanta import percorsi
    (tmp_path / "lega" / "esempio").mkdir(parents=True)
    monkeypatch.setattr(percorsi, "RADICE", tmp_path)
    monkeypatch.delenv("FANTA_LEGA", raising=False)
    assert percorsi.cartella_lega() == tmp_path / "lega" / "esempio"
    (tmp_path / "lega" / "regole.json").write_text("{}", encoding="utf-8")
    assert percorsi.cartella_lega() == tmp_path / "lega"
    monkeypatch.setenv("FANTA_LEGA", str(tmp_path / "altra"))
    assert percorsi.cartella_lega() == tmp_path / "altra"


def _scrivi_tratti(p: Path, pelle: int):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"versione": 3, "tratti": {"7": {"p": pelle, "c": 1, "a": "R", "b": 0}}}), encoding="utf-8")


def test_tratti_da_ambiente_poi_dal_file_vicino_poi_neutro(tmp_path, monkeypatch):
    vicino, esterno = tmp_path / "fanta" / "avatar_tratti.json", tmp_path / "dati" / "avatar_tratti.json"
    monkeypatch.setattr(avatar, "FILE", vicino)
    monkeypatch.setattr(avatar, "RADICE", tmp_path)
    monkeypatch.delenv("FANTA_AVATAR_TRATTI", raising=False)
    try:
        avatar.tutti.cache_clear()
        assert avatar.tutti() == {} and avatar.di(7) is None                      # senza file: volto neutro, nessun errore
        _scrivi_tratti(vicino, 2)
        avatar.tutti.cache_clear()
        assert avatar.di(7)["p"] == 2                                             # file accanto al codice
        _scrivi_tratti(esterno, 5)
        monkeypatch.setenv("FANTA_AVATAR_TRATTI", "dati/avatar_tratti.json")      # relativo alla radice
        avatar.tutti.cache_clear()
        assert avatar.di(7)["p"] == 5
        monkeypatch.setenv("FANTA_AVATAR_TRATTI", str(tmp_path / "non-c-e.json"))  # indicato ma assente: ripiega sul file vicino
        avatar.tutti.cache_clear()
        assert avatar.di(7)["p"] == 2
        vicino.unlink()
        avatar.tutti.cache_clear()
        assert avatar.tutti() == {}
    finally:
        avatar.tutti.cache_clear()
