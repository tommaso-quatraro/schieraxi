import XCTest
@testable import Schieraxi

/// Le frasi del widget «Attesi e fatti» con i plurali giusti.
final class WidgetFrasiTests: XCTestCase {
    func testDentroLaFascia() {
        XCTAssertEqual(RiassuntoWidget.fraseDentro(dentro: 1, su: 3), "Dentro la fascia prevista in 1 giornata su 3.")
        XCTAssertEqual(RiassuntoWidget.fraseDentro(dentro: 3, su: 5), "Dentro la fascia prevista in 3 giornate su 5.")
        XCTAssertEqual(RiassuntoWidget.fraseDentro(dentro: 0, su: 1), "Dentro la fascia prevista in 0 giornate su 1.")
    }

    func testMedia() {
        XCTAssertEqual(RiassuntoWidget.fraseMedia(1.5, giornate: 1), "In media +1,5 punti sul previsto nell'ultima giornata.")
        XCTAssertTrue(RiassuntoWidget.fraseMedia(-0.2, giornate: 5).hasSuffix("nelle ultime 5 giornate."))
    }
}
