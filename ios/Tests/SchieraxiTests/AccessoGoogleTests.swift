import XCTest
@testable import Schieraxi

// Accesso con Google: parte pura (PKCE, indirizzo di ritorno, risposte tolleranti) e giri completi con un server finto
// e un browser finto. Nessun identificativo di Google, nessun indirizzo vero: solo example.invalid.

final class AccessoGooglePuraTests: XCTestCase {
    func testSfidaPKCEConIlVettoreDellaRFC7636() {
        XCTAssertEqual(CoppiaPKCE.sfida(per: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
    }

    func testIlVerificatoreNuovoEValidoEDiverso() {
        let a = CoppiaPKCE.nuova(), b = CoppiaPKCE.nuova()
        XCTAssertTrue(CoppiaPKCE.verificatoreValido(a.verificatore))
        XCTAssertNotEqual(a.verificatore, b.verificatore)
        XCTAssertEqual(a.sfida, CoppiaPKCE.sfida(per: a.verificatore))
        XCTAssertFalse(a.sfida.contains("="))
        XCTAssertFalse(CoppiaPKCE.verificatoreValido("corto"))
        XCTAssertFalse(CoppiaPKCE.verificatoreValido(String(repeating: "a", count: 129)))
        XCTAssertFalse(CoppiaPKCE.verificatoreValido(String(repeating: "a", count: 42) + "+"))
    }

    func testIlRitornoSiLeggeDalLink() throws {
        func ritorno(_ testo: String) throws -> RitornoSocial? { RitornoSocial.interpreta(try XCTUnwrap(URL(string: testo))) }
        XCTAssertEqual(try ritorno("schieraxi://social?codice=abc123"), .codice("abc123"))
        XCTAssertEqual(try ritorno("schieraxi://social?errore=annullato"), .errore(.annullato))
        XCTAssertEqual(try ritorno("schieraxi://social?errore=scaduto"), .errore(.scaduto))
        XCTAssertEqual(try ritorno("schieraxi://social?errore=non_valido"), .errore(.nonValido))
        XCTAssertEqual(try ritorno("schieraxi://social?errore=boh"), .errore(.nonValido), "un motivo strano è un errore, non un successo")
        XCTAssertEqual(try ritorno("schieraxi://social?errore=scaduto&codice=x"), .errore(.scaduto), "l'errore vince")
        XCTAssertNil(try ritorno("schieraxi://social"))
        XCTAssertNil(try ritorno("schieraxi://social?codice="))
        XCTAssertNil(try ritorno("schieraxi://oggi?codice=abc"))
        XCTAssertNil(try ritorno("https://example.invalid/social?codice=abc"))
        XCTAssertNil(try ritorno("schieraxi://social?codice=" + String(repeating: "a", count: 201)))
        XCTAssertTrue(RitornoSocial.eRitorno(try XCTUnwrap(URL(string: "schieraxi://social?codice=x"))))
        XCTAssertNil(Collegamenti.interpreta(try XCTUnwrap(URL(string: "schieraxi://social?codice=x"))), "la navigazione dell'app lo lascia stare")
    }

    func testIServiziSociali() {
        func leggi(_ json: String) -> [String] { ServiziSociali.leggi(corpo: Data(json.utf8)) }
        XCTAssertEqual(leggi(#"{"detail": "Accesso richiesto", "social": ["google"]}"#), ["google"])
        XCTAssertEqual(leggi(#"{"social": []}"#), [])
        XCTAssertEqual(leggi(#"{"detail": "x"}"#), [], "campo mancante = nessun pulsante")
        XCTAssertEqual(leggi("<html>"), [])
        XCTAssertEqual(leggi(#"{"social": "google"}"#), [])
        XCTAssertEqual(leggi(#"{"social": ["Google", 5, "", "a b"]}"#), ["google"])
        XCTAssertTrue(ServiziSociali.googleAcceso("google"))
        XCTAssertTrue(ServiziSociali.googleAcceso("apple,google"))
        XCTAssertFalse(ServiziSociali.googleAcceso(""))
        XCTAssertFalse(ServiziSociali.googleAcceso("apple"))
    }

    func testIModiDiEntrare() throws {
        func accessi(_ json: String) throws -> AccessiAccount { try Decodifica.decodifica(Data(json.utf8)) }
        let conPassword = try accessi(#"{"password": true, "social": [{"provider": "google", "email": "a@example.invalid", "creata": "2026-11-01", "ultimo_uso": null}], "disponibili": ["google"]}"#)
        XCTAssertEqual(conPassword.google?.email, "a@example.invalid")
        XCTAssertTrue(conPassword.puoScollegareGoogle)
        XCTAssertFalse(conPassword.soloGoogle)
        let soloGoogle = try accessi(#"{"password": false, "social": [{"provider": "google"}], "disponibili": ["google"]}"#)
        XCTAssertTrue(soloGoogle.soloGoogle)
        XCTAssertFalse(soloGoogle.puoScollegareGoogle, "non si toglie l'unico modo per entrare")
        let senzaGoogle = try accessi(#"{"password": true, "social": [], "disponibili": ["google"]}"#)
        XCTAssertNil(senzaGoogle.google)
        XCTAssertFalse(senzaGoogle.puoScollegareGoogle)
        let strano = try accessi(#"{"password": "boh", "social": "x"}"#)
        XCTAssertNil(strano.password)
        XCTAssertEqual(strano.social, [])
        XCTAssertFalse(strano.puoScollegareGoogle)
    }

    func testIndirizzoDiAvvioSoloHttps() {
        XCTAssertNotNil(IndirizzoAvvioSocial.valido("https://accounts.google.com/o/oauth2/v2/auth?x=1"))
        XCTAssertNil(IndirizzoAvvioSocial.valido("https://accesso.example.invalid/auth?x=1"))
        XCTAssertNil(IndirizzoAvvioSocial.valido("https://accounts.google.com.example.invalid/auth"))
        XCTAssertNil(IndirizzoAvvioSocial.valido("http://accesso.example.invalid/auth"))
        XCTAssertNil(IndirizzoAvvioSocial.valido("javascript:alert(1)"))
        XCTAssertNil(IndirizzoAvvioSocial.valido("https://utente:segreto@example.invalid/"))
        XCTAssertNil(IndirizzoAvvioSocial.valido(""))
        XCTAssertNil(IndirizzoAvvioSocial.valido(nil))
    }

    func testNomeSuggerito() {
        XCTAssertEqual(NomeSuggerito.pulito("Mario.Rossi@example.invalid"), "mario.rossi")
        XCTAssertEqual(NomeSuggerito.pulito("  Mario Rossi "), "mario-rossi")
        XCTAssertEqual(NomeSuggerito.pulito("...ab"), "ab")
        XCTAssertEqual(NomeSuggerito.pulito(nil), "")
        XCTAssertLessThanOrEqual(NomeSuggerito.pulito(String(repeating: "a", count: 80)).count, 32)
    }

    func testIlCodiceDelServerFaDireLaFraseGiusta() {
        let e = ErroreApi.codificato(codice: "serve_riconferma", messaggio: "Conferma prima con Google")
        XCTAssertTrue(e.localizedDescription.contains("conferma prima con Google"))
        XCTAssertEqual(ErroreApi.codificato(codice: "boh", messaggio: "Messaggio del server").localizedDescription, "Messaggio del server")
        XCTAssertEqual(ServerHTTP.codiceErrore(Data(#"{"detail": "x", "codice": "ultimo_accesso"}"#.utf8)), "ultimo_accesso")
        XCTAssertNil(ServerHTTP.codiceErrore(Data(#"{"detail": "x"}"#.utf8)))
        XCTAssertNil(ServerHTTP.codiceErrore(Data(#"{"codice": "Strano Codice!"}"#.utf8)))
        for codice in ["email_gia_usata", "email_non_affidabile", "google_gia_collegato", "google_diverso", "ultimo_accesso", "serve_riconferma"] {
            XCTAssertNotNil(TestiSocial.errore(codice: codice), codice)
        }
    }
}

/// Un browser finto: risponde con il link deciso dal test e ricorda cosa gli è stato chiesto di aprire.
final class AvvioFinto: AvvioWeb, @unchecked Sendable {
    var risposta: Result<URL, Error>
    private(set) var aperti: [(url: URL, schema: String)] = []
    init(_ risposta: Result<URL, Error>) { self.risposta = risposta }
    convenience init(codice: String) { self.init(.success(URL(string: "schieraxi://social?codice=\(codice)")!)) }
    @MainActor func apri(_ url: URL, schema: String) async throws -> URL {
        aperti.append((url, schema))
        return try risposta.get()
    }
}

@MainActor
final class SessioneGoogleTests: XCTestCase {
    private var memoria: UserDefaults!
    private var archivio: MemoriaToken!
    private let nomeSuite = "prova-google-\(UUID().uuidString)"
    private let utenteJSON = #"{"id": 7, "nome_utente": "mister.rossi", "ruolo": "utente", "creato": "2026-11-01"}"#
    private let avviato = #"{"url": "https://accounts.google.com/o/oauth2/v2/auth?s=1", "scade_minuti": 10}"#

    override func setUp() {
        super.setUp()
        memoria = UserDefaults(suiteName: nomeSuite)
        archivio = MemoriaToken()
        memoria.set(true, forKey: "account.multiutente")
    }

    override func tearDown() {
        memoria.removePersistentDomain(forName: nomeSuite)
        super.tearDown()
    }

    private func sessione(_ server: ServerClient) -> SessioneAccount {
        SessioneAccount(server: server, archivio: archivio, memoria: memoria, pulisci: {})
    }

    /// Un server che risponde a `inizia` e allo `scambio`/`completa` con quello che passa il test.
    private func server(scambio: String = #"{"stato": "ok"}"#, extra: (@Sendable (String, String) throws -> Data?)? = nil) -> ServerDiProva {
        let avviato = self.avviato, utente = utenteJSON
        return ServerDiProva { metodo, percorso, _ in
            if let extra, let dati = try extra(metodo, percorso) { return dati }
            switch percorso {
            case "/api/account/social/google/inizia": return Data(avviato.utf8)
            case "/api/account/social/scambio":
                if scambio.contains("\"ok\"") { return Data(#"{"stato": "ok", "multiutente": true, "utente": \#(utente), "token": "tok-g"}"#.utf8) }
                return Data(scambio.utf8)
            case "/api/account/social/completa": return Data(#"{"stato": "ok", "multiutente": true, "utente": \#(utente), "token": "tok-nuovo"}"#.utf8)
            default: return Data("{}".utf8)
            }
        }
    }

    private func corpo(_ s: ServerDiProva, _ percorso: String) throws -> [String: Any] {
        let dati = try XCTUnwrap(s.corpiInviati(a: percorso).last, "nessun corpo inviato a \(percorso)")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: dati) as? [String: Any])
    }

    func testAccessoConGoogleDiUnAccountEsistente() async throws {
        let s = server()
        let sess = sessione(s)
        let browser = AvvioFinto(codice: "cod-1")
        let esito = try await sess.accediConGoogle(avvio: browser)
        XCTAssertEqual(esito, .entrato)
        XCTAssertEqual(sess.utente?.nomeUtente, "mister.rossi")
        XCTAssertEqual(archivio.leggi(server: s.indirizzo), "tok-g", "il token sta nell'archivio sicuro")
        // al browser: solo l'indirizzo del server, con lo schema di ritorno dell'app
        XCTAssertEqual(browser.aperti.count, 1)
        XCTAssertEqual(browser.aperti.first?.url.absoluteString, "https://accounts.google.com/o/oauth2/v2/auth?s=1")
        XCTAssertEqual(browser.aperti.first?.schema, "schieraxi")
        // al server: la sfida all'inizio, il verificatore (che la produce) alla fine; mai insieme
        let inizio = try corpo(s, "google/inizia"), fine = try corpo(s, "social/scambio")
        XCTAssertEqual(inizio["scopo"] as? String, "accedi")
        XCTAssertEqual(inizio["piattaforma"] as? String, "ios")
        XCTAssertNil(inizio["verificatore"])
        let verificatore = try XCTUnwrap(fine["verificatore"] as? String)
        XCTAssertEqual(CoppiaPKCE.sfida(per: verificatore), inizio["sfida"] as? String)
        XCTAssertEqual(fine["codice"] as? String, "cod-1")
        XCTAssertEqual(fine["nativo"] as? Bool, true)
    }

    func testAccountNuovoChiedeIlNomeUtente() async throws {
        let s = server(scambio: #"{"stato": "nuovo", "iscrizione": "isc-1", "provider": "google", "nome_suggerito": "Mario Rossi", "serve_invito": true}"#)
        let sess = sessione(s)
        let esito = try await sess.accediConGoogle(avvio: AvvioFinto(codice: "c"))
        guard case .nuovoAccount(let nuovo) = esito else { return XCTFail("doveva chiedere il nome: \(esito)") }
        XCTAssertEqual(nuovo.iscrizione, "isc-1")
        XCTAssertTrue(nuovo.serveInvito)
        XCTAssertEqual(NomeSuggerito.pulito(nuovo.nomeSuggerito), "mario-rossi")
        XCTAssertEqual(sess.stato, .daAccedere, "finché non sceglie il nome non è dentro")
        XCTAssertNil(archivio.leggi(server: s.indirizzo))

        try await sess.completaConGoogle(nuovo, nomeUtente: "  Mister.Rossi ", invito: " abc-123 ", accettoTermini: true)
        XCTAssertEqual(sess.utente?.nomeUtente, "mister.rossi")
        XCTAssertEqual(archivio.leggi(server: s.indirizzo), "tok-nuovo")
        XCTAssertNil(sess.codiceDaMostrare, "con Google non c'è un codice di recupero da salvare")
        let c = try corpo(s, "social/completa")
        XCTAssertEqual(c["iscrizione"] as? String, "isc-1")
        XCTAssertEqual(c["nome_utente"] as? String, "mister.rossi")
        XCTAssertEqual(c["invito"] as? String, "ABC-123")
        XCTAssertEqual(c["accetto_termini"] as? Bool, true)
        XCTAssertEqual(c["nativo"] as? Bool, true)
    }

    func testSenzaInvitoNonSiManda() async throws {
        let s = server(scambio: #"{"stato": "nuovo", "iscrizione": "isc-2", "serve_invito": false}"#)
        let sess = sessione(s)
        guard case .nuovoAccount(let nuovo) = try await sess.accediConGoogle(avvio: AvvioFinto(codice: "c")) else { return XCTFail() }
        XCTAssertFalse(nuovo.serveInvito)
        try await sess.completaConGoogle(nuovo, nomeUtente: "mister.rossi", invito: "  ", accettoTermini: true)
        XCTAssertNil(try corpo(s, "social/completa")["invito"])
    }

    func testChiHaChiusoLaFinestraNonFaNiente() async {
        let s = server()
        let sess = sessione(s)
        do {
            _ = try await sess.accediConGoogle(avvio: AvvioFinto(.failure(ErroreSocial.annullato)))
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertEqual(error as? ErroreSocial, .annullato)
        }
        XCTAssertEqual(s.quante("social/scambio"), 0, "senza codice non si chiede la sessione")
        XCTAssertFalse(sess.inCorso, "il pulsante si riaccende")
        XCTAssertNil(archivio.leggi(server: s.indirizzo))
    }

    func testErroriDelRitornoSonoFrasiSemplici() async throws {
        for (testo, atteso) in [("annullato", ErroreSocial.annullato), ("scaduto", .scaduto), ("non_valido", .nonValido)] {
            let s = server()
            let sess = sessione(s)
            let browser = AvvioFinto(.success(try XCTUnwrap(URL(string: "schieraxi://social?errore=\(testo)"))))
            do {
                _ = try await sess.accediConGoogle(avvio: browser)
                XCTFail("doveva fermarsi")
            } catch {
                XCTAssertEqual(error as? ErroreSocial, atteso)
                XCTAssertFalse(error.localizedDescription.isEmpty)
            }
            XCTAssertEqual(s.quante("social/scambio"), 0)
        }
    }

    func testUnRitornoStranoNonApreLaSessione() async {
        let s = server()
        let sess = sessione(s)
        do {
            _ = try await sess.accediConGoogle(avvio: AvvioFinto(.success(URL(string: "schieraxi://oggi")!)))
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertEqual(error as? ErroreSocial, .nonValido)
        }
        XCTAssertEqual(s.quante("social/scambio"), 0)
    }

    func testUnIndirizzoDiAvvioNonHttpsNonSiApre() async {
        let s = ServerDiProva { _, _, _ in Data(#"{"url": "http://accesso.example.invalid/auth"}"#.utf8) }
        let browser = AvvioFinto(codice: "c")
        do {
            _ = try await sessione(s).accediConGoogle(avvio: browser)
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertEqual(error as? SessioneAccount.Errore, .rispostaNonValida)
        }
        XCTAssertTrue(browser.aperti.isEmpty)
    }

    func testIlServerCheNonDaIlTokenNonFaEntrare() async {
        let s = server(scambio: #"{"stato": "ok"}"#, extra: { _, p in
            p == "/api/account/social/scambio" ? Data(#"{"stato": "ok", "utente": {"id": 1, "nome_utente": "x", "ruolo": "utente"}}"#.utf8) : nil
        })
        let sess = sessione(s)
        do {
            _ = try await sess.accediConGoogle(avvio: AvvioFinto(codice: "c"))
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertEqual(sess.stato, .daAccedere)
        }
    }

    func testErroreDelServerConCodice() async {
        let s = server(extra: { _, p in
            if p == "/api/account/social/scambio" { throw ErroreApi.codificato(codice: "email_gia_usata", messaggio: "Esiste già") }
            return nil
        })
        do {
            _ = try await sessione(s).accediConGoogle(avvio: AvvioFinto(codice: "c"))
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertTrue(SchermataAccesso.testoErrore(error).contains("collega Google da Impostazioni"))
        }
    }

    // MARK: da dentro l'account

    func testCollegaGoogle() async throws {
        let s = server(scambio: #"{"stato": "collegato", "accessi": {"password": true, "social": [{"provider": "google", "email": "a@example.invalid"}], "disponibili": ["google"]}}"#)
        let sess = sessione(s)
        try await sess.collegaGoogle(password: "p", avvio: AvvioFinto(codice: "c"))
        XCTAssertEqual(try corpo(s, "google/inizia")["scopo"] as? String, "collega")
        XCTAssertEqual(try corpo(s, "google/inizia")["password"] as? String, "p")
        XCTAssertEqual(sess.accessi?.google?.email, "a@example.invalid")
        XCTAssertTrue(sess.accessi?.puoScollegareGoogle ?? false)
    }

    func testRiconfermaGoogle() async throws {
        let s = server(scambio: #"{"stato": "riconfermato"}"#)
        try await sessione(s).riconfermaGoogle(avvio: AvvioFinto(codice: "c"))
        XCTAssertEqual(try corpo(s, "google/inizia")["scopo"] as? String, "riconferma")
    }

    func testRispostaSbagliataAllaRiconfermaNonVale() async {
        let s = server(scambio: #"{"stato": "collegato"}"#)
        do {
            try await sessione(s).riconfermaGoogle(avvio: AvvioFinto(codice: "c"))
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertEqual(error as? SessioneAccount.Errore, .rispostaNonValida)
        }
    }

    func testScollegaGoogle() async throws {
        let s = server(extra: { m, p in
            m == "DELETE" && p == "/api/account/social/google" ? Data(#"{"accessi": {"password": true, "social": [], "disponibili": ["google"]}}"#.utf8) : nil
        })
        let sess = sessione(s)
        try await sess.scollegaGoogle()
        XCTAssertNil(sess.accessi?.google)
        XCTAssertEqual(s.quante("DELETE /api/account/social/google"), 1)
    }

    func testScollegareLUltimoAccessoDaUnMessaggioChiaro() async {
        let s = server(extra: { m, _ in
            if m == "DELETE" { throw ErroreApi.codificato(codice: "ultimo_accesso", messaggio: "Prima aggiungi una password o un altro accesso.") }
            return nil
        })
        do {
            try await sessione(s).scollegaGoogle()
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertTrue(SchermataAccesso.testoErrore(error).contains("Prima aggiungi una password"))
        }
    }

    func testAggiungereUnaPasswordMostraIlCodiceDiRecupero() async throws {
        let s = server(extra: { _, p in
            p == "/api/account/imposta-password" ? Data(#"{"ok": true, "codice_recupero": "AAAAA-BBBBB-CCCCC"}"#.utf8) : nil
        })
        let sess = sessione(s)
        try await sess.impostaPassword("Prova-Finta-Zero")
        XCTAssertEqual(sess.codiceDaMostrare, "AAAAA-BBBBB-CCCCC")
        XCTAssertEqual(try corpo(s, "imposta-password")["password"] as? String, "Prova-Finta-Zero")
    }

    // MARK: cosa dichiara il server

    func testLaVerificaLeggeSocialEAccessi() async {
        let utente = utenteJSON
        let s = ServerDiProva { _, p, _ in
            p == "/api/account/me"
                ? Data(#"{"multiutente": true, "utente": \#(utente), "social": ["google"], "accessi": {"password": false, "social": [{"provider": "google", "email": "a@example.invalid"}], "disponibili": ["google"]}}"#.utf8)
                : Data("{}".utf8)
        }
        archivio.salva("tok", server: s.indirizzo)
        let sess = sessione(s)
        await sess.verifica()
        XCTAssertTrue(ServiziSociali.googleAcceso(in: memoria))
        XCTAssertTrue(sess.senzaPassword)
        XCTAssertFalse(sess.accessi?.puoScollegareGoogle ?? true)
    }

    func testSeIlServerSpegneGoogleIPulsantiSpariscono() async {
        ServiziSociali.salva(["google"], in: memoria)
        let utente = utenteJSON
        let s = ServerDiProva { _, p, _ in p == "/api/account/me" ? Data(#"{"multiutente": true, "utente": \#(utente)}"#.utf8) : Data("{}".utf8) }
        archivio.salva("tok", server: s.indirizzo)
        let sess = sessione(s)
        await sess.verifica()
        XCTAssertFalse(ServiziSociali.googleAcceso(in: memoria), "campo mancante = spento")
        XCTAssertNil(sess.accessi)
        XCTAssertFalse(sess.senzaPassword)
    }

    func testCambiandoServerOUscendoGliAccessiSiDimenticano() async throws {
        let s = server(scambio: #"{"stato": "collegato", "accessi": {"password": true, "social": [{"provider": "google"}]}}"#)
        let sess = sessione(s)
        archivio.salva("tok", server: s.indirizzo)
        try await sess.collegaGoogle(password: "p", avvio: AvvioFinto(codice: "c"))
        XCTAssertNotNil(sess.accessi)
        await sess.esci()
        XCTAssertNil(sess.accessi)
    }

    // MARK: con il server finto dell'app (FinteServer)

    func testConIlServerFintoPerOgniStato() async throws {
        let utente = utenteJSON
        let base = ["/api/account/social/google/inizia": avviato]
        // ok
        var finto = FinteServer(risposte: base.merging(["/api/account/social/scambio": #"{"stato": "ok", "utente": \#(utente), "token": "tok-f"}"#]) { $1 })
        finto.indirizzoFinto = "https://finto-google-ok.invalid"
        let uno = sessione(finto)
        let esitoOk = try await uno.accediConGoogle(avvio: AvvioFinto(codice: "c"))
        XCTAssertEqual(esitoOk, .entrato)
        // nuovo
        finto.risposte["/api/account/social/scambio"] = #"{"stato": "nuovo", "iscrizione": "i", "nome_suggerito": "x"}"#
        finto.indirizzoFinto = "https://finto-google-nuovo.invalid"
        let esitoNuovo = try await sessione(finto).accediConGoogle(avvio: AvvioFinto(codice: "c"))
        XCTAssertEqual(esitoNuovo, .nuovoAccount(NuovoAccountSocial(iscrizione: "i", provider: "google", nomeSuggerito: "x", serveInvito: false)))
        // collegato e riconfermato
        finto.risposte["/api/account/social/scambio"] = #"{"stato": "collegato", "accessi": {"password": true, "social": [{"provider": "google"}]}}"#
        let due = sessione(finto)
        try await due.collegaGoogle(password: "p", avvio: AvvioFinto(codice: "c"))
        XCTAssertNotNil(due.accessi?.google)
        finto.risposte["/api/account/social/scambio"] = #"{"stato": "riconfermato"}"#
        try await sessione(finto).riconfermaGoogle(avvio: AvvioFinto(codice: "c"))
        // errore del server
        finto.errori = ["/api/account/social/google/inizia": "Non trovato"]
        do {
            _ = try await sessione(finto).accediConGoogle(avvio: AvvioFinto(codice: "c"))
            XCTFail("doveva fermarsi")
        } catch {
            XCTAssertEqual(SchermataAccesso.testoErrore(error), "Non trovato")
        }
    }
}
