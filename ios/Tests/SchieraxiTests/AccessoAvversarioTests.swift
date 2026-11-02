import XCTest
@testable import Schieraxi

// Test «avversari» dell'accesso: server ostili (risposte strane, HTML, token enormi), 401 a catena, doppi tocchi, cambio server, Keychain che
// non salva, uscita che cancella davvero. Tutto con server finti.

/// Un server il cui indirizzo si può cambiare (per provare il cambio di server con la sessione aperta).
final class ServerCambiabile: ServerClient, @unchecked Sendable {
    private let blocco = NSLock()
    private var corrente: String
    private let gestore: @Sendable (String, String) async throws -> Data
    private var registro: [String] = []

    init(indirizzo: String, gestore: @escaping @Sendable (String, String) async throws -> Data) {
        corrente = indirizzo
        self.gestore = gestore
    }

    var indirizzo: String {
        get { blocco.lock(); defer { blocco.unlock() }; return corrente }
        set { blocco.lock(); defer { blocco.unlock() }; corrente = newValue }
    }

    var richieste: [String] { blocco.lock(); defer { blocco.unlock() }; return registro }

    private func annota(_ voce: String) { blocco.lock(); defer { blocco.unlock() }; registro.append(voce) }

    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data {
        annota("\(metodo) \(indirizzo) \(percorso)")
        return try await gestore(metodo, percorso)
    }

    func carica(_ percorso: String, nome: String, dati: Data, tipo: String) async throws -> Data { try await richiesta("POST", percorso, corpo: nil) }
}

/// Un archivio di token che non riesce a salvare (Keychain pieno o rifiutato).
final class ArchivioChePerde: ArchivioToken, @unchecked Sendable {
    private let memoria = MemoriaToken()
    func leggi(server: String) -> String? { memoria.leggi(server: server) }
    @discardableResult func salva(_ token: String, server: String) -> Bool { memoria.salva(token, server: server); return false }
    func cancella(server: String) { memoria.cancella(server: server) }
}

final class ValidazioneAvversariaTests: XCTestCase {
    func testSpaziPrimaEDopoNonSiAccettano() {
        XCTAssertNotNil(RegoleAccount.problemaSpaziNome(" mister"))
        XCTAssertNotNil(RegoleAccount.problemaSpaziNome("mister\n"))
        XCTAssertNil(RegoleAccount.problemaSpaziNome("mister"))
        XCTAssertNotNil(RegoleAccount.problemaPassword(" Prova-Finta-Zero"))
        XCTAssertNotNil(RegoleAccount.problemaPassword("Prova-Finta-Zero "))
        XCTAssertNotNil(RegoleAccount.problemaPassword("Prova-Finta-Zero\n"))
        XCTAssertNil(RegoleAccount.problemaPassword("Tre Quarti Dieci"), "gli spazi in mezzo vanno bene")
    }

    func testNomiOstili() {
        for nome in ["../../etc", "a b c", "mister\u{0000}rossi", "<script>", "MISTER'--", "rossi;drop", "mi", "é-é-é", String(repeating: "a", count: 1000), "🙂🙂🙂"] {
            XCTAssertNotNil(RegoleAccount.problemaNome(nome), "«\(nome.prefix(20))» non è un nome valido")
        }
        XCTAssertNil(RegoleAccount.problemaNome("a1_.-"), "lettere, cifre, punto, trattino e trattino basso")
    }

    func testPasswordOstili() {
        XCTAssertNotNil(RegoleAccount.problemaPassword(String(repeating: "ab1", count: 100)), "oltre 200 caratteri")
        XCTAssertNotNil(RegoleAccount.problemaPassword("\u{0000}\u{0000}\u{0000}\u{0000}\u{0000}\u{0000}\u{0000}\u{0000}\u{0000}\u{0000}"))
        XCTAssertNil(RegoleAccount.problemaPassword("Pass-con-émoji-🙂-e-accenti"), "caratteri Unicode ammessi")
    }

