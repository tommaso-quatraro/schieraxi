import XCTest
import UniformTypeIdentifiers
@testable import Schieraxi

/// Importazione delle rose da Excel, CSV e testo: quali file si ammettono, come si preparano per il server, cosa succede davvero all'invio.
final class FileRoseTests: XCTestCase {
    private let zip = Data([0x50, 0x4B, 0x03, 0x04, 0x14, 0x00])
    private let csv = Data("Squadra;Ruolo;Giocatore\nA;P;Sorvani\n".utf8)

    // MARK: tipi del selettore

    func testIlSelettoreAmmetteCsvTsvTestoEExcel() {
        let tipi = FileRose.tipiAmmessi
        for atteso in [UTType.spreadsheet, .commaSeparatedText, .tabSeparatedText, .plainText, .text, .data] {
            XCTAssertTrue(tipi.contains(atteso), "manca \(atteso.identifier)")
        }
        for estensione in ["xlsx", "csv", "tsv", "txt", "xls"] {
            let tipo = UTType(filenameExtension: estensione)
            XCTAssertNotNil(tipo, estensione)
            if let tipo { XCTAssertTrue(tipi.contains(tipo), "manca .\(estensione)") }
        }
        XCTAssertEqual(Set(tipi.map(\.identifier)).count, tipi.count, "nessun tipo ripetuto")
    }

    func testUnCsvSiRiconosceComeTestoSeparato() throws {
        let csvTipo = try XCTUnwrap(UTType(filenameExtension: "csv"))
        XCTAssertTrue(csvTipo.conforms(to: .commaSeparatedText))
        XCTAssertTrue(FileRose.tipiAmmessi.contains { csvTipo.conforms(to: $0) }, "il CSV non deve risultare non selezionabile")
    }

    @MainActor
    func testIlViewModelUsaGliStessiTipi() {
        let vm = ImportaExcelViewModel(server: ServerDiProva.chePrecipita())
        XCTAssertEqual(vm.tipiAmmessi, FileRose.tipiAmmessi)
    }

    // MARK: preparazione del file

    private func prepara(_ nome: String, _ dati: Data) -> FileRose.Preparato? {
        if case .success(let p) = FileRose.prepara(nome: nome, dati: dati) { return p }
        return nil
    }

    private func errore(_ nome: String, _ dati: Data) -> FileRose.Errore? {
        if case .failure(let e) = FileRose.prepara(nome: nome, dati: dati) { return e }
        return nil
    }

    func testCsvETestoSiMandanoConNomeETipoGiusti() {
        XCTAssertEqual(prepara("rose.csv", csv), FileRose.Preparato(nome: "rose.csv", tipo: "text/csv"))
        XCTAssertEqual(prepara("ROSE.CSV", csv), FileRose.Preparato(nome: "ROSE.csv", tipo: "text/csv"), "l'estensione in maiuscolo va bene")
        XCTAssertEqual(prepara("rose.txt", csv), FileRose.Preparato(nome: "rose.txt", tipo: "text/plain"))
        XCTAssertEqual(prepara("rose.tsv", Data("A\tP\tSorvani".utf8)), FileRose.Preparato(nome: "rose.csv", tipo: "text/csv"),
                       "il server legge CSV e testo: un .tsv va come .csv (il separatore lo riconosce da solo)")
        XCTAssertEqual(prepara("rose.text", csv), FileRose.Preparato(nome: "rose.txt", tipo: "text/plain"))
    }

    func testExcelServeUnoZipVero() {
        XCTAssertEqual(prepara("rose.xlsx", zip), FileRose.Preparato(nome: "rose.xlsx", tipo: FileRose.tipoExcel))
        XCTAssertEqual(prepara("rose.xlsm", zip)?.nome, "rose.xlsm")
        XCTAssertEqual(errore("rose.xlsx", csv), .excelRovinato, "un .xlsx che non è uno zip non si manda")
    }

    func testIlVecchioXlsHaUnMessaggioSuo() {
        XCTAssertEqual(errore("rose.xls", Data([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1])), .vecchioExcel)
        XCTAssertTrue(FileRose.Errore.vecchioExcel.localizedDescription.contains(".xlsx"))
        XCTAssertEqual(prepara("rose.xls", zip)?.nome, "rose.xlsx", "un .xls che in realtà è uno zip si manda come .xlsx")
    }

    func testFileSenzaEstensioneDalMenuCondividi() {
        XCTAssertEqual(prepara("rose", zip), FileRose.Preparato(nome: "rose.xlsx", tipo: FileRose.tipoExcel))
        XCTAssertEqual(prepara("rose", csv), FileRose.Preparato(nome: "rose.txt", tipo: "text/plain"))
        XCTAssertEqual(errore("rose", Data([0, 1, 2, 3])), .formato)
    }

