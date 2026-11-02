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
}