    func testTokenECodiciOstili() {
        XCTAssertTrue(Accesso.tokenValido("abcDEF123-_.~"))
        XCTAssertFalse(Accesso.tokenValido(""))
        XCTAssertFalse(Accesso.tokenValido("con spazio"))
        XCTAssertFalse(Accesso.tokenValido("con\r\nX-Falso: 1"), "niente a capo: finirebbe in un'intestazione HTTP")
        XCTAssertFalse(Accesso.tokenValido(String(repeating: "a", count: 513)))
        XCTAssertFalse(Accesso.tokenValido("tökén"))
        XCTAssertTrue(Accesso.codiceRecuperoValido("AAAAA-BBBBB-CCCCC-DDDDD"))
        XCTAssertFalse(Accesso.codiceRecuperoValido("AAAAA BBBBB"))
        XCTAssertFalse(Accesso.codiceRecuperoValido("<b>ciao</b>"))
        XCTAssertFalse(Accesso.codiceRecuperoValido(String(repeating: "A", count: 101)))
    }

    func testSoloHttpsTranneQuestoComputer() {
        XCTAssertTrue(IndirizzoServer.valido("https://server.example.invalid"))
        XCTAssertFalse(IndirizzoServer.valido("http://server.example.invalid"), "il testo in chiaro non è ammesso")
        XCTAssertTrue(IndirizzoServer.valido("http://localhost:8000"), "solo per le prove su questo computer")
        XCTAssertTrue(IndirizzoServer.valido("http://127.0.0.1:8000"))
        XCTAssertFalse(IndirizzoServer.valido("http://192.168.1.10:8000"))
        XCTAssertFalse(IndirizzoServer.valido("ftp://server.example.invalid"))
        XCTAssertFalse(IndirizzoServer.valido("javascript:alert(1)"))
        XCTAssertFalse(IndirizzoServer.valido("https://utente:password@server.example.invalid"), "niente credenziali dentro l'indirizzo")
        XCTAssertFalse(IndirizzoServer.valido("https://"))
        XCTAssertFalse(IndirizzoServer.valido(""))
    }

    func testIlConteAllaRovesciaSiFermaAZero() {
        let adesso = Date(timeIntervalSince1970: 1_000_000)
        XCTAssertEqual(AttesaRiprova.secondiRimasti(fino: adesso.addingTimeInterval(45), adesso: adesso), 45)
        XCTAssertEqual(AttesaRiprova.secondiRimasti(fino: adesso.addingTimeInterval(0.2), adesso: adesso), 1)
        XCTAssertEqual(AttesaRiprova.secondiRimasti(fino: adesso, adesso: adesso), 0)
        XCTAssertEqual(AttesaRiprova.secondiRimasti(fino: adesso.addingTimeInterval(-30), adesso: adesso), 0, "mai negativo")
    }

    func testMessaggiDErroreDicononCosaFare() {
        XCTAssertTrue(SchermataAccesso.testoErrore(ErroreApi.rete("x")).contains("connessione"))
        XCTAssertTrue(SchermataAccesso.testoErrore(ErroreApi.timeout).contains("troppo"))
        XCTAssertTrue(SchermataAccesso.testoErrore(ErroreApi.risposta(502)).contains("Riprova"), "dice cosa fare (senza il codice tecnico)")
        XCTAssertTrue(SchermataAccesso.testoErrore(ErroreApi.indirizzoNonValido).contains("https://"))
        XCTAssertEqual(SchermataAccesso.testoErrore(ErroreApi.accessoRichiesto("Nome utente o password sbagliati")), "Nome utente o password sbagliati")
        XCTAssertTrue(SchermataAccesso.testoErrore(ErroreApi.troppiTentativi("Calma.", riprovaTra: 30)).contains("30 secondi"))
        XCTAssertTrue(SchermataAccesso.testoErrore(SessioneAccount.Errore.serverNonValido).contains("server di SchieraXI"))
    }
}

/// ServerHTTP contro un server ostile.
final class ServerHTTPOstileTests: XCTestCase {
    private var server: ServerHTTP!
    private var archivio: MemoriaToken!
    private var indirizzoPrima: String?

    override func setUp() {
        super.setUp()
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        archivio = MemoriaToken()
        server = ServerHTTP(sessione: URLSession(configuration: configurazione), archivioToken: archivio, attesaCalcolo: 0.01, massimoTentativiCalcolo: 3)
        indirizzoPrima = UserDefaults.standard.string(forKey: "indirizzo")
        UserDefaults.standard.set("https://prova-ostile.invalid", forKey: "indirizzo")
        ProtocolloFinto.ultimaRichiesta = nil
    }

