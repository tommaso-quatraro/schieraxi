import Foundation

/// La regola del nuovo tentativo al ritorno della rete (`RitornoRete`), senza la rete vera: si riprova solo quando la rete torna
/// dopo essere caduta e una copia salvata aspettava, e una volta sola, come la web, che aspetta l'evento `online` del browser
/// (`alRitornoDellaRete` in `app.js`). Con il server spento e la rete accesa non si riprova da soli: c'è «Riprova».
/// Il tentativo non si riarma da solo: le letture che restano senza rete nei 5 minuti dopo (anche quelle partite dal tentativo,
/// con la rete a tratti) non fanno riprovare di nuovo, quindi fra due «Aggiorna» automatici passano almeno 5 minuti (revisione
/// della #972: prima ogni ritorno della rete faceva ripartire 8-10 richieste).
struct AttesaRete {
    /// Il tempo minimo fra due tentativi automatici.
    static let intervallo: TimeInterval = 5 * 60

    /// Una schermata mostra la copia salvata perché la rete non c'era.
    private(set) var inAttesa = false
    /// L'ultima notizia sulla rete; nil prima della prima.
    private var inLinea: Bool?
    /// Quando si è riprovato l'ultima volta; nil se mai.
    private var ultimoTentativo: Date?

    /// Una lettura è rimasta senza rete con la copia a video: si aspetta il ritorno della rete, se l'ultimo tentativo automatico
    /// non è di meno di `intervallo` fa.
    mutating func aspetta(adesso: Date = Date()) {
        if let ultimo = ultimoTentativo, adesso.timeIntervalSince(ultimo) < Self.intervallo { return }
        inAttesa = true
    }

    /// Una notizia sulla rete. true = la rete è tornata e una copia aspettava: si riprova (e non si aspetta più).
    mutating func cambio(inLinea nuovo: Bool, adesso: Date = Date()) -> Bool {
        defer { inLinea = nuovo }
        guard nuovo, inLinea == false, inAttesa else { return false }
        inAttesa = false
        ultimoTentativo = adesso
        return true
    }
}
