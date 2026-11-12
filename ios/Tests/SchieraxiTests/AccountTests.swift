import XCTest
import Security
@testable import Schieraxi

// Account del server con più utenti: regole di nome e password, token nel Keychain (con un archivio finto), gestione di 401, 429 e 202,
// accesso, uscita e ripristino. Tutto con server finti: nessun server vero e nessun indirizzo vero.

final class RegoleAccountTests: XCTestCase {
    func testNomeUtente() {
        XCTAssertNil(RegoleAccount.problemaNome("mister.rossi"))
        XCTAssertNil(RegoleAccount.problemaNome("  Mister_Rossi-1 "), "maiuscole e spazi ai lati si sistemano da soli")
        XCTAssertEqual(RegoleAccount.pulisciNome("  Mister.Rossi "), "mister.rossi")
        XCTAssertNotNil(RegoleAccount.problemaNome(""))
        XCTAssertNotNil(RegoleAccount.problemaNome("ab"), "almeno 3 caratteri")
        XCTAssertNotNil(RegoleAccount.problemaNome(String(repeating: "a", count: 33)), "al massimo 32")
        XCTAssertNotNil(RegoleAccount.problemaNome("mister rossi"), "niente spazi dentro")
        XCTAssertNotNil(RegoleAccount.problemaNome(".rossi"), "comincia con una lettera o un numero")
        XCTAssertNotNil(RegoleAccount.problemaNome("rossi@x"))
    }

    func testPassword() {
        XCTAssertNil(RegoleAccount.problemaPassword("Prova-Finta-Zero", nome: "mister"))
        XCTAssertNotNil(RegoleAccount.problemaPassword(""))
        XCTAssertNotNil(RegoleAccount.problemaPassword("corta1"), "almeno 10 caratteri")
        XCTAssertNotNil(RegoleAccount.problemaPassword(String(repeating: "x", count: 201)), "al massimo 200")
        XCTAssertNotNil(RegoleAccount.problemaPassword("1234567890123"), "solo numeri")
        XCTAssertNotNil(RegoleAccount.problemaPassword("aaaaaaaaaaaa"), "troppi caratteri uguali")
        XCTAssertNotNil(RegoleAccount.problemaPassword("mister.rossi1", nome: "mister.rossi"), "il nome con poco intorno")
        XCTAssertNil(RegoleAccount.problemaPassword("mister.rossi-e-la-sua-squadra", nome: "mister.rossi"))
    }
}

final class TokenTests: XCTestCase {
    func testMemoriaPerServer() {
        let archivio = MemoriaToken()
        XCTAssertNil(archivio.leggi(server: "https://a.invalid"))
        archivio.salva("uno", server: "https://a.invalid")
        archivio.salva("due", server: "https://b.invalid")
        XCTAssertEqual(archivio.leggi(server: "https://a.invalid"), "uno", "un token per server: cambiando server non si manda quello sbagliato")
        XCTAssertEqual(archivio.leggi(server: "https://b.invalid"), "due")
        archivio.cancella(server: "https://a.invalid")
        XCTAssertNil(archivio.leggi(server: "https://a.invalid"))
        XCTAssertEqual(archivio.leggi(server: "https://b.invalid"), "due")
    }

    /// Il Keychain vero. Nelle compilazioni senza firma iOS può rifiutarlo (errSecMissingEntitlement): in quel caso il test si salta,
    /// perché il ripiego in memoria di `KeychainToken` farebbe passare comunque il giro completo senza provare niente.
    func testKeychainVeroSalvaLeggeECancella() throws {
        let servizio = "it.schieraxi.app.prova-\(UUID().uuidString)"
        let sonda: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: servizio,
                                    kSecAttrAccount as String: "sonda", kSecValueData as String: Data("x".utf8)]
        let esito = SecItemAdd(sonda as CFDictionary, nil)
        try XCTSkipIf(esito != errSecSuccess, "Keychain non disponibile in questa compilazione (stato \(esito))")
        SecItemDelete(sonda as CFDictionary)

        let archivio = KeychainToken(servizio: servizio)
        let server = "https://prova-keychain.invalid"
        XCTAssertNil(archivio.leggi(server: server))
        archivio.salva("token-segreto", server: server)
        XCTAssertEqual(archivio.leggi(server: server), "token-segreto")
        archivio.salva("token-nuovo", server: server)
        XCTAssertEqual(archivio.leggi(server: server), "token-nuovo", "salvare di nuovo sostituisce")