    override func tearDown() {
        if let indirizzoPrima { UserDefaults.standard.set(indirizzoPrima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
        ProtocolloFinto.gestore = nil
        super.tearDown()
    }

    private func risposta(_ r: URLRequest, _ codice: Int, _ intestazioni: [String: String]? = nil) -> HTTPURLResponse {
        HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: intestazioni) ?? HTTPURLResponse()
    }

    func testIlTokenNonVaMaiAUnAltroServerNeAlTestoInChiaro() async throws {
        archivio.salva("token-vecchio", server: "https://server-vecchio.invalid")
        archivio.salva("token-in-chiaro", server: "http://evil.invalid")
        UserDefaults.standard.set("http://evil.invalid", forKey: "indirizzo")   // un indirizzo non ammesso: si ricade su quello della compilazione
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        do { _ = try await server.grezzo("/api/oggi") } catch {}
        if let r = ProtocolloFinto.ultimaRichiesta {
            XCTAssertEqual(r.url?.scheme, "https", "mai in chiaro")
            XCTAssertNil(r.value(forHTTPHeaderField: "Authorization"), "nessun token di un altro server")
        }
    }

    func testTimeoutDi20SecondiPerGliAccount() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.corpoJSON("POST", "/api/account/accedi", ["nome_utente": "x"])
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.timeoutInterval, 20)
        _ = try await server.grezzo("/api/oggi")
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.timeoutInterval, 25)
    }

    func testUnaPaginaHtmlNonDiventaUnMessaggioDelServer() async throws {
        for codice in [400, 404, 500, 502, 503] {
            ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, codice), Data("<html><body>Bad Gateway</body></html>".utf8)) }
            do {
                _ = try await server.grezzo("/api/oggi")
                XCTFail("doveva lanciare")
            } catch {
                XCTAssertEqual(error.localizedDescription, "SchieraXI ha un problema in questo momento. Riprova tra poco.", "codice \(codice)")
                XCTAssertFalse(error.localizedDescription.contains("codice"), "niente codici tecnici")
                XCTAssertFalse(error.localizedDescription.contains("<html"), "il corpo della risposta non finisce nei messaggi")
            }
        }
    }

    func testRisposteStraneNonFannoCrash() async throws {
        let corpi: [Data] = [Data(), Data("null".utf8), Data("[]".utf8), Data("{\"detail\": 5}".utf8), Data("{\"detail\": [1,2,3]}".utf8),
                             Data([0xFF, 0xFE, 0x00]), Data(repeating: 0x7B, count: 10_000), Data("{\"detail\": {\"a\": [null]}}".utf8)]
        for corpo in corpi {
            for codice in [200, 400, 401, 403, 429, 500] {
                ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, codice), corpo) }
                do {
                    let dati = try await server.grezzo("/api/oggi")
                    let _: RispostaAccount? = try? Decodifica.decodifica(dati)
                } catch {
                    XCTAssertFalse(error.localizedDescription.isEmpty)
                }
            }
        }
    }

    func testQuattrocentoUnoACatenaAvvisaSoloPerIlTokenGiusto() async throws {
        archivio.salva("token-di-oggi", server: "https://prova-ostile.invalid")
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 401), Data("{\"detail\": \"Accesso richiesto\"}".utf8)) }
        let impronte = Scatola<[Int]>()
        impronte.valore = []
        let osservatore = NotificationCenter.default.addObserver(forName: .accessoRichiesto, object: nil, queue: .main) { n in
            if let i = n.userInfo?["impronta"] as? Int { impronte.valore = (impronte.valore ?? []) + [i] }
        }
        defer { NotificationCenter.default.removeObserver(osservatore) }
        for _ in 0..<5 { _ = try? await server.grezzo("/api/oggi") }
        try await Task.sleep(nanoseconds: 300_000_000)
        XCTAssertEqual(impronte.valore?.count, 5)
        XCTAssertEqual(Set(impronte.valore ?? []), ["token-di-oggi".hashValue], "l'avviso dice quale token ha fallito, non il token")
    }

    func testUnQuattrocentoUnoDiUnProxyNonChiudeLaSessione() async throws {
        archivio.salva("token-di-oggi", server: "https://prova-ostile.invalid")
        let corpi = ["<html><body>Accedi al Wi-Fi</body></html>", "{\"errore\": \"x\"}", "{\"detail\": 5}", ""]
        let avvisi = Scatola<Int>()
        avvisi.valore = 0
        let osservatore = NotificationCenter.default.addObserver(forName: .accessoRichiesto, object: nil, queue: .main) { _ in
            avvisi.valore = (avvisi.valore ?? 0) + 1
        }
        defer { NotificationCenter.default.removeObserver(osservatore) }
        for corpo in corpi {
            ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 401), Data(corpo.utf8)) }
            do { _ = try await server.grezzo("/api/oggi"); XCTFail() } catch {
                XCTAssertTrue(error.localizedDescription.contains("rifiutata"), "dice che è rifiutata, non \u{ab}sessione finita\u{bb}")
            }
        }
        try await Task.sleep(nanoseconds: 300_000_000)
        XCTAssertEqual(avvisi.valore, 0)
        XCTAssertEqual(archivio.leggi(server: "https://prova-ostile.invalid"), "token-di-oggi")
    }

    func testUnQuattrocentoTreSenzaJsonDiceCheLaRichiestaERifiutata() {
        let testo = ErroreApi.risposta(403).localizedDescription
        XCTAssertTrue(testo.contains("rifiutata"))
        XCTAssertFalse(testo.contains("ha un problema"))
        XCTAssertTrue(ErroreApi.risposta(502).localizedDescription.contains("ha un problema"))
    }

    func testIlRetryAfterNonNumericoNonFaCrash() async throws {
        for valore in ["abc", "-5", "99999999999999999999", "", " 7 "] {
            ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 429, ["Retry-After": valore]), Data("{\"detail\": \"Calma\"}".utf8)) }
            do { _ = try await server.grezzo("/api/oggi"); XCTFail() } catch let e as ErroreApi {
                guard case .troppiTentativi = e else { return XCTFail("errore sbagliato: \(e)") }
            }
        }
    }

    func testIl202ContinuoSiArrendeSenzaCicliInfiniti() async {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 202, ["Retry-After": "0"]), Data("{}".utf8)) }
        let inizio = Date()
        do { _ = try await server.grezzo("/api/formazione"); XCTFail() } catch {
            XCTAssertTrue(error.localizedDescription.contains("Riprova"))
        }
        XCTAssertLessThan(Date().timeIntervalSince(inizio), 5)
    }
}

