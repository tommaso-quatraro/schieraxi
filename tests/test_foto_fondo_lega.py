"""Le foto iOS «-fondo» della Lega: Stato dei dati e Rosa (issue #425).

`lega-stato-fondo` e `lega-rosa-fondo` non scorrevano: la foto usciva uguale a quella senza «-fondo» e le parti nuove in basso (gli
indicatori del consiglio e i gol attesi nostri di Stato dei dati, l'ultima riga della Rosa) non si vedevano. Il Diario, che aveva
`lega-diario-fondo`, è la pagina Giornate (#673 passo 2): la riga su tutta la Serie A sta nei suoi «Dettagli» (foto
`giornate-dettagli`). Lo script toglie «-fondo» dal nome e manda `-DEMO_FONDO 1`; la demo (`Demo.applica`)
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

# nome della foto -> (pagina che apre la demo, file della vista che scorre)
FOTO = {
    "lega-stato-fondo": ("lega-stato", LEGA / "LegaExtra.swift"),
    "lega-stato-nostri": ("lega-stato", LEGA / "LegaExtra.swift"),   # #430: i gol attesi nostri non stanno nella foto del fondo
    "lega-rosa-fondo": ("lega-rosa", LEGA / "LegaExtra.swift"),
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


def test_la_foto_delle_nostri_apre_stato_dei_dati_e_chiede_il_punto_delle_nostri():
    # «lega-stato-nostri» non finisce per «-fondo»: la demo apre «lega-stato» e il valore di -DEMO_FONDO dice dove fermarsi
    testo = SCRIPT.read_text(encoding="utf-8")
    assert 'lega-stato-nostri) schermata="lega-stato"; fondo=(-DEMO_FONDO nostri) ;;' in testo


@pytest.mark.parametrize("foto", sorted(FOTO))
def test_la_demo_apre_la_pagina_della_foto(foto):
    pagina = FOTO[foto][0]
    assert f'case "{pagina}":' in DEMO.read_text(encoding="utf-8"), f"Demo.applica non conosce «{pagina}»"


@pytest.mark.parametrize("foto", sorted(FOTO))
def test_la_vista_scorre_solo_in_demo_con_la_foto_fondo(foto):
    pagina, file = FOTO[foto]
    chiamate = [c for c in _chiamate_demo_scorri_a(file.read_text(encoding="utf-8")) if f'schermate: ["{pagina}"]' in c]
    assert len(chiamate) == 1, f"{file.name}: serve un .demoScorriA con schermate: [\"{pagina}\"]"
    # inFondo: true = scorre solo con -DEMO_FONDO; senza, anche la foto «lega-…» (la cima della pagina) scorrerebbe
    assert "inFondo: true" in chiamate[0]


def test_la_riga_del_fondo_c_e_solo_in_demo_con_il_fondo_e_solo_in_stato_e_rosa():
    regola = (LEGA / "FondoDemo.swift").read_text(encoding="utf-8")
    assert 'Demo.argomento("DEMO_FONDO", in: argomenti)' in regola
    # Stato dei dati e Rosa finiscono con la riga
    assert (LEGA / "LegaExtra.swift").read_text(encoding="utf-8").count("RigaFondoDemo()") == 2


def test_il_punto_delle_nostri_sta_sulla_prima_riga_del_riquadro_e_la_lista_lo_usa():
    # una sola riga con l'identità (se fossero più righe, la foto si fermerebbe su una a caso)
    assert (LEGA / "GolAttesiNostriSezione.swift").read_text(encoding="utf-8").count(".id(FondoDemo.idNostri)") == 1
    assert "FondoDemo.arrivoDiStato" in (LEGA / "LegaExtra.swift").read_text(encoding="utf-8")
    regola = (LEGA / "FondoDemo.swift").read_text(encoding="utf-8")
    assert 'Demo.argomento("DEMO_FONDO", in: argomenti) == "nostri"' in regola


def test_le_righe_delle_misure_non_si_stringono_in_altezza():
    # #430: la riga prende l'altezza che i testi chiedono; senza, la VStack stringeva il nome a una riga con «…»
    riga = (LEGA / "RigaMisuraRegistro.swift").read_text(encoding="utf-8")
    assert ".fixedSize(horizontal: false, vertical: true)" in riga
    assert "lineLimit" not in riga and "truncationMode" not in riga