        // accessibile dopo il primo sblocco (serve all'aggiornamento in background)
        let chiedi: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: servizio,
                                     kSecAttrAccount as String: server, kSecReturnAttributes as String: true]
        var risultato: CFTypeRef?
        XCTAssertEqual(SecItemCopyMatching(chiedi as CFDictionary, &risultato), errSecSuccess)
        let attributi = risultato as? [String: Any]
        XCTAssertEqual(attributi?[kSecAttrAccessible as String] as? String, kSecAttrAccessibleAfterFirstUnlock as String)

        archivio.cancella(server: server)
        XCTAssertNil(archivio.leggi(server: server))
    }
}

/// ServerHTTP con l'accesso: intestazione Authorization, 401, 429, 202.
final class ServerHTTPAccountTests: XCTestCase {
    private var server: ServerHTTP!
    private var archivio: MemoriaToken!
    private var indirizzoPrima: String?
    private let indirizzo = "https://prova-account.invalid:8443"

    override func setUp() {
        super.setUp()
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        archivio = MemoriaToken()
        server = ServerHTTP(sessione: URLSession(configuration: configurazione), archivioToken: archivio, attesaCalcolo: 0.01, massimoTentativiCalcolo: 5)
        indirizzoPrima = UserDefaults.standard.string(forKey: "indirizzo")
        UserDefaults.standard.set(indirizzo, forKey: "indirizzo")
        ProtocolloFinto.gestore = nil
        ProtocolloFinto.ultimaRichiesta = nil
        ProtocolloFinto.ultimoCorpo = nil
    }

