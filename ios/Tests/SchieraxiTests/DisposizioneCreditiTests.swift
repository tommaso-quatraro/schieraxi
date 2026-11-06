import SwiftUI
import Testing
@testable import Schieraxi

/// «Crediti residui» nella rosa di una squadra con il testo molto grande (issue #467). Nelle foto con il testo al massimo il
/// campo (largo quanto il testo, `@ScaledMetric`) lasciava a «Salva» una striscia di pochi punti e la parola andava a capo
/// una lettera per riga («S», «al», «va»). Da «Accessibilità 1» in su titolo, campo e «Salva» vanno uno sotto l'altro.
/// Qui si prova la scelta della disposizione, misura per misura; l'aspetto (e il bersaglio di tocco di «Salva») lo guarda la
/// foto `lega-rosa` a testo massimo, scattata su `main` dopo l'unione.
@Suite("Crediti residui nella rosa: disposizione con il testo grande (#467)")
struct DisposizioneCreditiTests {

    @Test("Fino a XXXL la riga resta com'è; da Accessibilità 1 in su titolo, campo e «Salva» vanno uno sotto l'altro")
    func soglia() {
        let incolonnate = DynamicTypeSize.allCases.filter { DisposizioneCrediti.per($0) == .inColonna }
        #expect(incolonnate == [.accessibility1, .accessibility2, .accessibility3, .accessibility4, .accessibility5])
        let inRiga = DynamicTypeSize.allCases.filter { DisposizioneCrediti.per($0) == .inRiga }
        #expect(inRiga == [.xSmall, .small, .medium, .large, .xLarge, .xxLarge, .xxxLarge])
    }

    @Test("Ogni misura sotto «Accessibilità 1», compreso il testo predefinito di iOS (.large): la riga resta com'è",
          arguments: [DynamicTypeSize.xSmall, .small, .medium, .large, .xLarge, .xxLarge, .xxxLarge])
    func sottoLaSoglia(dimensione: DynamicTypeSize) {
        #expect(DisposizioneCrediti.per(dimensione) == .inRiga, "\(dimensione)")
    }

    @Test("Ogni misura da «Accessibilità 1» in su, compreso il testo al massimo della foto: titolo, campo e «Salva» in colonna",
          arguments: [DynamicTypeSize.accessibility1, .accessibility2, .accessibility3, .accessibility4, .accessibility5])
    func daAccessibilitaInSu(dimensione: DynamicTypeSize) {
        #expect(DisposizioneCrediti.per(dimensione) == .inColonna, "\(dimensione)")
    }
}
