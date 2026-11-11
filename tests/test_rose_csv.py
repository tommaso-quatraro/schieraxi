"""Rose da CSV: l'esportazione «rosters» di Leghe (nome squadra, codice calciatore, costo) e i CSV a colonne in tutte le
codifiche e i separatori che capitano (Excel italiano, iPhone, Mac). Fixture: `tests/dati/rosters_ridotto.csv` (2 squadre)."""
import codecs
import time
from pathlib import Path

import pytest

from fanta import lega, rose, server
from fanta.listone import Calciatore
from fanta.nomi import Indice

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture per i test sulle rotte)

RIDOTTO = Path(__file__).parent / "dati" / "rosters_ridotto.csv"
ROSA = {"P": 3, "D": 8, "C": 8, "A": 6}


def nome_di(i: int) -> str:
    """Un cognome inventato e diverso per ogni numero (solo lettere)."""
    return "Cog" + "".join(chr(97 + (i // 26 ** k) % 26) for k in range(4))


def listone_finto(codici) -> list[Calciatore]:
    """Un listone con quei codici: ruolo a rotazione (P, D, C, A) e nomi inventati."""
    return [Calciatore(c, nome_di(c), "PDCA"[i % 4], "", "INT", "inter", 10, 10, 100) for i, c in enumerate(sorted(set(codici)))]


def codici_del_file(testo: str) -> list[int]:
    return [int(r.split(",")[-2]) for r in testo.splitlines() if r.count(",") >= 2 and not r.startswith("$")]


@pytest.fixture
def ridotto() -> str:
    return RIDOTTO.read_text(encoding="utf-8")


@pytest.fixture
def indice_file(ridotto) -> Indice:
    return Indice(listone_finto(codici_del_file(ridotto)))


def leggi(dati: bytes, indice: Indice, avvisi=None):
    return rose.estrai(rose.griglie_da_bytes(dati), indice, ROSA, avvisi)


# ---------------------------------------------------------------- «rosters»
def test_rosters_ridotto_due_squadre(ridotto, indice_file):
    avvisi = []
    squadre = leggi(ridotto.encode(), indice_file, avvisi)
    assert [s.nome for s in squadre] == ["Real Esempio", "Under Prova"]          # il nome con la virgola resta intero
    assert [len(s.righe) for s in squadre] == [25, 25] and avvisi == []
    prima = squadre[0].righe[0]
    assert prima.esito.calciatore.id == 7647 and prima.costo == 4 and prima.testo == nome_di(7647)
    assert prima.ruolo == prima.esito.calciatore.ruolo and prima.esito.metodo == "esatto"
    assert [r.costo for r in squadre[1].righe][:6] == [1, 1, 36, 3, 1, 22]
    assert squadre[1].righe[21].costo == 290                                       # costi alti: un solo valore, non spezzato


def test_rosters_nome_squadra_lungo_si_accorcia_come_una_cella(ridotto, indice_file):
    """Il nome della squadra può stare su più celle (ha delle virgole): unito, si accorcia come una cella sola, così le rose
    importate rispettano sempre il tetto dei testi (anche quello del ripristino di un backup)."""
    lungo = ",".join(["N" * 150] * 3)
    squadre = leggi(ridotto.replace("Real Esempio", lungo).encode(), indice_file)
    assert [s.nome for s in squadre] == [lungo[:rose.MAX_TESTO_CELLA], "Under Prova"]


def test_rosters_nella_lega_senza_mia_squadra(ridotto, indice_file):
    nuove = lega.da_import(leggi(ridotto.encode(), indice_file))
    assert nuove.mia_squadra is None and [s.nome for s in nuove.squadre] == ["Real Esempio", "Under Prova"]
    g = nuove.squadre[0].giocatori[0]
    assert (g.id, g.nome, g.costo, g.riconosciuto) == (7647, nome_di(7647), 4, "esatto")
    attesi = [int(r.split(",")[-1]) for r in RIDOTTO.read_text().splitlines() if r.startswith("Real Esempio,")]
    assert [x.costo for x in nuove.squadre[0].giocatori] == attesi and sum(attesi) == 500


def test_rosters_i_ruoli_si_controllano_come_per_l_excel(ridotto):
    """Il ruolo viene dal listone: con tutti portieri il controllo della lega lo segnala (servono 3 P, 8 D, 8 C, 6 A)."""
    cal = [Calciatore(c, nome_di(c), "P", "", "INT", "inter", 1, 1, 1) for c in codici_del_file(ridotto)]
    nuove = lega.da_import(rose.estrai(rose.griglie_da_bytes(ridotto.encode()), Indice(cal), ROSA))
    avvisi = lega.controlla(nuove, _regole())
    assert any("Real Esempio: rosa diversa dalle regole" in a for a in avvisi)        # tutti portieri: lo si vede


def _regole():
    from fanta.regole import Regole
    return Regole()                  # le regole di base: 3 P, 8 D, 8 C, 6 A


VARIANTI = {
    "bom": lambda t: codecs.BOM_UTF8 + t.encode(),
    "crlf": lambda t: t.replace("\n", "\r\n").encode(),
    "crlf_con_bom": lambda t: codecs.BOM_UTF8 + t.replace("\n", "\r\n").encode(),
    "solo_cr": lambda t: t.replace("\n", "\r").encode(),
    "righe_vuote_finali": lambda t: (t + "\n\n\n   \n").encode(),
    "righe_vuote_in_mezzo": lambda t: t.replace("$,$,$\n", "$,$,$\n\n").encode(),
    "spazi_attorno": lambda t: "\n".join(", ".join(r.split(",")) + "  " for r in t.splitlines()).encode(),
    "senza_separatore_iniziale": lambda t: t.split("\n", 1)[1].encode(),
    "senza_separatore_finale": lambda t: t.rstrip().encode(),
    "senza_a_capo_finale": lambda t: t.rstrip("\n").encode(),
    "utf16_con_bom": lambda t: codecs.BOM_UTF16_LE + t.replace("\n", "\r\n").encode("utf-16-le"),
    "utf16_be_con_bom": lambda t: codecs.BOM_UTF16_BE + t.encode("utf-16-be"),
    "utf16_senza_bom": lambda t: t.encode("utf-16-le"),
    "punto_e_virgola": lambda t: t.replace("Under Prova", "Under Prova").replace(",", ";").replace("17;5", "17,5").encode(),
    "nome_tra_virgolette": lambda t: t.replace("Under Prova,", '"Under Prova",').encode(),
}


@pytest.mark.parametrize("nome", list(VARIANTI))
def test_rosters_in_tutte_le_varianti(nome, ridotto, indice_file):
    avvisi = []
    squadre = leggi(VARIANTI[nome](ridotto), indice_file, avvisi)
    assert [(s.nome, len(s.righe)) for s in squadre] == [("Real Esempio", 25), ("Under Prova", 25)], nome
    assert avvisi == [] and squadre[0].righe[0].esito.calciatore.id == 7647


def test_rosters_tab_e_barra_verticale(ridotto, indice_file):
    for sep in ("\t", "|"):
        dati = ridotto.replace(",", sep).replace("17" + sep + "5", "17,5").encode()
        assert [(s.nome, len(s.righe)) for s in leggi(dati, indice_file)] == [("Real Esempio", 25), ("Under Prova", 25)], sep


def test_rosters_senza_nessun_separatore_ma_con_codici_del_listone(ridotto, indice_file):
    senza = "\n".join(r for r in ridotto.splitlines() if not r.startswith("$")) + "\n"
    squadre = leggi(senza.encode(), indice_file)
    assert [(s.nome, len(s.righe)) for s in squadre] == [("Real Esempio", 25), ("Under Prova", 25)]


def test_tabella_generica_con_due_numeri_non_e_scambiata_per_rosters(indice):
    """«Nome,Squadra,Quotazione,Costo» non ha i separatori e i numeri non sono codici del listone: resta una tabella normale."""
    testo = "Real Esempio\nSommer,INT,20,10\nBastoni,INT,15,5\nKean,FIO,30,12\nBarella,INT,20,8\nThuram,INT,25,9\nDimarco,INT,12,3\n"
    squadre = rose.estrai(rose.griglie_da_bytes(testo.encode()), indice)
    assert [s.nome for s in squadre] == ["Real Esempio"] and len(squadre[0].righe) == 6


def test_codice_non_nel_listone_e_segnalato_con_squadra_e_codice(ridotto):
    codici = codici_del_file(ridotto)
    indice = Indice(listone_finto([c for c in codici if c not in (7550, 4751)]))
    avvisi = []
    squadre = leggi(ridotto.encode(), indice, avvisi)
    assert sorted(avvisi) == ["Under Prova: il codice 4751 non è nel listone, quindi non so chi sia: correggilo a mano.",
                              "Under Prova: il codice 7550 non è nel listone, quindi non so chi sia: correggilo a mano."]
    non = [r for s in squadre for r in s.righe if not r.esito.trovato]
    assert [(r.testo, r.costo) for r in non] == [("Codice 7550", 1), ("Codice 4751", 1)]      # tenuti in rosa, col loro costo
    nuove = lega.da_import(squadre)
    persi = [g for s in nuove.squadre for g in s.giocatori if g.id is None]
    assert [g.nome for g in persi] == ["Codice 7550", "Codice 4751"] and "non presente nel listone" in persi[0].avviso
    assert any("'Codice 7550' non riconosciuto" in a for a in lega.controlla(nuove, _regole()))     # e lo vede anche il controllo della lega


def test_stesso_codice_in_due_squadre_e_doppione_nella_stessa(ridotto, indice_file):
    doppio = ridotto + "Real Esempio,7647,5\nTerza,7647,2\nTerza,5,2\n"
    avvisi = []
    squadre = leggi(doppio.encode(), indice_file, avvisi)
    assert any("Real Esempio" in a and "compare due volte" in a for a in avvisi)
    assert len(squadre[0].righe) == 25
    assert any("è in più squadre" in a and "Real Esempio" in a and "Terza" in a for a in lega.controlla(lega.da_import(squadre), _regole()))


def test_righe_che_non_tornano_non_spariscono_in_silenzio(ridotto, indice_file):
    avvisi = []
    squadre = leggi(("Squadra,Codice,Costo\n" + ridotto + "Real Esempio,xx,3\nsolo due,3\n").encode(), indice_file, avvisi)
    assert len(avvisi) == 2 and "Riga" in avvisi[0] and "xx" in avvisi[0] and "solo due" in avvisi[1]        # l'intestazione in testa invece sì, ignorata
    assert [len(s.righe) for s in squadre] == [25, 25]


def test_squadre_poche_o_con_pochi_portieri_hanno_gli_avvisi_dell_excel(ridotto, indice_file):
    corto = "\n".join(ridotto.splitlines()[:30]) + "\n"          # Real Esempio con 24 giocatori e FC UNDER con 1
    nuove = lega.da_import(leggi(corto.encode(), indice_file))
    avvisi = lega.controlla(nuove, _regole())
    assert any(a.startswith("Under Prova: rosa diversa dalle regole") for a in avvisi)


# ---------------------------------------------------------------- CSV a colonne (non «rosters») in tante codifiche
CSV_TABELLA = "Squadra Uno;;\nCalciatore;Ruolo;Costo\nLaurienté;C;10\nSommer;P;20\nBastoni;D;5\n\nAltra Squadra;;\nKean;A;30\nN'Dicka;D;8\n"
ATTESO = {"Squadra Uno": [(5, "C", 10), (2, "P", 20), (3, "D", 5)], "Altra Squadra": [(14, "A", 30), (4, "D", 8)]}


def controlla_tabella(squadre):
    assert {s.nome: [(r.esito.calciatore.id, r.ruolo, r.costo) for r in s.righe] for s in squadre} == ATTESO


TABELLE = {
    "utf8": lambda t: t.encode(),
    "utf8_bom": lambda t: codecs.BOM_UTF8 + t.encode(),
    "utf16_bom": lambda t: codecs.BOM_UTF16_LE + t.encode("utf-16-le"),
    "utf16_be": lambda t: codecs.BOM_UTF16_BE + t.encode("utf-16-be"),
    "utf16_senza_bom": lambda t: t.encode("utf-16-le"),
    "cp1252": lambda t: t.encode("cp1252"),                         # Excel italiano: «é» è il byte 0xE9, che in UTF-8 non è valido
    "latin1": lambda t: t.encode("latin-1"),
    "tab": lambda t: t.replace(";", "\t").encode(),
    "virgola": lambda t: t.replace(";", ",").encode(),
    "barra": lambda t: t.replace(";", "|").encode(),
    "crlf": lambda t: t.replace("\n", "\r\n").encode("cp1252"),
    "virgolette": lambda t: t.replace("Sommer", '"Sommer"').replace("Squadra Uno", '"Squadra Uno"').encode(),
}


@pytest.mark.parametrize("nome", list(TABELLE))
def test_csv_a_colonne_in_ogni_codifica_e_separatore(nome, indice):
    controlla_tabella(rose.estrai(rose.griglie_da_bytes(TABELLE[nome](CSV_TABELLA)), indice))


def test_gli_accenti_restano_giusti_con_cp1252(indice):
    dati = "Mia\nP;Laurienté;5\n".encode("cp1252")
    assert b"\xe9" in dati
    assert rose.decodifica(dati) == "Mia\nP;Laurienté;5\n"
    assert rose.decodifica("è à ù ò ì €".encode("cp1252")) == "è à ù ò ì €"
    assert rose.decodifica("Laurienté".encode("utf-8")) == "Laurienté"
    assert rose.decodifica(b"\x81abc") == "\x81abc"                  # byte che cp1252 non ha: si ricade su latin-1, senza errori


def test_una_colonna_sola_una_squadra_per_blocco(indice):
    testo = "Real Esempio\nP\nSommer\nInter\n10\nD\nBastoni\nInter\n15\nI Bomber\nA\nKean\nFiorentina\n30\n"
    for dati in (testo.encode(), codecs.BOM_UTF8 + testo.replace("\n", "\r\n").encode(), codecs.BOM_UTF16_LE + testo.encode("utf-16-le")):
        s = {x.nome: x for x in rose.estrai(rose.griglie_da_bytes(dati), indice)}
        assert [(r.esito.calciatore.id, r.ruolo, r.costo) for r in s["Real Esempio"].righe] == [(2, "P", 10), (3, "D", 15)]
        assert [r.esito.calciatore.id for r in s["I Bomber"].righe] == [14]


def test_una_colonna_con_virgole_nei_nomi_non_la_spezza(indice):
    testo = "Real Esempio, il ritorno\nSommer\nBastoni\nI Bomber\nKean\n"
    s = {x.nome: x for x in rose.estrai(rose.griglie_da_bytes(testo.encode()), indice)}
    assert set(s) == {"Real Esempio, il ritorno", "I Bomber"} and len(s["Real Esempio, il ritorno"].righe) == 2


def test_celle_con_a_capo_e_virgolette_dentro(indice):
    testo = 'Squadra Uno;;\n"Sommer";P;"1\n0"\nBastoni;D;5\n'
    griglie = rose.griglie_da_bytes(testo.encode())
    assert griglie[0][1][1] == ["Sommer", "P", "1\n0"]


def test_squadre_affiancate_nel_csv(indice):
    testo = "Alfa;costo;;Beta;costo\nSommer;10;;Kean;7\nBastoni;5;;Barella;3\n"
    s = {x.nome: x for x in rose.estrai(rose.griglie_da_bytes(testo.encode()), indice)}
    assert [r.esito.calciatore.id for r in s["Alfa"].righe] == [2, 3] and [r.esito.calciatore.id for r in s["Beta"].righe] == [14, 12]


def test_testo_incollato_con_virgole(indice):
    testo = "Real Esempio\nP,Sommer,10\nD,Bastoni,15\n"
    s = rose.estrai([("testo", rose.griglia_da_testo(testo))], indice)[0]
    assert [(r.esito.calciatore.id, r.ruolo, r.costo) for r in s.righe] == [(2, "P", 10), (3, "D", 15)]
    incollato = "$,$,$\nReal Esempio,2,10\nReal Esempio,3,15\n"
    assert rose.griglia_da_testo(incollato)[1] == ["Real Esempio", "2", "10"]


# ---------------------------------------------------------------- celle e righe molto lunghe
def test_celle_incollate_accorciate_come_nel_csv():
    lunga = "Sommer" + "x" * 1000
    for testo in ("Mia\tx\nP\t{}\t10\n", "Mia;x\nP;{};10\n", "Mia\nP  {}  10\n"):     # tabulazione, punto e virgola, spazi
        assert rose.griglia_da_testo(testo.format(lunga))[1] == ["P", lunga[:rose.MAX_TESTO_CELLA], "10"], repr(testo)


def test_testo_incollato_molto_lungo_si_legge_in_poco_tempo(indice):
    testo = "Mia\tx\nP\tSommer\t10\nD\tBastoni" + " " * 20000 + "x\t5\n"
    inizio = time.perf_counter()
    rose.estrai([("testo", rose.griglia_da_testo(testo))], indice)
    assert time.perf_counter() - inizio < 1                  # soglia larga: di solito qualche millesimo


def test_riga_molto_lunga_si_legge_in_poco_tempo():
    inizio = time.perf_counter()
    rose.griglie_da_stringa("$" + "\t" * 59000 + "x\n")
    assert time.perf_counter() - inizio < 1                  # soglia larga: di solito qualche millesimo


@pytest.mark.parametrize("testo,atteso", [
    ("$,$,$\nA,1,2\n", ","),
    ("$;$;$\nA;1;2\n", ";"),
    ("$\t$\t$\nA\t1\t2\n", "\t"),
    ("$|$|$\nA|1|2\n", "|"),
    ("  $ , $ , $\nA,1,2\n", ","),                            # spazi attorno ai separatori
    ("\t$ \t $\nA\t1\n", "\t"),
    ("$\t,\t$\nA,1,2\n", ","),
    ("A,1,2\r\n$;$;$\r\nB;1;2\r\n", ";"),                     # la riga «$;$;$» vale più delle altre, anche con gli a capo di Windows
    ("Nome;x$,$;1\nA;B;2\n", ";"),                            # «$» a metà riga non è la riga dei separatori
    ("$ $\nA\n", None),
    ("Real Esempio\nSommer\nBastoni\n", None),
])
def test_separatore_dei_rosters_come_prima(testo, atteso):
    assert rose._delimitatore(testo) == atteso


# ---------------------------------------------------------------- file che non sono rose
@pytest.mark.parametrize("dati,frammento", [
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 50, ".xls"),
    (b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", "PDF"),
    (b"\x89PNG\r\n\x1a\n\x00\x00", "immagine"),
    (b"\xff\xd8\xff\xe0\x00\x10JFIF", "immagine"),
    (b"abc\x00\x01\x02\x03def\x00\x00\x00\x00", "né Excel"),
])
def test_file_binari_hanno_un_messaggio_chiaro(dati, frammento):
    with pytest.raises(ValueError, match=frammento):
        rose.decodifica(dati)


def test_csv_di_un_altro_tipo_da_un_messaggio_con_gli_esempi(indice):
    # (una classifica ha il suo messaggio: tests/test_rose_fogli_non_rose.py)
    appunti = "Data;Nota\n1 settembre;Asta di riparazione\n2 settembre;Mercato chiuso\n3 settembre;Rose consegnate\n"
    lette = rose.estrai(rose.griglie_da_bytes(appunti.encode()), indice)
    assert not any(r.esito.trovato for s in lette for r in s.righe)          # il server allora risponde con NESSUNA_ROSA
    for frammento in ("rosters", "$,$,$", "Real Esempio,7627,12", "P;Sommer;10"):
        assert frammento in rose.NESSUNA_ROSA


def test_celle_enormi_o_virgolette_sbilanciate_non_vanno_in_errore(indice):
    sbilanciate = b'Mia;;\n"Sommer;P;10\nBastoni;D;5\n'
    enorme = b'a;b\n"' + b"y" * 200000 + b'";c\nd;e\n'
    for dati in (sbilanciate, enorme, b"x;" * 5000 + b"\n"):
        try:
            rose.estrai(rose.griglie_da_bytes(dati), indice)      # al massimo «nessuna rosa»...
        except ValueError as e:                                    # ...o un messaggio chiaro (400), mai un errore 500
            assert "CSV" in str(e)


# ---------------------------------------------------------------- dal server, con gli account
def csv_lega(squadre=10, giocatori=25):
    """Un'esportazione «rosters» realistica (10 squadre x 25) con il suo listone finto."""
    righe, codici = ["$,$,$"], []
    for t in range(squadre):
        for g in range(giocatori):
            codice = 1000 + t * 100 + g
            codici.append(codice)
            righe.append(f"Squadra {t + 1},{codice},{1 + g}")
        righe.append("$,$,$")
    return "\n".join(righe[:-1]) + "\n", codici


def formati_della_lega(testo: str):
    """Lo stesso CSV nei formati che arrivano da telefoni e PC: (nome file, tipo, byte)."""
    return [
        ("rosters.csv", "text/csv", testo.encode()),
        ("rosters.CSV", "text/comma-separated-values", codecs.BOM_UTF8 + testo.replace("\n", "\r\n").encode()),
        ("rosters.txt", "text/plain", testo.encode()),
        ("rosters", "text/csv", testo.encode()),                                 # il menu Condividi a volte toglie l'estensione
        ("rosters", "application/octet-stream", codecs.BOM_UTF16_LE + testo.encode("utf-16-le")),
        ("rosters.tsv", "text/tab-separated-values", testo.replace(",", "\t").encode()),
        ("rosters.dat", "", testo.encode("cp1252")),
    ]


def test_dal_server_10_squadre_in_tutti_i_formati(ambiente, monkeypatch):
    testo, codici = csv_lega()
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_finto(codici), "oggi"))
    for i, (nome, tipo, dati) in enumerate(formati_della_lega(testo)):
        if i % 4 == 0:
            a, _ = nuovo_utente(f"utente{i}")                      # il tetto è di 10 importazioni al giorno per utente
        r = a.post("/api/rose/file", files={"file": (nome, dati, tipo)})
        assert r.status_code == 200, (nome, r.text)
        corpo = r.json()
        assert corpo["totale_squadre"] == 10 and len(corpo["squadre_importate"]) == 10, nome
        squadre = a.get("/api/squadre").json()
        assert len(squadre) == 10 and all(s["giocatori"] == 25 for s in squadre if "giocatori" in s)


def test_dal_server_i_limiti_di_sicurezza_non_rifiutano_un_csv_normale(ambiente, monkeypatch):
    from fanta import importa_sicuro
    for squadre, giocatori in ((10, 25), (20, 40)):
        testo, codici = csv_lega(squadre, giocatori)
        importa_sicuro.controlla_testo(testo)
        importa_sicuro.controlla_griglie(rose.griglie_da_bytes(testo.encode()))
    testo, _ = csv_lega(10, 25)
    # anche la forma «a colonne» di 10 squadre x 25: nome della squadra e sotto «ruolo;nome;costo»
    a_colonne = "".join(f"Squadra {t}\nRuolo;Calciatore;Costo\n" + "".join(f"P;{nome_di(1000 + t * 100 + g)};{g}\n" for g in range(25)) + "\n" for t in range(10))
    importa_sicuro.controlla_testo(a_colonne)
    importa_sicuro.controlla_griglie(rose.griglie_da_bytes(a_colonne.encode()))
    assert len(testo) < importa_sicuro.MAX_TESTO and len(a_colonne) < importa_sicuro.MAX_TESTO


def test_dal_server_formato_sconosciuto_messaggio_chiaro(ambiente):
    a, _ = nuovo_utente("utentea")
    r = a.post("/api/rose/file", files={"file": ("numeri.csv", b"Pos,Punti,Gol\n1,30,4\n2,25,7\n", "text/csv")})
    assert r.status_code == 400 and "rosters" in r.json()["detail"] and "$,$,$" in r.json()["detail"]
    r = a.post("/api/rose/file", files={"file": ("rose.pdf", b"%PDF-1.4 ...", "application/pdf")})
    assert r.status_code == 400 and "PDF" in r.json()["detail"] and "Formato non supportato" not in r.json()["detail"]
    r = a.post("/api/rose/file", files={"file": ("rose.xls", b"\xd0\xcf\x11\xe0" + b"\x00" * 30, "application/vnd.ms-excel")})
    assert r.status_code == 400 and ".xlsx" in r.json()["detail"]


def test_dal_server_con_un_codice_sconosciuto_l_avviso_arriva_all_app(ambiente, monkeypatch):
    testo, codici = csv_lega(2, 25)
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_finto([c for c in codici if c != 1105]), "oggi"))
    a, _ = nuovo_utente("utentea")
    r = a.post("/api/rose/file", files={"file": ("rosters.csv", testo.encode(), "text/csv")})
    assert r.status_code == 200
    assert any("Squadra 2: il codice 1105 non è nel listone" in x for x in r.json()["avvisi"])


def test_spento_anche_il_csv_si_legge(monkeypatch, tmp_path, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    testo, codici = csv_lega(3, 25)
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_finto(codici), "oggi"))
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: "2026-27")
    from test_account_http import cliente
    r = cliente().post("/api/rose/file", files={"file": ("rosters.csv", testo.encode(), "text/csv")})
    assert r.status_code == 200 and r.json()["totale_squadre"] == 3
