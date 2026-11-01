import Foundation

/// Dove porta un indirizzo `schieraxi://...`.
enum Destinazione: Equatable {
    case sezione(Sezione)
    case giocatore(Int)
    /// Una pagina di Squadra o di Altro (`schieraxi://scambi`).
    case pagina(PaginaLega)
    /// Il foglio delle Impostazioni (`schieraxi://impostazioni`).
    case impostazioni
    /// «Collega il widget» (`schieraxi://widget/collega`, il tocco sul widget non collegato): copia il codice di collegamento.
    case collegaWidget
}

/// Indirizzi accettati dall'app (schema `schieraxi://`), per aprirla dal tocco su una notifica di ntfy (intestazione `Click`):
/// `schieraxi://oggi`, `formazione`, `squadra`, `altro` (e i vecchi `mercato`, `scambi`, `lega`) e `schieraxi://giocatore/<id>`.
enum Collegamenti {
    static let schema = "schieraxi"

    /// Esempio da mostrare all'utente.
    static let esempioNtfy = "Click: schieraxi://formazione"

    static func interpreta(_ url: URL) -> Destinazione? {
        guard let schemaUrl = url.scheme?.lowercased(), schemaUrl == schema, let host = url.host?.lowercased() else { return nil }
        if host == "impostazioni" { return .impostazioni }
        if host == "widget" {
            // "schieraxi://widget/collega" (e, per tolleranza, "schieraxi://widget")
            let parte = url.pathComponents.dropFirst().first?.lowercased()
            guard parte == nil || parte == "collega" else { return nil }
            return .collegaWidget
        }
        if host == "giocatore" {
            // pathComponents di "schieraxi://giocatore/12" è ["/", "12"]
            guard let testo = url.pathComponents.dropFirst().first, let id = Int(testo), id > 0 else { return nil }
            return .giocatore(id)
        }
        if host == "scambi" { return .pagina(.scambi) }   // Scambi è una pagina di Altro
        return Sezione.da(nome: host).map { .sezione($0) }
    }
}
