import Testing
@testable import Schieraxi

// Collaudo del 26/11: le righe con − e + delle regole (malus, fasce del modificatore) scrivevano «-0,5» con il trattino corto, il
// formato italiano di `Formato.decimali`, mentre l'anteprima del regolamento, gli avvisi sui limiti e la web scrivono «−0,5» con
// il meno tipografico (U+2212). Sull'iPhone il numero non si scrive a mano (solo − e +): conta solo come si legge.

@Suite("Regole: il meno tipografico nelle righe con − e + (collaudo del 26/11)")
struct RigaStepperMenoTests {
    @Test("Con un decimale, come i punteggi: «−0,5»; positivi e zero senza segno", arguments: [
        (-0.5, "\u{2212}0,5"), (-1.0, "\u{2212}1,0"), (-20.0, "\u{2212}20,0"), (3.0, "3,0"), (0.0, "0,0"),
    ])
    func unDecimale(valore: Double, testo: String) {
        #expect(RigaStepper.testo(valore, cifre: 1) == testo)
        #expect(!RigaStepper.testo(valore, cifre: 1).contains("-"), "mai il trattino corto")
    }

    @Test("Senza decimali (rosa, panchina) e con due (la media delle fasce)")
    func altreCifre() {
        #expect(RigaStepper.testo(-2, cifre: 0) == "\u{2212}2")
        #expect(RigaStepper.testo(-0.25, cifre: 2) == "\u{2212}0,25")
        #expect(RigaStepper.testo(6.25, cifre: 2) == "6,25")
    }

    @Test("Un valore che arrotondato vale zero resta senza segno: «0,0», non «−0,0»")
    func quasiZero() {
        #expect(RigaStepper.testo(-0.01, cifre: 1) == "0,0")
    }
}
