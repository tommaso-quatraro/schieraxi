import Foundation

/// Formattazione dei numeri in un solo posto. Sempre in italiano (virgola decimale), come le date di `Quando`,
/// così l'app, il widget e le risposte di Siri scrivono i numeri allo stesso modo qualunque sia la lingua del telefono.
enum Formato {
    static let locale = Locale(identifier: "it_IT")

    /// Un numero con `cifre` decimali, arrotondato come la web app (`toFixed`): a metà si va lontano dallo zero
    /// (6,25 → 6,3; -6,25 → -6,3), non al pari come fa `formatted` da solo (6,25 → 6,2).
    /// Un valore assente o non finito si scrive «–», come sul web.
    static func decimali(_ valore: Double?, cifre: Int = 1) -> String {
        guard let valore, valore.isFinite else { return "–" }
        let cifre = min(max(cifre, 0), 6)
        let scala = pow(10.0, Double(cifre))
        var tondo = (valore * scala).rounded() / scala
        if !tondo.isFinite { tondo = valore }   // numeri enormi: la moltiplicazione esce dai limiti, si formatta com'è
        if tondo == 0 { tondo = 0 }             // niente «-0,0»
        return tondo.formatted(.number.precision(.fractionLength(cifre)).locale(locale))
    }

    /// «1 credito», «12 crediti»: il plurale giusto per ogni numero (anche 0 e i negativi: «0 crediti», «-1 credito» no, «-1 crediti»).
    static func plurale(_ n: Int, _ singolare: String, _ plurale: String) -> String {
        "\(n) \(abs(n) == 1 ? singolare : plurale)"
    }

    static func crediti(_ n: Int) -> String { plurale(n, "credito", "crediti") }
    static func giornate(_ n: Int) -> String { plurale(n, "giornata", "giornate") }
    static func giocatori(_ n: Int) -> String { plurale(n, "giocatore", "giocatori") }

    /// Punti attesi: una cifra decimale; un valore mancante si scrive «–», come sul web.
    static func punti(_ valore: Double?) -> String {
        decimali(valore, cifre: 1)
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
    /// Un numero del server come intero ARROTONDATO come la web app (`Math.round`: 155,9 → 156, 4,5 → 5, -2,5 → -2), senza rischi:
    /// `Int(Double)` va in crash con valori non finiti o enormi.
    static func intero(_ valore: Double?) -> Int {
        guard let valore, valore.isFinite, abs(valore) < 1e15 else { return 0 }
        return Int((valore + 0.5).rounded(.down))
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
