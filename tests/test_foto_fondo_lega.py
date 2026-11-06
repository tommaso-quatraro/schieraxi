"""Le foto iOS «-fondo» della Lega: Diario, Stato dei dati e Rosa (issue #425).

`lega-diario-fondo`, `lega-stato-fondo` e `lega-rosa-fondo` non scorrevano: la foto usciva uguale a quella senza «-fondo» e le parti
nuove in basso (la riga su tutta la Serie A del Diario, gli indicatori del consiglio e i gol attesi nostri di Stato dei dati,
l'ultima riga della Rosa) non si vedevano. Lo script toglie «-fondo» dal nome e manda `-DEMO_FONDO 1`; la demo (`Demo.applica`)
apre la pagina e la vista scorre con `demoScorriA` (solo in demo). Qui si controlla che i nomi, la demo e le viste dicano la stessa cosa:
un nome scritto male non darebbe errore, solo una foto uguale a quella di prima.
"""
import re
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
SCRIPT = RADICE / "ios" / "scripts" / "screenshot.sh"
DEMO = RADICE / "ios" / "Sources" / "Support" / "Demo.swift"
LEGA = RADICE / "ios" / "Sources" / "Presentation" / "Lega"

# nome della foto -> file della vista che scorre
FOTO = {
    "lega-diario-fondo": LEGA / "DiarioView.swift",
    "lega-stato-fondo": LEGA / "LegaExtra.swift",
    "lega-rosa-fondo": LEGA / "LegaExtra.swift",
}


def _elenco(nome: str) -> list[str]:
    """Le parole di un array bash di screenshot.sh (da «NOME=(» alla prima «)» a fine riga)."""
    testo = SCRIPT.read_text(encoding="utf-8")
    m = re.search(rf"^{nome}=\((.*?)\)\s*$", testo, re.S | re.M)
    assert m, f"manca l'elenco {nome} in screenshot.sh"
    return m.group(1).split()


def _chiamate_demo_scorri_a(vista: str) -> list[str]:
    """Gli argomenti di ogni `.demoScorriA(...)` della vista (anche su più righe, con parentesi dentro)."""
    return re.findall(r"\.demoScorriA\(((?:[^()]|\([^()]*\))*)\)", vista)


@pytest.mark.parametrize("foto", sorted(FOTO))
def test_il_giro_completo_fotografa_la_variante_fondo(foto):
    assert foto in _elenco("TUTTE")


def test_lo_script_toglie_il_fondo_dal_nome_e_manda_demo_fondo():
    testo = SCRIPT.read_text(encoding="utf-8")
    assert '*-fondo) schermata="${nome%-fondo}"; fondo=(-DEMO_FONDO 1) ;;' in testo


@pytest.mark.parametrize("foto", sorted(FOTO))
def test_la_demo_apre_la_pagina_della_foto(foto):
    pagina = foto.removesuffix("-fondo")
    assert f'case "{pagina}":' in DEMO.read_text(encoding="utf-8"), f"Demo.applica non conosce «{pagina}»"


@pytest.mark.parametrize("foto", sorted(FOTO))
def test_la_vista_scorre_solo_in_demo_con_la_foto_fondo(foto):
    pagina = foto.removesuffix("-fondo")
    chiamate = [c for c in _chiamate_demo_scorri_a(FOTO[foto].read_text(encoding="utf-8")) if f'schermate: ["{pagina}"]' in c]
    assert len(chiamate) == 1, f"{FOTO[foto].name}: serve un .demoScorriA con schermate: [\"{pagina}\"]"
    # inFondo: true = scorre solo con -DEMO_FONDO; senza, anche la foto «lega-…» (la cima della pagina) scorrerebbe
    assert "inFondo: true" in chiamate[0]


def test_la_riga_del_fondo_c_e_solo_in_demo_con_il_fondo_e_solo_in_stato_e_rosa():
    regola = (LEGA / "FondoDemo.swift").read_text(encoding="utf-8")
    assert 'Demo.argomento("DEMO_FONDO", in: argomenti)' in regola
    # Stato dei dati e Rosa finiscono con la riga; il Diario scorre a un riquadro che c'è già (la riga su tutta la Serie A non è in fondo)
    assert (LEGA / "LegaExtra.swift").read_text(encoding="utf-8").count("RigaFondoDemo()") == 2
    assert "RigaFondoDemo" not in (LEGA / "DiarioView.swift").read_text(encoding="utf-8")
