import Foundation

/// Formattazione dei numeri in un solo posto. Sempre in italiano (virgola decimale), come le date di `Quando`,
/// così l'app, il widget e le risposte di Siri scrivono i numeri allo stesso modo qualunque sia la lingua del telefono.
enum Formato {
    static let locale = Locale(identifier: "it_IT")

    /// Un numero con `cifre` decimali, arrotondato come il server (`frasi.arrotonda`) e la web (`toFixed`): sul valore vero del
    /// numero in memoria, e a metà si va lontano dallo zero (6,25 → 6,3; -6,25 → -6,3), non al pari come fa `formatted` da solo
    /// (6,25 → 6,2). 6,35 in memoria è 6,3499…, quindi «6,3». Un valore assente o non finito si scrive «–», come sul web.
    static func decimali(_ valore: Double?, cifre: Int = 1) -> String {
        guard let valore, valore.isFinite else { return "–" }
        let cifre = min(max(cifre, 0), 6)
        let scala = pow(10.0, Double(cifre))
        var tondo = arrotondato(valore, scala: scala) / scala
        if !tondo.isFinite { tondo = valore }   // numeri enormi: la moltiplicazione esce dai limiti, si formatta com'è
        if tondo == 0 { tondo = 0 }             // niente «-0,0»
        return tondo.formatted(.number.precision(.fractionLength(cifre)).locale(locale))
    }

    /// `valore × scala` arrotondato all'intero sul prodotto VERO, il mezzo lontano dallo zero. Il prodotto calcolato è già
    /// arrotondato e può cadere proprio a metà anche quando quello vero non ci cade: 6,35 è 6,3499… e 6,35 × 10 dà 63,5 tondo.
    /// Solo in quel caso decide il resto, la parte persa dal prodotto: `addingProduct` lo calcola esatto, senza arrotondamenti
    /// intermedi. Gli stessi casi del server e della web: ArrotondaComeIlServerTests e tests/test_arrotonda_come_server.py.
    private static func arrotondato(_ valore: Double, scala: Double) -> Double {
        let prodotto = valore * scala
        let resto = (-prodotto).addingProduct(valore, scala)   // prodotto vero − prodotto calcolato
        let versoZero = prodotto.rounded(.towardZero)
        guard abs(prodotto - versoZero) == 0.5, resto != 0 else { return prodotto.rounded(.toNearestOrAwayFromZero) }
        // a metà solo in apparenza: se il prodotto vero sta dalla parte dello zero si va verso lo zero, altrimenti lontano
        return (resto < 0) == (prodotto > 0) ? versoZero : prodotto.rounded(.toNearestOrAwayFromZero)
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

    /// Con il segno davanti, come la web (`segno` di `app.js`): «+2,5», «−0,4» con il meno tipografico (U+2212).
    /// Se arrotondato vale zero resta «0,0» senza segno; un valore mancante o non finito si scrive «–».
    static func conSegno(_ valore: Double, cifre: Int = 1) -> String {
        let testo = decimali(abs(valore), cifre: cifre)
        guard testo.contains(where: { ("1"..."9").contains($0) }) else { return testo }
        return (valore > 0 ? "+" : "\u{2212}") + testo
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

    /// Difficoltà di una partita (1 facile ... 5 molto dura) a parole: l'unica scala dell'app, quella della web
    /// (`diff.1`…`diff.5` di testi.js, #293), uguale su schermo e per VoiceOver. Con la maiuscola, come nelle pillole.
    static func nomeDifficolta(_ valore: Double?) -> String {
        switch intero(valore ?? 3) {
        case ...1: return "Facile"
        case 2: return "Abbordabile"
        case 3: return "Normale"
        case 4: return "Dura"
        default: return "Molto dura"
        }
    }

    /// Le stesse parole in minuscolo, dentro una frase («Partita normale», «…, in casa, dura»), anche per VoiceOver.
    static func difficolta(_ valore: Double?) -> String {
        nomeDifficolta(valore).lowercased()
    }
}