    override func tearDown() {
        if let indirizzoPrima { UserDefaults.standard.set(indirizzoPrima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
        ProtocolloFinto.gestore = nil
        super.tearDown()
    }

    private func risposta(_ r: URLRequest, _ codice: Int, _ intestazioni: [String: String]? = nil) -> HTTPURLResponse {
        HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: intestazioni) ?? HTTPURLResponse()
    }

    func testIlTokenVaComeBearerSoloSeCe() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.grezzo("/api/oggi")
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "Authorization"), "senza token niente intestazione (server di sempre)")
        archivio.salva("abc123", server: indirizzo)
        _ = try await server.grezzo("/api/oggi")
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "Authorization"), "Bearer abc123")
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "X-Fanta"), "1")
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "Cookie"), "l'app nativa non usa i cookie")
    }

    func testIlTokenDiUnAltroServerNonVieneMandato() async throws {
        archivio.salva("abc123", server: "https://altro-server.invalid")
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 200), Data("{}".utf8)) }
        _ = try await server.grezzo("/api/oggi")
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "Authorization"))
    }

    func test401FuoriDallAccessoAvvisaLApp() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in (risposta(r, 401), Data("{\"detail\": \"Accesso richiesto\", \"multiutente\": true}".utf8)) }
        let avviso = expectation(forNotification: .accessoRichiesto, object: nil) { n in n.userInfo?["server"] as? String == self.indirizzo }
        do {
            _ = try await server.grezzo("/api/formazione")
            XCTFail("doveva lanciare")
        } catch ErroreApi.accessoRichiesto(let messaggio) {
            XCTAssertEqual(messaggio, "Accesso richiesto")
        }
        await fulfillment(of: [avviso], timeout: 10)   // la notifica passa dalla coda principale: sul Mac di GitHub carico serve margine
    }

    func test401DiUnAccessoSbagliatoNonAvvisaLApp() async throws {
        // Il finto internet è uno solo e condiviso: il 401 lo diamo SOLO alla richiesta di accesso.
        ProtocolloFinto.gestore = { [unowned self] r in
            r.url?.path == "/api/account/accedi"
                ? (risposta(r, 401), Data("{\"detail\": \"Nome utente o password non corretti\"}".utf8))
                : (risposta(r, 200), Data("{}".utf8))
        }
        // Indirizzo solo di questo test: l'avviso di una richiesta rimasta in giro da un altro test (che usa l'indirizzo
        // comune della classe) non può essere scambiato per uno nostro.
        let mio = "https://prova-\(UUID().uuidString.lowercased()).invalid"
        UserDefaults.standard.set(mio, forKey: "indirizzo")
        let visti = Scatola<[String]>()
        visti.valore = []
        let osservatore = NotificationCenter.default.addObserver(forName: .accessoRichiesto, object: nil, queue: .main) { n in
            visti.valore = (visti.valore ?? []) + ["\(n.userInfo ?? [:])"]
        }
        defer { NotificationCenter.default.removeObserver(osservatore) }
        do {
            _ = try await server.corpoJSON("POST", "/api/account/accedi", ["nome_utente": "x"])
            XCTFail("doveva lanciare")
        } catch ErroreApi.accessoRichiesto(let messaggio) {
            XCTAssertEqual(messaggio, "Nome utente o password non corretti")
        }
        try await Task.sleep(nanoseconds: 400_000_000)
        let miei = (visti.valore ?? []).filter { $0.contains(mio) && $0.contains("/api/account/accedi") }
        XCTAssertTrue(miei.isEmpty, "avvisi arrivati: \(miei) (tutti: \(visti.valore ?? []))")
    }

    func test429ConAttesa() async throws {
        ProtocolloFinto.gestore = { [unowned self] r in
            (risposta(r, 429, ["Retry-After": "30"]), Data("{\"detail\": \"Troppi tentativi\"}".utf8))
        }
        do {
            _ = try await server.corpoJSON("POST", "/api/account/accedi", ["nome_utente": "x"])
            XCTFail("doveva lanciare")
        } catch let e as ErroreApi {
            guard case .troppiTentativi(let messaggio, let attesa) = e else { return XCTFail("errore sbagliato: \(e)") }
            XCTAssertEqual(messaggio, "Troppi tentativi")
            XCTAssertEqual(attesa, 30)
            XCTAssertEqual(e.errorDescription, "Troppi tentativi. Riprova tra 30 secondi.")
        }
    }

    func test429SenzaAttesaEConAttesaLunga() {
        XCTAssertEqual(ErroreApi.troppiTentativi("Calma.", riprovaTra: nil).errorDescription, "Calma.")
        XCTAssertEqual(ErroreApi.troppiTentativi("Calma.", riprovaTra: 600).errorDescription, "Calma. Riprova tra 10 minuti.")
    }

    func test202SiRiprovaDaSoli() async throws {
        let conteggio = Scatola<Int>()
        conteggio.valore = 0
        ProtocolloFinto.gestore = { [unowned self] r in
            let n = (conteggio.valore ?? 0) + 1
            conteggio.valore = n
            return n < 3 ? (risposta(r, 202, ["Retry-After": "0"]), Data("{\"detail\": \"Sto calcolando\"}".utf8))
                         : (risposta(r, 200), Data("{\"modulo\": \"3-4-3\"}".utf8))
        }
        let dati = try await server.grezzo("/api/formazione")
        XCTAssertEqual(String(decoding: dati, as: UTF8.self), "{\"modulo\": \"3-4-3\"}")
        XCTAssertEqual(conteggio.valore, 3, "due risposte «sto calcolando» e poi quella vera")
    }

    func test202ChePersisteSiArrende() async throws {
        let conteggio = Scatola<Int>()
        conteggio.valore = 0
        ProtocolloFinto.gestore = { [unowned self] r in
            conteggio.valore = (conteggio.valore ?? 0) + 1
            return (risposta(r, 202, ["Retry-After": "0"]), Data("{}".utf8))
        }
        do {
            _ = try await server.grezzo("/api/formazione")
            XCTFail("doveva arrendersi")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("Riprova tra poco"), error.localizedDescription)
        }
        XCTAssertEqual(conteggio.valore, 6, "una richiesta più cinque tentativi")
    }
}

@MainActor
final class SessioneAccountTests: XCTestCase {
    private var memoria: UserDefaults!
    private var archivio: MemoriaToken!
    private var pulizie = 0
    private let nomeSuite = "prova-account-\(UUID().uuidString)"

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

    private let utenteJSON = "{\"id\": 7, \"nome_utente\": \"mister.rossi\", \"ruolo\": \"utente\", \"creato\": \"2026-10-29\"}"

