import json
from dataclasses import asdict

import pytest

from fanta import regole
from fanta.regole import Regole, modulo_in_numeri


def test_predefinite_valide():
    assert Regole().problemi() == []


def test_salva_e_ricarica(tmp_path):
    f = tmp_path / "regole.json"
    r = regole.imposta(Regole(), "bonus.gol.D", "4.5")
    regole.salva(r, f)
    assert regole.carica(f) == r
    assert regole.carica(f).bonus.gol["D"] == 4.5


def test_file_mancante_da_predefinite(tmp_path):
    assert regole.carica(tmp_path / "manca.json") == Regole()


def test_imposta_converte_intero_in_decimale():
    r = regole.imposta(Regole(), "bonus.assist", "2")
    assert r.bonus.assist == 2.0 and isinstance(r.bonus.assist, float)


def test_imposta_testo_e_liste_e_null():
    r = regole.imposta(Regole(), "nome_lega", "Lega Prova")
    r = regole.imposta(r, "moduli", '["3-4-3", "4-4-2"]')
    r = regole.imposta(r, "voto_senza_sostituto", "4")
    r = regole.imposta(r, "voto_senza_sostituto", "null")
    assert (r.nome_lega, r.moduli, r.voto_senza_sostituto) == ("Lega Prova", ["3-4-3", "4-4-2"], None)


def test_imposta_non_tocca_l_originale():
    r = Regole()
    regole.imposta(r, "bonus.assist", "3")
    assert r.bonus.assist == 1.0


@pytest.mark.parametrize("chiave,valore", [
    ("bonus.assit", "1"),          # chiave sbagliata
    ("bonus.assist", '"tanto"'),   # tipo sbagliato
    ("fonte_voto", "gazzetta"),    # valore non ammesso
    ("moduli", '["3-4-4"]'),       # modulo da 11 di movimento
    ("panchina.tipo", "strana"),
    ("bonus.gol.X", "3"),
])
def test_imposta_rifiuta_errori(chiave, valore):
    with pytest.raises(ValueError):
        regole.imposta(Regole(), chiave, valore)


def test_file_con_chiave_sconosciuta(tmp_path):
    f = tmp_path / "regole.json"
    f.write_text(json.dumps({"bonus": {"assistt": 1}}), encoding="utf-8")
    with pytest.raises(ValueError, match="assistt"):
        regole.carica(f)


def test_modulo_in_numeri():
    assert modulo_in_numeri("3-4-3") == (3, 4, 3)
    assert modulo_in_numeri(" 5 - 4 - 1 ") == (5, 4, 1)
    with pytest.raises(ValueError):
        modulo_in_numeri("343")


def test_numeri_interi_dall_app_diventano_decimali():
    from dataclasses import asdict
    dati = asdict(Regole())
    dati["bonus"]["assist"] = 1
    dati["bonus"]["gol"]["D"] = 4
    r = regole.da_dict(dati)
    assert isinstance(r.bonus.assist, float) and isinstance(r.bonus.gol["D"], float)
    assert regole.imposta(r, "bonus.assist", "1.5").bonus.assist == 1.5


def test_posti_della_panchina_devono_tornare_con_il_numero():
    from fanta.regole import Regole, da_dict
    from dataclasses import asdict
    r = Regole()
    r.panchina.numero, r.panchina.posti = 11, {"P": 2, "D": 3, "C": 3, "A": 3}
    assert r.problemi() == []
    assert da_dict(asdict(r)).panchina.posti == {"P": 2, "D": 3, "C": 3, "A": 3}
    r.panchina.numero = 7
    assert any("somma dei posti" in p for p in r.problemi())
    r.panchina.numero, r.panchina.posti = 11, {"P": 2, "D": 3}
    assert any("panchina.posti" in p for p in r.problemi())


