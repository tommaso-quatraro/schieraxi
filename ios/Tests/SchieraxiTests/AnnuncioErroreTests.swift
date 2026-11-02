import XCTest
@testable import Schieraxi

/// L'errore a schermo deve essere anche annunciato a voce (VoiceOver).
final class AnnuncioErroreTests: XCTestCase {
    func testLAnnuncioDiceCheQualcosaNonVaESpiegaPerche() {
        XCTAssertEqual(ErroreVista.annuncio("Server non raggiungibile."), "Qualcosa non va. Server non raggiungibile.")
        XCTAssertEqual(ErroreVista.annuncio("  Riprova tra 5 minuti.\n"), "Qualcosa non va. Riprova tra 5 minuti.")
    }

    func testSenzaMessaggioRestaUnaFraseSensata() {
        XCTAssertEqual(ErroreVista.annuncio("   "), "Qualcosa non va")
    }
}
