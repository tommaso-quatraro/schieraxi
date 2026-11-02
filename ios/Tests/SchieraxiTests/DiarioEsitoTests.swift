import XCTest
@testable import Schieraxi

/// Diario: l'esito di «Ho schierato…» sa a quale giornata appartiene (si mostra nella sua sezione) e usa il numero della lega.
@MainActor
final class DiarioEsitoTests: XCTestCase {
    func testLEsitoStaConLaSuaGiornata() async {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/diario/schierata") { return Data("{}".utf8) }
            return Data(#"{"giornate": []}"#.utf8)
        }
        let vm = DiarioViewModel(server: s)
        await vm.haSchieratoLaConsigliata(giornata: 11, numero: 8)
        XCTAssertEqual(vm.giornataDelMessaggio, 11)
        XCTAssertTrue(vm.messaggioRiuscito)
        XCTAssertEqual(vm.messaggio, "Salvato: per la giornata 8 hai schierato la consigliata.")
    }

    func testUnErroreStaAncheLuiConLaSuaGiornata() async {
        let vm = DiarioViewModel(server: ServerDiProva.chePrecipita(.server("Giornata non valida")))
        await vm.haSchieratoLaConsigliata(giornata: 3)
        XCTAssertEqual(vm.giornataDelMessaggio, 3)
        XCTAssertFalse(vm.messaggioRiuscito)
        XCTAssertEqual(vm.messaggio, "Giornata non valida")
    }
}
