import XCTest
@testable import Schieraxi

/// Regole e crediti: una modifica non salvata non si perde ricaricando (cambio di scheda, comando «Aggiorna»).
@MainActor
final class ModificheNonSalvateTests: XCTestCase {
    func testLeRegoleCambiateNonSiPerdonoRicaricando() async {
        let s = ServerDiProva.conFixture(["/api/regole": "regole"])
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        XCTAssertTrue(vm.caricato)
        let prima = vm.valore
        vm.numero("bonus.assist", 1).wrappedValue = 9.5
        XCTAssertTrue(vm.modificato)

        await vm.carica()   // come tornando sulla schermata
        XCTAssertTrue(vm.modificato, "la modifica è ancora lì")
        XCTAssertEqual(vm.numero("bonus.assist").wrappedValue, 9.5)
        XCTAssertEqual(s.quante("GET /api/regole"), 2, "le regole si rileggono comunque")

        await vm.annulla()
        XCTAssertFalse(vm.modificato, "«Annulla le modifiche» riparte dal server")
        XCTAssertEqual(vm.valore, prima)
    }

    func testLeRegoleCambiateAltroveSiRileggonoDopoUnConflitto() async {
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT" { throw ErroreApi.conflitto }
            if percorso.hasPrefix("/api/regole") { return try Fixture.dati("regole") }
            return Data("{}".utf8)
        }
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        let prima = vm.valore
        vm.numero("bonus.assist", 1).wrappedValue = 9.5
        await vm.salva()
        XCTAssertFalse(vm.modificato, "dopo il conflitto si vedono le regole nuove del server")
        XCTAssertEqual(vm.valore, prima)
    }

}
