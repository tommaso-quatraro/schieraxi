import Foundation

/// L'indirizzo web di un'immagine (stemma o divisa) incollato dall'utente: si controlla qui PRIMA di mandarlo al server, che poi lo
/// scarica da solo (solo https, host pubblico: i controlli veri sono lato server).
enum IndirizzoImmagine {
    static let lunghezzaMassima = 2000

    /// L'indirizzo ripulito, se è accettabile: https, un nome di host, niente nome utente e password dentro.
    static func pulito(_ testo: String) -> String? {
        let t = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, t.count <= lunghezzaMassima, !t.contains(where: \.isNewline),
              let url = URL(string: t), url.scheme?.lowercased() == "https",
              let host = url.host, host.contains("."), url.user == nil, url.password == nil else { return nil }
        return t
    }

    static func valido(_ testo: String) -> Bool { pulito(testo) != nil }
}

/// Il corpo di `POST /api/squadre/immagine/da-url`.
struct CorpoImmagineDaUrl: Encodable {
    let squadra: String
    /// «stemma» o «maglia».
    let tipo: String
    let url: String
}
