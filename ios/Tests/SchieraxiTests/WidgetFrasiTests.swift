import Testing
@testable import Schieraxi

/// Le frasi dei widget con i plurali giusti e il meno tipografico (U+2212), confrontate per intero.
@Suite("Frasi dei widget")
struct WidgetFrasiTests {
    @Test("«Attesi e fatti»: dentro la fascia in 1 giornata, in 3 giornate", arguments: [
        (1, 3, "Dentro la fascia prevista in 1 giornata su 3."),
        (3, 5, "Dentro la fascia prevista in 3 giornate su 5."),
        (0, 1, "Dentro la fascia prevista in 0 giornate su 1."),
    ])
    func dentroLaFascia(dentro: Int, su: Int, frase: String) {
        #expect(RiassuntoWidget.fraseDentro(dentro: dentro, su: su) == frase)
    }

    @Test("Chi non entra nell'elenco: «e un altro», mai «e altri 1»", arguments: [
        (1, "e un altro"),
        (2, "e altri 2"),
        (3, "e altri 3"),
    ])
    func altri(n: Int, frase: String) {
        #expect(RiassuntoWidget.altri(n) == frase)
    }

    @Test("«Attesi e fatti»: la media con il segno, anche il meno tipografico", arguments: [
        (1.5, 1, "In media +1,5 punti sul previsto nell'ultima giornata."),
        (-0.2, 5, "In media \u{2212}0,2 punti sul previsto nelle ultime 5 giornate."),
    ])
    func media(valore: Double, giornate: Int, frase: String) {
        #expect(RiassuntoWidget.fraseMedia(valore, giornate: giornate) == frase)
    }
}
