import Foundation

/// Dove porta un indirizzo `schieraxi://...`.
enum Destinazione: Equatable {
    case sezione(Sezione)
    case giocatore(Int)
    /// Il foglio delle Impostazioni (`schieraxi://impostazioni`).
    case impostazioni
}

/// Indirizzi accettati dall'app (schema `schieraxi://`), per aprirla dal tocco su una notifica di ntfy (intestazione `Click`):
/// `schieraxi://oggi`, `formazione`, `mercato`, `scambi`, `lega` e `schieraxi://giocatore/<id>`.
enum Collegamenti {
    static let schema = "schieraxi"

    /// Esempio da mostrare all'utente.
    static let esempioNtfy = "Click: schieraxi://formazione"

    static func interpreta(_ url: URL) -> Destinazione? {
        guard url.scheme?.lowercased() == schema, let host = url.host?.lowercased() else { return nil }
        if host == "impostazioni" { return .impostazioni }
        if host == "giocatore" {
            // pathComponents di "schieraxi://giocatore/12" è ["/", "12"]
            guard let testo = url.pathComponents.dropFirst().first, let id = Int(testo), id > 0 else { return nil }
            return .giocatore(id)
        }
        return Sezione(rawValue: host).map { .sezione($0) }
    }
}
