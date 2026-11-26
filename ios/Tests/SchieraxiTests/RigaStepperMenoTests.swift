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

    /// Le cifre del valore contano come sulla web (`decimaliRegola`): il valore si scrive con i decimali che ha, almeno `cifre`.
    @Test("Un valore che arrotondato vale zero resta senza segno: «0,00», non «−0,00»")
    func quasiZero() {
        #expect(RigaStepper.testo(-0.001, cifre: 1) == "0,00")
    }

    /// #923: «−0,25» si vedeva «−0,3», perché la riga scriveva sempre un decimale; la web scrive i decimali che il valore ha
    /// (`cifraCampo(v, Math.max(dec, decimaliRegola(v)))` in app.js), almeno quelli del campo.
    @Test("I decimali del valore, come la web: «−0,25» in un campo da un decimale, non «−0,3»")
    func decimaliDelValore() {
        #expect(RigaStepper.testo(-0.25, cifre: 1) == "\u{2212}0,25")
        #expect(RigaStepper.testo(0.75, cifre: 1) == "0,75")
        #expect(RigaStepper.testo(-0.5, cifre: 1) == "\u{2212}0,5")
        #expect(RigaStepper.testo(6, cifre: 1) == "6,0", "almeno le cifre del campo")
        #expect(RigaStepper.testo(2, cifre: 0) == "2")
        #expect(RigaStepper.testo(1.5, cifre: 0) == "1,5")
        #expect(RigaStepper.testo(6.25, cifre: 2) == "6,25")
    }

    @Test("Quanti decimali ha un valore delle regole: 0, 1 o 2, come `decimaliRegola` della web", arguments: [
        (3.0, 0), (-1.0, 0), (0.5, 1), (-0.5, 1), (0.25, 2), (-0.25, 2), (6.125, 2),
    ])
    func decimaliRegola(valore: Double, cifre: Int) {
        #expect(RegoleLogica.decimaliRegola(valore) == cifre)
    }
}
