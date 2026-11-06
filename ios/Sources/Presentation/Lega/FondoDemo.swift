import Foundation

/// Le foto `lega-stato-fondo` e `lega-rosa-fondo` (#425): la lista parte scorsa in fondo, dove sono le parti nuove di Stato dei
/// dati (gol attesi nostri, indicatori del consiglio) e l'ultima riga della Rosa. Vale solo in demo e solo con `-DEMO_FONDO`:
/// nell'app vera la lista non ha niente in più.
enum FondoDemo {
    /// L'identità dell'ultima riga della lista (`RigaFondoDemo`): è lì che scorre la foto, appena i dati sono arrivati.
    static let idRiga = "fondo-demo-lega"

    /// Vero in demo con `-DEMO_FONDO <valore>` fra gli argomenti di lancio, come per `demoInFondo`.
    static func attivo(demo: Bool, argomenti: [String]) -> Bool {
        demo && Demo.argomento("DEMO_FONDO", in: argomenti) != nil
    }

    /// Vero adesso: l'app è in demo e le foto chiedono la schermata scorsa in fondo.
    static var richiesto: Bool {
        attivo(demo: Demo.attivo, argomenti: ProcessInfo.processInfo.arguments)
    }
}
