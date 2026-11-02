"""Rose lette con l'OCR dalle schermate «Dettaglio squadra» dell'app di Leghe (app per iPhone): testo «ruolo;nome;club;prezzo» sotto
il nome di ogni fantasquadra. Con ruolo E squadra uguali al listone anche un nome abbreviato è sicuro; se uno dei due non torna,
mai sicuro. Listone e rose INVENTATI (stessi schemi dei nomi veri: iniziali di due lettere, omonimi in squadre diverse, accenti)."""
import pytest

from fanta import lega, limiti, nomi, rose
from fanta.anteprima_rose import anteprima
from fanta.listone import Calciatore
from fanta.regole import Regole

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

SQUADRE = {"ATA": "atalanta", "BOL": "bologna", "CRE": "cremonese", "GEN": "genoa", "INT": "inter", "JUV": "juventus",
           "LAZ": "lazio", "NAP": "napoli", "PIS": "pisa", "ROM": "roma", "SAS": "sassuolo", "TOR": "torino", "VER": "verona"}
INVENTATI = [
    (1, "Ferrandi L.", "A", "INT"), (2, "Ferrandi Jo.", "P", "INT"), (3, "Brahmeri", "D", "NAP"), (4, "Brahmeri Al.", "A", "PIS"),
    (5, "Adamis C.", "D", "TOR"), (6, "Adamis A.", "C", "CRE"), (7, "Spadafino Se.", "A", "SAS"), (8, "Spadafino F.P.", "A", "INT"),
    (9, "Turano", "A", "INT"), (10, "Turano K.", "C", "JUV"), (11, "Koné M.", "C", "ROM"), (12, "Touré E.", "A", "PIS"),
    (13, "N'Dorka", "D", "ROM"), (14, "Milanovic-Sabic V.", "P", "NAP"), (15, "Milanovic-Sabic S.", "C", "LAZ"),
    (16, "Nicolosi Cavaglia", "C", "GEN"), (17, "Ederinho D.S.", "C", "ATA"), (18, "Sandoval Ro.", "C", "BOL"),
    (19, "Lucumì", "D", "BOL"), (20, "Rossetti", "A", "VER"), (21, "Koné I.", "C", "SAS"),
]


@pytest.fixture
def calciatori():
    """Sostituisce quello di conftest anche per `ambiente`: qui solo nomi inventati."""
    return [Calciatore(i, n, r, "", sq, SQUADRE[sq], 10, 10, 100) for i, n, r, sq in INVENTATI]


@pytest.fixture(autouse=True)
def _niente_ricordi_di_altri_test():
    limiti._gia_contate.clear()
    yield
    limiti._gia_contate.clear()


def leggi(testo, calciatori):
    r, avvisi = Regole(), []
    lette = rose.estrai([("testo", rose.griglia_da_testo(testo))], nomi.Indice(calciatori), r.rosa, avvisi)
    return lette, avvisi, anteprima(lette, avvisi, r, None, lega.da_import(lette, None))


def giocatori(risposta, squadra):
    s = next(x for x in risposta["squadre"] if x["nome"] == squadra)
    return {g["testo"]: g for g in s["giocatori"]}


TESTO = """ruolo;nome;club;prezzo
AC Fantasia 21,5
P;Ferrandi J;Inter;3
D;Brahmeri;Napoli;20
D;Adamis;Torino;4
D;N Dorka;ROM;6
C;K0ne  M;Roma;9
C;Ederinho DS;Atalanta;11
C;Sandoval R0.;BOL;1O
A;Ferrandi;Inter;40
A;Spadafino F;Inter;31
A;Tourè E;Pisa;12
crediti;37
Real Esempio
P;Milanovic Sabic;Napoli;2
D;Lucumi;Bologna;5
C;Turano K.;Juventus;14
A;Brahmeri A.;Pisa;8
A;Rossetti;Hellas Verona;3
"""


def test_formato_delle_schermate(calciatori):
    lette, avvisi, a = leggi(TESTO, calciatori)
    assert [s.nome for s in lette] == ["AC Fantasia 21,5", "Real Esempio"]        # virgola e numeri restano nel nome della squadra
    assert avvisi == []
    under = lette[0]
    assert under.crediti_residui == 37 and len(under.righe) == 10
    assert [r.costo for r in under.righe][:3] == [3, 20, 4] and under.righe[6].costo == 10       # «1O» letto come 10
    assert under.righe[0].ruolo == "P" and under.righe[0].squadra == "Inter"


def test_abbreviati_con_ruolo_e_squadra_diventano_sicuri_e_giusti(calciatori):
    _, _, a = leggi(TESTO, calciatori)
    attesi = {"Ferrandi J": 2, "Brahmeri": 3, "Adamis": 5, "N Dorka": 13, "K0ne  M": 11, "Ederinho DS": 17, "Sandoval R0.": 18,
              "Ferrandi": 1, "Spadafino F": 8, "Tourè E": 12}
    g = giocatori(a, "AC Fantasia 21,5")
    assert {t: (x["stato"], x["id"]) for t, x in g.items()} == {t: ("sicuro", i) for t, i in attesi.items()}
    g = giocatori(a, "Real Esempio")
    attesi = {"Milanovic Sabic": 14, "Lucumi": 19, "Turano K.": 10, "Brahmeri A.": 4, "Rossetti": 20}
    assert {t: (x["stato"], x["id"]) for t, x in g.items()} == {t: ("sicuro", i) for t, i in attesi.items()}


