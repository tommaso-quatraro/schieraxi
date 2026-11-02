import XCTest
@testable import Schieraxi

/// Una risposta di /api/giocatori con `n` giocatori finti.
private func elencoFinto(_ n: Int) -> Data {
    let voci = (0..<n).map { #"{"id": \#($0 + 1), "nome": "Giocatore \#($0 + 1)", "ruolo": "C", "squadra": "inter", "quotazione": 10}"# }
    return Data("[\(voci.joined(separator: ","))]".utf8)
}

@MainActor
final class RicercaMercatoTests: XCTestCase {
    func testSottoDueLettereNonSiCerca() async {
        let s = ServerDiProva { _, _, _ in elencoFinto(3) }
        let vm = RicercaMercatoViewModel(server: s)
        vm.testo = " a "
        await vm.cerca()
        XCTAssertEqual(s.quante("/api/giocatori"), 0)
        XCTAssertTrue(vm.visibili.isEmpty)
        XCTAssertFalse(vm.abbastanzaLungo)
    }

    func testRisultatiAPagineConMostraAltri() async {
        let s = ServerDiProva { _, _, _ in elencoFinto(45) }
        let vm = RicercaMercatoViewModel(server: s)
        vm.testo = "gio"
        await vm.cerca()
        XCTAssertEqual(vm.trovati.count, 45)
        XCTAssertEqual(vm.visibili.count, RicercaMercatoViewModel.perPagina, "all'inizio solo la prima pagina")
        XCTAssertTrue(vm.ciSonoAltri)
        vm.mostraAltri()
        XCTAssertEqual(vm.visibili.count, 40)
        vm.mostraAltri()
        XCTAssertEqual(vm.visibili.count, 45, "non oltre quelli trovati")
        XCTAssertFalse(vm.ciSonoAltri)
    }

    func testLaRichiestaChiedeUnLimiteEIlTestoRipulito() async {
        let s = ServerDiProva { _, _, _ in elencoFinto(1) }
        let vm = RicercaMercatoViewModel(server: s)
        vm.testo = "  Mar Co "
        await vm.cerca()
        XCTAssertEqual(s.quante("GET /api/giocatori?limite=\(RicercaMercatoViewModel.daChiedere)&q=mar%20co"), 1)
    }

    func testLaStessaRicercaNonSiRifaENemmenoTornandoIndietro() async {
        let s = ServerDiProva { _, _, _ in elencoFinto(2) }
        let vm = RicercaMercatoViewModel(server: s)
        vm.testo = "mar"
        await vm.cerca()
        await vm.cerca()                      // stesso testo: niente di nuovo
        vm.testo = "mari"
        await vm.cerca()
        vm.testo = "mar"                      // si è cancellata una lettera: risposta dalla memoria
        await vm.cerca()
        XCTAssertEqual(s.quante("/api/giocatori"), 2)
        XCTAssertEqual(vm.trovati.count, 2)
    }

    func testUnaRicercaAnnullataNonArrivaAlServer() async {
        let s = ServerDiProva { _, _, _ in elencoFinto(2) }
        let vm = RicercaMercatoViewModel(server: s)
        vm.testo = "mar"
        let t = Task { await vm.cerca() }
        t.cancel()
        await t.value
        XCTAssertEqual(s.quante("/api/giocatori"), 0, "si è continuato a scrivere durante la pausa")
    }

    func testErroreENessunRisultato() async {
        let vm = RicercaMercatoViewModel(server: ServerDiProva.chePrecipita())
        vm.testo = "mar"
        await vm.cerca()
        XCTAssertNotNil(vm.errore)
        XCTAssertFalse(vm.nessunRisultato, "con un errore non si dice «nessun risultato»")
        let vuoto = RicercaMercatoViewModel(server: ServerDiProva { _, _, _ in Data("[]".utf8) })
        vuoto.testo = "zzz"
        await vuoto.cerca()
        XCTAssertTrue(vuoto.nessunRisultato)
    }

    func testLaRicercaNonFaRidisegnareMercato() {
        let mercato = MercatoViewModel(server: ServerDiProva { _, _, _ in Data("[]".utf8) })
        var cambi = 0
        let ascolto = mercato.objectWillChange.sink { _ in cambi += 1 }
        defer { ascolto.cancel() }
        mercato.testoRicerca = "mar"
        mercato.testoRicerca = "mari"
        XCTAssertEqual(cambi, 0, "scrivendo nella ricerca cambia solo la vista dei risultati")
        XCTAssertEqual(mercato.ricerca.testo, "mari")
    }
}
