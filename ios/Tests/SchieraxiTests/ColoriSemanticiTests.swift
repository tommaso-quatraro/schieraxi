import XCTest
import SwiftUI
@testable import Schieraxi

/// I colori semantici di docs/DESIGN.md: uguali a quelli della web, in scuro e in chiaro.
final class ColoriSemanticiTests: XCTestCase {
    private func esadecimale(_ colore: Color, scuro: Bool) -> String {
        let tratti = UITraitCollection(userInterfaceStyle: scuro ? .dark : .light)
        let ui = UIColor(colore).resolvedColor(with: tratti)
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        ui.getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "%02X%02X%02X", Int((r * 255).rounded()), Int((g * 255).rounded()), Int((b * 255).rounded()))
    }

    func testITreColoriDellaTabella() {
        XCTAssertEqual(esadecimale(.malus, scuro: true), "FF6B5E")
        XCTAssertEqual(esadecimale(.malus, scuro: false), "B3261E")
        XCTAssertEqual(esadecimale(.attenzione, scuro: true), "FFB04A")
        XCTAssertEqual(esadecimale(.attenzione, scuro: false), "9C5400")
        XCTAssertEqual(esadecimale(.informazione, scuro: true), "62A9FF")
        XCTAssertEqual(esadecimale(.informazione, scuro: false), "1A5BB5")
    }

    func testIlSecondarioESulFondoPiuLeggibile() {
        XCTAssertEqual(esadecimale(.testo2, scuro: true), "B3C6BA")
        XCTAssertEqual(esadecimale(.testo2, scuro: false), "587064")
    }
}
