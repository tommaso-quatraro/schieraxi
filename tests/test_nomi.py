import pytest

from corpus_nomi import genera, listone_inventato, misura
from fanta.listone import Calciatore
from fanta.nomi import Indice, normalizza


@pytest.mark.parametrize("testo,atteso", [
    ("Laurientè", "lauriente"),
    ("Laurienté", "lauriente"),
    ("N'Dicka", "ndicka"),
    ("Esposito Se.", "esposito se"),
    ("Esposito F.P.", "esposito f p"),
    ("  Milinkovic-Savic V. ", "milinkovic savic v"),
])
def test_normalizza(testo, atteso):
    assert normalizza(testo) == atteso


def test_esatto_con_accenti_diversi(indice):
    e = indice.cerca("Laurientè")
    assert e.metodo == "esatto" and e.calciatore.id == 5


def test_apostrofo(indice):
    assert indice.cerca("Ndicka").calciatore.id == 4


def test_abbreviato(indice):
    e = indice.cerca("Esposito S")
    assert e.metodo == "abbreviato" and e.calciatore.id == 8


def test_simile_con_errore_di_battitura(indice):
    e = indice.cerca("Carnesechi")
    assert e.metodo == "simile" and e.calciatore.id == 1


def test_nomi_diversi_non_si_confondono(indice):
    # "Thuram" e "Thuram K." sono due giocatori diversi: il nome esatto vince
    assert indice.cerca("Thuram").calciatore.id == 7
    assert indice.cerca("Thuram K.").calciatore.id == 6


def test_omonimi_ambigui_e_risolti(indice):
    e = indice.cerca("Rossi")
    assert e.metodo == "ambiguo" and {c.id for c in e.alternative} == {15, 16}
    assert indice.cerca("Rossi", ruolo="A").calciatore.id == 16
    assert indice.cerca("Rossi", squadra="Genoa").calciatore.id == 15
    assert indice.cerca("Rossi", squadra="GEN").calciatore.id == 15


def test_filtro_che_esclude_tutti_viene_ignorato(indice):
    # Kean è nel listone con la Fiorentina: una squadra diversa nel file non deve impedirne il riconoscimento
    assert indice.cerca("Kean", squadra="Juventus").calciatore.id == 14


def test_non_trovato(indice):
    assert not indice.cerca("Pinco Pallino").trovato
    assert not indice.cerca("").trovato


def test_squadre_serie_a(indice):
    assert indice.e_squadra_serie_a("Inter")
    assert indice.e_squadra_serie_a("ATA")
    assert not indice.e_squadra_serie_a("Real Esempio")


# ---------- celle sporche, iniziali, omonimi (S3 «Ingresso facile») ----------
@pytest.mark.parametrize("testo", [
    "A Martinez L. (INT) 45", "L. Martinez", "Martinez L. - Inter - 23", "#10 Martinez L. ⭐",
    "A Martinez L. – Inter – 40", "MARTINEZ L.", "Martinez L. 45 cr", "[INT] Martinez L.",
])
def test_cella_sporca_riconosciuta_con_sicurezza(indice, testo):
    e = indice.cerca(testo)
    assert (e.metodo, e.calciatore.id, e.avviso) == ("esatto", 10, "")


def test_iniziali_puntate_davanti(indice):
    assert indice.cerca("F.P. Esposito").calciatore.id == 9
    assert indice.cerca("K. Thuram").calciatore.id == 6
    assert indice.cerca("Jo. Martinez").calciatore.id == 11


def test_iniziale_che_non_e_di_nessuno_non_si_indovina(indice):
    # «A. Martinez» non è né Martinez L. né Martinez Jo.: meglio non trovarlo che dare quello sbagliato
    for testo in ("A. Martinez", "Martinez A"):
        assert not indice.cerca(testo).trovato


def test_solo_cognome(indice):
    e = indice.cerca("Pellegrini")                      # nel listone solo «Pellegrini Lu.»
    assert (e.metodo, e.calciatore.id) == ("abbreviato", 17)   # trovato, ma da controllare
    e = indice.cerca("Martinez")                        # due Martinez: dubbio con entrambi
    assert e.metodo == "ambiguo" and {c.id for c in e.alternative} == {10, 11}
    assert indice.cerca("Martinez", ruolo="P").calciatore.id == 11


def test_ruolo_e_squadra_nella_cella_sciolgono_gli_omonimi(indice):
    assert indice.cerca("Rossi (LEC)").calciatore.id == 16
    assert indice.cerca("D Rossi").calciatore.id == 15
    assert indice.cerca("Rossi - Genoa - 12").calciatore.id == 15


def test_squadra_della_cella_diversa_dal_listone_non_e_sicura(indice):
    e = indice.cerca("Kean (JUV)")
    assert e.calciatore.id == 14 and e.avviso          # trovato ma con l'avviso: da controllare
    # squadra e ruolo passati da chi chiama valgono più di quelli scritti nella cella
    assert indice.cerca("Rossi (GEN)", squadra="Lecce").calciatore.id == 16


