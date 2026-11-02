import XCTest
@testable import Schieraxi

/// «Trova per me»: prima della prima ricerca un invito (non un caricamento finto); proposte di filtri vecchi segnalate.
@MainActor
final class ScambiStatoTests: XCTestCase {
    private func server() -> ServerDiProva {
        ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scambi/proposte") { return Data(#"{"proposte": []}"#.utf8) }
            throw ErroreApi.server("niente")
        }
    }

    func testPrimaDiCercareNonSembraCheStiaCaricando() async {
        let s = server()
        let vm = ScambiViewModel(server: s)
        XCTAssertTrue(vm.maiCercato, "nessuna ricerca partita: si invita a cercare")
        XCTAssertEqual(s.quante("/api/scambi/proposte"), 0)
        await vm.caricaProposte()
        XCTAssertFalse(vm.maiCercato)
        XCTAssertFalse(vm.risultatiDiAltriFiltri)
    }

    func testCambiandoIFiltriLeProposteVecchieSiSegnalano() async {
        let vm = ScambiViewModel(server: server())
        await vm.caricaProposte()
        vm.con = "Real Madrink"
        XCTAssertTrue(vm.risultatiDiAltriFiltri, "le proposte a video sono per «Tutte le squadre»")
        vm.fino = 3
        XCTAssertTrue(vm.risultatiDiAltriFiltri)
        await vm.caricaProposte()
        XCTAssertFalse(vm.risultatiDiAltriFiltri, "dopo la nuova ricerca sono quelle giuste")
        vm.con = "Tutte"
        vm.fino = 1
        XCTAssertTrue(vm.risultatiDiAltriFiltri)
    }
}
