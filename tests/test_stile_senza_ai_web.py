"""La web non deve sembrare generata in serie: i segni vietati di docs/STILE-SENZA-AI.md non tornano nel CSS."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "fanta" / "web"
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")


def test_fondo_piatto_senza_macchie_che_si_muovono():
    """Il fondo è quello del body, piatto: niente più un elemento a parte dietro la pagina (prima `.sfondo`, con le macchie che si
    muovevano e poi piatto), niente animazioni del fondo."""
    assert re.search(r"\nbody \{[^}]*background: var\(--sfondo\);", CSS)
    assert 'class="sfondo"' not in HTML and "\n.sfondo {" not in CSS
    # il fondo anche sotto la fine della pagina: il body è un contenitore (`container`) e il suo fondo non passa alla finestra;
    # senza, nello scuro sotto il contenuto restava il grigio del browser (#121212 invece di #121513, visto nelle foto)
    assert re.search(r"\nhtml \{ background: var\(--sfondo\); \}", CSS)
    assert "@keyframes deriva" not in CSS


def test_superfici_piene_senza_sfocatura():
    """Grafica B (spec §7.5-7.6): niente vetro sfocato. Le superfici sono piene: quello che galleggia (foglio, avvisi, calcolo in
    corso) prende il fondo della pagina e le variabili del vetro trasparente non ci sono più (piano, compito 12.2); la testata non
    torna semitrasparente (senza sfocatura si leggerebbe il testo sotto)."""
    assert "backdrop-filter" not in CSS
    assert "--vetro" not in CSS
    assert re.search(r"\n\.vetro \{[^}]*background: var\(--sfondo\);", CSS)
    testata = re.search(r"\.testata\.vetro \{([^}]*)\}", CSS)
    assert not testata or "transparent" not in testata.group(1)


def test_niente_riflessi_lucidi_sulle_superfici():
    assert "inset 0 1.5px 0 var(--luce)" not in CSS                      # il bordo luminoso in alto di ogni carta
    assert not re.search(r"linear-gradient\(1[5-7]0deg, (?:var\(--luce-2\)|rgba\(255, 255, 255)", CSS)   # il lucido obliquo
    assert ".carta::after" not in CSS                                     # il riflesso che seguiva il dito


def test_niente_aloni_luminosi():
    assert not re.search(r"box-shadow: 0 0 \d+px var\(--", CSS)


def test_etichette_senza_maiuscole_spaziate():
    maiuscole = re.findall(r"([^{}\n]*)\{[^}]*text-transform: uppercase", CSS)
    assert [m.strip() for m in maiuscole] == []


def test_niente_transition_all_e_niente_cascata_di_entrate():
    assert "transition: all" not in CSS
    assert "main > :nth-child(2) { animation-delay" not in CSS
    assert ".elenco li:nth-child(2) { animation-delay" not in CSS
