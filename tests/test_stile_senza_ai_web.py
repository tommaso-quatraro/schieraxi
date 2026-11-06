"""La web non deve sembrare generata in serie: i segni vietati di docs/STILE-SENZA-AI.md non tornano nel CSS."""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "fanta" / "web" / "stile.css").read_text(encoding="utf-8")


def test_fondo_piatto_senza_macchie_che_si_muovono():
    assert ".sfondo { position: fixed; inset: 0; z-index: -1; background: var(--sfondo); }" in CSS
    assert "@keyframes deriva" not in CSS


def test_superfici_piene_senza_sfocatura():
    """Grafica B (spec §7.5-7.6): niente vetro sfocato. Le superfici sono piene: il «vetro» e le carte prendono il fondo della
    pagina nei tre blocchi dei temi, e la testata non torna semitrasparente (senza sfocatura si leggerebbe il testo sotto)."""
    assert "backdrop-filter" not in CSS
    temi = [CSS.split(":root {", 1)[1].split("\n}", 1)[0], CSS.split("@media (prefers-color-scheme: light) {")[1].split("}")[0],
            CSS.split(':root[data-tema="chiaro"] {')[1].split("}")[0]]
    for blocco in temi:
        assert "--vetro: var(--sfondo);" in blocco and "--vetro-carta: var(--sfondo);" in blocco
    testata = re.search(r"\.testata\.vetro \{([^}]*)\}", CSS)
    assert not testata or "transparent" not in testata.group(1)


def test_niente_riflessi_lucidi_sulle_superfici():
    assert "inset 0 1.5px 0 var(--luce)" not in CSS                      # il bordo luminoso in alto di ogni carta
    assert not re.search(r"linear-gradient\(1[5-7]0deg, (?:var\(--luce-2\)|rgba\(255, 255, 255)", CSS)   # il lucido obliquo
    assert ".carta::after" not in CSS                                     # il riflesso che seguiva il dito


def test_niente_aloni_luminosi():
    assert not re.search(r"box-shadow: 0 0 \d+px var\(--", CSS)


def test_etichette_senza_maiuscole_spaziate():
    # unica eccezione: la prima lettera di «sab 31» / «ieri» nei titoli dei giorni
    maiuscole = re.findall(r"([^{}\n]*)\{[^}]*text-transform: uppercase", CSS)
    assert [m.strip() for m in maiuscole] == [".giorno-titolo::first-letter"]


def test_niente_transition_all_e_niente_cascata_di_entrate():
    assert "transition: all" not in CSS
    assert "main > :nth-child(2) { animation-delay" not in CSS
    assert ".elenco li:nth-child(2) { animation-delay" not in CSS
