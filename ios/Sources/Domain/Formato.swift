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
        Int(((probabilita ?? 0) * 100).rounded())
    }
}