    private func sessione(_ server: ServerDiProva) -> SessioneAccount {
        SessioneAccount(server: server, archivio: archivio, memoria: memoria, pulisci: { [unowned self] in pulizie += 1 })
    }

    private func serverAccount(accesso: String? = nil, extra: (@Sendable (String, String) throws -> Data?)? = nil) -> ServerDiProva {
        let utente = utenteJSON
        return ServerDiProva { metodo, percorso, _ in
            if let extra, let dati = try extra(metodo, percorso) { return dati }
            switch percorso {
            case "/api/account/accedi": return Data("{\"multiutente\": true, \"utente\": \(utente), \"token\": \"tok-1\"}".utf8)
            case "/api/account/registra": return Data("{\"multiutente\": true, \"utente\": \(utente), \"token\": \"tok-2\", \"codice_recupero\": \"AAAAA-BBBBB-CCCCC\"}".utf8)
            case "/api/account/codice-recupero": return Data("{\"codice_recupero\": \"DDDDD-EEEEE-FFFFF\"}".utf8)
            case "/api/account/recupero": return Data("{\"ok\": true, \"codice_recupero\": \"GGGGG-HHHHH-JJJJJ\"}".utf8)
            default: return Data("{\"ok\": true}".utf8)
            }
        }
    }

    // MARK: partenza

    func testSenzaTokenEServerDiSempreNonServeAccesso() {
        XCTAssertEqual(sessione(serverAccount()).stato, .nonRichiesto)
    }

    func testConTokenSiPartePerGiaConnessi() throws {
        let server = serverAccount()
        archivio.salva("tok", server: server.indirizzo)
        memoria.set(try JSONEncoder().encode(Utente(id: 7, nomeUtente: "mister.rossi", ruolo: "utente", creato: nil)), forKey: "account.utente")
        let s = sessione(server)
        XCTAssertEqual(s.utente?.nomeUtente, "mister.rossi", "l'app si apre subito, senza aspettare la rete")
        XCTAssertTrue(s.multiutente)
    }

    func testSeSiSaChePiaccountEMancaIlTokenSiPartDallAccesso() {
        memoria.set(true, forKey: "account.multiutente")
        XCTAssertEqual(sessione(serverAccount()).stato, .daAccedere)
    }

    // MARK: verifica (GET /api/account/me)

    func testVerificaServerSenzaAccount() async {
        let server = serverAccount(extra: { _, p in p == "/api/account/me" ? Data("{\"multiutente\": false, \"utente\": {\"id\": 0, \"nome_utente\": \"locale\", \"ruolo\": \"amministratore\", \"creato\": \"\"}}".utf8) : nil })
        archivio.salva("vecchio", server: server.indirizzo)
        let s = sessione(server)
        await s.verifica()
        XCTAssertEqual(s.stato, .nonRichiesto)
        XCTAssertFalse(s.multiutente)
        XCTAssertNil(archivio.leggi(server: server.indirizzo), "un token che non serve più si butta")
    }

    func testVerificaConSessioneValida() async {
        let utente = utenteJSON
        let server = serverAccount(extra: { _, p in p == "/api/account/me" ? Data("{\"multiutente\": true, \"utente\": \(utente)}".utf8) : nil })
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        await s.verifica()
        XCTAssertEqual(s.utente?.nomeUtente, "mister.rossi")
        XCTAssertEqual(s.utente?.id, 7)
        XCTAssertEqual(pulizie, 0, "una sessione che si conferma non svuota niente")
    }

    func testVerificaCon401TornaAllAccessoESvuotaIDati() async {
        let server = serverAccount(extra: { _, p in
            if p == "/api/account/me" { throw ErroreApi.accessoRichiesto("Accesso richiesto") }
            return nil
        })
        archivio.salva("scaduto", server: server.indirizzo)
        let s = sessione(server)
        await s.verifica()
        XCTAssertEqual(s.stato, .daAccedere)
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
        XCTAssertEqual(pulizie, 1, "i dati locali dell'altro utente si cancellano")
        XCTAssertTrue(memoria.bool(forKey: "account.multiutente"))
    }

    func testServerSpentoNonCambiaNiente() async {
        let server = serverAccount(extra: { _, p in
            if p == "/api/account/me" { throw ErroreApi.rete("spento") }
            return nil
        })
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        let prima = s.stato
        await s.verifica()
        XCTAssertEqual(s.stato, prima, "con la rete spenta si resta dov'eravamo (con i dati salvati)")
        XCTAssertEqual(pulizie, 0)
    }

