"""Differenze tra due importazioni delle rose: scambi, svincolati presi, tagli, crediti."""
import json

from fanta import lega, movimenti


def _g(i, nome, ruolo="C"):
    return lega.GiocatoreRosa(i, nome, ruolo, "XXX", 10)


def _rose(**squadre):
    return lega.Rose([lega.Squadra(n, gs, cr) for n, (gs, cr) in squadre.items()], None)


PRIMA = _rose(
    A=([_g(1, "Rowe"), _g(2, "Kaiki", "D"), _g(3, "Bayo", "A")], 50),
    B=([_g(4, "Paz"), _g(5, "Mangas", "D")], 30),
    C=([_g(6, "Zambo")], 20),
)


def test_prima_importazione():
    d = movimenti.differenze(None, PRIMA)
    assert d["prima_importazione"] and "3 squadre" in d["testo"]


def test_nessuna_differenza():
    d = movimenti.differenze(PRIMA, PRIMA)
    assert d["nessuna_differenza"] and d["testo"] == "Nessuna differenza rispetto a prima."


def test_scambio_svincolato_taglio_e_crediti():
    dopo = _rose(
        A=([_g(4, "Paz"), _g(2, "Kaiki", "D"), _g(9, "Mendy", "A")], 44),    # Rowe<->Paz con B; Bayo lasciato, Mendy preso
        B=([_g(1, "Rowe"), _g(5, "Mangas", "D")], 30),
        C=([_g(6, "Zambo")], 20),
    )
    d = movimenti.differenze(PRIMA, dopo)
    assert len(d["scambi"]) == 1
    sc = d["scambi"][0]
    assert sc["squadre"] == ["A", "B"] and [g["nome"] for g in sc["da_a"]] == ["Rowe"] and [g["nome"] for g in sc["da_b"]] == ["Paz"]
    assert d["svincolati_presi"][0]["squadra"] == "A" and d["svincolati_presi"][0]["giocatori"][0]["nome"] == "Mendy"
    assert d["tagliati"][0]["giocatori"][0]["nome"] == "Bayo"
    assert d["crediti"] == [{"squadra": "A", "prima": 50, "dopo": 44}]
    assert "Scambio A / B: Rowe ⇄ Paz" in d["testo"]


def test_passaggio_senza_contropartita():
    dopo = _rose(A=([_g(2, "Kaiki", "D"), _g(3, "Bayo", "A")], 50), B=([_g(4, "Paz"), _g(5, "Mangas", "D"), _g(1, "Rowe")], 30),
                 C=([_g(6, "Zambo")], 20))
    d = movimenti.differenze(PRIMA, dopo)
    assert "Passaggio da A a B: Rowe" in d["testo"]


def test_squadre_che_spariscono_o_nuove_non_creano_movimenti():
    dopo = _rose(A=([_g(1, "Rowe"), _g(2, "Kaiki", "D"), _g(3, "Bayo", "A")], 50),
                 D=([_g(4, "Paz")], 10))       # B e C spariscono, D è nuova: Paz "cambia squadra" ma D è nuova
    d = movimenti.differenze(PRIMA, dopo)
    assert not d["scambi"] and not d["svincolati_presi"] and not d["tagliati"]
    # ...ma non è «nessuna differenza»: si dice quali squadre sono arrivate o sparite
    assert d["squadre_nuove"] == ["D"] and d["squadre_tolte"] == ["B", "C"] and not d["nessuna_differenza"]
    assert d["testo"] == "Squadre aggiunte: D\nSquadre tolte: B, C"


def test_prima_importazione_di_una_squadra_al_singolare():
    assert movimenti.differenze(None, _rose(A=([_g(1, "Rowe")], 50)))["testo"] == "Prima importazione: 1 squadra."


def test_storico_si_salva_solo_se_cambia_qualcosa(tmp_path):
    f = tmp_path / "movimenti.json"
    movimenti.registra(f, movimenti.differenze(PRIMA, PRIMA))
    assert movimenti.leggi(f) == []
    dopo = _rose(A=([_g(2, "Kaiki", "D")], 50), B=([_g(4, "Paz"), _g(5, "Mangas", "D")], 30), C=([_g(6, "Zambo")], 20))
    movimenti.registra(f, movimenti.differenze(PRIMA, dopo))
    s = movimenti.leggi(f)
    assert len(s) == 1 and "lascia liberi" in s[0]["testo"]
    f.write_text("rovinato", encoding="utf-8")
    assert movimenti.leggi(f) == []


def _lega_intera(base: int) -> lega.Rose:
    """20 squadre da 40 giocatori, con numeri che partono da `base`: due leghe con basi diverse non hanno giocatori in comune."""
    return lega.Rose([lega.Squadra(f"Squadra {s}", [_g(base + s * 40 + i, f"Giocatore dal nome lungo {base + s * 40 + i}")
                                                    for i in range(40)], 100) for s in range(20)], None)


def test_storico_con_un_tetto_di_spazio(tmp_path):
    """Importazioni che cambiano tutte le rose, una dopo l'altra: il file resta sotto il suo tetto (escono le voci più vecchie)
    e l'ultima voce c'è sempre."""
    f = tmp_path / "movimenti.json"
    prima = _lega_intera(0)
    for giro in range(1, 13):
        dopo = _lega_intera(giro * 1000)
        diff = movimenti.differenze(prima, dopo)
        movimenti.registra(f, diff)
        prima = dopo
    assert f.stat().st_size <= movimenti.MAX_BYTE_STORICO
    storico = movimenti.leggi(f)
    assert 1 <= len(storico) < 12 and storico[-1]["testo"] == diff["testo"]


def test_lo_storico_normale_tiene_tutte_le_sue_voci(tmp_path):
    """Il tetto di spazio non tocca uno storico fatto di importazioni normali (pochi movimenti alla volta)."""
    f = tmp_path / "movimenti.json"
    a = _rose(A=([_g(1, "Rowe"), _g(2, "Kaiki", "D")], 50), B=([_g(4, "Paz")], 30))
    b = _rose(A=([_g(1, "Rowe"), _g(4, "Paz")], 45), B=([_g(2, "Kaiki", "D")], 35))
    movimenti.registra(f, movimenti.differenze(a, b))
    f.write_text(json.dumps(movimenti.leggi(f) * movimenti.MAX_STORICO, ensure_ascii=False), encoding="utf-8")
    movimenti.registra(f, movimenti.differenze(b, a))
    storico = movimenti.leggi(f)
    assert len(storico) == movimenti.MAX_STORICO and "Kaiki" in storico[-1]["testo"]


def test_giocatore_prima_non_riconosciuto_e_poi_si_non_conta_come_movimento():
    prima = _rose(A=([_g(None, "Mendy P."), _g(2, "Kaiki", "D")], 50))
    dopo = _rose(A=([_g(77, "Mendy P."), _g(2, "Kaiki", "D")], 50))
    d = movimenti.differenze(prima, dopo)
    assert d["nessuna_differenza"], d["testo"]
