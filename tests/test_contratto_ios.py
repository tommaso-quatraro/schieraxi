"""Contratto fra iPhone e server: ogni campo che l'iPhone legge dalle risposte esiste come chiave nel codice del server.

Gira su Linux e Windows, senza Mac e senza rete, in pochi secondi. Se fallisce, il messaggio dice struttura, campo, file e
riga dell'iPhone e come rimediare. Il lettore sta in `tests/contratto_ios.py`; le eccezioni (con il motivo) in
`tests/dati/contratto_ios_eccezioni.json`.
"""
import json
import textwrap
from pathlib import Path

import pytest

import contratto_ios as ci

RADICE = Path(__file__).resolve().parent.parent


def _swift(tmp_path, testo, nome="Modelli.swift"):
    cartella = tmp_path / "Sources"
    cartella.mkdir(exist_ok=True)
    (cartella / nome).write_text(textwrap.dedent(testo), encoding="utf-8")
    return cartella


def _per_nome(campi):
    return {f"{c.struttura}.{c.nome_swift}": c for c in campi}


# ---- nomi ----

@pytest.mark.parametrize("swift, json_", [
    ("pVoto", "p_voto"), ("fvAtteso", "fv_atteso"), ("ultimoAggiornamento", "ultimo_aggiornamento"), ("id", "id"),
    ("golCasa", "gol_casa"), ("promemoria_60", "promemoria_60"),
])
def test_nome_json(swift, json_):
    assert ci.nome_json(swift) == json_


@pytest.mark.parametrize("chiave, swift", [
    ("p_voto", "pVoto"), ("ultimo_aggiornamento", "ultimoAggiornamento"), ("id", "id"), ("I2_calibrazione", "i2Calibrazione"),
    ("promemoria_60", "promemoria60"), ("giaCamel", "giaCamel"), ("_privato", "_privato"), ("a__b", "aB"),
])
def test_da_snake_come_swift(chiave, swift):
    """Come `JSONDecoder.KeyDecodingStrategy.convertFromSnakeCase` di Foundation."""
    assert ci.da_snake(chiave) == swift


# ---- lettura dei modelli Swift ----

def test_campi_semplici_con_file_e_riga(tmp_path):
    cartella = _swift(tmp_path, """\
        import Foundation

        struct Giocatore: Decodable, Identifiable {
            let id: Int
            let pVoto: Double?
            var fvAtteso: Double? = nil
        }
        """)
    campi = _per_nome(ci.campi_swift([cartella], radice=tmp_path))
    assert set(campi) == {"Giocatore.id", "Giocatore.pVoto", "Giocatore.fvAtteso"}
    c = campi["Giocatore.pVoto"]
    assert (c.nome_json, c.file, c.riga) == ("p_voto", "Sources/Modelli.swift", 5)


def test_coding_keys_vincono(tmp_path):
    cartella = _swift(tmp_path, """\
        struct StatoAvvisi: Decodable {
            let canale: Bool?
            let spente: Bool
            let calcolata: Int
            private enum CodingKeys: String, CodingKey {
                case canale
                case spente = "ore_tranquille_spente", altroNome = "nomeCamel"
            }
            init(from decoder: Decoder) throws {
                let c = try decoder.container(keyedBy: CodingKeys.self)
                canale = try? c.decodeIfPresent(Bool.self, forKey: .canale)
                spente = (try? c.decodeIfPresent(Bool.self, forKey: .spente)) ?? false
                calcolata = 1
            }
        }
        """)
    campi = _per_nome(ci.campi_swift([cartella], radice=tmp_path))
    assert set(campi) == {"StatoAvvisi.canale", "StatoAvvisi.spente", "StatoAvvisi.altroNome"}
    assert campi["StatoAvvisi.spente"].nome_json == "ore_tranquille_spente"
    assert campi["StatoAvvisi.altroNome"].nome_json == "nome_camel"
    assert campi["StatoAvvisi.spente"].riga == 7


def test_altre_enum_di_chiavi_con_init_proprio(tmp_path):
    cartella = _swift(tmp_path, """\
        struct Voce: Decodable {
            let id: Int
            let nascosto: String
            private enum Chiavi: String, CodingKey { case id, giornataLega }
            init(from decoder: Decoder) throws {
                let c = try decoder.container(keyedBy: Chiavi.self)
                id = try c.decode(Int.self, forKey: .id)
                nascosto = ""
            }
        }
        """)
    assert set(_per_nome(ci.campi_swift([cartella], radice=tmp_path))) == {"Voce.id", "Voce.giornataLega"}