    // MARK: accesso, registrazione, uscita

    func testAccediSalvaIlTokenSoloNelKeychainEPassaAConnesso() async throws {
        memoria.set(true, forKey: "account.multiutente")
        let server = serverAccount()
        let s = sessione(server)
        let generazione = s.generazione
        try await s.accedi(nomeUtente: "  Mister.Rossi ", password: "Prova-Finta-Zero")
        XCTAssertEqual(s.utente?.nomeUtente, "mister.rossi")
        XCTAssertEqual(archivio.leggi(server: server.indirizzo), "tok-1")
        XCTAssertGreaterThan(s.generazione, generazione, "le schermate si ricostruiscono")
        XCTAssertNil(s.codiceDaMostrare, "il codice di recupero c'è solo alla registrazione")
        // il corpo: nome pulito, password, nativo (così il token torna nella risposta e non nel cookie)
        let corpo = try XCTUnwrap(server.corpiInviati(a: "/api/account/accedi").first)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: corpo) as? [String: Any])
        XCTAssertEqual(json["nome_utente"] as? String, "mister.rossi")
        XCTAssertEqual(json["password"] as? String, "Prova-Finta-Zero")
        XCTAssertEqual(json["nativo"] as? Bool, true)
        // il token non finisce da nessuna parte tranne il Keychain
        for (chiave, valore) in memoria.dictionaryRepresentation() {
            XCTAssertFalse("\(valore)".contains("tok-1"), "il token non va in UserDefaults (\(chiave))")
        }
        for (_, valore) in UserDefaults.standard.dictionaryRepresentation() {
            XCTAssertFalse("\(valore)".contains("tok-1"))
        }
    }

    func testAccessoSbagliatoRestaFuoriEDiceCosaNonVa() async {
        memoria.set(true, forKey: "account.multiutente")
        let server = serverAccount(extra: { _, p in
            if p == "/api/account/accedi" { throw ErroreApi.accessoRichiesto("Nome utente o password non corretti") }
            return nil
        })
        let s = sessione(server)
        do {
            try await s.accedi(nomeUtente: "mister", password: "sbagliata-sbagliata")
            XCTFail("doveva lanciare")
        } catch {
            XCTAssertEqual(error.localizedDescription, "Nome utente o password non corretti")
        }
        XCTAssertEqual(s.stato, .daAccedere)
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
    }

    func testRegistrazioneMostraIlCodiceDiRecuperoEPoiLoNasconde() async throws {
        memoria.set(true, forKey: "account.multiutente")
        let server = serverAccount()
        let s = sessione(server)
        try await s.registra(nomeUtente: "mister.rossi", password: "Prova-Finta-Zero", invito: " inv-123 ")
        let corpo = try XCTUnwrap(JSONSerialization.jsonObject(with: XCTUnwrap(server.corpiInviati(a: "/registra").first)) as? [String: Any])
        XCTAssertEqual(corpo["invito"] as? String, "INV-123", "spazi tolti e maiuscolo, come i codici del server")
        XCTAssertEqual(corpo["nativo"] as? Bool, true)
        XCTAssertEqual(corpo["accetto_termini"] as? Bool, true, "l'accettazione di Termini e Privacy parte con la registrazione")
        XCTAssertEqual(s.codiceDaMostrare, "AAAAA-BBBBB-CCCCC")
        XCTAssertNotNil(s.utente)
        s.codiceDaMostrare = nil   // «l'ho salvato»
        XCTAssertNil(s.codiceDaMostrare)
    }

    func testRecuperoRestituisceIlNuovoCodiceEMandaMaiuscolo() async throws {
        let server = serverAccount()
        let s = sessione(server)
        let nuovo = try await s.recupera(nomeUtente: "Mister.Rossi", codice: " aaaaa-bbbbb ", nuovaPassword: "Prova-Finta-Zero")
        XCTAssertEqual(nuovo, "GGGGG-HHHHH-JJJJJ")
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: XCTUnwrap(server.corpiInviati(a: "/recupero").first)) as? [String: Any])
        XCTAssertEqual(json["codice"] as? String, "AAAAA-BBBBB")
        XCTAssertEqual(json["nome_utente"] as? String, "mister.rossi")
        XCTAssertEqual(json["nuova"] as? String, "Prova-Finta-Zero")
        XCTAssertEqual(s.stato, .nonRichiesto, "dopo il recupero non si è connessi: si fa l'accesso con la password nuova")
    }

    func testUscitaButtaIlTokenSvuotaITuoiDatiEPoiSiPuoRientrare() async throws {
        let server = serverAccount()
        memoria.set(true, forKey: "account.multiutente")
        let s = sessione(server)
        try await s.accedi(nomeUtente: "mister.rossi", password: "Prova-Finta-Zero")
        let prima = pulizie
        await s.esci()
        XCTAssertEqual(server.quante("POST /api/account/esci"), 1)
        XCTAssertEqual(s.stato, .daAccedere)
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
        XCTAssertGreaterThan(pulizie, prima, "all'uscita i dati locali si cancellano")
        XCTAssertNil(memoria.data(forKey: "account.utente"))
        // ripristino: si può accedere di nuovo
        try await s.accedi(nomeUtente: "mister.rossi", password: "Prova-Finta-Zero")
        XCTAssertNotNil(s.utente)
        XCTAssertEqual(archivio.leggi(server: server.indirizzo), "tok-1")
    }

    func testUscitaFunzionaAncheSeIlServerNonRisponde() async {
        let server = serverAccount(extra: { _, p in
            if p == "/api/account/esci" { throw ErroreApi.rete("spento") }
            return nil
        })
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        await s.esci()
        XCTAssertEqual(s.stato, .daAccedere, "uscire dal telefono non dipende dal server")
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
    }

    func testEliminaChiudeAncheQuestoTelefono() async throws {
        let server = serverAccount()
        archivio.salva("tok", server: server.indirizzo)
        let t = sessione(server)
        try await t.elimina(password: "Prova-Finta-Zero")
        XCTAssertEqual(server.quante("/api/account/elimina"), 1)
        XCTAssertEqual(t.stato, .daAccedere)
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
    }

    func testEliminaConPasswordSbagliataNonTocchiaNiente() async {
        let server = serverAccount(extra: { _, p in
            if p == "/api/account/elimina" { throw ErroreApi.accessoRichiesto("Password non corretta") }
            return nil
        })
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        do { try await s.elimina(password: "no"); XCTFail("doveva lanciare") } catch {}
        XCTAssertNotNil(archivio.leggi(server: server.indirizzo), "il token resta: l'account non è stato eliminato")
        XCTAssertEqual(pulizie, 0)
    }

    func testCambioPasswordENuovoCodice() async throws {
        let server = serverAccount()
        let s = sessione(server)
        try await s.cambiaPassword(attuale: "vecchia-vecchia", nuova: "nuova-nuova-1")
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: XCTUnwrap(server.corpiInviati(a: "/cambia-password").first)) as? [String: Any])
        XCTAssertEqual(json["attuale"] as? String, "vecchia-vecchia")
        XCTAssertEqual(json["nuova"] as? String, "nuova-nuova-1")
        let codice = try await s.nuovoCodiceRecupero(password: "nuova-nuova-1")
        XCTAssertEqual(codice, "DDDDD-EEEEE-FFFFF")
    }

    // MARK: sessione finita (401 in giro per l'app)

    private func aspetta(_ condizione: @MainActor () -> Bool) async {
        for _ in 0..<100 where !condizione() { try? await Task.sleep(nanoseconds: 20_000_000) }
    }

    func testUn401InGiroPerLAppPortaAllAccessoEDaSvuotaIDati() async {
        let server = serverAccount()
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        XCTAssertNotNil(s.utente)
        NotificationCenter.default.post(name: .accessoRichiesto, object: nil, userInfo: ["server": server.indirizzo])
        await aspetta { s.stato == .daAccedere }
        XCTAssertEqual(s.stato, .daAccedere)
        XCTAssertNil(archivio.leggi(server: server.indirizzo))
        XCTAssertEqual(pulizie, 1)
    }

    func testUn401DiUnAltroServerNonSiTocca() async {
        let server = serverAccount()
        archivio.salva("tok", server: server.indirizzo)
        let s = sessione(server)
        NotificationCenter.default.post(name: .accessoRichiesto, object: nil, userInfo: ["server": "https://un-altro.invalid"])
        try? await Task.sleep(nanoseconds: 200_000_000)
        XCTAssertNotNil(s.utente)
        XCTAssertEqual(pulizie, 0)
    }

    func testCambiaServerRipartDallAccessoDiQuelServer() async {
        let server = serverAccount(extra: { _, p in p == "/api/account/me" ? Data("{\"multiutente\": false, \"utente\": null}".utf8) : nil })
        let s = sessione(server)
        await s.cambiaServer()
        XCTAssertEqual(s.stato, .nonRichiesto)
    }
}