@pytest.mark.parametrize("riga,proposti", [
    ("A;Ferrandi Jo.;Inter;1", [2]),           # nome uguale ma il ruolo no: da controllare, con l'avviso
    ("P;Ferrandi L.;Inter;1", [1]),
    ("D;Brahmeri;Pisa;1", [3]),                 # squadra diversa
    ("C;Turano;Juventus;1", [10, 9]),           # l'OCR ha perso «K.»: dubbio tra i due, quello con ruolo e squadra giusti per primo
    ("A;Adamis;Torino;1", [5]),                 # abbreviato con il ruolo sbagliato: mai sicuro (dubbio, senza avviso)
    ("C;Kone;Roma;1", None),                    # «Kone» senza iniziale: c'è anche Koné I. del Sassuolo, ma la squadra scioglie
])
def test_se_ruolo_o_squadra_non_tornano_mai_sicuro(calciatori, riga, proposti):
    _, _, a = leggi(f"ruolo;nome;club;prezzo\nMia\n{riga}\n", calciatori)
    (g,) = giocatori(a, "Mia").values()
    if proposti is None:
        assert (g["stato"], g["id"]) == ("sicuro", 11)
        return
    assert g["stato"] == "da_controllare"
    assert [x["id"] for x in g["alternative"]] == proposti
    if g["id"] is not None:                     # nome uguale al listone: proposta con l'avviso
        assert "nel listone" in g["avviso"]


def test_senza_ruolo_e_squadra_l_abbreviato_resta_da_controllare(calciatori):
    ind = nomi.Indice(calciatori)
    assert ind.cerca("Ferrandi").metodo == "ambiguo"
    assert ind.cerca("Ferrandi", ruolo="A").metodo == "abbreviato"           # solo il ruolo: proposta, non sicuro
    assert ind.cerca("Ferrandi", squadra="Inter").metodo == "ambiguo"
    assert ind.cerca("Ferrandi", "Inter", "A").metodo == "esatto"


def test_errori_dell_ocr_solo_senza_ambiguita(calciatori):
    ind = nomi.Indice(calciatori)
    assert ind.cerca("NDorka").calciatore.id == 13 and ind.cerca("N Dorka").metodo == "esatto"
    assert ind.cerca("Spadafino FP").calciatore.id == 8 and ind.cerca("Spadafino FP").metodo == "esatto"
    assert ind.cerca("Lucum1").metodo == "esatto"                            # «1» al posto della «ì»
    assert ind.cerca("Kone").metodo == "ambiguo"                             # due Koné: senza squadra non si sceglie
    # una chiave «compattata» che porta a due nomi diversi non vale: si torna ai modi prudenti
    doppi = calciatori + [Calciatore(30, "De Lunis", "D", "", "GEN", "genoa", 1, 1, 1),
                          Calciatore(31, "Delunis", "C", "", "LAZ", "lazio", 1, 1, 1)]
    e = nomi.Indice(doppi).cerca("De1unis")
    assert not (e.metodo == "esatto" and not e.avviso)


def test_righe_strane_negli_avvisi(calciatori):
    lette, avvisi, _ = leggi("ruolo;nome;club;prezzo\nMia\nX;Ferrandi;Inter;3\nP;;Inter;3\nAllenatore: Pino\nP;Ferrandi J;Inter\n", calciatori)
    assert [s.nome for s in lette] == ["Mia"] and len(lette[0].righe) == 1 and lette[0].righe[0].costo is None
    assert len(avvisi) == 2


def test_squadre_con_nomi_che_sembrano_altro(calciatori):
    testo = "ruolo;nome;club;prezzo\nTotale Calcio\nA;Ferrandi;Inter;3\nCrediti FC\nD;Brahmeri;Napoli;2\nCrediti residui: 15\n"
    lette, avvisi, _ = leggi(testo, calciatori)
    assert [(s.nome, len(s.righe)) for s in lette] == [("Totale Calcio", 1), ("Crediti FC", 1)] and avvisi == []
    assert lette[1].crediti_residui == 15 and lette[0].crediti_residui is None


def test_senza_intestazione_si_legge_come_prima(calciatori):
    """Senza la riga «ruolo;nome;club;prezzo» vale il lettore generico: ruolo e squadra aiutano lo stesso."""
    lette, _, a = leggi("Mia\nA;Ferrandi;Inter;40\nP;Ferrandi J;Inter;3\n", calciatori)
    g = giocatori(a, "Mia")
    assert (g["Ferrandi"]["stato"], g["Ferrandi"]["id"]) == ("sicuro", 1)
    assert (g["Ferrandi J"]["stato"], g["Ferrandi J"]["id"]) == ("sicuro", 2)


def test_dalla_rotta_dell_anteprima(ambiente):
    c, _ = nuovo_utente("ocrprova")
    r = c.post("/api/rose/anteprima", json={"testo": TESTO})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [s["nome"] for s in d["squadre"]] == ["AC Fantasia 21,5", "Real Esempio"]
    assert d["sicuri"] == 15 and d["da_controllare"] == 0 and d["non_trovati"] == 0
