import XCTest
import UIKit
@testable import Schieraxi

/// Nel tema chiaro i pulsanti pieni, i link e i testi di azione usano l'oliva scuro (#526600) con testo bianco: almeno 4,5:1 sul bianco
/// e sul grigio dei fondi raggruppati (#F2F2F7). Il lime (#86A800) resta solo fondo o accento decorativo, mai testo.
final class ContrastoOlivaTests: XCTestCase {
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

    private let grigio = UIColor(red: 242 / 255, green: 242 / 255, blue: 247 / 255, alpha: 1)
    private let oliva = UIColor(red: 0x52 / 255, green: 0x66 / 255, blue: 0, alpha: 1)
    private let lime = UIColor(red: 0x86 / 255, green: 0xA8 / 255, blue: 0, alpha: 1)

    func testAccentoPredefinitoChiaroEOlivaScuro() {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        Accento.verde.chiaro.getRed(&r, green: &g, blue: &b, alpha: &a)
        XCTAssertEqual(r * 255, 0x52, accuracy: 0.5)
        XCTAssertEqual(g * 255, 0x66, accuracy: 0.5)
        XCTAssertEqual(b * 255, 0, accuracy: 0.5)
    }

    func testOlivaHaContrastoAlmeno45SulleSuperficiChiare() {
        XCTAssertGreaterThanOrEqual(contrasto(Accento.verde.chiaro, .white), 4.5, "testo di azione sul bianco")
        XCTAssertGreaterThanOrEqual(contrasto(Accento.verde.chiaro, grigio), 4.5, "testo di azione sul grigio raggruppato")
    }

    func testTestoBiancoSuPulsanteOlivaHaContrastoAlmeno45() {
        XCTAssertGreaterThanOrEqual(contrasto(.white, oliva), 4.5)
    }

    func testLimeNonBastaPerIlTesto() {
        // Documenta perché il lime non si usa per i testi sul chiaro.
        XCTAssertLessThan(contrasto(lime, .white), 4.5)
        XCTAssertLessThan(contrasto(lime, grigio), 4.5)
    }
}
