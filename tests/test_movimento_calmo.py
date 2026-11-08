"""«Ridurre movimento» non deve spegnere tutte le animazioni (MARCHIO.md): resta la versione calma."""
from pathlib import Path
import codice_web

WEB = Path(__file__).resolve().parent.parent / "fanta" / "web"


def test_niente_blocco_totale_delle_animazioni():
    css = (WEB / "stile.css").read_text(encoding="utf-8")
    assert "animation-duration: .001ms" not in css, "un blocco globale azzera ogni animazione sotto «riduci movimento»"
    assert "html[data-calmo]" in css and "--mov: 0" in css
    # il marchio dei caricamenti resta vivo nella versione calma
    assert "html[data-calmo] .marchio.muove .capitano" in css and "html[data-calmo] .marchio.muove .punti circle" in css


def test_app_imposta_la_versione_calma():
    js = codice_web.app()
    assert "function segnaMovimento" in js and 'dataset.calmo' in js
    assert "if (menoMovimento()) { fine(); return; }" not in js, "il foglio deve chiudersi con la dissolvenza anche in versione calma"
