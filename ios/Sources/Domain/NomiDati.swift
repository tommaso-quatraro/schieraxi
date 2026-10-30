import Foundation

/// I nomi grezzi dei dati del server («quote-odds», «quote-giocatore 2026-27 g10») in parole per l'utente.
enum NomiDati {
    private static let noti: [String: String] = [
        "aggiornamento": "Aggiornamento generale",
        "dati-extra": "Dati extra delle partite",
        "quote-odds": "Quote delle partite",
        "voti": "Voti delle giornate",
        "calendario": "Calendario",
        "listone": "Elenco dei calciatori",
        "probabili": "Probabili formazioni",
        "understat": "Statistiche delle partite",
    ]

    static func leggibile(_ cosa: String) -> String {
        let t = cosa.trimmingCharacters(in: .whitespaces)
        let minuscolo = t.lowercased()
        if let n = noti[minuscolo] { return n }
        // «quote-giocatore 2026-27 g10» -> «Quote dei giocatori (giornata 10)»
        if minuscolo.hasPrefix("quote-giocatore") {
            if let g = giornata(in: minuscolo) { return "Quote dei giocatori (giornata \(g))" }
            return "Quote dei giocatori"
        }
        // «crediti-giocatore 2026-10» -> «Crediti dei giocatori»
        if minuscolo.hasPrefix("crediti-giocatore") { return "Crediti dei giocatori" }
        let parole = minuscolo.replacingOccurrences(of: "-", with: " ").replacingOccurrences(of: "_", with: " ")
        return parole.prefix(1).uppercased() + parole.dropFirst()
    }

    /// Il numero dopo una «g» alla fine («... g10»).
    private static func giornata(in testo: String) -> Int? {
        guard let ultima = testo.split(separator: " ").last, ultima.hasPrefix("g"), let n = Int(ultima.dropFirst()) else { return nil }
        return n
    }
}