    func testFormatiNonAmmessiDannoIlMessaggioGiusto() {
        for nome in ["rose.pdf", "rose.png", "rose.docx", "rose.exe", "rose.json"] {
            XCTAssertEqual(errore(nome, csv), .formato, nome)
        }
        XCTAssertEqual(FileRose.Errore.formato.localizedDescription, "Usa un Excel (.xlsx), un CSV o un file di testo.")
        XCTAssertEqual(FileRose.messaggioFormato, "Usa un Excel (.xlsx), un CSV o un file di testo.")
    }

    func testFileVuotiTroppoGrandiEBinari() {
        XCTAssertEqual(errore("rose.csv", Data()), .vuoto)
        XCTAssertEqual(errore("rose.csv", Data(count: FileRose.massimoByte + 1)), .troppoGrande)
        XCTAssertEqual(errore("rose.csv", Data([0x41, 0x00, 0x42])), .nonETesto, "un file con byte nulli non è un testo")
        XCTAssertNil(errore("rose.csv", Data("Giocatore;Costo\nÇalvaroğlu;18\n".utf8)), "accenti e simboli sono testo normale")
    }

    func testIlNomeNonPuoRompereLIntestazione() {
        let nome = prepara("ro\"se\r\n../x\\y.csv", csv)?.nome ?? ""
        XCTAssertFalse(nome.contains("\""))
        XCTAssertFalse(nome.contains("\n"))
        XCTAssertFalse(nome.contains("/"))
        XCTAssertFalse(nome.contains("\\"))
        XCTAssertTrue(nome.hasSuffix(".csv"))
        XCTAssertEqual(FileRose.pulisciNome(String(repeating: "a", count: 300)).count, 80)
        XCTAssertEqual(FileRose.pulisciNome("\"\"\n"), "rose")
    }
}

