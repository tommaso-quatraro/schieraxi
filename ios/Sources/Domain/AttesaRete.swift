import Foundation

/// La regola del nuovo tentativo al ritorno della rete (`RitornoRete`), senza la rete vera: si riprova solo quando la rete torna
/// dopo essere caduta e una copia salvata aspettava, e una volta sola, come la web, che aspetta l'evento `online` del browser
/// (`alRitornoDellaRete` in `app.js`). Con il server spento e la rete accesa non si riprova da soli: c'è «Riprova».
/// Il tentativo non si riarma da solo: le letture che restano senza rete nei 5 minuti dopo (anche quelle partite dal tentativo,
/// con la rete a tratti) non fanno riprovare di nuovo, quindi fra due «Aggiorna» automatici passano almeno 5 minuti (revisione
/// della #972: prima ogni ritorno della rete faceva ripartire 8-10 richieste). Lo riarma un «Riprova» toccato a mano, come sulla
/// web, dove «Riprova» rilegge la pagina e riattiva il tentativo; una lettura che riesce lo toglie, perché la copia non è più a
/// video (#980).
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

    /// «Riprova» toccato a mano: se anche questa lettura resta senza rete si aspetta di nuovo il ritorno della rete, pure entro
    /// `intervallo` dall'ultimo tentativo automatico, come la web (#980). Prima un «Riprova» fallito in quei 5 minuti non riattivava
    /// il tentativo. Da solo non fa riprovare: serve una lettura rimasta senza rete con la copia a video (`aspetta`).
    mutating func riprovaAMano() {
        ultimoTentativo = nil
    }

    /// Una lettura è riuscita: la copia non è più a video e non si aspetta più la rete (#980). Prima l'attesa restava, per esempio
    /// dopo un «Riprova» riuscito, e un passaggio dal Wi-Fi al cellulare faceva partire un «Aggiorna» inutile.
    mutating func letturaRiuscita() {
        inAttesa = false
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
