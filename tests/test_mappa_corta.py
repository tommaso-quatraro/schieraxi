"""`MAPPA.md` resta corta (issue #620): una riga per cartella o file importante, i dettagli in `docs/RIFERIMENTO.md`.

La mappa si consulta con una ricerca e chi lavora la legge spesso: con un tetto di righe e di lunghezza della riga non torna
a crescere come prima (era arrivata a più di 300 righe)."""
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
MAPPA = RADICE / "MAPPA.md"
MAX_RIGHE = 120
MAX_CARATTERI = 200


def test_mappa_entro_il_tetto_di_righe():
    righe = MAPPA.read_text(encoding="utf-8").splitlines()
    assert len(righe) <= MAX_RIGHE, (f"MAPPA.md ha {len(righe)} righe, al massimo {MAX_RIGHE}: i dettagli vanno in "
                                     "docs/RIFERIMENTO.md")


def test_ogni_riga_della_mappa_entro_il_tetto_di_caratteri():
    lunghe = [(n, len(r)) for n, r in enumerate(MAPPA.read_text(encoding="utf-8").splitlines(), start=1) if len(r) > MAX_CARATTERI]
    assert not lunghe, (f"righe di MAPPA.md oltre {MAX_CARATTERI} caratteri (numero, lunghezza): {lunghe}. Si va a capo, si divide "
                        "la riga della tabella o il dettaglio passa in docs/RIFERIMENTO.md")


def test_i_dettagli_hanno_dove_andare():
    assert (RADICE / "docs" / "RIFERIMENTO.md").is_file()
    assert "docs/RIFERIMENTO.md" in MAPPA.read_text(encoding="utf-8")
