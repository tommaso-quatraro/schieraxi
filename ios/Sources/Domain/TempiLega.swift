import Foundation

/// I «tempi della lega»: la scadenza della formazione (prima partita meno i minuti scelti) e la numerazione della lega,
/// che può partire da una giornata di Serie A diversa dalla prima. Tutti i campi del server sono facoltativi.
extension Oggi {
    /// Quando si chiude la formazione: `scadenza`, o l'inizio della prima partita se il server non la manda (o è vuota).
    var chiusura: String? {
        if let s = scadenza?.trimmingCharacters(in: .whitespaces), !s.isEmpty { return s }
        return inizio
    }

    /// Il numero da mostrare: quello della lega se c'è (e ha senso), altrimenti quello di Serie A.
    var giornataMostrata: Int {
        if let g = giornataLega, g > 0 { return g }
        return giornata
    }

    /// «Giornata 7 di lega (Serie A 10)» se i numeri sono diversi, altrimenti «Giornata 10».
    var etichettaGiornata: String {
        if let g = giornataLega, g > 0 {
            return g == giornata ? "Giornata \(g)" : "Giornata \(g) di lega (Serie A \(giornata))"
        }
        return "Giornata \(giornata)"
    }
}

enum TempiLega {
    static let minutiMassimi = 720.0
    static let primaGiornataMassima = 38.0

    /// «Con la prima giornata 4: la giornata 1 della lega è la 4ª di Serie A.» Valori fuori dai limiti si riportano dentro.
    static func spiegaPartenza(_ prima: Double) -> String {
        let n = Int(min(max(prima, 1), primaGiornataMassima))
        return n == 1 ? "La lega parte dalla prima giornata di Serie A: i due numeri coincidono."
                      : "La giornata 1 della lega è la \(n)ª di Serie A: prima di allora per la lega non esiste nulla."
    }

    /// «Si chiude 30 minuti prima della prima partita.» / «…all'inizio della prima partita.»
    static func spiegaScadenza(_ minuti: Double) -> String {
        let m = Int(min(max(minuti, 0), minutiMassimi))
        if m == 0 { return "La formazione si chiude all'inizio della prima partita." }
        return "La formazione si chiude \(Formato.plurale(m, "minuto", "minuti")) prima della prima partita."
    }
}