/// La sessione davanti a risposte ostili e a casi limite.
@MainActor
final class SessioneAvversariaTests: XCTestCase {
    private var memoria: UserDefaults!
    private var archivio: MemoriaToken!
    private var pulizie = 0
    private let nomeSuite = "prova-avversaria-\(UUID().uuidString)"
    private let utenteJSON = "{\"id\": 7, \"nome_utente\": \"mister.rossi\", \"ruolo\": \"utente\", \"creato\": \"x\"}"

    override func setUp() {
        super.setUp()
        memoria = UserDefaults(suiteName: nomeSuite)
        archivio = MemoriaToken()
        pulizie = 0
    }

    override func tearDown() {
        memoria.removePersistentDomain(forName: nomeSuite)
        super.tearDown()
    }

    private func sessione(_ server: any ServerClient, archivio: (any ArchivioToken)? = nil) -> SessioneAccount {
        SessioneAccount(server: server, archivio: archivio ?? self.archivio, memoria: memoria, pulisci: { [unowned self] in pulizie += 1 })
    }

    private func conRisposta(_ testo: String) -> ServerDiProva {
        ServerDiProva { _, _, _ in Data(testo.utf8) }
    }

    // MARK: server ostile

    func testHtmlAlPostoDelJsonDiceCheNonESerUnServerDiSchieraxi() async {
        memoria.set(true, forKey: "account.multiutente")
        let s = sessione(conRisposta("<html><body>Benvenuto</body></html>"))
        do { try await s.accedi(nomeUtente: "mister", password: "Prova-Finta-Zero"); XCTFail("doveva lanciare") } catch {
            XCTAssertEqual(error as? SessioneAccount.Errore, .serverNonValido)
            XCTAssertTrue(error.localizedDescription.contains("server di SchieraXI"))
        }
        XCTAssertEqual(s.stato, .daAccedere)
        XCTAssertFalse(s.inCorso)
    }