def test_lettera_davanti_ruolo_o_iniziale(calciatori):
    # «C Bastoni»: C è il ruolo (nessun Bastoni centrocampista) o l'iniziale di «Bastoni C.»? Non si dà per sicuro
    altri = calciatori + [Calciatore(30, "Bastoni C.", "D", "", "GEN", "genoa", 1, 1, 1)]
    e = Indice(altri).cerca("C Bastoni")
    assert e.metodo == "ambiguo" and {c.id for c in e.alternative} == {3, 30}


def test_errori_di_battitura(indice):
    e = indice.cerca("Barlela")                         # due lettere scambiate
    assert (e.metodo, e.calciatore.id) == ("simile", 12)
    e = indice.cerca("Martinex L.")
    assert (e.metodo, e.calciatore.id) == ("simile", 10)


def test_ordine_invertito(calciatori):
    ind = Indice(calciatori + [Calciatore(31, "Kolo Mbeki", "A", "", "JUV", "juventus", 1, 1, 1)])
    e = ind.cerca("Mbeki Kolo")
    assert (e.metodo, e.calciatore.id) == ("simile", 31)


def test_nomi_che_non_sono_calciatori(indice):
    for testo in ("Inter Nos", "Real Barella", "FC Bomber 2000", "Crediti residui 12", "⚽⚽", "---", "N/D"):
        assert not indice.cerca(testo).trovato, testo


def test_corpus_zero_sicuri_sbagliati():
    """Corpus generato dal listone inventato (tests/corpus_nomi.py): regola d'oro e almeno il 97% di riconosciuti."""
    calciatori = listone_inventato()
    veri, finti, _ = misura(Indice(calciatori), genera(calciatori))
    assert veri["sicuro SBAGLIATO"] == 0 and finti["sicuro SBAGLIATO"] == 0
    assert veri["proposto SBAGLIATO"] == 0 and finti["proposto SBAGLIATO"] == 0
    riconosciuti = veri["sicuro giusto"] + veri["proposto giusto"]
    assert riconosciuti / sum(veri.values()) >= 0.97


def test_nome_e_cognome_per_esteso(indice):
    # il nome proprio comincia con l'iniziale del listone: proposto, mai sicuro
    for testo in ("Lautaro Martinez", "Martinez Lautaro", "Lautaro Martínez (INT)", "A Lautaro Martinez 45"):
        e = indice.cerca(testo)
        assert (e.metodo, e.calciatore.id) == ("abbreviato", 10), testo
    assert indice.cerca("Josep Martinez").calciatore.id == 11
    assert indice.cerca("Francesco Pio Esposito").calciatore.id == 9
    assert indice.cerca("Sebastiano Esposito").calciatore.id == 8
    # un nome proprio che non c'entra con nessuna iniziale: non si indovina
    assert not indice.cerca("Antonio Martinez").trovato
    # «Kevin Thuram»: c'è «Thuram K.» ma anche «Thuram» senza iniziale, il nome proprio può essere suo: dubbio tra i due
    e = indice.cerca("Kevin Thuram")
    assert e.metodo == "ambiguo" and {c.id for c in e.alternative} == {6, 7}


def test_iniziale_in_piu_con_il_cognome_nudo(indice):
    for testo in ("Kean M.", "M. Kean", "Kean M"):
        e = indice.cerca(testo)
        assert (e.metodo, e.calciatore.id) == ("abbreviato", 14), testo
    e = indice.cerca("Thuram M.")                       # «Thuram K.» è un altro: resta il Thuram senza iniziale
    assert (e.metodo, e.calciatore.id) == ("abbreviato", 7)


def test_nome_completo_da_un_altra_fonte(calciatori):
    ind = Indice(calciatori, {7: "Marcus Thuram", 14: "Moise Kean", 999: "Nessuno Qui", 2: "Sommer"})
    for testo in ("Marcus Thuram", "Thuram Marcus", "MOISE KEAN"):
        e = ind.cerca(testo)
        assert e.metodo == "abbreviato" and e.calciatore.id in (7, 14), testo
    assert ind.cerca("Sommer").metodo == "esatto"
    # senza nome completo il cognome nudo non basta: «Real Barella» non è Barella
    assert not ind.cerca("Real Barella").trovato
    assert not Indice(calciatori).cerca("Marcus Thuram").trovato


def test_non_trovato_con_suggerimenti(indice):
    # nessun abbinamento, ma qualche nome somigliante da scegliere a mano (mai scelto in partenza)
    for testo, attesi in (("Dimarko", {13}), ("Dimarko Federico", {13}), ("Carnesecky", {1}), ("Martines Lautaro", {10, 11})):
        e = indice.cerca(testo)
        assert e.metodo == "non trovato" and not e.trovato, testo
        assert {c.id for c in e.alternative} == attesi, testo
    assert not indice.cerca("Pinco Pallino").alternative
