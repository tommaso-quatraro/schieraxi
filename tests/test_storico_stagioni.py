"""Storico a N stagioni: di default come prima (solo la scorsa), con N scarica le N precedenti, una alla volta."""
import pytest

from fanta import aggiorna, archivio


class _Finto(aggiorna.Aggiornamento):
    """Non scarica nulla: registra solo quali stagioni toccherebbe."""

    def __init__(self, db):
        super().__init__(db, aggiorna.Stagione(2026), scrivi=lambda _: None)
        self.visti: list[tuple[str, str]] = []
        self.slug_noti = {"x"}

    def listone(self): pass
    def calendario(self): pass
    def probabili(self): pass

    def voti(self, stagione=None): self.visti.append(("voti", (stagione or self.st).codice))
    def understat(self, stagione=None, dettaglio_partite=True): self.visti.append(("understat", (stagione or self.st).codice))
    def dati_extra(self, stagione=None): self.visti.append(("dati_extra", (stagione or self.st).codice))
    def quotazioni(self, stagione): self.visti.append(("quotazioni", stagione.codice))


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _stagioni(a):
    return [s for _, s in a.visti]


def test_senza_storico_solo_stagione_corrente(db):
    a = _Finto(db)
    a.esegui()
    assert set(_stagioni(a)) == {"2026-27"}


def test_storico_di_default_e_solo_la_scorsa(db):
    a = _Finto(db)
    a.esegui(storico=True)
    assert set(_stagioni(a)) == {"2026-27", "2025-26"}


def test_storico_a_tre_stagioni(db):
    a = _Finto(db)
    a.esegui(storico=True, stagioni_storiche=3)
    assert set(_stagioni(a)) == {"2026-27", "2025-26", "2024-25", "2023-24"}
    assert _stagioni(a).index("2025-26") < _stagioni(a).index("2024-25")    # prima le più recenti


def test_numero_di_stagioni_fuori_misura_rifiutato(db):
    for n in (0, aggiorna.MAX_STAGIONI_STORICHE + 1):
        with pytest.raises(ValueError):
            _Finto(db).esegui(storico=True, stagioni_storiche=n)


def test_stagione_precedente_di_k():
    assert aggiorna.Stagione(2026).precedente().codice == "2025-26"
    assert aggiorna.Stagione(2026).precedente(3).codice == "2023-24"