    func testRispostaSenzaTokenONonUtilizzabileNonFaEntrare() async {
        let ostili = [
            "{\"multiutente\": true, \"utente\": \(utenteJSON)}",                                                  // niente token
            "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"\"}",                                 // token vuoto
            "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"con spazio\"}",                       // caratteri non ammessi
            "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"a\\r\\nX-Falso: 1\"}",                  // a capo: iniezione nelle intestazioni
            "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"\(String(repeating: "a", count: 5000))\"}",  // enorme
            "{\"multiutente\": true, \"token\": \"abc\"}",                                                         // niente utente
            "{\"multiutente\": true, \"utente\": {\"id\": 1, \"nome_utente\": \"\(String(repeating: "x", count: 500))\", \"ruolo\": \"utente\"}, \"token\": \"abc\"}",
            "[]", "null", "{}", "\"testo\"", "42",
        ]
        for corpo in ostili {
            let archivioPulito = MemoriaToken()
            let server = conRisposta(corpo)
            let s = sessione(server, archivio: archivioPulito)
            do { try await s.accedi(nomeUtente: "mister", password: "Prova-Finta-Zero"); XCTFail("non doveva entrare con: \(corpo.prefix(60))") } catch {}
            XCTAssertNil(s.utente, "non si entra con: \(corpo.prefix(60))")
            XCTAssertNil(archivioPulito.leggi(server: server.indirizzo), "nessun token salvato")
            XCTAssertFalse(s.inCorso)
        }
    }

    func testCodiceDiRecuperoOstileNonSiMostra() async {
        let corpo = "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"abc\", \"codice_recupero\": \"<b>ciao</b> ciao\"}"
        let s = sessione(conRisposta(corpo))
        do { try await s.registra(nomeUtente: "mister", password: "Prova-Finta-Zero", invito: "X"); XCTFail() } catch {
            XCTAssertEqual(error as? SessioneAccount.Errore, .rispostaNonValida)
        }
        XCTAssertNil(s.codiceDaMostrare)
        XCTAssertNil(s.utente)
    }

    func testIlTokenNonFinisceInUserDefaultsNeNelloStato() async throws {
        let corpo = "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"segretissimo-123\", \"codice_recupero\": \"AAAAA-BBBBB-CCCCC\"}"
        let s = sessione(conRisposta(corpo))
        try await s.registra(nomeUtente: "mister", password: "Prova-Finta-Zero", invito: "X")
        for suite in [memoria!, UserDefaults.standard] {
            for (chiave, valore) in suite.dictionaryRepresentation() {
                let testo = "\(valore)"
                XCTAssertFalse(testo.contains("segretissimo-123"), "token in UserDefaults (\(chiave))")
                XCTAssertFalse(testo.contains("Prova-Finta-Zero"), "password in UserDefaults (\(chiave))")
                XCTAssertFalse(testo.contains("AAAAA-BBBBB-CCCCC"), "codice di recupero in UserDefaults (\(chiave))")
            }
        }
    }

    // MARK: Keychain che non salva

    func testKeychainCheNonSalvaDaUnAvvisoENonUnCrash() async throws {
        let perde = ArchivioChePerde()
        let corpo = "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"abc\"}"
        let server = conRisposta(corpo)
        let s = sessione(server, archivio: perde)
        try await s.accedi(nomeUtente: "mister", password: "Prova-Finta-Zero")
        XCTAssertNotNil(s.utente, "si entra lo stesso, finché l'app è aperta")
        XCTAssertTrue(s.avviso?.contains("in modo sicuro") == true, s.avviso ?? "nessun avviso")
        await s.esci()
        XCTAssertNil(s.avviso)
        XCTAssertNil(perde.leggi(server: server.indirizzo))
    }

    // MARK: doppi tocchi e richieste in parallelo

    func testDoppioToccoSuEntraMandaUnaSolaRichiesta() async throws {
        let corpo = "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"abc\"}"
        let server = ServerDiProva { _, _, _ in
            try await Task.sleep(nanoseconds: 200_000_000)
            return Data(corpo.utf8)
        }
        let s = sessione(server)
        async let primo: Void = s.accedi(nomeUtente: "mister", password: "Prova-Finta-Zero")
        async let secondo: Void = s.accedi(nomeUtente: "mister", password: "Prova-Finta-Zero")
        var esiti: [Bool] = []
        do { try await primo; esiti.append(true) } catch { esiti.append(false) }
        do { try await secondo; esiti.append(true) } catch { esiti.append(false) }
        XCTAssertEqual(esiti.filter { $0 }.count, 1, "uno entra, l'altro è rifiutato: \(esiti)")
        XCTAssertEqual(server.quante("POST /api/account/accedi"), 1, "al server arriva una sola richiesta")
        XCTAssertFalse(s.inCorso)
    }

