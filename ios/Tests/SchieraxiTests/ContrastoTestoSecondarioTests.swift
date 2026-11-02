import XCTest
import UIKit
@testable import Schieraxi

/// Il grigio dei testi secondari (`Color.testoSecondario`, definito in `Tema`) deve restare sopra 4,5:1 (WCAG AA, testo normale)
/// su tutti i fondi dell'app: bianco delle schede, grigio dei fondi raggruppati, campi incassati e sotto l'alone sfumato di `Sfondo`
/// nel punto più carico. Il grigio di sistema (`.secondary`) è semitrasparente e lì scendeva sotto 3:1 (collaudo di accessibilità).
final class ContrastoTestoSecondarioTests: XCTestCase {
    private typealias RGB = (r: Double, g: Double, b: Double)

    private func rgb(_ n: UInt32) -> RGB {
        (Double((n >> 16) & 0xff), Double((n >> 8) & 0xff), Double(n & 0xff))
    }

    /// Un colore con trasparenza `alfa` sopra un fondo pieno.
    private func sopra(_ colore: RGB, _ alfa: Double, _ fondo: RGB) -> RGB {
        (alfa * colore.r + (1 - alfa) * fondo.r, alfa * colore.g + (1 - alfa) * fondo.g, alfa * colore.b + (1 - alfa) * fondo.b)
    }

    private func mescola(_ a: RGB, _ b: RGB, _ t: Double) -> RGB { sopra(b, t, a) }

    private func luminanza(_ c: RGB) -> Double {
        func lineare(_ v: Double) -> Double { let x = v / 255; return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4) }
        return 0.2126 * lineare(c.r) + 0.7152 * lineare(c.g) + 0.0722 * lineare(c.b)
    }

    private func contrasto(_ a: RGB, _ b: RGB) -> Double {
        let (x, y) = (luminanza(a), luminanza(b))
        return (max(x, y) + 0.05) / (min(x, y) + 0.05)
    }

    // Fondi del tema chiaro: bianco (schede), #F2F2F7 (fondi raggruppati), riempimento terziario (12% di #767680), alone di `Sfondo`
    // (28% del verde, o del verde mescolato al blu e al lime, sopra il grigio).
    private var fondiChiari: [(String, RGB)] {
        let grigio = rgb(0xF2F2F7), bianco = rgb(0xFFFFFF), riempimento = rgb(0x767680)
        let verde = rgb(0x526600), blu = rgb(0x007AFF), lime = rgb(0x86A800)
        return [
            ("bianco", bianco), ("grigio dei fondi", grigio),
            ("campo incassato su scheda", sopra(riempimento, 0.12, bianco)), ("campo incassato sul fondo", sopra(riempimento, 0.12, grigio)),
            ("alone verde", sopra(verde, 0.28, grigio)), ("alone freddo", sopra(mescola(verde, blu, 0.45), 0.28, grigio)),
            ("alone caldo", sopra(mescola(verde, lime, 0.3), 0.28, grigio)),
        ]
    }

    // Fondi del tema scuro: nero, #1C1C1E (schede), riempimento terziario (24%), alone (34% del verde acceso).
    private var fondiScuri: [(String, RGB)] {
        let nero = rgb(0x000000), scheda = rgb(0x1C1C1E), riempimento = rgb(0x767680)
        let verde = rgb(0x3DDC97), blu = rgb(0x0A84FF), lime = rgb(0xD4F34A)
        return [
            ("nero", nero), ("scheda", scheda), ("campo incassato", sopra(riempimento, 0.24, scheda)),
            ("alone verde", sopra(verde, 0.34, nero)), ("alone freddo", sopra(mescola(verde, blu, 0.45), 0.34, nero)),
            ("alone caldo", sopra(mescola(verde, lime, 0.3), 0.34, nero)),
        ]
    }

    func testGrigioSecondarioChiaroAlmeno45SuOgniFondo() {
        for (nome, fondo) in fondiChiari {
            XCTAssertGreaterThanOrEqual(contrasto(rgb(Tema.secondarioChiaro), fondo), 4.5, "tema chiaro, fondo: \(nome)")
        }
    }

    func testGrigioSecondarioScuroAlmeno45SuOgniFondo() {
        for (nome, fondo) in fondiScuri {
            XCTAssertGreaterThanOrEqual(contrasto(rgb(Tema.secondarioScuro), fondo), 4.5, "tema scuro, fondo: \(nome)")
        }
    }

    func testIlGrigioDiSistemaNonBastava() {
        // Documenta perché non si usa più `.secondary`: 60% di #3C3C43 sul grigio dei fondi.
        let grigio = rgb(0xF2F2F7)
        XCTAssertLessThan(contrasto(sopra(rgb(0x3C3C43), 0.6, grigio), grigio), 4.5)
    }

    func testNumeriSuiDistintiviColoratiAlmeno45() {
        // Distintivo dell'indice sull'avatar e pallini dei voti: bianco sui colori semantici del chiaro, nero su quelli dello scuro.
        for c: UInt32 in [0x526600, 0x9C5400, 0xB3261E, Tema.secondarioChiaro] {
            XCTAssertGreaterThanOrEqual(contrasto(rgb(0xFFFFFF), rgb(c)), 4.5, String(c, radix: 16))
        }
        for c: UInt32 in [0x3DDC97, 0xFFB04A, 0xFF6B5E, Tema.secondarioScuro] {
            XCTAssertGreaterThanOrEqual(contrasto(rgb(0x000000), rgb(c)), 4.5, String(c, radix: 16))
        }
    }
}
