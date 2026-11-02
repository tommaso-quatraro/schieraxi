import XCTest
@testable import Schieraxi

/// Chi aggiorna da una versione vecchia con un indirizzo di rete privata salvato passa al server predefinito.
/// Nei test solo indirizzi inventati (`example`, `invalid`).
@MainActor
final class MigrazioneServerTests: XCTestCase {
    private var memoria: UserDefaults!
    private let nomeSuite = "prova-migrazione-\(UUID().uuidString)"
    private var pulizie = 0
    // Il suffisso è composto a pezzi: nel repository pubblico non deve comparire come testo intero.
    private let suffisso = ".ts" + ".net"
    private var privato: String { "https://nodo-di-prova.esempio" + suffisso }

    override func setUp() {
        super.setUp()
        memoria = UserDefaults(suiteName: nomeSuite)
    }

    override func tearDown() {
        memoria.removePersistentDomain(forName: nomeSuite)
        super.tearDown()
    }

    func testRiconosceSoloLaReteprivata() {
        XCTAssertTrue(MigrazioneServer.eReteprivata("https://a.b" + suffisso))
        XCTAssertTrue(MigrazioneServer.eReteprivata("https://A" + suffisso.uppercased() + ":8443"))
        XCTAssertFalse(MigrazioneServer.eReteprivata("https://server.example"))
        XCTAssertFalse(MigrazioneServer.eReteprivata("https://" + String(suffisso.dropFirst()) + ".example.com"))
        XCTAssertFalse(MigrazioneServer.eReteprivata("https://nots" + String(suffisso.dropFirst(3)) + ".example"))
    }

    func testIndirizzoPredefinitoOVuotoNonSiTocca() {
        XCTAssertNil(MigrazioneServer.migraSubito(memoria))
        memoria.set(Config.indirizzoPredefinito + "/", forKey: "indirizzo")
        XCTAssertNil(MigrazioneServer.migraSubito(memoria))
        XCTAssertFalse(memoria.bool(forKey: MigrazioneServer.chiaveSpostato))
    }

    func testIndirizzoProprioNonDiReteprivataResta() {
        memoria.set("https://mio-server.example", forKey: "indirizzo")
        XCTAssertNil(MigrazioneServer.migraSubito(memoria))
        XCTAssertEqual(memoria.string(forKey: "indirizzo"), "https://mio-server.example")
    }

    func testReteprivataSiSostituisceConIlPredefinito() {
        memoria.set(privato + "/", forKey: "indirizzo")
        XCTAssertEqual(MigrazioneServer.migraSubito(memoria), privato)
        XCTAssertNil(memoria.string(forKey: "indirizzo"))
        XCTAssertTrue(memoria.bool(forKey: MigrazioneServer.chiaveSpostato))
    }

    func testNonRisponde_DueProveFalliteEIlPredefinitoRisponde() async {
        memoria.set(privato, forKey: "indirizzo")
        var chiamate: [String] = []
        let cambiato = await MigrazioneServer.migraSeIrraggiungibile(memoria) { indirizzo in
            chiamate.append(indirizzo)
            return indirizzo == Config.indirizzoPredefinito ? .raggiunto(versione: nil, squadra: nil) : .nonRaggiungibile
        }
        XCTAssertTrue(cambiato)
        XCTAssertEqual(chiamate.filter { $0 == privato }.count, 2)
        XCTAssertNil(memoria.string(forKey: "indirizzo"))
        XCTAssertTrue(memoria.bool(forKey: MigrazioneServer.chiaveSpostato))
    }

    func testServerScelto_DallUtenteNonSiToccaMaiDaSolo() async {
        memoria.set("https://mio-server.example", forKey: "indirizzo")
        var chiamate = 0
        let cambiato = await MigrazioneServer.migraSeIrraggiungibile(memoria) { indirizzo in
            chiamate += 1
            return indirizzo == Config.indirizzoPredefinito ? .raggiunto(versione: nil, squadra: nil) : .nonRaggiungibile
        }
        XCTAssertFalse(cambiato, "un server proprio che non risponde per un po' non fa perdere token e dati")
        XCTAssertEqual(chiamate, 0, "nemmeno si prova")
        XCTAssertEqual(memoria.string(forKey: "indirizzo"), "https://mio-server.example")
        XCTAssertFalse(memoria.bool(forKey: MigrazioneServer.chiaveSpostato))
    }

    func testTelefonoOffline_NienteCambia() async {
        memoria.set("https://mio-server.example", forKey: "indirizzo")
        let cambiato = await MigrazioneServer.migraSeIrraggiungibile(memoria) { _ in .nonRaggiungibile }
        XCTAssertFalse(cambiato)
        XCTAssertEqual(memoria.string(forKey: "indirizzo"), "https://mio-server.example")
    }

    func testServerChePrimaOPoiRisponde_Resta() async {
        memoria.set("https://mio-server.example", forKey: "indirizzo")
        var volte = 0
        let cambiato = await MigrazioneServer.migraSeIrraggiungibile(memoria) { indirizzo in
            if indirizzo == Config.indirizzoPredefinito { return .raggiunto(versione: nil, squadra: nil) }
            volte += 1
            return volte == 1 ? .timeout : .chiedeAccesso
        }
        XCTAssertFalse(cambiato)
        XCTAssertEqual(memoria.string(forKey: "indirizzo"), "https://mio-server.example")
    }

    func testServerCheRispondeConUnErrore_Resta() async {
        memoria.set("https://mio-server.example", forKey: "indirizzo")
        let cambiato = await MigrazioneServer.migraSeIrraggiungibile(memoria) { indirizzo in
            indirizzo == Config.indirizzoPredefinito ? .raggiunto(versione: nil, squadra: nil) : .erroreServer(500)
        }
        XCTAssertFalse(cambiato)
    }

    func testLaSessioneDelVecchioServerSiButtaEsiParteDallAccesso() {
        let archivio = MemoriaToken()
        archivio.salva("token-di-prova", server: privato)
        memoria.set(privato, forKey: "indirizzo")
        memoria.set(privato, forKey: "account.indirizzo")
        memoria.set(true, forKey: "account.multiutente")
        let server = ServerDiProva { _, _, _ in Data("{}".utf8) }
        let sessione = SessioneAccount(server: server, archivio: archivio, memoria: memoria, pulisci: { [unowned self] in pulizie += 1 })
        XCTAssertEqual(sessione.stato, .daAccedere)
        XCTAssertTrue(sessione.serverSpostato)
        XCTAssertNil(archivio.leggi(server: privato))
        XCTAssertEqual(pulizie, 1)
        XCTAssertEqual(memoria.string(forKey: "account.indirizzo"), server.indirizzo)
    }
}
