import Foundation

/// La lingua dei testi che scrive il server. L'interfaccia dell'app è solo in italiano, quindi si chiede SEMPRE l'italiano:
/// `URLSession` altrimenti manda da sola la lingua del telefono e un telefono in inglese riceverebbe testi misti.
/// (Il server accetta `Accept-Language`; l'ETag con il suffisso della lingua si rimanda com'è in `If-None-Match`.)
enum LinguaServer {
    static let codice = "it"

    /// Mette l'intestazione della lingua su una richiesta al server.
    static func applica(_ richiesta: inout URLRequest) {
        richiesta.setValue(codice, forHTTPHeaderField: "Accept-Language")
    }
}
