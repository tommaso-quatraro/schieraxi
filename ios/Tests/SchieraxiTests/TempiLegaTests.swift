import XCTest
@testable import Schieraxi

/// Scadenza della formazione e numerazione della lega: tutti i campi nuovi del server sono facoltativi.
final class TempiLegaTests: XCTestCase {
    private func oggi(_ extra: String) throws -> Oggi {
        try Decodifica.decodifica(Data("{\"giornata\": 10, \"inizio\": \"2026-11-08 18:30\"\(extra)}".utf8))
    }

    func testIlContoPuntaAllaScadenza() throws {
        let o = try oggi(", \"scadenza\": \"2026-11-08 18:00\", \"minuti_scadenza\": 30")
        XCTAssertEqual(o.chiusura, "2026-11-08 18:00")
        XCTAssertEqual(o.minutiScadenza, 30)
    }

    func testServerVecchioOScadenzaVuotaUsaLInizio() throws {
        XCTAssertEqual(try oggi("").chiusura, "2026-11-08 18:30")
        XCTAssertEqual(try oggi(", \"scadenza\": null").chiusura, "2026-11-08 18:30")
        XCTAssertEqual(try oggi(", \"scadenza\": \"  \"").chiusura, "2026-11-08 18:30")
    }

    func testEtichettaDellaGiornata() throws {
        // #299: i due numeri, lega e Serie A; senza il numero della lega solo Serie A
        XCTAssertEqual(try oggi("").etichettaGiornata, "10ª giornata di Serie A")
        XCTAssertEqual(try oggi(", \"giornata_lega\": null").etichettaGiornata, "10ª giornata di Serie A")
        XCTAssertEqual(try oggi(", \"giornata_lega\": 10").etichettaGiornata, "Giornata 10 · 10ª di Serie A")
        XCTAssertEqual(try oggi(", \"giornata_lega\": 7").etichettaGiornata, "Giornata 7 · 10ª di Serie A")
        XCTAssertEqual(try oggi(", \"giornata_lega\": 7").giornataMostrata, 7)
        XCTAssertEqual(try oggi(", \"giornata_lega\": 0").giornataMostrata, 10)
    }

    func testGliAvvisiESiriDicianoLaGiornataDellaLega() throws {
        // lega che parte dalla 4ª di Serie A: la 10ª di Serie A è la 7ª della lega; in testa i due numeri e i due punti (#299)
        let o = try oggi(", \"giornata_lega\": 7")
        XCTAssertEqual(Aggiornamento.corpoCambioModulo(o, modulo: "3-5-2", punti: "66,0", moduloPrima: "4-3-3"),
                       "Giornata 7 · 10ª di Serie A: ora 3-5-2, 66,0 punti attesi (prima 4-3-3).")
        XCTAssertEqual(Aggiornamento.corpoProbabili(o, modulo: "3-5-2", punti: "66,0"),
                       "Giornata 7 · 10ª di Serie A: modulo consigliato 3-5-2, 66,0 punti attesi.")
        XCTAssertEqual(FormazioneComando.fraseBase(o, modulo: "3-5-2", punti: "66,0"),
                       "Giornata 7, 10ª di Serie A: ti consiglio il 3-5-2, con 66,0 punti attesi.", "Siri legge la virgola, non «·»")
        // senza il numero della lega solo quello di Serie A
        let senza = try oggi("")
        XCTAssertTrue(Aggiornamento.corpoProbabili(senza, modulo: "3-5-2", punti: "66,0").hasPrefix("10ª giornata di Serie A:"))
    }

    func testIlRiassuntoDelWidgetUsaLaScadenza() throws {
        let o = try oggi(", \"scadenza\": \"2026-11-08 18:00\"")
        XCTAssertEqual(RiassuntoOggi(oggi: o).inizio, Quando.data("2026-11-08 18:00"))
    }

    func testFrasiDiSpiegazione() {
        XCTAssertEqual(TempiLega.spiegaScadenza(0), "La formazione si chiude all'inizio della prima partita.")
        XCTAssertEqual(TempiLega.spiegaScadenza(1), "La formazione si chiude 1 minuto prima della prima partita.")
        XCTAssertEqual(TempiLega.spiegaScadenza(45), "La formazione si chiude 45 minuti prima della prima partita.")
        XCTAssertTrue(TempiLega.spiegaPartenza(1).contains("coincidono"))
        XCTAssertTrue(TempiLega.spiegaPartenza(4).contains("la 4ª di Serie A"))
        XCTAssertTrue(TempiLega.spiegaPartenza(99).contains("la 38ª"))
    }