    func testUscireSiPuoSempreAncheConUnaRichiestaInCorso() async {
        let server = ServerDiProva { _, percorso, _ in
            if percorso == "/api/account/cambia-password" { try await Task.sleep(nanoseconds: 300_000_000) }
            return Data("{\"ok\": true}".utf8)
        }
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        let lenta = Task { try? await s.cambiaPassword(attuale: "a", nuova: "b") }
        try? await Task.sleep(nanoseconds: 50_000_000)
        await s.esci()
        _ = await lenta.value
        XCTAssertEqual(s.stato, .daAccedere)
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
    }

    // MARK: 401 a catena e token scaduto a metà uso

    func testCentoQuattrocentoUnoDiSeguitoPulisconoUnaVoltaSola() async {
        let server = ServerDiProva { _, _, _ in Data("{}".utf8) }
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        for _ in 0..<100 { NotificationCenter.default.post(name: .accessoRichiesto, object: nil, userInfo: ["server": server.indirizzo]) }
        for _ in 0..<100 where s.stato != .daAccedere { try? await Task.sleep(nanoseconds: 20_000_000) }
        try? await Task.sleep(nanoseconds: 100_000_000)
        XCTAssertEqual(s.stato, .daAccedere)
        XCTAssertEqual(pulizie, 1, "i dati locali si cancellano una volta sola")
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
    }

    func testUn401InRitardoDiUnaRichiestaVecchiaNonButtaFuoriLaSessioneNuova() async {
        // il ricontrollo con /api/account/me conferma che la sessione è finita
        let server = ServerDiProva { _, p, _ in
            if p == "/api/account/me" { throw ErroreApi.accessoRichiesto("Accesso richiesto") }
            return Data("{}".utf8)
        }
        archivio.salva("token-nuovo", server: server.indirizzo)
        let s = sessione(server)
        NotificationCenter.default.post(name: .accessoRichiesto, object: nil,
                                        userInfo: ["server": server.indirizzo, "impronta": "token-vecchio".hashValue])
        try? await Task.sleep(nanoseconds: 200_000_000)
        XCTAssertNotNil(s.utente, "il 401 era di un token che non è più quello di adesso")
        XCTAssertEqual(pulizie, 0)
        NotificationCenter.default.post(name: .accessoRichiesto, object: nil,
                                        userInfo: ["server": server.indirizzo, "impronta": "token-nuovo".hashValue])
        for _ in 0..<100 where s.stato != .daAccedere { try? await Task.sleep(nanoseconds: 20_000_000) }
        XCTAssertEqual(s.stato, .daAccedere, "con il token giusto invece sì")
    }

    func testUn401SospettoNonButtaFuoriSeIlServerDiceCheLaSessioneVale() async {
        let server = ServerDiProva { _, p, _ in
            if p == "/api/account/me" {
                return Data("{\"multiutente\": true, \"utente\": {\"id\": 7, \"nome_utente\": \"mister\", \"ruolo\": \"utente\"}}".utf8)
            }
            return Data("{}".utf8)
        }
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        NotificationCenter.default.post(name: .accessoRichiesto, object: nil, userInfo: ["server": server.indirizzo, "impronta": "tok".hashValue])
        for _ in 0..<50 where server.quante("/api/account/me") == 0 { try? await Task.sleep(nanoseconds: 20_000_000) }
        try? await Task.sleep(nanoseconds: 200_000_000)
        XCTAssertEqual(server.quante("/api/account/me"), 1, "prima di buttare il token si chiede al server")
        XCTAssertNotEqual(s.stato, .daAccedere)
        XCTAssertEqual(archivio.leggi(server: server.indirizzo), "tok")
        XCTAssertEqual(pulizie, 0)
    }

    func testUn401SospettoConLaReteAssenteNonButtaFuori() async {
        let server = ServerDiProva { _, p, _ in
            if p == "/api/account/me" { throw ErroreApi.rete("senza rete") }
            return Data("{}".utf8)
        }
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        NotificationCenter.default.post(name: .accessoRichiesto, object: nil, userInfo: ["server": server.indirizzo, "impronta": "tok".hashValue])
        try? await Task.sleep(nanoseconds: 300_000_000)
        XCTAssertNotEqual(s.stato, .daAccedere)
        XCTAssertEqual(archivio.leggi(server: server.indirizzo), "tok")
    }

