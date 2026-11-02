import XCTest
@testable import Schieraxi

/// I test non devono MAI raggiungere il server vero (i Mac di GitHub lo tempestavano di richieste).
final class NienteReteVeraTests: XCTestCase {
    func testLAppSaDiFareDaContenitoreDeiTest() {
        XCTAssertTrue(Ambiente.ospiteDeiTest, "XCTest avvia l'app con XCTestConfigurationFilePath: l'app deve accorgersene")
    }

    func testIlClientConLaSessioneDiSistemaNonParte() async {
        let server = ServerHTTP(archivioToken: MemoriaToken())
        do {
            _ = try await server.grezzo("/api/stato")
            XCTFail("nei test una richiesta con la sessione di sistema deve fermarsi prima di partire")
        } catch ErroreApi.rete(let motivo) {
            XCTAssertTrue(motivo.contains("vietata"))
        } catch {
            XCTFail("errore inatteso: \(error)")
        }
    }
}
