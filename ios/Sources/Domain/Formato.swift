import Foundation

/// Formattazione dei numeri in un solo posto. Sempre in italiano (virgola decimale), come le date di `Quando`,
/// così l'app, il widget e le risposte di Siri scrivono i numeri allo stesso modo qualunque sia la lingua del telefono.
enum Formato {
    static let locale = Locale(identifier: "it_IT")

    static func decimali(_ valore: Double, cifre: Int = 1) -> String {
        valore.formatted(.number.precision(.fractionLength(cifre)).locale(locale))
    }

    /// Punti attesi: una cifra decimale; un valore mancante vale zero.
    static func punti(_ valore: Double?) -> String {
        decimali(valore ?? 0, cifre: 1)
    }

    /// Con il segno davanti anche per i positivi: «+2,5».
    static func conSegno(_ valore: Double, cifre: Int = 1) -> String {
        (valore >= 0 ? "+" : "") + decimali(valore, cifre: cifre)
    }

    /// Una probabilità tra 0 e 1 come percentuale intera.
    static func percento(_ probabilita: Double?) -> Int {
        intero(((probabilita ?? 0) * 100).rounded())
    }
}

extension Formato {
    /// Un numero del server come intero, senza rischi: `Int(Double)` va in crash con valori non finiti o enormi.
    static func intero(_ valore: Double?) -> Int {
        guard let valore, valore.isFinite, abs(valore) < 1e15 else { return 0 }
        return Int(valore)
    }

    /// Difficoltà di una partita (1 facile ... 5 difficile) a parole, anche per VoiceOver.
    static func difficolta(_ valore: Double?) -> String {
        switch intero(valore ?? 3) {
        case ...1: return "molto facile"
        case 2: return "facile"
        case 3: return "difficoltà media"
        case 4: return "difficile"
        default: return "molto difficile"
        }
    }
}
