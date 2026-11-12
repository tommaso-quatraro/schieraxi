import XCTest

/// Aiuti comuni dei test di interfaccia.
extension XCTestCase {
    /// Tocca `tocco` e aspetta `atteso`, un elemento che compare solo per effetto del tocco (la pagina d'arrivo, il riquadro
    /// della voce scelta). Sul simulatore carico di GitHub un tocco a volte non arriva all'app: l'app resta dov'era e un test che
    /// tocca una volta sola fallisce senza un difetto vero (#212: tocco su una voce di Altro e la sua pagina mai comparsa;
    /// prima i pulsanti delle schede di AccessoUITests, 1/11/2026). Si controlla l'effetto e, se manca, si ritocca: al massimo
    /// 3 tocchi, aspettando `secondi` dopo ognuno; dopo il primo si ritocca solo se `tocco` c'è ancora e si può toccare (se la
    /// pagina è già cambiata non si tocca altro). Se `atteso` non compare mai, il test fallisce con `messaggio`.
    /// `tap` serve solo al test che simula un tocco perso (`FumoUITests.testUnToccoPersoSiRitocca`).
    func tocca(_ tocco: XCUIElement, finchéCompare atteso: XCUIElement, _ messaggio: String, entro secondi: TimeInterval = 10,
               file: StaticString = #filePath, line: UInt = #line, tap: ((XCUIElement) -> Void)? = nil) {
        XCTAssertTrue(tocco.waitForExistence(timeout: 20), "manca l'elemento da toccare: \(messaggio)", file: file, line: line)
        var arrivato = false
        for tentativo in 0..<3 where !arrivato {
            if tentativo == 0 || (tocco.exists && tocco.isHittable) {
                if let tap { tap(tocco) } else { tocco.tap() }
            }
            arrivato = atteso.waitForExistence(timeout: secondi)
        }
        XCTAssertTrue(arrivato, messaggio, file: file, line: line)
    }
}
