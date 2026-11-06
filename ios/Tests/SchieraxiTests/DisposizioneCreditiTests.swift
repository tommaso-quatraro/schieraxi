import SwiftUI
import Testing
@testable import Schieraxi

/// «Crediti residui» nella rosa di una squadra con il testo molto grande (issue #467). Nelle foto con il testo al massimo il
/// campo (largo quanto il testo, `@ScaledMetric`) lasciava a «Salva» una striscia di pochi punti e la parola andava a capo
/// una lettera per riga («S», «al», «va»). Da «Accessibilità 1» in su titolo, campo e «Salva» vanno uno sotto l'altro, e
/// «Salva» ha un bersaglio di tocco intero. Qui si prova la scelta della disposizione; l'aspetto lo guarda la foto
/// `lega-rosa` a testo massimo, scattata su `main` dopo l'unione.
@Suite("Crediti residui nella rosa: disposizione con il testo grande (#467)")
struct DisposizioneCreditiTests {

    @Test("Fino a XXXL la riga resta com'è; da Accessibilità 1 in su titolo, campo e «Salva» vanno uno sotto l'altro")
    func soglia() {
        let incolonnate = DynamicTypeSize.allCases.filter { DisposizioneCrediti.per($0) == .inColonna }
        #expect(incolonnate == [.accessibility1, .accessibility2, .accessibility3, .accessibility4, .accessibility5])
        let inRiga = DynamicTypeSize.allCases.filter { DisposizioneCrediti.per($0) == .inRiga }
        #expect(inRiga == [.xSmall, .small, .medium, .large, .xLarge, .xxLarge, .xxxLarge])
    }

    @Test("La disposizione segue le misure «Accessibilità» di sistema, senza una soglia scritta a parte", arguments: DynamicTypeSize.allCases)
    func comeIlSistema(dimensione: DynamicTypeSize) {
        #expect((DisposizioneCrediti.per(dimensione) == .inColonna) == dimensione.isAccessibilitySize, "\(dimensione)")
    }

    @Test("Il testo predefinito di iOS resta in riga; il testo al massimo (la foto) va in colonna")
    func predefinitoEMassimo() {
        #expect(DisposizioneCrediti.per(.large) == .inRiga, "il testo predefinito di iOS non cambia")
        #expect(DisposizioneCrediti.per(.accessibility5) == .inColonna, "il testo al massimo è il caso della foto")
    }

    @Test("Il bersaglio di tocco di «Salva» è alto almeno 44 punti")
    func bersaglioDiTocco() {
        #expect(DisposizioneCrediti.latoMinimoTocco >= 44)
    }
}
