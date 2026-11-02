import XCTest
@testable import Schieraxi

final class FormatoTests: XCTestCase {
    /// Il segno meno può essere «-» o «−» secondo il sistema: si confronta con un solo carattere.
    private func normalizza(_ t: String) -> String { t.replacingOccurrences(of: "\u{2212}", with: "-") }

    func testVirgolaDecimaleSempreInItaliano() {
        XCTAssertEqual(Formato.decimali(6.26), "6,3")
        XCTAssertEqual(Formato.decimali(6, cifre: 2), "6,00")
    }

    func testPuntiConValoreMancanteSiScriveTrattino() {
        XCTAssertEqual(Formato.punti(nil), "–", "come la web: un valore assente non è zero")
        XCTAssertEqual(Formato.punti(7.44), "7,4")
    }

    func testArrotondaComeLaWeb() {
        // toFixed della web: a metà si va lontano dallo zero, non al pari
        XCTAssertEqual(Formato.decimali(6.25), "6,3")
        XCTAssertEqual(Formato.decimali(0.5, cifre: 0), "1")
        XCTAssertEqual(normalizza(Formato.decimali(-6.25)), "-6,3")
        XCTAssertEqual(Formato.decimali(-0.04), "0,0", "niente «-0,0»")
        XCTAssertEqual(Formato.punti(6.25), "6,3")
        XCTAssertEqual(Formato.conSegno(1.25), "+1,3")
    }

    func testValoreAssenteONonFinitoSiScriveTrattino() {
        XCTAssertEqual(Formato.decimali(nil), "–")
        XCTAssertEqual(Formato.decimali(.nan), "–")
        XCTAssertEqual(Formato.decimali(.infinity, cifre: 2), "–")
        XCTAssertEqual(Formato.decimali(1e300).isEmpty, false, "numeri enormi: niente crash")
    }

    func testConSegno() {
        XCTAssertEqual(Formato.conSegno(2.5), "+2,5")
        XCTAssertEqual(normalizza(Formato.conSegno(-1.2)), "-1,2")
        XCTAssertEqual(Formato.conSegno(0), "+0,0")
        XCTAssertEqual(Formato.conSegno(3.456, cifre: 2), "+3,46")
    }

    func testPercento() {
        XCTAssertEqual(Formato.percento(0.456), 46)
        XCTAssertEqual(Formato.percento(1), 100)
        XCTAssertEqual(Formato.percento(nil), 0)
    }

    func testInteroNonVaMaiInCrash() {
        XCTAssertEqual(Formato.intero(3.9), 4, "si arrotonda come la web, non si tronca")
        XCTAssertEqual(Formato.intero(155.9), 156)
        XCTAssertEqual(Formato.intero(4.5), 5)
        XCTAssertEqual(Formato.intero(3.4), 3)
        XCTAssertEqual(Formato.intero(-2.5), -2, "come Math.round")
        XCTAssertEqual(Formato.intero(-4.6), -5)
        XCTAssertEqual(Formato.intero(nil), 0)
        XCTAssertEqual(Formato.intero(.nan), 0)
        XCTAssertEqual(Formato.intero(.infinity), 0)
        XCTAssertEqual(Formato.intero(1e20), 0)
    }

    func testDifficoltaAParole() {
        XCTAssertEqual(Formato.difficolta(1), "molto facile")
        XCTAssertEqual(Formato.difficolta(2), "facile")
        XCTAssertEqual(Formato.difficolta(nil), "difficoltà media")
        XCTAssertEqual(Formato.difficolta(4), "difficile")
        XCTAssertEqual(Formato.difficolta(5), "molto difficile")
        XCTAssertEqual(Formato.difficolta(0), "molto facile")
    }
}
