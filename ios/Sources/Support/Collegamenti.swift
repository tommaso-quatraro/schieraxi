import Foundation

/// Dove porta un indirizzo `schieraxi://...`.
enum Destinazione: Equatable {
    case sezione(Sezione)
    case giocatore(Int)
    /// Una pagina di Squadra o di Altro (da «Da fare» e da «Apri il Diario»).
    case pagina(PaginaLega)
    /// Il foglio delle Impostazioni (`schieraxi://impostazioni`).
    case impostazioni
    /// «Collega il widget» (`schieraxi://widget/collega`, il tocco sul widget non collegato): apre solo la schermata, che aspetta il
    /// tocco su «Collega» prima di collegare o di copiare il codice (l'indirizzo lo può aprire anche un'altra app, #482).
    case collegaWidget
}

/// Indirizzi accettati dall'app (schema `schieraxi://`), per aprirla dal tocco su una notifica di ntfy (intestazione `Click`):
/// `schieraxi://oggi`, `formazione`, `squadra`, `altro` e `schieraxi://giocatore/<id>`. I vecchi `mercato`, `scambi` e `lega`
/// valgono ancora: le pagine tolte il 12/11/2026 (#634) aprono la scheda più vicina che resta (`mercato` Squadra, `scambi` e `lega` Altro).
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
        return Sezione.da(nome: host).map { .sezione($0) }
    }
}
