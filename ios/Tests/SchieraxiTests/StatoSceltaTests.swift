import XCTest
@testable import Schieraxi

/// La riga di stato della Formazione (scelta salvata o no) e come si legge una pedina del campo.
final class StatoSceltaTests: XCTestCase {
    private let scelti = Array(1...11)

    private func data(_ testo: String) throws -> Date { try XCTUnwrap(Quando.data(testo)) }

    func testGliStati() throws {
        let alle = try data("2026-11-02T21:40:00")
        XCTAssertEqual(StatoScelta.calcola(letta: false, salvati: scelti, salvataIl: alle, manuale: scelti), .sconosciuto)
        XCTAssertEqual(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: nil), .consigliata)
        XCTAssertEqual(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: scelti), .bozza)
        XCTAssertEqual(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: scelti.reversed()), .salvata(alle),
                       "l'ordine dei titolari non conta")
        var altri = scelti
        altri[0] = 99
        XCTAssertEqual(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: altri), .modificata(alle))
        XCTAssertEqual(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: nil), .modificata(alle))
    }

    func testLeFrasi() throws {
        let adesso = try data("2026-11-02T22:00:00")
        XCTAssertEqual(StatoScelta.salvata(try data("2026-11-02T21:40:00")).titolo(adesso: adesso), "La tua formazione è salvata (oggi alle 21:40).")
        XCTAssertEqual(StatoScelta.salvata(nil).titolo(adesso: adesso), "La tua formazione è salvata.")
        XCTAssertEqual(StatoScelta.modificata(try data("2026-11-01T09:05:00")).titolo(adesso: adesso),
                       "Modifiche non salvate: la formazione salvata è di ieri alle 09:05.")
        XCTAssertEqual(StatoScelta.consigliata.titolo(), "Stai vedendo la consigliata: non hai salvato una tua formazione.")
        XCTAssertEqual(StatoScelta.momento(try data("2026-10-31T21:40:00"), adesso: adesso), "sab 31 ott alle 21:40")
        XCTAssertEqual(StatoScelta.sconosciuto.titolo(), "")
        XCTAssertFalse(StatoScelta.salvata(nil).daSalvare)
        XCTAssertTrue(StatoScelta.modificata(nil).daSalvare)
        XCTAssertEqual(StatoScelta.salvata(nil).tono, .bene)
        XCTAssertFalse(StatoScelta.consigliata.simbolo.isEmpty)
    }

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
        XCTAssertTrue(LetturaPedina.incerto(0.45))
        XCTAssertTrue(LetturaPedina.incerto(0.69))
        XCTAssertFalse(LetturaPedina.incerto(0.70))
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
