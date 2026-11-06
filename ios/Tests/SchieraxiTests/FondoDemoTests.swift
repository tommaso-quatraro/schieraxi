import Testing
@testable import Schieraxi

/// La riga in fondo alle liste della Lega che serve alle foto `lega-stato-fondo` e `lega-rosa-fondo` (#425): c'è solo in demo
/// e solo con `-DEMO_FONDO`. Nell'app vera, e nella demo di chi prova l'app senza foto, la lista non cambia.
struct FondoDemoTests {

    struct Caso: Sendable, CustomTestStringConvertible {
        let demo: Bool
        let argomenti: [String]
        let attesa: Bool
        var testDescription: String { "demo \(demo): " + argomenti.joined(separator: " ") }
    }

    @Test("La riga del fondo c'è solo in demo e solo con -DEMO_FONDO", arguments: [
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "1"], attesa: true),
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-rosa", "-DEMO_FONDO", "1"], attesa: true),
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato"], attesa: false),       // foto senza «-fondo»
        Caso(demo: false, argomenti: ["-DEMO_FONDO", "1"], attesa: false),                              // app vera
        Caso(demo: false, argomenti: [], attesa: false),
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_FONDO"], attesa: false),                           // senza valore dopo l'argomento
    ])
    func laRigaDelFondoSoloInDemo(_ caso: Caso) {
        #expect(FondoDemo.attivo(demo: caso.demo, argomenti: caso.argomenti) == caso.attesa)
    }
}