    // MARK: cambio server con la sessione aperta

    func testCambiandoServerIlTokenVecchioSiButta() async {
        let server = ServerCambiabile(indirizzo: "https://vecchio.invalid") { _, percorso in
            percorso == "/api/account/me" ? Data("{\"multiutente\": false, \"utente\": null}".utf8) : Data("{}".utf8)
        }
        archivio.salva("token-del-vecchio", server: "https://vecchio.invalid")
        let s = sessione(server)
        XCTAssertNotNil(s.utente)
        server.indirizzo = "https://nuovo.invalid"
        await s.cambiaServer()
        XCTAssertNil(archivio.leggi(server: "https://vecchio.invalid"), "il token del server vecchio è cancellato, non solo ignorato")
        XCTAssertNil(archivio.leggi(server: "https://nuovo.invalid"))
        XCTAssertEqual(pulizie, 1, "anche i dati locali del server vecchio")
        XCTAssertNil(s.utente)
        // nessuna richiesta al server nuovo ha portato il token (l'archivio ha solo quello vecchio, già cancellato)
        XCTAssertTrue(server.richieste.allSatisfy { !$0.contains("token-del-vecchio") })
    }

    func testRipetereLoStessoServerNonCancellaNiente() async {
        let utente = utenteJSON
        let server = ServerCambiabile(indirizzo: "https://stesso.invalid") { _, p in
            p == "/api/account/me" ? Data("{\"multiutente\": true, \"utente\": \(utente)}".utf8) : Data("{}".utf8)
        }
        archivio.salva("tok", server: "https://stesso.invalid")
        let s = sessione(server)
        await s.cambiaServer()
        await s.cambiaServer()
        XCTAssertNotNil(s.utente)
        XCTAssertEqual(pulizie, 0)
        XCTAssertEqual(archivio.leggi(server: "https://stesso.invalid"), "tok")
    }

    // MARK: uscita che cancella davvero

    func testUscitaCancellaTokenCacheScambiRiassuntoENotifiche() async throws {
        let server = ServerDiProva { _, _, _ in Data("{\"ok\": true}".utf8) }
        archivio.salva("tok", server: server.indirizzo)
        // dati «di un altro utente» sul telefono
        let indirizzo = "https://prova-uscita-\(UUID().uuidString).invalid"
        Cache.salva(Data("dati".utf8), "/api/oggi", indirizzo: indirizzo)
        UserDefaults.standard.set(Data("scambi".utf8), forKey: "archivioScambi")
        UserDefaults.standard.set(Data("riassunto".utf8), forKey: "ultimoRiassunto")
        UserDefaults.standard.set("3-4-3", forKey: "bg.modulo")
        for _ in 0..<100 { if await Cache.leggi("/api/oggi", indirizzo: indirizzo) != nil { break }; try await Task.sleep(nanoseconds: 20_000_000) }

        // l'uscita vera (non il finto «pulisci» dei test): DatiLocali.svuota
        let s = SessioneAccount(server: server, archivio: archivio, memoria: memoria, pulisci: { DatiLocali.svuota() })
        await s.esci()

        XCTAssertNil(archivio.leggi(server: server.indirizzo))
        let copia = await Cache.leggi("/api/oggi", indirizzo: indirizzo)
        XCTAssertNil(copia, "la cache su disco è vuota")
        XCTAssertNil(UserDefaults.standard.data(forKey: "archivioScambi"))
        XCTAssertNil(UserDefaults.standard.data(forKey: "ultimoRiassunto"))
        XCTAssertNil(UserDefaults.standard.string(forKey: "bg.modulo"))
        XCTAssertNil(s.codiceDaMostrare)
    }

    func testUscitaDopoRegistrazioneNonLasciaIlCodiceDiRecupero() async throws {
        let corpo = "{\"multiutente\": true, \"utente\": \(utenteJSON), \"token\": \"abc\", \"codice_recupero\": \"AAAAA-BBBBB-CCCCC\"}"
        let s = sessione(conRisposta(corpo))
        try await s.registra(nomeUtente: "mister", password: "Prova-Finta-Zero", invito: "X")
        XCTAssertNotNil(s.codiceDaMostrare)
        await s.esci()
        XCTAssertNil(s.codiceDaMostrare, "stato impossibile: codice da mostrare senza utente")
        XCTAssertEqual(s.stato, .daAccedere)
    }
}
