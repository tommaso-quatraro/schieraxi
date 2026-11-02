import XCTest
import SwiftUI
@testable import Schieraxi

/// Il nome disegnato («SchieraXI» in testa a Oggi, ad Accesso e al primo avvio) e il colore della sua «XI».
final class NomeSchieraXITests: XCTestCase {
    /// Luminanza relativa (WCAG) di un colore risolto nel tema chiaro o scuro.
    private func luminanza(_ colore: Color, _ schema: ColorScheme) -> Double {
        var ambiente = EnvironmentValues()
        ambiente.colorScheme = schema
        let r = colore.resolve(in: ambiente)
        return 0.2126 * Double(r.linearRed) + 0.7152 * Double(r.linearGreen) + 0.0722 * Double(r.linearBlue)
    }

    private func contrasto(_ a: Double, _ b: Double) -> Double { (max(a, b) + 0.05) / (min(a, b) + 0.05) }

    func testLaXIDelloSloganSiLeggeInChiaroEInScuro() {
        let xiChiaro = luminanza(Color.xi, .light)
        let xiScuro = luminanza(Color.xi, .dark)
        // bianco, grigio dei fondi raggruppati (#F2F2F7), nero e grigio delle schede scure (#1C1C1E)
        XCTAssertGreaterThanOrEqual(contrasto(xiChiaro, 1.0), 4.5, "XI sul bianco")
        XCTAssertGreaterThanOrEqual(contrasto(xiChiaro, 0.888), 4.5, "XI sul grigio chiaro")
        XCTAssertGreaterThanOrEqual(contrasto(xiScuro, 0.0), 4.5, "XI sul nero")
        XCTAssertGreaterThanOrEqual(contrasto(xiScuro, 0.0116), 4.5, "XI sul grigio scuro")
    }

    @MainActor
    func testIlNomeSiDisegnaInOgniMisura() {
        let misure: [(CGFloat, Bool)] = [(16, false), (22, false), (40, true), (120, true)]
        for (altezza, puntino) in misure {
            let vista = WordmarkSchieraXI(puntino: puntino).frame(width: altezza * WordmarkSchieraXI.rapporto, height: altezza)
            let foto = ImageRenderer(content: vista)
            foto.scale = 2
            guard let immagine = foto.uiImage else { return XCTFail("nessuna immagine a \(altezza) punti") }
            XCTAssertEqual(immagine.size.height, altezza, accuracy: 0.5)
        }
    }
}
