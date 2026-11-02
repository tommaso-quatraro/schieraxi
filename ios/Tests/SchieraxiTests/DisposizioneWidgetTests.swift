import SwiftUI
import Testing
@testable import Schieraxi

/// Le scelte di disposizione dei widget che cambiano con il testo grande (Dynamic Type): misure fisse, quindi meno righe.
@Suite("Disposizione dei widget con il testo grande")
struct DisposizioneWidgetTests {
    @Test("Prossima giornata, misura media: due giocatori da controllare, uno solo dal testo più grande del normale")
    func righeDubbi() {
        #expect(DisposizioneWidget.righeDubbi(.xSmall) == 2)
        #expect(DisposizioneWidget.righeDubbi(.large) == 2)
        #expect(DisposizioneWidget.righeDubbi(.xLarge) == 1)
        #expect(DisposizioneWidget.righeDubbi(.xxLarge) == 1)
        #expect(DisposizioneWidget.righeDubbi(.accessibility3) == 1)
    }

    @Test("Cruscotto in linea (Schermata di blocco): con il testo grande via il modulo, mai «2 da contr…»")
    func rigaInLinea() {
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 2, testo: .large) == "3-4-3 · 2 da controllare")
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 0, testo: .large) == "3-4-3 · titolari a posto")
        #expect(DisposizioneWidget.rigaInLinea(modulo: nil, dubbi: 1, testo: .large) == "— · 1 da controllare")
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 2, testo: .xLarge) == "2 da controllare")
        #expect(DisposizioneWidget.rigaInLinea(modulo: "3-4-3", dubbi: 0, testo: .accessibility3) == "titolari a posto")
    }
}