/// Dal selettore fino al server.
@MainActor
final class ImportaFileTests: XCTestCase {
    private let esito = Data(#"{"squadre_importate": ["A"], "totale_squadre": 1, "avvisi": [], "riepilogo": "Fatto"}"#.utf8)
    private var cartella: URL!

    override func setUpWithError() throws {
        cartella = FileManager.default.temporaryDirectory.appendingPathComponent("rose-test-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
    }

    override func tearDown() {
        try? FileManager.default.removeItem(at: cartella)
        super.tearDown()
    }

    private func file(_ nome: String, _ dati: Data) throws -> URL {
        let url = cartella.appendingPathComponent(nome)
        try dati.write(to: url)
        return url
    }

    private func server() -> ServerDiProva {
        let risposta = esito
        return ServerDiProva { metodo, _, _ in metodo == "UPLOAD" ? risposta : Data("{}".utf8) }
    }

    func testUnCsvSiImportaConNomeETipoGiusti() async throws {
        let s = server()
        let vm = ImportaExcelViewModel(server: s)
        await vm.importa(.success([try file("rose.csv", Data("Squadra;Ruolo;Giocatore\nA;P;Sorvani\n".utf8))]))
        XCTAssertNil(vm.errore)
        // prima l'anteprima (non salva niente), poi «Conferma e salva» con lo stesso file
        XCTAssertNotNil(vm.anteprima)
        XCTAssertNil(vm.esito)
        XCTAssertEqual(s.quante("UPLOAD /api/rose/anteprima/file?sostituisci_tutto=false"), 1)
        XCTAssertEqual(s.quante("UPLOAD /api/rose/file"), 0, "l'anteprima non salva")
        await vm.conferma()
        XCTAssertNil(vm.errore)
        XCTAssertEqual(vm.esito?.riepilogo, "Fatto")
        XCTAssertEqual(s.fileCaricati.count, 2)
        XCTAssertEqual(s.fileCaricati.map(\.nome), ["rose.csv", "rose.csv"])
        XCTAssertEqual(s.fileCaricati.map(\.tipo), ["text/csv", "text/csv"])
        XCTAssertEqual(s.quante("UPLOAD /api/rose/file?sostituisci_tutto=false"), 1)
    }

    func testTsvETestoPassanoEIlTipoTornaGiusto() async throws {
        let s = server()
        let vm = ImportaExcelViewModel(server: s)
        await vm.importa(.success([try file("rose.tsv", Data("A\tP\tSorvani\n".utf8))]))
        await vm.importa(.success([try file("rose.txt", Data("A P Sorvani\n".utf8))]))
        XCTAssertEqual(s.fileCaricati.map(\.nome), ["rose.csv", "rose.txt"])
        XCTAssertEqual(s.fileCaricati.map(\.tipo), ["text/csv", "text/plain"])
    }

    func testUnFileDiUnTipoNonAmmessoNonSiInviaEDiceCosaFare() async throws {
        let s = server()
        let vm = ImportaExcelViewModel(server: s)
        await vm.importa(.success([try file("rose.pdf", Data("%PDF-1.4".utf8))]))
        XCTAssertEqual(vm.errore, "Usa un Excel (.xlsx), un CSV o un file di testo.")
        XCTAssertNil(vm.esito)
        XCTAssertEqual(s.fileCaricati.count, 0, "non parte niente verso il server")
    }

    func testIlVecchioXlsEUnXlsxFinto() async throws {
        let s = server()
        let vm = ImportaExcelViewModel(server: s)
        await vm.importa(.success([try file("rose.xls", Data([0xD0, 0xCF, 0x11, 0xE0, 0, 0, 0]))]))
        XCTAssertTrue(vm.errore?.contains("(.xls)") == true, vm.errore ?? "")
        await vm.importa(.success([try file("falso.xlsx", Data("non sono uno zip".utf8))]))
        XCTAssertTrue(vm.errore?.contains("vero Excel") == true, vm.errore ?? "")
        XCTAssertEqual(s.fileCaricati.count, 0)
    }

    func testUnFileTroppoGrandeNonSiLegge() async throws {
        let s = server()
        let vm = ImportaExcelViewModel(server: s)
        await vm.importa(.success([try file("grande.csv", Data(count: FileRose.massimoByte + 10))]))
        XCTAssertTrue(vm.errore?.contains("troppo grande") == true, vm.errore ?? "")
        XCTAssertEqual(s.fileCaricati.count, 0)
    }

    func testUnFileCheNonEsisteDaUnMessaggioNonUnCrash() async {
        let vm = ImportaExcelViewModel(server: server())
        await vm.importa(.success([cartella.appendingPathComponent("non-c-e.csv")]))
        XCTAssertTrue(vm.errore?.contains("Non riesco a leggere") == true, vm.errore ?? "")
        XCTAssertFalse(vm.inCorso)
    }

    func testIlServerCheRifiutaDaUnMessaggioChiaro() async throws {
        let s = ServerDiProva { _, _, _ in throw ErroreApi.server("Formato non supportato: usa Excel (.xlsx), CSV o testo") }
        let vm = ImportaExcelViewModel(server: s)
        await vm.importa(.success([try file("rose.csv", Data("A;P;S".utf8))]))
        XCTAssertEqual(vm.errore, "Formato non supportato: usa Excel (.xlsx), CSV o testo")
        XCTAssertFalse(vm.inCorso)
    }

    func testLaLetturaSicuraRispettaIlTetto() async throws {
        let piccolo = try file("p.csv", Data("abc".utf8))
        let dati = try await LetturaFile.leggi(piccolo)
        XCTAssertEqual(String(decoding: dati, as: UTF8.self), "abc")
        do {
            _ = try await LetturaFile.leggi(piccolo, massimo: 2)
            XCTFail("doveva rifiutare")
        } catch {
            XCTAssertEqual(error as? FileRose.Errore, .troppoGrande)
        }
    }

    func testUnFileArrivatoDaUnaltraAppSiAccettaSoloSeELocale() throws {
        let nav = Navigazione()
        nav.apriFile(try XCTUnwrap(URL(string: "https://example.invalid/rose.csv")))
        XCTAssertNil(nav.fileDaImportare, "un indirizzo web non è un file")
        let locale = URL(fileURLWithPath: "/tmp/rose.csv")
        nav.apriFile(locale)
        XCTAssertEqual(nav.fileDaImportare, locale)
    }
}

/// L'invio multipart: nome con estensione e Content-Type giusti.
final class InvioFileTests: XCTestCase {
    func testIlMultipartPortaNomeETipoDelFile() async throws {
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        let server = ServerHTTP(sessione: URLSession(configuration: configurazione), archivioToken: MemoriaToken())
        let prima = UserDefaults.standard.string(forKey: "indirizzo")
        UserDefaults.standard.set("https://prova-invio.invalid", forKey: "indirizzo")
        defer { if let prima { UserDefaults.standard.set(prima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") } }
        ProtocolloFinto.gestore = { r in
            (HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: 200, httpVersion: nil, headerFields: nil) ?? HTTPURLResponse(), Data("{}".utf8))
        }
        defer { ProtocolloFinto.gestore = nil }

        _ = try await server.carica("/api/rose/file", nome: "rose.csv", dati: Data("A;P;S".utf8), tipo: "text/csv")
        var corpo = String(decoding: try XCTUnwrap(ProtocolloFinto.ultimoCorpo), as: UTF8.self)
        XCTAssertTrue(corpo.contains("name=\"file\"; filename=\"rose.csv\""), corpo)
        XCTAssertTrue(corpo.contains("Content-Type: text/csv\r\n\r\nA;P;S"), "il tipo giusto e subito dopo i dati del file")

        // un tipo con un a capo non può aggiungere intestazioni
        _ = try await server.carica("/api/rose/file", nome: "x.txt", dati: Data("x".utf8), tipo: "text/plain\r\nX-Falso: 1")
        corpo = String(decoding: try XCTUnwrap(ProtocolloFinto.ultimoCorpo), as: UTF8.self)
        XCTAssertFalse(corpo.contains("\r\nX-Falso"), corpo)

        // senza un tipo preciso (immagini) resta quello generico
        _ = try await server.carica("/api/squadre/immagine", nome: "a.jpg", dati: Data([1, 2, 3]))
        corpo = String(decoding: try XCTUnwrap(ProtocolloFinto.ultimoCorpo), as: UTF8.self)
        XCTAssertTrue(corpo.contains("Content-Type: application/octet-stream"))
    }
}
