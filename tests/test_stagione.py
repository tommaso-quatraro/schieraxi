"""Passaggio di stagione (fanta/stagione.py) e campo `stagione` delle rose: solo nomi di stagione nel formato «2026-27».
Tutto su cartelle temporanee e rose inventate."""
import json

import pytest

from fanta import lega, percorsi, stagione

STRANE = ["../../fuori", "..\\..\\fuori", "2026-27/../../fuori", "..", "2026", "26-27", "2026-27\n", "2026-27 ", "2026_27",
          "precedente", "٢٠٢٦-٢٧"]


def _lega(tmp_path, nome_stagione: str):
    """Una cartella `lega` con rose (una giocatore), regole e una scelta da archiviare; restituisce (rose, file delle rose, scelta)."""
    cartella = tmp_path / "utente" / "lega"
    cartella.mkdir(parents=True)
    file = cartella / "rose.json"
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 20)], 3)], "Mia", "", "2026-27")
    lega.salva(rose, file)
    (cartella / "regole.json").write_text("{}", encoding="utf-8")
    scelta = cartella / "scelte.json"
    scelta.write_text("{}", encoding="utf-8")
    rose.stagione = nome_stagione               # come se fosse arrivata da fuori, senza passare dal controllo delle rose
    return rose, file, scelta


def _tutti_i_file(cartella):
    return {p.relative_to(cartella).as_posix(): p.read_bytes() for p in sorted(cartella.rglob("*")) if p.is_file()}


@pytest.mark.parametrize("nome_stagione", STRANE)
def test_l_archivio_non_accetta_una_stagione_che_non_e_una_stagione(tmp_path, nome_stagione):
    rose, file, scelta = _lega(tmp_path, nome_stagione)
    prima = _tutti_i_file(tmp_path)
    with pytest.raises(ValueError):
        stagione.archivia_e_riparti(rose, file, "2027-28", 500, [scelta])
    assert _tutti_i_file(tmp_path) == prima                          # niente scritto, niente spostato, niente cancellato
    assert not (file.parent / "archivio").exists()


def test_l_archivio_non_accetta_un_percorso_completo(tmp_path):
    altrove = tmp_path / "altrove"
    rose, file, scelta = _lega(tmp_path, str(altrove))
    prima = _tutti_i_file(tmp_path)
    with pytest.raises(ValueError):
        stagione.archivia_e_riparti(rose, file, "2027-28", 500, [scelta])
    assert not altrove.exists() and _tutti_i_file(tmp_path) == prima


def test_la_risposta_dice_la_stagione_archiviata_e_non_dove_sta(tmp_path):
    rose, file, scelta = _lega(tmp_path, "2026-27")
    r = stagione.archivia_e_riparti(rose, file, "2027-28", 500, [scelta])
    assert r == {"archivio": "2026-27", "squadre": 1, "stagione": "2027-28"}
    testo = json.dumps(r)
    assert str(tmp_path) not in testo and "/" not in testo and "\\" not in testo
    assert (file.parent / "archivio" / "2026-27" / "rose.json").exists() and not scelta.exists()


def test_senza_stagione_segnata_vale_quella_del_file(tmp_path):
    rose, file, scelta = _lega(tmp_path, "")
    r = stagione.archivia_e_riparti(rose, file, "2099-00", 500, [scelta])
    assert lega.stagione_valida(r["archivio"]) and (file.parent / "archivio" / r["archivio"] / "rose.json").exists()


def test_dentro_vuole_un_percorso_sotto_la_cartella(tmp_path):
    archivio = tmp_path / "lega" / "archivio"
    assert percorsi.dentro(archivio, archivio / "2026-27")
    assert percorsi.dentro(archivio, archivio / "2026-27" / "rose.json")
    for fuori in (archivio, archivio / ".." / "x", archivio / ".." / ".." / "altro", tmp_path / "altrove", archivio / str(tmp_path / "y"),
                  archivio / "a\x00b"):                    # un nome che il disco non accetta: no, senza errori
        assert not percorsi.dentro(archivio, fuori), fuori


@pytest.mark.parametrize("nome_stagione", STRANE + [7, ["2026-27"], {"a": 1}])
def test_le_rose_con_una_stagione_strana_non_si_leggono(nome_stagione):
    with pytest.raises(ValueError):
        lega.da_dict({"squadre": [], "stagione": nome_stagione})


@pytest.mark.parametrize("dati, attesa", [({"squadre": []}, ""), ({"squadre": [], "stagione": ""}, ""),
                                          ({"squadre": [], "stagione": None}, ""), ({"squadre": [], "stagione": "2026-27"}, "2026-27")])
def test_le_rose_con_la_stagione_giusta_o_senza_si_leggono(dati, attesa):
    assert lega.da_dict(dati).stagione == attesa
