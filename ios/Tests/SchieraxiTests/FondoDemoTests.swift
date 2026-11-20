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

    /// La foto `lega-stato-nostri` (#430): Stato dei dati ha due riquadri lunghi quasi quanto lo schermo (gol attesi nostri e consiglio
    /// di formazione), che in una foto sola non stanno insieme. `-DEMO_FONDO nostri` ferma la lista sul primo; con `1` va in fondo.
    @Test("«-DEMO_FONDO nostri» ferma Stato dei dati sui gol attesi nostri, solo in demo", arguments: [
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "nostri"], attesa: true),
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "1"], attesa: false),     // fondo vero
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato"], attesa: false),
        Caso(demo: false, argomenti: ["-DEMO_FONDO", "nostri"], attesa: false),                                         // app vera
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_FONDO"], attesa: false),
    ])
    func ilPuntoDelleNostriSoloInDemo(_ caso: Caso) {
        #expect(FondoDemo.vaAlleNostri(demo: caso.demo, argomenti: caso.argomenti) == caso.attesa)
    }

    /// La foto `lega-stato-taratura` (#527): la riga della taratura di «gioca N%», sotto i gruppi di «Quanto sono giuste le
    /// previsioni», sta fra la cima della pagina (`lega-stato`) e le nostri, in nessuna delle due foto. `-DEMO_FONDO taratura` la
    /// ferma lì.
    @Test("«-DEMO_FONDO taratura» ferma Stato dei dati sulla riga della taratura, solo in demo", arguments: [
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "taratura"], attesa: true),
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "nostri"], attesa: false),
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "1"], attesa: false),     // fondo vero
        Caso(demo: true, argomenti: ["-DEMO", "-DEMO_SCHERMATA", "lega-stato"], attesa: false),
        Caso(demo: false, argomenti: ["-DEMO_FONDO", "taratura"], attesa: false),                                       // app vera
    ])
    func ilPuntoDellaTaraturaSoloInDemo(_ caso: Caso) {
        #expect(FondoDemo.vaAllaTaratura(demo: caso.demo, argomenti: caso.argomenti) == caso.attesa)
    }

    struct Arrivo: Sendable, CustomTestStringConvertible {
        let valore: String
        let id: String
        var testDescription: String { "-DEMO_FONDO " + valore }
    }

    @Test("Stato dei dati si ferma sulle nostri, sull'ultimo gruppo sopra la taratura o in fondo, secondo -DEMO_FONDO", arguments: [
        Arrivo(valore: "nostri", id: FondoDemo.idNostri),
        Arrivo(valore: "taratura", id: FondoDemo.idTaratura),
        Arrivo(valore: "1", id: FondoDemo.idRiga),
    ])
    func dovesiFermaStatoDeiDati(_ caso: Arrivo) {
        let argomenti = ["-DEMO", "-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", caso.valore]
        #expect(FondoDemo.arrivo(demo: true, argomenti: argomenti).id == caso.id)
    }

    /// La riga della taratura è nel piè della sezione, che non è una riga della lista: il punto della foto sta sull'ultimo gruppo,
    /// subito sopra. Gli altri gruppi tengono la loro identità.
    @Test("Solo l'ultimo gruppo della calibrazione prende il punto della foto della taratura")
    func ilPuntoStaSullUltimoGruppo() {
        let gruppi = ["Titolare 90-100%", "Titolare 70-89%", "Panchina 20-49%"]
        #expect(gruppi.map { FondoDemo.idGruppo($0, ultimo: gruppi.last) } == ["Titolare 90-100%", "Titolare 70-89%", FondoDemo.idTaratura])
        #expect(FondoDemo.idGruppo("Titolare 90-100%", ultimo: nil) == "Titolare 90-100%")
    }
}
