"""Crediti solo con le fonti accese, «Elimina il tuo account» senza contatto, e l'esportazione pubblica che pretende titolare e contatto."""
import importlib.util
import sys

import pytest

from fanta import testi_legali as tl

RADICE = __import__("pathlib").Path(__file__).resolve().parent.parent
FILE_ESPORTA = RADICE / "script" / "pubblico" / "esporta.py"          # nella copia pubblica non c'e'
if FILE_ESPORTA.exists():
    _spec = importlib.util.spec_from_file_location("esporta_pubblico_prova", FILE_ESPORTA)
    esp = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = esp
    _spec.loader.exec_module(esp)


def test_crediti_mostra_solo_le_fonti_accese(monkeypatch):
    fa = pytest.importorskip("fanta.fonti_attive")
    monkeypatch.setattr(fa, "PREDEFINITO_ACCESO", False)
    for k in fa.FONTI:
        monkeypatch.delenv(f"FANTA_FONTE_{k.upper()}", raising=False)
    monkeypatch.setenv("FANTA_FONTE_UNDERSTAT", "1")
    c = tl.pagina("crediti")
    assert "Understat" in c and "Fantacalcio.it:" not in c and "ESPN" not in c and "inserisci tu" in c


def test_elimina_account_senza_contatto_dice_una_frase_chiara(monkeypatch):
    monkeypatch.delenv("FANTA_CONTATTO", raising=False)
    t = tl.pagina("elimina")
    assert "non ha ancora indicato un recapito" in t
    monkeypatch.setenv("FANTA_CONTATTO", "aiuto@example.org")
    t = tl.pagina("elimina")
    assert "Scrivi a aiuto@example.org" in t and "non ha ancora indicato" not in t


@pytest.mark.skipif(not FILE_ESPORTA.exists(), reason="lo strumento di esportazione non e' nella copia pubblica")
def test_la_pubblicazione_vera_pretende_titolare_e_contatto(tmp_path, monkeypatch):
    with pytest.raises(esp.Errore, match="FANTA_TITOLARE"):
        esp.controlla_dati_legali({"FANTA_CONTATTO": "aiuto@example.org"})
    with pytest.raises(esp.Errore, match="FANTA_CONTATTO"):
        esp.controlla_dati_legali({"FANTA_TITOLARE": "Mario Rossi", "FANTA_CONTATTO": "  "})
    esp.controlla_dati_legali({"FANTA_TITOLARE": "Mario Rossi", "FANTA_CONTATTO": "aiuto@example.org"})
    mappa = tmp_path / "mappa.txt"
    mappa.write_text("Real Esempio => Squadra Finta\nSquadra Demo => FC Segnaposto\nLega Vera Di Prova => Lega Esempio\n", encoding="utf-8")
    for v in ("FANTA_TITOLARE", "FANTA_CONTATTO"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(esp.Errore, match="FANTA_TITOLARE"):          # senza --senza-test e senza --prova-con-esempio: rifiuta
        esp.main(["--uscita", str(tmp_path / "u"), "--mappatura", str(mappa)])
    assert not (tmp_path / "u").exists()


def test_ripiego_senza_ambiente_e_accettabile(monkeypatch):
    for v in ("FANTA_CONTATTO", "FANTA_TITOLARE", "FANTA_BACKUP_GIORNI"):
        monkeypatch.delenv(v, raising=False)
    p = tl.pagina("privacy")
    assert "un tempo limitato." in p and "poche settimane" not in p and "chi gestisce questa copia" in p
