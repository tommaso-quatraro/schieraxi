import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// La scritta dei pulsanti pieni (`pulsanteVetro(prominente: true)`: «Accedi», «Valuta l'offerta», «Seguito», «Condividi l'immagine»)
/// deve stare ad almeno 4,5:1 (WCAG 2.2, 1.4.3) sul loro fondo, il colore principale dell'app, in chiaro e in scuro. Prima
/// dell'issue #248 lo stile di sistema la scriveva bianca anche sul verde chiaro del tema scuro: 1,77:1. I colori sono quelli della
/// web (`--azione`, `--azione-testo` in fanta/web/stile.css; `tests/test_design_web.py` controlla che coincidano).
@Suite("Pulsanti pieni leggibili in chiaro e in scuro")
struct ContrastoPulsantiPieniTests {
    private static func luminanza(_ colore: Color, scuro: Bool) -> Double {
        let ui = UIColor(colore).resolvedColor(with: UITraitCollection(userInterfaceStyle: scuro ? .dark : .light))
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        ui.getRed(&r, green: &g, blue: &b, alpha: &a)
        func lineare(_ c: CGFloat) -> Double { let x = Double(c); return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4) }
        return 0.2126 * lineare(r) + 0.7152 * lineare(g) + 0.0722 * lineare(b)
    }

    private static func contrasto(_ a: Color, _ b: Color, scuro: Bool) -> Double {
        let (x, y) = (luminanza(a, scuro: scuro), luminanza(b, scuro: scuro))
        return (max(x, y) + 0.05) / (min(x, y) + 0.05)
    }

    @Test("La scritta sul fondo del pulsante pieno: almeno 4,5:1", arguments: [false, true])
    func scrittaSulFondo(scuro: Bool) {
        let c = Self.contrasto(Color.scrittaPulsante, Color.verde, scuro: scuro)
        #expect(c >= 4.5, "\(scuro ? "scuro" : "chiaro"): \(c)")
    }

    @Test("Nello scuro il bianco sul verde chiaro non basta: per questo la scritta non è quella del sistema")
    func biancoNelloScuroNonBasta() {
        #expect(Self.contrasto(.white, Color.verde, scuro: true) < 4.5)
    }

    @Test("Spento: la scritta è il grigio dell'app, leggibile sul grigio del pulsante spento", arguments: [false, true])
    func scrittaSpenta(scuro: Bool) {
        // il fondo grigio del pulsante spento: #2C2C2E nello scuro, #E5E5EA nel chiaro (riempimenti di sistema)
        let fondo = scuro ? Color(red: 0x2C / 255, green: 0x2C / 255, blue: 0x2E / 255) : Color(red: 0xE5 / 255, green: 0xE5 / 255, blue: 0xEA / 255)
        let c = Self.contrasto(Color.testoSecondario, fondo, scuro: scuro)
        #expect(c >= 4.5, "\(scuro ? "scuro" : "chiaro"): \(c)")
    }
}