@MainActor
final class DatiLocaliTests: XCTestCase {
    func testLaCacheSiSvuotaTutta() async throws {
        let indirizzo = "https://prova-svuota-\(UUID().uuidString).invalid"
        Cache.salva(Data("uno".utf8), "/api/oggi", indirizzo: indirizzo)
        Cache.salva(Data("png".utf8), "/api/foto/1", indirizzo: indirizzo, cartella: "img")
        var presenti = false
        for _ in 0..<100 where !presenti {
            let a = await Cache.leggi("/api/oggi", indirizzo: indirizzo)
            let b = await Cache.leggi("/api/foto/1", indirizzo: indirizzo, cartella: "img")
            presenti = a != nil && b != nil
            if !presenti { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        XCTAssertTrue(presenti)
        Cache.svuotaTutto()
        let dopoA = await Cache.leggi("/api/oggi", indirizzo: indirizzo)
        let dopoB = await Cache.leggi("/api/foto/1", indirizzo: indirizzo, cartella: "img")
        XCTAssertNil(dopoA, "all'uscita le risposte salvate di chi c'era prima spariscono")
        XCTAssertNil(dopoB)
    }
}

@MainActor
final class UscitaCancellaLeCopieDiIosTests: XCTestCase {
    func testLaCacheDiUrlSessionSiSvuotaConLUscita() async throws {
        // Prima il test usava la cache vera dell'app (`URLCache.shared`, su disco e condivisa con l'app che ospita i test):
        // la scrittura su disco è asincrona e poteva arrivare DOPO lo svuotamento, rimettendo la risposta (test instabile).
        // Ora per la durata del test `URLCache.shared` è una cache nuova solo in memoria: niente scritture in ritardo né
        // risposte d'altri; si controlla comunque che `DatiLocali.svuota()` svuoti proprio `URLCache.shared`.
        let vera = URLCache.shared
        URLCache.shared = URLCache(memoryCapacity: 1_000_000, diskCapacity: 0, diskPath: nil)
        defer { URLCache.shared = vera }
        let richiesta = URLRequest(url: URL(string: "https://prova-urlcache.invalid/api/oggi")!)
        let risposta = HTTPURLResponse(url: richiesta.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
        URLCache.shared.storeCachedResponse(CachedURLResponse(response: risposta, data: Data("x".utf8)), for: richiesta)
        // si aspetta che la copia ci sia davvero: se non c'è il test non prova niente e deve dirlo (prima proseguiva in silenzio)
        for _ in 0..<100 where URLCache.shared.cachedResponse(for: richiesta) == nil { try await Task.sleep(nanoseconds: 20_000_000) }
        XCTAssertNotNil(URLCache.shared.cachedResponse(for: richiesta), "la copia di prova deve esserci prima dell'uscita")
        DatiLocali.svuota()
        for _ in 0..<100 where URLCache.shared.cachedResponse(for: richiesta) != nil { try await Task.sleep(nanoseconds: 20_000_000) }
        XCTAssertNil(URLCache.shared.cachedResponse(for: richiesta))
    }
}

final class ConfiguraLegaTests: XCTestCase {
    func testRiconoscimentoDelMessaggioDiLegaSenzaRose() {
        XCTAssertTrue("Il server dice: Nessuna rosa importata".dicePerNessunaRosa)
        XCTAssertTrue("nessuna ROSA importata".dicePerNessunaRosa)
        XCTAssertFalse("Non riesco a raggiungere il server. Controlla la connessione.".dicePerNessunaRosa)
    }
}

/// Gli errori con messaggio del server (429) si leggono una volta sola, con il tempo che manca in parole.
final class ErroriDelServerTests: XCTestCase {
    func testIlTempoInParole() {
        XCTAssertEqual(ErroreApi.tempoLeggibile(30), "30 secondi")
        XCTAssertEqual(ErroreApi.tempoLeggibile(600), "10 minuti")
        XCTAssertEqual(ErroreApi.tempoLeggibile(415 * 60), "6 h 55 min")
        XCTAssertEqual(ErroreApi.tempoLeggibile(3 * 3600), "3 h")
        XCTAssertEqual(ErroreApi.tempoLeggibile(72 * 3600), "3 giorni")
    }

    func testIlLimiteDiRicercheNonHaDoppioniNeRetePrivata() {
        let e = ErroreApi.troppiTentativi("Per oggi hai già fatto 20 ricerche di scambi. Riprova domani.", riprovaTra: 415 * 60)
        let testo = e.errorDescription ?? ""
        XCTAssertEqual(testo, "Per oggi hai già fatto 20 ricerche di scambi. Riprova tra 6 h 55 min.")
        XCTAssertFalse(testo.localizedCaseInsensitiveContains("rete privata"))
        XCTAssertEqual(testo.components(separatedBy: "Riprova").count - 1, 1, "una volta sola")
        XCTAssertTrue(e.eLimite)
    }

    func testSenzaAttesaIlMessaggioResta() {
        XCTAssertEqual(ErroreApi.troppiTentativi("Calma.", riprovaTra: nil).errorDescription, "Calma.")
    }

    func testIMessaggiDiReteNonParlanoSoloDiRetePrivata() {
        XCTAssertFalse((ErroreApi.rete("x").errorDescription ?? "").contains("rete privata"))
        XCTAssertTrue((ErroreApi.rete("x").errorDescription ?? "").contains("connessione"))
        XCTAssertFalse((ErroreApi.timeout.errorDescription ?? "").contains("rete privata"))
        XCTAssertFalse(ErroreApi.rete("x").eLimite)
    }
}

/// Le proposte di scambio si cercano solo su richiesta e gli stessi parametri si ricordano.
@MainActor
final class RicercheDiScambiTests: XCTestCase {
}

/// Nome visualizzato dell'utente e plurali.
final class NomeEPluraliTests: XCTestCase {
    func testSiMostraIlNomeVisualizzato() throws {
        let r: RispostaAccount = try Decodifica.decodifica(Data(#"{"multiutente": true, "utente": {"id": 3, "nome_utente": "tuttobene", "nome_visualizzato": "TuttoBene", "ruolo": "utente"}}"#.utf8))
        let u = try XCTUnwrap(r.utente)
        XCTAssertEqual(u.nome, "TuttoBene")
        XCTAssertEqual(u.nomeUtente, "tuttobene")
    }

    func testSenzaNomeVisualizzatoSiUsaIlNomeUtente() throws {
        let r: RispostaAccount = try Decodifica.decodifica(Data(#"{"multiutente": true, "utente": {"id": 3, "nome_utente": "mario", "ruolo": "utente"}}"#.utf8))
        XCTAssertEqual(r.utente?.nome, "mario")
        XCTAssertEqual(Utente(id: 1, nomeUtente: "a", ruolo: "utente", creato: nil, nomeVisualizzato: "   ").nome, "a", "un nome vuoto non conta")
    }

    func testUnUtenteSalvatoPrimaDelNuovoCampoSiLegge() throws {
        let vecchio = #"{"id": 1, "nomeUtente": "mario", "ruolo": "utente"}"#
        let u = try JSONDecoder().decode(Utente.self, from: Data(vecchio.utf8))
        XCTAssertEqual(u.nome, "mario")
    }

    func testIPlurali() {
        XCTAssertEqual(Formato.crediti(1), "1 credito")
        XCTAssertEqual(Formato.crediti(0), "0 crediti")
        XCTAssertEqual(Formato.crediti(12), "12 crediti")
        XCTAssertEqual(Formato.crediti(-1), "-1 credito")
        XCTAssertEqual(Formato.giornate(1), "1 giornata")
        XCTAssertEqual(Formato.giornate(5), "5 giornate")
        XCTAssertEqual(Formato.giocatori(1), "1 giocatore")
        XCTAssertEqual(Formato.plurale(2, "posto", "posti"), "2 posti")
    }
}