def test_init_in_estensione_con_chiavi_implicite(tmp_path):
    cartella = _swift(tmp_path, """\
        struct Impostazioni: Codable {
            var cambi: Bool
            var promemoria_60: Bool
        }
        extension Impostazioni {
            init(from decoder: Decoder) throws {
                let c = try decoder.container(keyedBy: CodingKeys.self)
                cambi = try c.decode(Bool.self, forKey: .cambi)
                promemoria_60 = try c.decode(Bool.self, forKey: .promemoria_60)
            }
        }
        """)
    assert set(_per_nome(ci.campi_swift([cartella], radice=tmp_path))) == {"Impostazioni.cambi", "Impostazioni.promemoria_60"}


def test_solo_decodable_e_proprieta_memorizzate(tmp_path):
    cartella = _swift(tmp_path, """\
        /// struct Commento: Decodable { let falso: Int }
        struct Corpo: Encodable { let password: String }
        struct Locale { let x: Int }
        enum Stato: String, Codable { case uno, due }
        final class Caricatore<T: Decodable>: ObservableObject { @Published var valore: T? = nil }
        struct Tollerante<T: Decodable>: Decodable {
            let valore: T?
            init(from decoder: Decoder) throws { valore = try? T(from: decoder) }
        }
        struct Partita: Decodable, Identifiable {
            let casa: String
            let trasferta: String
            let fisso = "costante"
            static let vuota = Partita(casa: "", trasferta: "")
            lazy var pigra: Int = 0
            var id: String { casa + trasferta }
            var testo: String {
                get { casa }
            }
            var conOsservatore: Int = 0 { didSet { print("x {") } }
            func descrizione() -> String { let interno = 1; return "\\(interno)" }
            struct Dentro: Decodable { let totali: Int?; let giocate: Int? }
        }
        """)
    campi = _per_nome(ci.campi_swift([cartella], radice=tmp_path))
    assert set(campi) == {
        "Partita.casa", "Partita.trasferta", "Partita.conOsservatore",
        "Partita.Dentro.totali", "Partita.Dentro.giocate",
    }


def test_stringhe_con_graffe_e_commenti_non_confondono(tmp_path):
    cartella = _swift(tmp_path, '''\
        struct A: Decodable {
            let uno: Int // commento con { graffa
            /* commento
               su più righe } */
            let due: String
            var testo: String { "graffa } dentro \\("x" + "}") fine" }
            var lungo: String {
                """
                riga con { e }
                """
            }
            let tre: Int
        }
        struct B: Decodable { let quattro: Int }
        ''')
    assert set(_per_nome(ci.campi_swift([cartella], radice=tmp_path))) == {"A.uno", "A.due", "A.tre", "B.quattro"}


# ---- chiavi del server ----

def test_chiavi_server_da_dizionari_dataclass_e_dict(tmp_path):
    (tmp_path / "pacchetto").mkdir()
    (tmp_path / "pacchetto" / "rotte.py").write_text(textwrap.dedent("""\
        from dataclasses import dataclass
        from typing import TypedDict

        TIPI = ("stemma", "maglia")

        @dataclass
        class Riga:
            fv_atteso: float
            costante = 3

        class Risposta(TypedDict):
            p_voto: float

        def oggi(x):
            r = {"giornata": 1, "ultimo_aggiornamento": None, 5: "numero"}
            r["miei_titolari"] = []
            r.setdefault("da_fare", [])
            r.update(gol_casa=1)
            altro = dict(scadenza="ora", **r)
            somme = {k: 0 for k in ("rig_segnati", "rig_parati")}
            presenti = {t: True for t in TIPI}
            x.funzione(non_chiave=1)
            testo = "solo testo: con due punti"
            return r, altro
        """), encoding="utf-8")
    chiavi = ci.chiavi_server(tmp_path)
    for attesa in ("fv_atteso", "p_voto", "giornata", "ultimo_aggiornamento", "miei_titolari", "da_fare", "gol_casa", "scadenza",
                   "rig_segnati", "rig_parati", "stemma", "maglia"):
        assert attesa in chiavi
    assert "non_chiave" not in chiavi
    assert "costante" not in chiavi
    assert "solo testo" not in chiavi


def test_campo_trovato_con_e_senza_conversione():
    chiavi = {"p_voto", "ore_tranquille_spente", "promemoria_60"}
    indice = ci.indice_chiavi(chiavi)
    campo = lambda nome: ci.Campo("S", nome, ci.nome_json(nome), "f.swift", 1)  # noqa: E731
    assert ci.trovato(campo("pVoto"), indice)
    assert ci.trovato(campo("promemoria_60"), indice)          # decodificatore senza conversione
    assert ci.trovato(campo("promemoria60"), indice)           # con conversione: «promemoria_60» → «promemoria60»
    assert ci.trovato(ci.Campo("S", "spente", "ore_tranquille_spente", "f.swift", 1, "ore_tranquille_spente"), indice)
    assert not ci.trovato(ci.Campo("S", "spente", "ore_tranquille", "f.swift", 1, "ore_tranquille"), indice)
    assert not ci.trovato(campo("pVotoNuovo"), indice)


# ---- eccezioni e messaggio ----

