import SwiftUI

/// Le foto `lega-stato-fondo`, `lega-rosa-fondo` e `lega-stato-nostri` (#425, #430): la lista parte scorsa in fondo, dove sono le
/// parti nuove di Stato dei dati (indicatori del consiglio) e l'ultima riga della Rosa; per Stato dei dati c'è anche un secondo
/// punto di arrivo, i gol attesi nostri, che col consiglio non entra in una foto sola. Vale solo in demo, con `-DEMO_FONDO`:
/// nell'app vera la lista non ha niente in più.
enum FondoDemo {
    /// L'identità dell'ultima riga della lista (`RigaFondoDemo`): è lì che scorre la foto, appena i dati sono arrivati.
    static let idRiga = "fondo-demo-lega"

    /// L'identità della prima riga del riquadro «Gol attesi nostri» (`GolAttesiNostriSezione`): dove si ferma `lega-stato-nostri`.
    static let idNostri = "fondo-demo-nostri"

    /// Dove si ferma la foto «nostri»: la riga un po' sotto il bordo alto, così sopra si vede anche il titolo del riquadro.
    static let ancoraNostri = UnitPoint(x: 0.5, y: 0.06)

    /// Vero in demo con `-DEMO_FONDO <valore>` fra gli argomenti di lancio, come per `demoInFondo`.
    static func attivo(demo: Bool, argomenti: [String]) -> Bool {
        demo && Demo.argomento("DEMO_FONDO", in: argomenti) != nil
    }

    /// Vero in demo con `-DEMO_FONDO nostri`: Stato dei dati si ferma sui gol attesi nostri invece di andare in fondo.
    static func vaAlleNostri(demo: Bool, argomenti: [String]) -> Bool {
        demo && Demo.argomento("DEMO_FONDO", in: argomenti) == "nostri"
    }

    /// Vero adesso: l'app è in demo e le foto chiedono la schermata scorsa in fondo.
    static var richiesto: Bool {
        attivo(demo: Demo.attivo, argomenti: ProcessInfo.processInfo.arguments)
    }

    /// Vero adesso: l'app è in demo e la foto vuole Stato dei dati fermo sui gol attesi nostri.
    static var richiestoAlleNostri: Bool {
        vaAlleNostri(demo: Demo.attivo, argomenti: ProcessInfo.processInfo.arguments)
    }

    /// Dove deve arrivare la foto di Stato dei dati: la riga delle nostri, o l'ultima riga della lista.
    static var arrivoDiStato: (id: String, ancora: UnitPoint) {
        richiestoAlleNostri ? (idNostri, ancoraNostri) : (idRiga, .bottom)
    }
}
