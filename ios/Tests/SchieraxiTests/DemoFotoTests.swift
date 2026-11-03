import Testing
@testable import Schieraxi

/// Gli argomenti di lancio con cui `scripts/screenshot.sh` chiede una fotografia all'app in modalità demo.
struct DemoFotoTests {

    struct Caso: Sendable, CustomTestStringConvertible {
        let argomenti: [String]
        let foto: String?
        var testDescription: String { argomenti.joined(separator: " ") }
    }

    @Test("Il nome della foto viene da -DEMO_SCHERMATA o, per l'accesso, da -DEMO_ACCESSO come nello script", arguments: [
        Caso(argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-regole", "-DEMO_FONDO", "1"], foto: "lega-regole"),
        Caso(argomenti: ["-DEMO", "-DEMO_ACCESSO", "account", "-DEMO_FONDO", "1"], foto: "accesso-account"),
        Caso(argomenti: ["-DEMO", "-DEMO_ACCESSO", "accedi", "-DEMO_ORIENTAMENTO", "orizzontale"], foto: "accesso-accedi"),
        Caso(argomenti: ["-DEMO"], foto: nil),
        Caso(argomenti: ["-DEMO", "-DEMO_SCHERMATA"], foto: nil),   // nome mancante in fondo
    ])
    func nomeDellaFoto(_ caso: Caso) {
        #expect(Demo.nomeFoto(argomenti: caso.argomenti) == caso.foto)
    }

    @Test("L'orizzontale si chiede solo con -DEMO_ORIENTAMENTO orizzontale, anche per l'accesso")
    func orizzontale() {
        #expect(Demo.chiedeOrizzontale(argomenti: ["-DEMO", "-DEMO_ACCESSO", "accedi", "-DEMO_ORIENTAMENTO", "orizzontale"]))
        #expect(Demo.chiedeOrizzontale(argomenti: ["-DEMO", "-DEMO_SCHERMATA", "formazione", "-DEMO_ORIENTAMENTO", "orizzontale"]))
        #expect(!Demo.chiedeOrizzontale(argomenti: ["-DEMO", "-DEMO_ACCESSO", "accedi"]))
        #expect(!Demo.chiedeOrizzontale(argomenti: ["-DEMO", "-DEMO_ORIENTAMENTO", "verticale"]))
    }
}
