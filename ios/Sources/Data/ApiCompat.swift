import Foundation

/// Scorciatoia temporanea per le parti non ancora passate ai ViewModel: inoltra al client condiviso.
enum Api {
    static var base: String { ServerCorrente.condiviso.indirizzo }
    static func indirizzoValido(_ testo: String) -> Bool { IndirizzoServer.valido(testo) }
    static func codifica(_ testo: String) -> String { IndirizzoServer.codifica(testo) }
    static func get<T: Decodable>(_ percorso: String, snake: Bool = true) async throws -> T { try await ServerCorrente.condiviso.get(percorso, snake: snake) }
    static func grezzo(_ percorso: String) async throws -> Data { try await ServerCorrente.condiviso.grezzo(percorso) }
    static func decodifica<T: Decodable>(_ dati: Data, snake: Bool = true) throws -> T { try Decodifica.decodifica(dati, snake: snake) }
    static func testo(_ percorso: String) async throws -> String { try await ServerCorrente.condiviso.testo(percorso) }
    static func invia(_ metodo: String, _ percorso: String) async throws { try await ServerCorrente.condiviso.invia(metodo, percorso) }
    static func corpoJSON<B: Encodable>(_ metodo: String, _ percorso: String, _ corpo: B) async throws -> Data { try await ServerCorrente.condiviso.corpoJSON(metodo, percorso, corpo) }
    static func posta<T: Decodable, B: Encodable>(_ metodo: String = "POST", _ percorso: String, _ corpo: B, snake: Bool = true) async throws -> T { try await ServerCorrente.condiviso.posta(metodo, percorso, corpo, snake: snake) }
    static func caricaFile<T: Decodable>(_ percorso: String, nome: String, dati: Data) async throws -> T { try await ServerCorrente.condiviso.caricaFile(percorso, nome: nome, dati: dati) }
}
