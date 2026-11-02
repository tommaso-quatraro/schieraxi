import XCTest
@testable import Schieraxi

/// Le fasi della giornata nei widget (`fase`, `in_corso`, `riepilogo` di `/api/oggi` e, quando li manda, di `/api/widget`):
/// in corso e a giornata finita niente «Da controllare»; senza `fase` tutto come prima. Dati inventati.
final class WidgetFasiTests: XCTestCase {
    /// Il riassunto del widget di prova con dei campi in più (testo JSON senza la graffa iniziale).
    private func widget(_ extra: String) throws -> RiassuntoWidget {
        let base = WidgetRiassuntoTests.corpo.trimmingCharacters(in: .whitespacesAndNewlines)
        let corpo = "{" + extra + (extra.isEmpty ? "" : ", ") + base.dropFirst()
        return try XCTUnwrap(RiassuntoWidget.leggi(Data(corpo.utf8)))
    }

    private let inCorso = #"""
    "fase": "in_corso", "in_corso": {"giornata": 11, "giornata_lega": 8, "formazione_di": "tua", "punti_fatti": 41.5,
      "punti_attesi_restanti": 30.9, "punti_previsti": 72.4, "ancora_da_giocare": 4, "giocatori": [], "sostituzioni": [],
      "partite": {"in_corso": 2, "finite": 3, "da_giocare": 5, "rinviate": 0}}
    """#

    private let finita = #"""
    "fase": "finita", "giornata_lega": 9, "riepilogo": {"giornata": 10, "giornata_lega": 8, "formazione_di": "tua", "nel_diario": true,
      "punti_fatti": 69.5, "punti_attesi": 73.7, "consigliata": {"punti_fatti": 71.0, "punti_attesi": 74.1}},
     "prossima": {"giornata": 11, "giornata_lega": 9, "scadenza": "2026-11-07 14:50", "prepara_da": "2026-11-04 14:50", "con_probabili": false}
    """#

    func testSenzaFaseComePrima() throws {
        let w = try widget("")
        XCTAssertNil(w.fase)
        XCTAssertEqual(w.daControllare.map(\.id), [5], "il dubbio in formazione resta, come prima")
        let r = try XCTUnwrap(w.comeRiassuntoOggi())
        XCTAssertNil(r.fase)
        XCTAssertEqual(r.daControllare, 1)
        XCTAssertFalse(r.mostraFase)
        XCTAssertNil(r.descrizioneFase)
    }

    func testGiornataInCorsoNienteDaControllareEPuntiFatti() throws {
        let w = try widget(inCorso)
        XCTAssertEqual(w.fase, "in_corso")
        XCTAssertTrue(w.daControllare.isEmpty, "a formazione chiusa i dubbi non contano")
        let r = try XCTUnwrap(w.comeRiassuntoOggi())
        XCTAssertTrue(r.inCorso)
        XCTAssertFalse(r.finita)
        XCTAssertEqual(r.daControllare, 0)
        XCTAssertEqual(r.dubbi ?? [], [])
        XCTAssertTrue(r.mostraFase)
        XCTAssertEqual(r.puntiFatti, 41.5)
        XCTAssertEqual(r.puntiFine, 72.4)
        XCTAssertEqual(r.punti, 73.7, "i punti attesi prima restano quelli della formazione")
        XCTAssertEqual(r.puntiFattiTesto, "41,5")
        XCTAssertEqual(r.puntiFineTesto, "circa 72,4 a fine giornata")
        XCTAssertEqual(r.ancoraDaGiocareTesto, "4 devono ancora giocare")
        XCTAssertEqual(r.descrizioneFase, "Giornata 11 in corso: 41,5 punti fatti, circa 72,4 a fine giornata. 4 devono ancora giocare.")
    }

    func testGiornataFinitaRiepilogoEProssima() throws {
        let w = try widget(finita)
        XCTAssertTrue(w.daControllare.isEmpty)
        let r = try XCTUnwrap(w.comeRiassuntoOggi())
        XCTAssertTrue(r.finita)
        XCTAssertTrue(r.mostraFase)
        XCTAssertEqual(r.daControllare, 0)
        XCTAssertEqual(r.puntiFatti, 69.5)
        XCTAssertEqual(r.puntiFine, 73.7)
        XCTAssertEqual(r.puntiFineTesto, "73,7 attesi")
        XCTAssertEqual(r.giornataChiusa, 10)
        XCTAssertEqual(r.etichettaGiornataChiusa, "Giornata 8")
        XCTAssertEqual(r.siglaGiornataChiusa, "G8")
        XCTAssertEqual(r.giornata, 11, "giornata e scadenza sono già quelle della prossima")
        XCTAssertEqual(r.siglaGiornata, "G9")
        XCTAssertNil(r.ancoraDaGiocareTesto)
        XCTAssertTrue(r.descrizioneFase?.hasPrefix("Giornata 8 finita: 69,5 punti fatti su 73,7 attesi. Prossima: Giornata 9") == true,
                      r.descrizioneFase ?? "nil")
    }

    func testFaseSenzaNumeriTogliePeroIDubbi() throws {
        let r = try XCTUnwrap(try widget(#""fase": "in_corso", "in_corso": null"#).comeRiassuntoOggi())
        XCTAssertTrue(r.inCorso)
        XCTAssertEqual(r.daControllare, 0)
        XCTAssertFalse(r.mostraFase, "senza punti fatti il widget resta quello di sempre (con «In corso»)")
    }

    func testBlocchiFuoriFaseOFaseStranaSiIgnorano() throws {
        // il blocco in_corso con fase «prima» non vale; una fase non testuale non rompe il resto
        let prima = try XCTUnwrap(try widget(#""fase": "prima", "in_corso": {"punti_fatti": 10}"#).comeRiassuntoOggi())
        XCTAssertNil(prima.puntiFatti)
        XCTAssertEqual(prima.daControllare, 1)
        let strana = try widget(#""fase": 3, "riepilogo": "boh""#)
        XCTAssertNil(strana.fase)
        XCTAssertEqual(strana.giornata, 11)
        XCTAssertEqual(strana.daControllare.count, 1)
    }

    func testDaOggiInCorso() throws {
        let json = #"""
        {"giornata": 11, "iniziata": true, "fase": "in_corso",
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 73.7},
         "avvisi": [{"id": 120, "nome": "Leonel", "tipo": "dubbio", "in_formazione": true}],
         "in_corso": {"giornata": 11, "punti_fatti": 39.0, "punti_previsti": 77.7, "ancora_da_giocare": 6}}
        """#
        let o: Oggi = try Decodifica.decodifica(Data(json.utf8))
        let r = RiassuntoOggi(oggi: o)
        XCTAssertEqual(r.daControllare, 0, "prima contava ancora il dubbio")
        XCTAssertEqual(r.dubbi ?? [], [])
        XCTAssertEqual(r.puntiFatti, 39.0)
        XCTAssertEqual(r.puntiFine, 77.7)
        XCTAssertEqual(r.ancoraDaGiocare, 6)
        // senza fase: come sempre
        let vecchio: Oggi = try Decodifica.decodifica(Data(json.replacingOccurrences(of: #""fase": "in_corso","#, with: "").utf8))
        XCTAssertEqual(RiassuntoOggi(oggi: vecchio).daControllare, 1)
    }

    func testRiassuntoSalvatoDaUnaVersioneVecchiaSiLeggeAncora() throws {
        let vecchio = #"{"giornata": 9, "daControllare": 2, "scaricatoIl": 0, "modulo": "3-4-3", "punti": 64.5}"#
        let r = try JSONDecoder().decode(RiassuntoOggi.self, from: Data(vecchio.utf8))
        XCTAssertEqual(r.daControllare, 2)
        XCTAssertNil(r.fase)
        XCTAssertFalse(r.mostraFase)
        // e il nuovo si salva e si rilegge uguale
        let nuovo = try XCTUnwrap(try widget(inCorso).comeRiassuntoOggi(scaricatoIl: Date(timeIntervalSinceReferenceDate: 0)))
        let riletto = try JSONDecoder().decode(RiassuntoOggi.self, from: JSONEncoder().encode(nuovo))
        XCTAssertEqual(riletto, nuovo)
    }
}
