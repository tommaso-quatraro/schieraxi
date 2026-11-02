import XCTest
import UIKit
@testable import Schieraxi

/// Gli accenti in modo chiaro devono restare leggibili (almeno 4,5:1) anche sul grigio dei fondi raggruppati (#F2F2F7) e sul bianco.
final class ContrastoAccentiTests: XCTestCase {
    private func luminanza(_ colore: UIColor) -> Double {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        colore.getRed(&r, green: &g, blue: &b, alpha: &a)
        func lineare(_ c: CGFloat) -> Double { let x = Double(c); return x <= 0.03928 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4) }
        return 0.2126 * lineare(r) + 0.7152 * lineare(g) + 0.0722 * lineare(b)
    }

    private func contrasto(_ a: UIColor, _ b: UIColor) -> Double {
        let (x, y) = (luminanza(a), luminanza(b))
        return (max(x, y) + 0.05) / (min(x, y) + 0.05)
    }

    func testOgniAccentoChiaroHaContrastoAlmeno45() {
        let grigio = UIColor(red: 242 / 255, green: 242 / 255, blue: 247 / 255, alpha: 1)
        for accento in Accento.allCases {
            XCTAssertGreaterThanOrEqual(contrasto(accento.chiaro, grigio), 4.5, "\(accento.nome) sul grigio raggruppato")
            XCTAssertGreaterThanOrEqual(contrasto(accento.chiaro, .white), 4.5, "\(accento.nome) sul bianco")
        }
    }

    func testOgniAccentoScuroHaContrastoAlmeno45SulNero() {
        for accento in Accento.allCases {
            XCTAssertGreaterThanOrEqual(contrasto(accento.scuro, .black), 4.5, "\(accento.nome) sul nero")
        }
    }
}
