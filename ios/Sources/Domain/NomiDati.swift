import Foundation

/// I nomi grezzi dei dati del server («dati-extra», «crediti-giocatore 2026-10») in parole per l'utente.
enum NomiDati {
    private static let noti: [String: String] = [
        "aggiornamento": "Aggiornamento generale",
        "dati-extra": "Dati extra delle partite",
        "voti": "Voti delle giornate",
        "calendario": "Calendario",
        "listone": "Elenco dei calciatori",
        "probabili": "Probabili formazioni",
        "understat": "Statistiche delle partite",
    ]

    /// Voci di server vecchi che l'app non mostra più (fonti di dati non più usate).
    static func daNascondere(_ cosa: String) -> Bool {
        cosa.lowercased().hasPrefix("quote")
    }

    static func leggibile(_ cosa: String) -> String {
        let t = cosa.trimmingCharacters(in: .whitespaces)
        let minuscolo = t.lowercased()
        if let n = noti[minuscolo] { return n }
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
