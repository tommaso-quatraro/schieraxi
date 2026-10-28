import Foundation

/// Un JSON qualsiasi, da leggere e rimandare identico al server (regole della lega). Gli interi restano interi.
indirect enum JSONValue: Codable, Equatable {
    case nullo
    case booleano(Bool)
    case intero(Int)
    case decimale(Double)
    case testo(String)
    case lista([JSONValue])
    case oggetto([String: JSONValue])

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .nullo }
        else if let v = try? c.decode(Bool.self) { self = .booleano(v) }
        else if let v = try? c.decode(Int.self) { self = .intero(v) }
        else if let v = try? c.decode(Double.self) { self = .decimale(v) }
        else if let v = try? c.decode(String.self) { self = .testo(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .lista(v) }
        else { self = .oggetto(try c.decode([String: JSONValue].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .nullo: try c.encodeNil()
        case .booleano(let v): try c.encode(v)
        case .intero(let v): try c.encode(v)
        case .decimale(let v): try c.encode(v)
        case .testo(let v): try c.encode(v)
        case .lista(let v): try c.encode(v)
        case .oggetto(let v): try c.encode(v)
        }
    }

    /// Testo breve per i valori che l'app non modifica (liste, vuoti).
    var descrizione: String {
        switch self {
        case .nullo: return "—"
        case .booleano(let v): return v ? "sì" : "no"
        case .intero(let v): return String(v)
        case .decimale(let v): return String(v)
        case .testo(let v): return v
        case .lista(let v): return v.map(\.descrizione).joined(separator: ", ")
        case .oggetto: return "…"
        }
    }
}

/// Impostazioni degli avvisi del server: chiavi identiche a quelle del server (si leggono senza conversione).
struct ImpostazioniAvvisi: Codable {
    var cambi: Bool
    var promemoria_60: Bool
    var promemoria_15: Bool
    var riepilogo: Bool
    /// Avvisi anche con ntfy, il cui tocco apre l'app nativa. Opzionale: un server più vecchio non lo manda
    /// (e se è nil non viene rimandato, quindi non si azzera niente).
    var app_nativa: Bool?
}

struct StatoAvvisi: Decodable {
    let impostazioni: ImpostazioniAvvisi
    let canale: Bool?
    let dispositivi: Int?
}

struct SceltaSalvata: Decodable {
    let titolari: [Int]
    let modulo: String?
    let salvata: String?
}

struct ValutazioneManuale: Decodable {
    let modulo: String
    let punteggioAtteso: Double
    let dev: Double?
    let panchina: [Int]
    let differenza: Double?
    let consigliata: Double?
    let consigliataStessoModulo: Double?
    let bruttaGiornata: Double?
    let giornataEccezionale: Double?
}

struct RichiestaValutazione: Encodable {
    let titolari: [Int]
    let salva: Bool
    /// Se si guarda la formazione di un'altra squadra (altrimenti la propria).
    var squadra: String? = nil
    var giornata: Int? = nil
}

struct CreditiSquadre: Encodable {
    let crediti: [String: Int]
}

struct NomeSquadra: Encodable {
    let nome: String
}

struct SquadraCrediti: Decodable, Identifiable {
    let nome: String
    let mia: Bool?
    let creditiResidui: Double?
    var id: String { nome }
}
