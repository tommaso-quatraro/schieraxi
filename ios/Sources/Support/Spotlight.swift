import CoreSpotlight
import UniformTypeIdentifiers

/// I giocatori osservati compaiono nella ricerca di iOS (Spotlight): toccandoli si apre la loro scheda nell'app.
enum Spotlight {
    private static let dominio = "it.schieraxi.app.osservati"

    /// Sostituisce l'elenco indicizzato con i giocatori osservati di adesso.
    static func indicizza(_ giocatori: [Giocatore]) {
        let indice = CSSearchableIndex.default()
        let voci = giocatori.map { g -> CSSearchableItem in
            let attributi = CSSearchableItemAttributeSet(contentType: .content)
            attributi.title = g.nome
            attributi.contentDescription = [nomeRuolo(g.ruolo).capitalized, g.squadra?.uppercased()].compactMap { $0 }.joined(separator: " · ")
            attributi.keywords = [g.nome, g.squadra ?? "", "fantacalcio", "osservato"]
            return CSSearchableItem(uniqueIdentifier: "giocatore-\(g.id)", domainIdentifier: dominio, attributeSet: attributi)
        }
        indice.deleteSearchableItems(withDomainIdentifiers: [dominio]) { _ in
            if !voci.isEmpty { indice.indexSearchableItems(voci) { _ in } }
        }
    }

    /// Numero del giocatore se l'app è stata aperta da un risultato di Spotlight.
    static func idGiocatore(da attivita: NSUserActivity) -> Int? {
        guard let testo = attivita.userInfo?[CSSearchableItemActivityIdentifier] as? String, testo.hasPrefix("giocatore-") else { return nil }
        return Int(testo.dropFirst("giocatore-".count))
    }
}
