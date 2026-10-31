import Foundation

/// Le pagine di Privacy e Termini sono sul server di chi usa SchieraXI: l'app non ha indirizzi dentro (il repository e l'IPA sono pubblici),
/// compone il collegamento con l'indirizzo che l'utente ha scritto. Qui solo logica pura, provata nei test.
enum PaginaServer: String, CaseIterable {
    case privacy
    case termini

    var titolo: String {
        switch self {
        case .privacy: return "Informativa sulla privacy"
        case .termini: return "Termini d'uso"
        }
    }

    var icona: String {
        switch self {
        case .privacy: return "hand.raised"
        case .termini: return "doc.text"
        }
    }
}

enum InformazioniLegali {
    /// Il collegamento a una pagina del server (`<server>/privacy`, `<server>/termini`). `nil` se l'indirizzo del server manca o non è valido.
    static func indirizzo(_ pagina: PaginaServer, server: String) -> URL? {
        var base = server.trimmingCharacters(in: .whitespacesAndNewlines)
        while base.hasSuffix("/") { base.removeLast() }
        guard !base.isEmpty, IndirizzoServer.valido(base) else { return nil }
        return URL(string: base + "/" + pagina.rawValue)
    }

    /// Il collegamento al codice sorgente, come lo manda il server (campo facoltativo `sorgente` di `/api/stato`).
    /// Solo `https://` con un nome di sito, senza utente e password e non troppo lungo: tutto il resto si ignora e la voce non compare.
    static func sorgente(_ testo: String?) -> URL? {
        guard let testo else { return nil }
        let pulito = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !pulito.isEmpty, pulito.count <= 300,
              let url = URL(string: pulito),
              url.scheme?.lowercased() == "https",
              let host = url.host, !host.isEmpty,
              url.user == nil, url.password == nil else { return nil }
        return url
    }
}

/// Solo il campo che serve a questa parte dell'app: `/api/stato` ha molto altro, qui non interessa.
struct StatoSorgente: Decodable {
    let sorgente: String?
}