    func testLeRegoleConservanoITempiNelSalvataggio() throws {
        var regole = try JSONDecoder().decode(JSONValue.self, from: Data(#"{"nome_lega":"Lega","moduli":["3-4-3"]}"#.utf8))
        // server vecchio: i campi mancano e non cambia nulla finché non si tocca
        XCTAssertNil(regole.valore("scadenza_minuti"))
        regole.imposta("scadenza_minuti", JSONValue.numero(30))
        regole.imposta("prima_giornata_lega", JSONValue.numero(4))
        let pronte = try RegoleLogica.preparaPerSalvataggio(regole)
        XCTAssertEqual(pronte.valore("scadenza_minuti"), .intero(30))
        XCTAssertEqual(pronte.valore("prima_giornata_lega"), .intero(4))
    }

    func testAggiornamentiVicinoAllaScadenzaSiConservanoENonSiInventano() throws {
        var regole = try JSONDecoder().decode(JSONValue.self, from: Data(#"{"nome_lega":"Lega","moduli":["3-4-3"]}"#.utf8))
        // server vecchio: il campo manca e nel salvataggio non compare (il server lo considera acceso)
        XCTAssertNil(try RegoleLogica.preparaPerSalvataggio(regole).valore("aggiornamenti_vicino_scadenza"))
        regole.imposta("aggiornamenti_vicino_scadenza", .booleano(false))
        XCTAssertEqual(try RegoleLogica.preparaPerSalvataggio(regole).valore("aggiornamenti_vicino_scadenza"), .booleano(false))
    }
}

/// Account nuovo, calendario non pronto o stagione finita: il server manda `giornata: null` (o non manda campi). Nessun errore, nessun crash.
final class OggiSenzaGiornataTests: XCTestCase {
    private func leggi(_ json: String) throws -> Oggi {
        try Decodifica.decodifica(Data(json.utf8))
    }

    private let nuovoSenzaRose = """
    {"giornata": null, "inizio": null, "scadenza": null, "giornata_lega": null, "iniziata": false, "con_probabili": false,
     "formazione": null, "avvisi": [], "migliori": [], "partite": [], "da_fare": [], "senza_rose": true}
    """

    func testGiornataNullSiLegge() throws {
        let o = try leggi(nuovoSenzaRose)
        XCTAssertNil(o.giornata)
        XCTAssertNil(o.giornataMostrata)
        XCTAssertNil(o.etichettaGiornata)
        XCTAssertTrue(o.senzaGiornata)
        XCTAssertEqual(o.senzaRose, true)
        XCTAssertNil(o.chiusura)
    }

    func testCampiMancantiESoloGraffe() throws {
        let vuoto = try leggi("{}")
        XCTAssertNil(vuoto.giornata)
        XCTAssertNil(vuoto.senzaRose)
        XCTAssertNil(vuoto.formazione)
        XCTAssertNil(vuoto.avvisi)
        XCTAssertNil(try leggi(#"{"senza_rose": true}"#).giornata)
    }

    func testConLaSolaGiornataDiLegaMaSenzaSerieA() throws {
        // la giornata di Serie A manca: non si inventa niente, nemmeno dal numero della lega
        let o = try leggi(#"{"giornata": null, "giornata_lega": 3}"#)
        XCTAssertNil(o.etichettaGiornata)
        XCTAssertEqual(o.giornataMostrata, 3)
    }

    func testIlWidgetEilRiassuntoNonSiRompono() throws {
        let o = try leggi(nuovoSenzaRose)
        let r = RiassuntoOggi(oggi: o)
        XCTAssertNil(r.giornata)
        XCTAssertEqual(r.etichettaGiornata, "Nessuna giornata")
        XCTAssertEqual(r.siglaGiornata, "G–")
        // salvato e riletto (come fa il file condiviso)
        let dati = try JSONEncoder().encode(r)
        XCTAssertEqual(try JSONDecoder().decode(RiassuntoOggi.self, from: dati), r)
        // il widget completo senza giornata non fa crollare la lettura
        let w = RiassuntoWidget.leggi(Data(#"{"giornata": null, "senza_rose": true}"#.utf8))
        XCTAssertNotNil(w)
        XCTAssertNil(w?.comeRiassuntoOggi())
    }

    func testSiriENotificheSenzaGiornata() throws {
        let o = try leggi(nuovoSenzaRose)
        XCTAssertTrue(Aggiornamento.corpoProbabili(o, modulo: "3-5-2", punti: "66,0").hasPrefix("Prossima giornata:"))
        XCTAssertTrue(Aggiornamento.corpoCambioModulo(o, modulo: "3-5-2", punti: "66,0", moduloPrima: "4-3-3").hasPrefix("Prossima giornata:"))
        XCTAssertFalse(FormazioneComando.fraseBase(o, modulo: "3-5-2", punti: "66,0").contains("nil"))
    }
}