@pytest.mark.parametrize("valore", ["metà", -3, 1.5, float("nan"), None])
def test_rimborso_allo_svincolo_controllato(valore):
    """Prima il rimborso non si controllava: «metà» (o null) passava, si salvava, e poi il Mercato andava in errore a ogni apertura."""
    with pytest.raises(ValueError, match="rimborso"):
        regole.da_dict({"rimborso_svincolo": valore})
    for buono in (0, 0.5, 1):
        assert regole.da_dict({"rimborso_svincolo": buono}).rimborso_svincolo == buono


# ---------------------------------------------------------------- tetti di misura (#480)
LUNGO = "x" * 5000
TROPPO = {
    "nome della lega": ({"nome_lega": "L" * 101}, "nome della lega"),
    "troppi moduli": ({"moduli": ["3-4-3"] * 31}, "al massimo 30 moduli"),
    "modulo lunghissimo": ({"moduli": [" " * 5000 + "3-4-3"]}, "ogni modulo si scrive come 3-4-3"),
    "troppe fasce": ({"modificatore_difesa": {"soglie": [[6 + i / 100, 1] for i in range(21)]}}, "al massimo 20 fasce"),
    "troppe eccezioni": ({"rinvii_giornate": {f"20{a}-{a + 1}/{g}": "aspetta" for a in range(10, 13) for g in range(1, 39)}},
                         "al massimo 76 eccezioni"),
    "giornata lunghissima": ({"rinvii_giornate": {LUNGO: "aspetta"}}, "2026-27/12"),
    "troppe finestre": ({"finestre_scambio": [{"dal": "2026-11-14"}] * 21}, "al massimo 20 finestre"),
    "gol con troppi ruoli": ({"bonus": {"gol": {"P": 3, "D": 3, "C": 3, "A": 3} | {f"{LUNGO}{i}": 1 for i in range(50)}}}, "bonus.gol"),
    "rosa con troppi ruoli": ({"rosa": {"P": 3, "D": 8, "C": 8, "A": 6} | {f"{LUNGO}{i}": 1 for i in range(50)}}, "rosa"),
    "posti con troppi ruoli": ({"panchina": {"posti": {"P": 2, "D": 3, "C": 3, "A": 3} | {f"{LUNGO}{i}": 0 for i in range(50)},
                                             "numero": 11}}, "panchina.posti"),
}


@pytest.mark.parametrize("nome", sorted(TROPPO))
def test_regole_oltre_i_tetti_errore_chiaro_senza_ripetere_i_dati(nome):
    """Liste e testi oltre i tetti: errore apposta (il server risponde 422) con una frase che non ripete il valore ricevuto."""
    campi, frase = TROPPO[nome]
    with pytest.raises(regole.RegoleTroppoGrandi, match=frase) as e:
        regole.da_dict(campi)
    assert LUNGO[:50] not in str(e.value) and len(str(e.value)) < 500


def test_regole_al_limite_dei_tetti_vanno_bene():
    r = regole.da_dict({"nome_lega": "L" * regole.MAX_NOME_LEGA, "moduli": [" 3 - 4 - 3 ", "4-4-2"],
                        "modificatore_difesa": {"soglie": [[6 + i / 100, 1] for i in range(regole.MAX_SOGLIE)]}})
    assert len(r.modificatore_difesa.soglie) == regole.MAX_SOGLIE


def test_un_file_salvato_prima_dei_tetti_si_legge_ancora(tmp_path):
    """Regole salvate quando i tetti non c'erano (nome lungo, tante fasce): si leggono come prima; per salvarle di nuovo vanno accorciate."""
    f = tmp_path / "regole.json"
    vecchio = asdict(Regole()) | {"nome_lega": "L" * 150}
    vecchio["modificatore_difesa"]["soglie"] = [[6 + i / 100, 1] for i in range(25)]
    f.write_text(json.dumps(vecchio), encoding="utf-8")
    r = regole.carica(f)
    assert r.nome_lega == "L" * 150 and len(r.modificatore_difesa.soglie) == 25
    with pytest.raises(regole.RegoleTroppoGrandi, match="nome della lega"):
        regole.salva(r, f)
