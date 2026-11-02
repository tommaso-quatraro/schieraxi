import XCTest
@testable import Schieraxi

/// La «dieta delle funzioni»: cosa dice il server, cosa nasconde l'app, il 404 con il campo `funzione`.
final class FunzioniTests: XCTestCase {
    func testUnaChiaveCheMancaValeAcceso() throws {
        let r: RispostaFunzioni = try Decodifica.decodifica(Data(#"{"funzioni": {"live": false, "stili_ridotti": true}, "mostra_tutte": false}"#.utf8), snake: false)
        let s = r.stato
        XCTAssertFalse(s.acceso("live"))
        XCTAssertTrue(s.acceso("stili_ridotti"))
        XCTAssertTrue(s.acceso("una_funzione_nuova"), "una chiave sconosciuta vale acceso")
        XCTAssertFalse(s.mostraTutte)
    }

    func testRispostaVuotaOStranaNonRompe() throws {
        let vuota: RispostaFunzioni = try Decodifica.decodifica(Data("{}".utf8), snake: false)
        XCTAssertEqual(vuota.stato, StatoFunzioni.tutteAccese)
        let strana: RispostaFunzioni = try Decodifica.decodifica(Data(#"{"funzioni": {"live": false}, "campo_nuovo": 3}"#.utf8), snake: false)
        XCTAssertFalse(strana.stato.acceso("live"))
    }

    func testMostraTutteVinceSulleScelte() {
        let s = StatoFunzioni(scelte: ["live": false, "asta": false], mostraTutte: true)
        XCTAssertTrue(s.acceso("live"))
        XCTAssertTrue(s.acceso("asta"))
    }

    func testUnaFunzioneSpentaDaUn404SiNasconde() {
        let s = StatoFunzioni.tutteAccese.spenta("asta")
        XCTAssertFalse(s.acceso("asta"))
        XCTAssertTrue(s.acceso("live"))
    }

    func testIlMessaggioDelServerSiRiconosce() {
        XCTAssertTrue("«Asta e riparazione» non è disponibile in questa versione dell'app. Si può rivedere da Impostazioni.".dicePerFunzioneSpenta)
        XCTAssertFalse("Nessuna rosa importata".dicePerFunzioneSpenta)
        XCTAssertFalse("Non riesco a raggiungere il server.".dicePerFunzioneSpenta)
    }

    func testLeVecchieSezioniPortanoNelleNuove() {
        XCTAssertEqual(Sezione.da(nome: "Mercato"), .squadra)
        XCTAssertEqual(Sezione.da(nome: "scambi"), .altro)
        XCTAssertEqual(Sezione.da(nome: "lega"), .altro)
        XCTAssertEqual(Sezione.da(nome: "squadra"), .squadra)
        XCTAssertNil(Sezione.da(nome: "boh"))
        XCTAssertNil(Sezione.da(nome: nil))
        XCTAssertEqual(Sezione.allCases.map(\.titolo), ["Oggi", "Formazione", "Squadra", "Altro"])
    }

    func testOgniPaginaStaNellaSuaScheda() {
        XCTAssertEqual(PaginaLega.importa.sezione, .squadra)
        XCTAssertEqual(PaginaLega.rosa("X").sezione, .squadra)
        XCTAssertEqual(PaginaLega.cambi.sezione, .squadra)
        XCTAssertEqual(PaginaLega.seguiti.sezione, .squadra)
        XCTAssertEqual(PaginaLega.scambi.sezione, .altro)
        XCTAssertEqual(PaginaLega.regole.sezione, .altro)
        XCTAssertEqual(PaginaLega.diario.sezione, .altro)
    }

    @MainActor
    func testApriUnaPaginaScegliLaSchedaGiusta() {
        let lega = LegaViewModel(server: FinteServer(risposte: [:]))
        XCTAssertEqual(lega.apri([.squadre, .rosa("X")]), .squadra)
        XCTAssertEqual(lega.percorsoSquadra, [.squadre, .rosa("X")])
        XCTAssertEqual(lega.apri([.regole]), .altro)
        XCTAssertEqual(lega.percorso, [.regole])
    }

    @MainActor
    func testArchivioLeggeEImpostaMostraTutte() async {
        let server = FinteServer(risposte: ["/api/funzioni": #"{"funzioni": {"live": false}, "mostra_tutte": false}"#])
        let archivio = ArchivioFunzioni(server: server)
        XCTAssertTrue(archivio.stato.acceso("live"), "all'inizio è tutto acceso")
        await archivio.carica()
        XCTAssertFalse(archivio.stato.acceso("live"))
    }

    @MainActor
    func testMostraTutteSiSalvaEdAccendeTutto() async {
        // il server finto risponde allo stesso modo a GET e PUT: qui è la risposta al PUT
        let archivio = ArchivioFunzioni(server: FinteServer(risposte: ["/api/funzioni": #"{"funzioni": {"live": true}, "mostra_tutte": true}"#]))
        await archivio.impostaMostraTutte(true)
        XCTAssertTrue(archivio.stato.mostraTutte)
        XCTAssertTrue(archivio.stato.acceso("live"))
        XCTAssertNil(archivio.errore)
    }

    @MainActor
    func testSeIlServerNonRispondeSiVedeTutto() async {
        let archivio = ArchivioFunzioni(server: FinteServer(risposte: [:]))
        await archivio.carica()
        XCTAssertEqual(archivio.stato, StatoFunzioni.tutteAccese)
    }
}

final class FunzioneSpentaReteTests: XCTestCase {
    private var indirizzoPrima: String?

    override func setUp() {
        super.setUp()
        indirizzoPrima = UserDefaults.standard.string(forKey: "indirizzo")
        UserDefaults.standard.set("https://prova.invalid:8443", forKey: "indirizzo")
    }

    override func tearDown() {
        if let indirizzoPrima { UserDefaults.standard.set(indirizzoPrima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
        ProtocolloFinto.gestore = nil
        super.tearDown()
    }

    private func server() -> ServerHTTP {
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        return ServerHTTP(sessione: URLSession(configuration: configurazione))
    }

    private func risposta(_ r: URLRequest, _ codice: Int) -> HTTPURLResponse {
        HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: nil) ?? HTTPURLResponse()
    }

    func testUn404ConIlCampoFunzioneEUnaFunzioneSpenta() async {
        ProtocolloFinto.gestore = { [unowned self] r in
            (risposta(r, 404), Data(#"{"detail": "«Asta» non è disponibile in questa versione dell'app.", "funzione": "asta"}"#.utf8))
        }
        do {
            _ = try await server().grezzo("/api/asta")
            XCTFail("doveva lanciare")
        } catch let e as ErroreApi {
            guard case .funzioneSpenta(let funzione, let messaggio) = e else { return XCTFail("errore sbagliato: \(e)") }
            XCTAssertEqual(funzione, "asta")
            XCTAssertTrue(messaggio.dicePerFunzioneSpenta)
            XCTAssertEqual(e.errorDescription, messaggio, "senza il prefisso «Il server dice»")
        } catch {
            XCTFail("errore inatteso: \(error)")
        }
    }

    func testUn404SenzaCampoRestaUnErroreNormale() async {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 404), Data(#"{"detail": "Giocatore non trovato"}"#.utf8)) }
        do {
            _ = try await server().grezzo("/api/giocatore/1")
            XCTFail("doveva lanciare")
        } catch let e as ErroreApi {
            guard case .server(let messaggio) = e else { return XCTFail("errore sbagliato: \(e)") }
            XCTAssertEqual(messaggio, "Giocatore non trovato")
        } catch {
            XCTFail("errore inatteso: \(error)")
        }
    }

    func testSenzaFrasePrevistaSiUsaIlNostroTesto() async {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 404), Data(#"{"detail": "Spenta", "funzione": "live"}"#.utf8)) }
        do {
            _ = try await server().grezzo("/api/live")
            XCTFail("doveva lanciare")
        } catch let e as ErroreApi {
            XCTAssertTrue((e.errorDescription ?? "").dicePerFunzioneSpenta, "la schermata deve riconoscerla")
        } catch {
            XCTFail("errore inatteso: \(error)")
        }
    }
}