def test_messaggio_dice_struttura_campo_file_riga_rotta_e_rimedio():
    campo = ci.Campo("Giocatore", "pVotoNuovo", "p_voto_nuovo", "ios/Sources/Domain/Modelli.swift", 42)
    testo = ci.messaggio([campo], {"Giocatore": ["/api/giocatori"]})
    for pezzo in ("Giocatore.pVotoNuovo", "p_voto_nuovo", "ios/Sources/Domain/Modelli.swift:42", "/api/giocatori",
                  "contratto_ios_eccezioni.json"):
        assert pezzo in testo


def test_eccezioni_per_campo_e_per_struttura():
    campi = [ci.Campo("A", "x", "x", "f", 1), ci.Campo("A", "y", "y", "f", 2), ci.Campo("A.Dentro", "z", "z", "f", 3),
             ci.Campo("B", "w", "w", "f", 4)]
    mancanti = ci.campi_mancanti(campi, ci.indice_chiavi(set()), {"A.x": "motivo", "A": "motivo", "B.w": "motivo"})
    assert [c.nome_swift for c in mancanti] == ["z"]  # «A» copre i campi di A, non quelli delle strutture dentro A


def test_eccezioni_vecchie_trovate():
    campi = [ci.Campo("A", "x", "x", "f", 1), ci.Campo("A", "y", "y", "f", 2), ci.Campo("B", "w", "w", "f", 3),
             ci.Campo("C", "z", "z", "f", 4)]
    indice = ci.indice_chiavi({"x", "w"})
    motivo = "riempito sul telefono, non dal server"
    problemi = ci.eccezioni_vecchie(campi, indice, {
        "A.x": motivo,          # il server ora manda «x»
        "A.y": "",              # senza motivo
        "B": motivo,            # tutti i campi di B ora ci sono
        "C": motivo,            # giusta: «z» manca davvero
        "C.z": motivo,          # doppia: c'è già quella per tutta C
        "Sparita.campo": motivo,
    })
    testo = "\n".join(problemi)
    assert "«A.x»: il server ora manda" in testo
    assert "«A.y»: manca il motivo" in testo
    assert "«B»: tutti i suoi campi" in testo
    assert "«C.z»: c'è già l'eccezione" in testo
    assert "«Sparita.campo»: non c'è più" in testo
    assert not any(p.startswith("«C»") for p in problemi)
    assert len(problemi) == 5


def test_rotte_probabili_seguono_i_tipi(tmp_path):
    cartella = _swift(tmp_path, """\
        struct Oggi: Decodable { let partite: [Partita]?; let livello: Livello }
        struct Partita: Decodable { let casa: String }
        struct Livello: Decodable { let valore: Int }
        func carica() async throws {
            let o: Oggi = try await server.get("/api/oggi?giornata=\\(g)")
            let p: [Partita] = try await server.get("/api/partite")
        }
        """)
    rotte = ci.rotte_probabili([cartella], radice=tmp_path)
    assert rotte["Oggi"] == ["/api/oggi"]
    assert rotte["Partita"] == ["/api/oggi", "/api/partite"]
    assert rotte["Livello"] == ["/api/oggi"]


# ---- repository vero ----

@pytest.fixture(scope="module")
def vero():
    campi = ci.campi_swift(ci.CARTELLE_SWIFT, radice=RADICE)
    indice = ci.indice_chiavi(ci.chiavi_server(RADICE / "fanta"))
    return campi, indice, ci.carica_eccezioni()


def test_il_lettore_trova_i_modelli_veri(vero):
    campi, _, _ = vero
    nomi = {f"{c.struttura}.{c.nome_swift}" for c in campi}
    # Un campione noto: se sparisce, il lettore si è rotto (non il contratto).
    for atteso in ("Giocatore.id", "StatoAvvisi.oreTranquilleSpente", "ImpostazioniAvvisi.promemoria_60",
                   "StatoDati.Partite.totali", "RispostaAccount.emailAttiva"):
        assert atteso in nomi, atteso
    assert len(campi) > 400


def test_ogni_campo_letto_dall_iphone_esiste_nel_server(vero):
    campi, indice, eccezioni = vero
    mancanti = ci.campi_mancanti(campi, indice, eccezioni)
    assert not mancanti, ci.messaggio(mancanti, ci.rotte_probabili(ci.CARTELLE_SWIFT))


def test_eccezioni_con_motivo_e_ancora_vere(vero):
    campi, indice, eccezioni = vero
    problemi = ci.eccezioni_vecchie(campi, indice, eccezioni)
    assert not problemi, "Eccezioni da sistemare in tests/dati/contratto_ios_eccezioni.json:\n" + "\n".join(problemi)


def test_file_eccezioni_ordinato_e_leggibile():
    testo = ci.ECCEZIONI.read_text(encoding="utf-8")
    dati = json.loads(testo)
    assert list(dati) == sorted(dati), "Tieni le eccezioni in ordine alfabetico"
