import XCTest
@testable import Schieraxi

/// La prova di connessione: un 401 è «raggiunto», e ogni altro caso ha il suo esito chiaro.
final class ProvaConnessioneTests: XCTestCase {
    private func sessione(_ gestore: @escaping (URLRequest) throws -> (Int, Data)) -> URLSession {
        let c = URLSessionConfiguration.ephemeral
        c.protocolClasses = [ProtocolloFinto.self]
        ProtocolloFinto.gestore = { r in
            let (codice, dati) = try gestore(r)
            return (HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: nil) ?? HTTPURLResponse(), dati)
        }
        return URLSession(configuration: c)
    }

    override func tearDown() {
        ProtocolloFinto.gestore = nil
        super.tearDown()
    }

    private let stato = Data(#"{"stagione": "2026-27", "versione": "1.41", "mia_squadra": "Schiera FC", "prossima_giornata": 10}"#.utf8)

    func test200ConLoStatoDiSchieraxiERaggiunto() async {
        let s = sessione { _ in (200, self.stato) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .raggiunto(versione: "1.41", squadra: "Schiera FC"))
        XCTAssertTrue(e.raggiunto)
        XCTAssertTrue(e.dettaglio.contains("1.41"))
    }

    func test401ERaggiuntoEChiedeAccesso() async {
        let s = sessione { _ in (401, Data(#"{"detail": "Accesso richiesto", "multiutente": true}"#.utf8)) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid:8443", sessione: s)
        XCTAssertEqual(e, .chiedeAccesso)
        XCTAssertTrue(e.raggiunto, "con gli account accesi il server risponde 401: è un successo")
    }

    func test401SenzaIlFormatoDiSchieraxiNonELoStessoServer() async {
        let s = sessione { _ in (401, Data("<html>Login</html>".utf8)) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .nonSchieraxi)
        XCTAssertFalse(e.raggiunto)
    }

    func test403() async {
        let s = sessione { _ in (403, Data("vietato".utf8)) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .rifiutato(403))
        XCTAssertFalse(e.raggiunto)
    }

    func test404NonEUnServerDiSchieraxi() async {
        let s = sessione { _ in (404, Data(#"{"detail": "Not Found"}"#.utf8)) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .nonSchieraxi)
    }

    func testUnaPaginaHTMLConCodice200NonEUnServerDiSchieraxi() async {
        let s = sessione { _ in (200, Data("<!doctype html><html><body>Benvenuto</body></html>".utf8)) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .nonSchieraxi)
    }

    func testUnJSONQualsiasiNonEUnServerDiSchieraxi() async {
        let s = sessione { _ in (200, Data(#"{"ciao": 1}"#.utf8)) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .nonSchieraxi)
    }

    func testUnErroreDelServer() async {
        let s = sessione { _ in (503, Data()) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .erroreServer(503))
    }

    func testTimeout() async {
        let s = sessione { _ in throw URLError(.timedOut) }
        let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
        XCTAssertEqual(e, .timeout)
    }

    func testCertificatoNonValido() async {
        for codice: URLError.Code in [.serverCertificateUntrusted, .secureConnectionFailed, .serverCertificateHasBadDate] {
            let s = sessione { _ in throw URLError(codice) }
            let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
            XCTAssertEqual(e, .certificato, "\(codice)")
        }
    }

    func testServerSpentoOSenzaRete() async {
        for codice: URLError.Code in [.cannotFindHost, .cannotConnectToHost, .notConnectedToInternet, .networkConnectionLost] {
            let s = sessione { _ in throw URLError(codice) }
            let e = await ProvaConnessione.prova("https://prova-connessione.invalid", sessione: s)
            XCTAssertEqual(e, .nonRaggiungibile, "\(codice)")
        }
    }

    func testIndirizziNonAmmessiNonFannoNessunaRichiesta() async {
        let chiamate = Scatola<Int>()
        chiamate.valore = 0
        let s = sessione { _ in chiamate.valore = (chiamate.valore ?? 0) + 1; return (200, self.stato) }
        for cattivo in ["", "   ", "http://server.example.invalid", "ftp://x.invalid", "https://utente:pw@x.invalid", "non un indirizzo"] {
            let e = await ProvaConnessione.prova(cattivo, sessione: s)
            XCTAssertEqual(e, .indirizzoNonValido, cattivo)
        }
        XCTAssertEqual(chiamate.valore, 0)
    }

    func testLaProvaNonManda5IlTokenENonToccaLaSessione() async {
        let visto = Scatola<String>()
        let s = sessione { r in visto.valore = r.value(forHTTPHeaderField: "Authorization") ?? "nessuno"; return (401, Data(#"{"detail": "x"}"#.utf8)) }
        let avvisi = Scatola<Int>()
        avvisi.valore = 0
        let osservatore = NotificationCenter.default.addObserver(forName: .accessoRichiesto, object: nil, queue: .main) { n in
            // Solo gli avvisi del nostro indirizzo: altri test possono lasciare 401 in coda.
            if (n.userInfo?["server"] as? String)?.contains("prova-connessione-token") == true { avvisi.valore = (avvisi.valore ?? 0) + 1 }
        }
        defer { NotificationCenter.default.removeObserver(osservatore) }
        _ = await ProvaConnessione.prova("https://prova-connessione-token.invalid", sessione: s)
        XCTAssertEqual(visto.valore, "nessuno", "il token non viaggia verso un indirizzo ancora da provare")
        try? await Task.sleep(nanoseconds: 300_000_000)
        XCTAssertEqual(avvisi.valore, 0, "un 401 della prova non manda l'app alla schermata di accesso")
    }

    func testConUnaSessioneValidaLaProvaUsaIlTokenEDiceConnesso() async {
        let archivio = MemoriaToken()
        archivio.salva("tok-sessione", server: "https://prova-sessione.invalid")
        let visto = Scatola<String>()
        let s = sessione { r in visto.valore = r.value(forHTTPHeaderField: "Authorization") ?? "nessuno"; return (200, self.stato) }
        let e = await ProvaConnessione.prova("https://prova-sessione.invalid/", sessione: s, archivio: archivio)
        XCTAssertEqual(visto.valore, "Bearer tok-sessione")
        XCTAssertEqual(e, .raggiunto(versione: "1.41", squadra: "Schiera FC"), "poi la vista lo mostra come «Connesso come …»")
        XCTAssertEqual(EsitoConnessione.connesso(utente: "utente").titolo, "Connesso come utente")
        XCTAssertTrue(EsitoConnessione.connesso(utente: "t").raggiunto)
    }

    func testConUnTokenScadutoIl401DiceSessioneScaduta() async {
        let archivio = MemoriaToken()
        archivio.salva("vecchio", server: "https://prova-sessione.invalid")
        let s = sessione { _ in (401, Data(#"{"detail": "Accesso richiesto"}"#.utf8)) }
        let e = await ProvaConnessione.prova("https://prova-sessione.invalid", sessione: s, archivio: archivio)
        XCTAssertEqual(e, .sessioneScaduta)
        XCTAssertTrue(e.raggiunto)
        XCTAssertFalse(e.dettaglio.contains("schermata di accesso"), "non si dice di accedere dalla schermata di accesso a chi ha una sessione")
    }

    func testIlTokenDiUnAltroIndirizzoNonViaggia() async {
        let archivio = MemoriaToken()
        archivio.salva("tok", server: "https://un-altro.invalid")
        let visto = Scatola<String>()
        let s = sessione { r in visto.valore = r.value(forHTTPHeaderField: "Authorization") ?? "nessuno"; return (401, Data(#"{"detail": "x"}"#.utf8)) }
        let e = await ProvaConnessione.prova("https://prova-nuovo.invalid", sessione: s, archivio: archivio)
        XCTAssertEqual(visto.valore, "nessuno")
        XCTAssertEqual(e, .chiedeAccesso)
    }

    func testPulisciGliIndirizzi() {
        XCTAssertEqual(ProvaConnessione.pulisci("  https://server.example.invalid:8443/ "), "https://server.example.invalid:8443")
        XCTAssertEqual(ProvaConnessione.pulisci("https://server.example.invalid///"), "https://server.example.invalid")
        XCTAssertNil(ProvaConnessione.pulisci("server.example.invalid"))
        XCTAssertEqual(ProvaConnessione.pulisci("http://localhost:8000"), "http://localhost:8000")
    }

    func testOgniEsitoHaTestiEIcona() {
        let tutti: [EsitoConnessione] = [.raggiunto(versione: nil, squadra: nil), .chiedeAccesso, .rifiutato(403), .nonSchieraxi, .nonRaggiungibile,
                                         .certificato, .timeout, .erroreServer(500), .indirizzoNonValido]
        for e in tutti {
            XCTAssertFalse(e.titolo.isEmpty)
            XCTAssertFalse(e.dettaglio.isEmpty)
            XCTAssertFalse(e.icona.isEmpty)
        }
        XCTAssertEqual(tutti.filter(\.raggiunto).count, 2)
    }
}

/// L'indirizzo del server non sta dentro l'app: si scrive al primo avvio e resta sul telefono.
final class IndirizzoNonNellApp: XCTestCase {
    private var prima: String?

    override func setUp() {
        super.setUp()
        prima = UserDefaults.standard.string(forKey: "indirizzo")
    }

    override func tearDown() {
        if let prima { UserDefaults.standard.set(prima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
        super.tearDown()
    }

    func testSenzaIndirizzoSalvatoSiUsaIlServerPubblico() {
        UserDefaults.standard.removeObject(forKey: "indirizzo")
        XCTAssertEqual(Config.indirizzoPredefinito, "https://app.schieraxi.it")
        XCTAssertFalse(IndirizzoServer.manca, "l'indirizzo non si chiede più all'utente")
        XCTAssertEqual(IndirizzoServer.attuale, "https://app.schieraxi.it")
        UserDefaults.standard.set("   ", forKey: "indirizzo")
        XCTAssertEqual(IndirizzoServer.attuale, "https://app.schieraxi.it")
        UserDefaults.standard.set("http://non-valido.invalid", forKey: "indirizzo")
        XCTAssertEqual(IndirizzoServer.attuale, "https://app.schieraxi.it", "un indirizzo non ammesso vale come mancante")
    }

    func testUnIndirizzoGiaSalvatoSiMantieneDopoLAggiornamento() {
        // chi aveva già scritto l'indirizzo (UserDefaults «indirizzo», la stessa chiave di sempre) non deve rifarlo
        UserDefaults.standard.set("https://gia-salvato.invalid:8443/", forKey: "indirizzo")
        XCTAssertFalse(IndirizzoServer.manca)
        XCTAssertEqual(IndirizzoServer.attuale, "https://gia-salvato.invalid:8443")
    }

    func testNelleInfoDellAppNonCeNessunIndirizzo() {
        for chiave in ["FantaHost", "FantaPort"] {
            XCTAssertNil(Bundle.main.object(forInfoDictionaryKey: chiave), "\(chiave) non deve stare nell'Info.plist (l'IPA è pubblico)")
        }
    }
}

/// La data delle versioni: con secondi se il server la manda con l'ora, solo il giorno se manda solo la data.
final class DataVersioneTests: XCTestCase {
    func testConOraESecondi() {
        XCTAssertEqual(Quando.dataVersione("2026-10-30T14:05:09"), "30 ott 2026, 14:05:09")
        XCTAssertEqual(Quando.dataVersione("2026-10-30 14:05:09"), "30 ott 2026, 14:05:09", "anche con lo spazio")
        XCTAssertEqual(Quando.dataVersione("2026-12-01T00:00:00"), "1 dic 2026, 00:00:00")
    }

    func testSoloData() {
        XCTAssertEqual(Quando.dataVersione("2026-10-30"), "30 ott 2026")
    }

    func testTestiStraniRestanoCosiCome() {
        XCTAssertEqual(Quando.dataVersione("ieri"), "ieri")
        XCTAssertEqual(Quando.dataVersione(nil), "")
        XCTAssertEqual(Quando.dataVersione(""), "")
        XCTAssertEqual(Quando.dataVersione("2026-13-45"), "2026-13-45")
    }

    func testIlFusoEQuelloItaliano() {
        // il testo è già ora italiana: si scrive uguale, anche in estate (ora legale)
        XCTAssertEqual(Quando.dataVersione("2026-07-15T23:59:59"), "15 lug 2026, 23:59:59")
    }
}
