import XCTest
@testable import Schieraxi

/// Modulo dai ruoli, validità della scelta salvata e come si legge una pedina del campo.
final class StatoSceltaTests: XCTestCase {
    private let scelti = Array(1...11)

    // stati e frasi della riga di stato: `RigaStatoComeWebTests` (confrontati con la web)

    func testIlModuloSiContaDaiRuoli() {
        XCTAssertEqual(ModuloTitolari.modulo(ruoli: ["P", "D", "D", "D", "C", "C", "C", "C", "A", "A", "A"]), "3-4-3")
        XCTAssertEqual(ModuloTitolari.modulo(ruoli: []), "0-0-0")
    }

    func testValiditaDellaSceltaSoloConLaRosa() throws {
        let rosa: [String: Giocatore] = try Dictionary(uniqueKeysWithValues: (1...12).map { id in
            (String(id), try Decodifica.decodifica(Data("{\"id\": \(id), \"nome\": \"Prova \(id)\", \"ruolo\": \"C\"}".utf8)) as Giocatore)
        })
        XCTAssertEqual(ValiditaScelta.controlla(titolari: scelti, rosa: rosa), .valida)
        XCTAssertEqual(ValiditaScelta.controlla(titolari: Array(1...10), rosa: rosa), .nonValida)
        XCTAssertEqual(ValiditaScelta.controlla(titolari: Array(1...10) + [1], rosa: rosa), .nonValida, "doppioni")
        XCTAssertEqual(ValiditaScelta.controlla(titolari: Array(2...12), rosa: [:]), .nonSiSa, "rosa vuota: non si giudica")
        XCTAssertEqual(ValiditaScelta.controlla(titolari: Array(1...10), rosa: nil), .nonSiSa, "senza rosa: non si giudica")
        XCTAssertEqual(ValiditaScelta.controlla(titolari: Array(1...10) + [77], rosa: rosa), .nonValida, "uno fuori rosa")
    }

    // MARK: pedina del campo

    func testLaPedinaSiLeggeAParole() {
        XCTAssertEqual(LetturaPedina.gioca(0.85), "gioca 85%")
        XCTAssertNil(LetturaPedina.gioca(nil))
        // la soglia della web e della scheda (`SogliaGioca`, #673): sotto l'80% sul numero che si legge
        XCTAssertTrue(LetturaPedina.incerto(0.45))
        XCTAssertTrue(LetturaPedina.incerto(0.79))
        XCTAssertFalse(LetturaPedina.incerto(0.80))
        XCTAssertFalse(LetturaPedina.incerto(0.796), "si legge «80%»")
        XCTAssertFalse(LetturaPedina.incerto(nil), "senza probabilità niente avviso")
        XCTAssertEqual(LetturaPedina.prefisso(inCasa: true), "vs")
        XCTAssertEqual(LetturaPedina.prefisso(inCasa: false), "@")
        XCTAssertNil(LetturaPedina.prefisso(inCasa: nil))
        XCTAssertEqual(LetturaPedina.nomeSquadra("napoli"), "Napoli")
        XCTAssertEqual(LetturaPedina.nomeSquadra("XYZ"), "XYZ")
        XCTAssertNil(LetturaPedina.nomeSquadra(" "))
        XCTAssertEqual(LetturaPedina.voce(nome: "Mario Prova", ruolo: "difensore", fvAtteso: 6.5, pVoto: 0.45, avversario: "napoli", inCasa: false),
                       "Mario Prova, difensore, fantavoto atteso 6,5, gioca al 45 per cento, non è sicuro di giocare, avversario Napoli, in trasferta")
    }

    func testIlTestoDelDistintivoSiLegge() {
        XCTAssertTrue(LetturaPedina.testoScuro(suEsadecimale: "f3f4f6"), "fondo bianco: testo scuro")
        XCTAssertFalse(LetturaPedina.testoScuro(suEsadecimale: "0a58a8"), "fondo blu scuro: testo chiaro")
        XCTAssertFalse(LetturaPedina.testoScuro(suEsadecimale: "111827"))
        XCTAssertTrue(LetturaPedina.testoScuro(suEsadecimale: "f2d200"), "giallo: testo scuro")
    }
}
