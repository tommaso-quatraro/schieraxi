import Foundation

// Altre risposte del server, usate solo dall'app (il widget non le compila): confronto, affidabilità, regole riconosciute, stagione...
// Come per gli altri modelli, quasi tutto è opzionale: un campo mancante non deve rompere la schermata.

// MARK: - Confronto tra due giocatori

/// Una causa del confronto («Probabilità di giocare», «Voto atteso»...): quanto pesa, in punti attesi, a favore di A (positivo) o di B.
struct FattoreConfronto: Decodable, Identifiable, Equatable {
    let chiave: String
    let etichetta: String
    let a: Double?
    let b: Double?
    let effetto: Double
    let percentuale: Bool?
    var id: String { chiave }
}

/// Se i due sono in una formazione: dove stanno e cosa cambierebbe a invertirli.
struct ConfrontoFormazione: Decodable, Equatable {
    let modulo: String?
    let postoA: String?
    let postoB: String?
    let differenza: Double?
    let testo: String?
}

struct Confronto: Decodable {
    let giornata: Int?
    let giocatori: [Giocatore]
    /// L'id del giocatore consigliato.
    let consigliato: Int?
    let margine: Double?
    let fattori: [FattoreConfronto]
    let perche: String?
    let formazione: ConfrontoFormazione?
}

// MARK: - Prova del modello

struct RigaAffidabilita: Decodable, Identifiable, Equatable {
    let giornata: Int
    let erroreModello: Double?
    let erroreFantamedia: Double?
    let puntiModello: Double?
    let puntiFantamedia: Double?
    let puntiPerfetta: Double?
    var id: Int { giornata }
}

struct SintesiAffidabilita: Decodable, Equatable {
    let giornate: Int?
    let erroreModello: Double?
    let erroreFantamedia: Double?
    let puntiModello: Double?
    let puntiFantamedia: Double?
    let puntiPerfetta: Double?
}

/// `/api/affidabilita`: la prova del modello sulle giornate passate (vuota se non è ancora stata fatta).
struct Affidabilita: Decodable {
    let calcolato: String?
    let righe: [RigaAffidabilita]?
    let sintesi: SintesiAffidabilita?
}

// MARK: - Regole e stagione

/// Un valore riconosciuto nel testo del regolamento: la chiave dice quale regola cambia («bonus.assist», «panchina.numero»...).
struct ModificaRegola: Decodable, Identifiable {
    let chiave: String
    let etichetta: String
    let valore: JSONValue
    let riga: String?
    var id: String { chiave }
}

struct RiconoscimentoRegole: Decodable {
    let modifiche: [ModificaRegola]
    let nonRiconosciute: [String]?
}

struct RichiestaTesto: Encodable {
    let testo: String
}

struct StatoStagione: Decodable, Equatable {
    let corrente: String?
    let rose: String?
    /// true quando le rose sono di una stagione finita: si può archiviare e ripartire.
    let nuova: Bool?
}

// MARK: - Offerta ricevuta a parole

struct RichiestaOfferta: Encodable {
    let testo: String
    let con: String?
}

/// Cosa ha capito il server dal messaggio incollato: con chi, cosa dai, cosa ricevi e (se ha trovato tutto) l'analisi.
struct OffertaRiconosciuta: Decodable {
    let con: String?
    let `do`: [String]
    let ricevo: [String]
    let ambigui: [String]?
    let analisi: PropostaScambio?
}

// MARK: - Aggiornamento dei dati, icona, foto

struct AvvioAggiornamento: Decodable {
    let avviato: Bool?
    let messaggio: String?
}

struct StatoAggiornamento: Decodable, Equatable {
    let inCorso: Bool?
    let righe: [String]?
    let errori: [String]?
}

struct IconaServer: Decodable, Equatable {
    let scelta: String?
    let elenco: [String]?
}

struct FotoDisponibili: Decodable, Equatable {
    let ids: [Int]
}

// MARK: - Colori delle squadre (per la maglia di chi non ha la foto)

/// Colore principale e secondario (esadecimali RRGGBB) delle squadre di Serie A, come nella web app.
enum ColoriSquadra {
    static let tabella: [String: (String, String)] = [
        "atalanta": ("1e71b8", "111827"), "bologna": ("a21c26", "1a2f5a"), "cagliari": ("a51e36", "0b2a52"), "como": ("1b5fa8", "f3f4f6"),
        "fiorentina": ("6b2f9a", "f3f4f6"), "frosinone": ("f2d200", "1a56a6"), "genoa": ("b3202a", "0a2a52"), "inter": ("0a58a8", "111827"),
        "juventus": ("f3f4f6", "111827"), "lazio": ("8fc4ea", "f3f4f6"), "lecce": ("d8232a", "f2d200"), "milan": ("d11f2f", "111827"),
        "monza": ("d11f2f", "f3f4f6"), "napoli": ("3d8fd1", "f3f4f6"), "parma": ("f2f2f2", "f2c200"), "roma": ("8b1c2e", "f2a900"),
        "sassuolo": ("1f8a4c", "111827"), "torino": ("7a1f2a", "f3f4f6"), "udinese": ("f3f4f6", "111827"), "venezia": ("0b3d2e", "f08a1a"),
        "verona": ("1a3a8a", "f2d200"), "cremonese": ("b3202a", "8b95a1"), "pisa": ("0b2a52", "111827"), "sampdoria": ("1b5fa8", "f3f4f6"),
        "palermo": ("f4a6c0", "111827"), "spezia": ("f3f4f6", "111827"),
    ]

    /// I due colori della squadra (grigi se la squadra non è nell'elenco o manca). Gli «slug» sono minuscoli (`inter`); le sigle del
    /// server in maiuscolo (`INT`) non corrispondono e restano grigie.
    static func esadecimali(_ squadra: String?) -> (String, String) {
        guard let s = squadra?.lowercased(), let colori = tabella[s] else { return ("6b7280", "e5e7eb") }
        return colori
    }

    /// Sigla di tre lettere della squadra (`inter` → `INT`).
    static let sigle: [String: String] = [
        "atalanta": "ATA", "bologna": "BOL", "cagliari": "CAG", "como": "COM", "fiorentina": "FIO", "frosinone": "FRO", "genoa": "GEN",
        "inter": "INT", "juventus": "JUV", "lazio": "LAZ", "lecce": "LEC", "milan": "MIL", "monza": "MON", "napoli": "NAP", "parma": "PAR",
        "roma": "ROM", "sassuolo": "SAS", "torino": "TOR", "udinese": "UDI", "venezia": "VEN", "verona": "VER", "cremonese": "CRE",
        "pisa": "PIS", "sampdoria": "SAM", "palermo": "PAL", "spezia": "SPE",
    ]

    static func sigla(_ squadra: String?) -> String {
        guard let s = squadra, !s.isEmpty else { return "" }
        return sigle[s.lowercased()] ?? String(s.prefix(3)).uppercased()
    }
}
