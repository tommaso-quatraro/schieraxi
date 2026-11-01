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
    var etichettaGiornata: String { TempiLega.etichetta(serieA: giornata, lega: giornataLega) }
}

extension Formazione {
    var etichettaGiornata: String { TempiLega.etichetta(serieA: giornata, lega: giornataLega) }
}

enum TempiLega {
    /// «Giornata 7 di lega (Serie A 10)» se il numero di lega c'è ed è diverso, altrimenti «Giornata 10». Lega mancante o non valida: Serie A.
    static func etichetta(serieA: Int, lega: Int?) -> String {
        guard let l = lega, l > 0 else { return "Giornata \(serieA)" }
        return l == serieA ? "Giornata \(l)" : "Giornata \(l) di lega (Serie A \(serieA))"
    }

    /// La sigla corta per gli spazi stretti: «G7» (il numero di lega se c'è, altrimenti quello di Serie A).
    static func sigla(serieA: Int, lega: Int?) -> String {
        if let l = lega, l > 0 { return "G\(l)" }
        return "G\(serieA)"
    }

    /// La riga sotto il modulo in Formazione. Se la formazione l'hai già scelta tu non si ripete «la tua scelta»
    /// (lo dicono già il testo sotto e il pulsante «Torna alla consigliata»): resta solo la giornata.
    static func didascalia(giornata: String, scelta: Bool, comeConsigliato: Bool) -> String {
        if scelta { return giornata }
        return giornata + " · " + (comeConsigliato ? "modulo consigliato" : "modulo scelto")
    }

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
