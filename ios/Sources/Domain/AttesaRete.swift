import Foundation

/// La regola del nuovo tentativo al ritorno della rete (`RitornoRete`), senza la rete vera: si riprova solo quando la rete torna
/// dopo essere caduta e una copia salvata aspettava, e una volta sola, come la web, che aspetta l'evento `online` del browser
/// (`alRitornoDellaRete` in `app.js`). Con il server spento e la rete accesa non si riprova da soli: c'è «Riprova».
struct AttesaRete {
    static let intervallo: TimeInterval = 5 * 60

    /// Una schermata mostra la copia salvata perché la rete non c'era.
    private(set) var inAttesa = false
    /// L'ultima notizia sulla rete; nil prima della prima.
    private var inLinea: Bool?

    mutating func aspetta(adesso: Date = Date()) {
        inAttesa = true
    }

    /// Una notizia sulla rete. true = la rete è tornata e una copia aspettava: si riprova (e non si aspetta più).
    mutating func cambio(inLinea nuovo: Bool, adesso: Date = Date()) -> Bool {
        defer { inLinea = nuovo }
        guard nuovo, inLinea == false, inAttesa else { return false }
        inAttesa = false
        return true
    }
}
