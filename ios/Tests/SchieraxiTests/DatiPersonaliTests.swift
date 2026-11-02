import Foundation
import XCTest
@testable import Schieraxi

/// «Scarica i tuoi dati»: la richiesta giusta, il nome del file, il file salvato così com'è e gli errori in parole semplici.
final class DatiPersonaliTests: XCTestCase {
    private var cartella: URL!

    override func setUpWithError() throws {
        cartella = FileManager.default.temporaryDirectory.appendingPathComponent("prova-dati-\(UUID().uuidString)", isDirectory: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: cartella)
    }

    private let fileFinto = Data(#"{"formato": "schieraxi-backup", "versione": 1, "creato": "2026-11-01T10:00:00", "file": {}, "account": {"nome_utente": "prova"}}"#.utf8)

    func testNomeFileConIlGiornoItaliano() {
        // 31/10 alle 23:30 UTC = 1/11 alle 00:30 in Italia (ora solare, +1)
        let tardi = Date(timeIntervalSince1970: 1_793_489_400)
        XCTAssertEqual(DatiPersonali.nomeFile(tardi), "schieraxi-i-miei-dati-2026-11-01.json")
        let estate = Date(timeIntervalSince1970: 1_783_000_000)   // 2/7/2026
        XCTAssertEqual(DatiPersonali.nomeFile(estate), "schieraxi-i-miei-dati-2026-07-02.json")
    }

    func testScaricaFaUnaSolaGetESalvaIlFileComE() async throws {
        let dati = fileFinto
        let server = ServerDiProva { _, _, _ in dati }
        let adesso = Date(timeIntervalSince1970: 1_793_489_400)
        let url = try await DatiPersonali.scarica(server: server, adesso: adesso, cartella: cartella)
        XCTAssertEqual(server.richieste, ["GET /api/backup"], "una sola richiesta, senza parametri")
        XCTAssertEqual(url.lastPathComponent, "schieraxi-i-miei-dati-2026-11-01.json")
        XCTAssertEqual(try Data(contentsOf: url), dati, "il file è quello del server, senza modifiche")
    }

    func testUnNuovoScaricamentoTogliQuelloDiPrima() async throws {
        let dati = fileFinto
        let server = ServerDiProva { _, _, _ in dati }
        let primo = try await DatiPersonali.scarica(server: server, adesso: Date(timeIntervalSince1970: 1_783_000_000), cartella: cartella)
        let secondo = try await DatiPersonali.scarica(server: server, adesso: Date(timeIntervalSince1970: 1_793_489_400), cartella: cartella)
        XCTAssertFalse(FileManager.default.fileExists(atPath: primo.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: secondo.path))
        DatiPersonali.pulisci(cartella: cartella)
        XCTAssertFalse(FileManager.default.fileExists(atPath: secondo.path))
    }

    func testUnaPaginaQualsiasiNonSiSalva() async {
        let server = ServerDiProva { _, _, _ in Data("<html>accedi al Wi-Fi</html>".utf8) }
        do {
            _ = try await DatiPersonali.scarica(server: server, cartella: cartella)
            XCTFail("doveva fallire")
        } catch {
            XCTAssertEqual(DatiPersonali.testoErrore(error), "Il server non ha mandato il file dei dati. Riprova tra poco.")
        }
        XCTAssertFalse(DatiPersonali.eValido(Data(#"{"formato": "altro", "file": {}}"#.utf8)))
        XCTAssertFalse(DatiPersonali.eValido(Data()))
        XCTAssertTrue(DatiPersonali.eValido(fileFinto))
    }

    func testErroriInParoleSemplici() async {
        let scaduto = ServerDiProva.chePrecipita(.accessoRichiesto("Accesso richiesto"))
        do {
            _ = try await DatiPersonali.scarica(server: scaduto, cartella: cartella)
            XCTFail("doveva fallire")
        } catch {
            XCTAssertEqual(DatiPersonali.testoErrore(error), "La sessione è scaduta: rientra nel tuo account e riprova.")
        }
        XCTAssertEqual(DatiPersonali.testoErrore(ErroreApi.rete("spento")), "Non riesco a collegarmi a SchieraXI. Controlla la connessione e riprova.")
        XCTAssertEqual(DatiPersonali.testoErrore(ErroreApi.timeout), "Non riesco a collegarmi a SchieraXI. Controlla la connessione e riprova.")
        XCTAssertFalse(FileManager.default.fileExists(atPath: cartella.appendingPathComponent(DatiPersonali.nomeCartella).path), "niente file se la richiesta fallisce")
    }
}
