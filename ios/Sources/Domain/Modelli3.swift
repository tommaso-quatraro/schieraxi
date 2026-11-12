import Foundation

// Altre risposte del server, usate solo dall'app (il widget non le compila): affidabilità, regole riconosciute, stagione...
// Come per gli altri modelli, quasi tutto è opzionale: un campo mancante non deve rompere la schermata.

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
