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
        XCTAssertEqual(try oggi("").etichettaGiornata, "Giornata 10")
        XCTAssertEqual(try oggi(", \"giornata_lega\": null").etichettaGiornata, "Giornata 10")
        XCTAssertEqual(try oggi(", \"giornata_lega\": 10").etichettaGiornata, "Giornata 10")
        XCTAssertEqual(try oggi(", \"giornata_lega\": 7").etichettaGiornata, "Giornata 7 di lega (Serie A 10)")
        XCTAssertEqual(try oggi(", \"giornata_lega\": 7").giornataMostrata, 7)
        XCTAssertEqual(try oggi(", \"giornata_lega\": 0").giornataMostrata, 10)
    }

    func testGliAvvisiESiriDicianoLaGiornataDellaLega() throws {
        // lega che parte dalla 4ª di Serie A: la 10ª di Serie A è la 7ª della lega, e l'app mostra «7»
        let o = try oggi(", \"giornata_lega\": 7")
        XCTAssertTrue(Aggiornamento.corpoCambioModulo(o, modulo: "3-5-2", punti: "66,0", moduloPrima: "4-3-3").hasPrefix("Mister, giornata 7:"))
        XCTAssertTrue(Aggiornamento.corpoProbabili(o, modulo: "3-5-2", punti: "66,0").hasPrefix("Giornata 7:"))
        XCTAssertTrue(FormazioneComando.fraseBase(o, modulo: "3-5-2", punti: "66,0").hasPrefix("Per la giornata 7 "))
        // senza il numero della lega vale quello di Serie A
        let senza = try oggi("")
        XCTAssertTrue(Aggiornamento.corpoProbabili(senza, modulo: "3-5-2", punti: "66,0").hasPrefix("Giornata 10:"))
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

/// La giornata di lega nelle formazioni, nel testo condiviso e nei widget.
final class GiornataLegaTests: XCTestCase {
    func testEtichetta() {
        XCTAssertEqual(TempiLega.etichetta(serieA: 11, lega: 8), "Giornata 8 di lega (Serie A 11)")
        XCTAssertEqual(TempiLega.etichetta(serieA: 11, lega: 11), "Giornata 11")
        XCTAssertEqual(TempiLega.etichetta(serieA: 11, lega: nil), "Giornata 11")
        XCTAssertEqual(TempiLega.etichetta(serieA: 11, lega: -2), "Giornata 11")
        XCTAssertEqual(TempiLega.sigla(serieA: 11, lega: 8), "G8")
        XCTAssertEqual(TempiLega.sigla(serieA: 11, lega: nil), "G11")
    }

    func testTestoCondiviso() {
        XCTAssertEqual(TestoFormazione.crea(giornata: 11, giornataLega: 8, modulo: "4-3-3", titolari: [], panchina: []).components(separatedBy: "\n").first,
                       "Giornata 8 di lega (Serie A 11) · 4-3-3")
        XCTAssertEqual(TestoFormazione.crea(giornata: 11, modulo: "4-3-3", titolari: [], panchina: []).components(separatedBy: "\n").first,
                       "Giornata 11 · 4-3-3")
    }

    func testIlWidgetLeggeLaGiornataDiLega() throws {
        let con = RiassuntoWidget.leggi(Data(#"{"giornata": 11, "giornata_lega": 8}"#.utf8))
        XCTAssertEqual(con?.etichettaGiornata, "Giornata 8 di lega (Serie A 11)")
        XCTAssertEqual(con?.siglaGiornata, "G8")
        XCTAssertEqual(con?.comeRiassuntoOggi()?.etichettaGiornata, "Giornata 8 di lega (Serie A 11)")
        // server vecchio o valore nullo
        let senza = RiassuntoWidget.leggi(Data(#"{"giornata": 11, "giornata_lega": null}"#.utf8))
        XCTAssertEqual(senza?.etichettaGiornata, "Giornata 11")
        XCTAssertNil(RiassuntoWidget.leggi(Data(#"{}"#.utf8))?.etichettaGiornata)
    }

    func testIlRiassuntoVecchioSenzaGiornataDiLegaSiLegge() throws {
        let vecchio = Data(#"{"giornata": 9, "daControllare": 0, "scaricatoIl": 0}"#.utf8)
        let r = try JSONDecoder().decode(RiassuntoOggi.self, from: vecchio)
        XCTAssertEqual(r.etichettaGiornata, "Giornata 9")
    }

    func testLaDidascaliaNonRipeteLaTuaScelta() {
        XCTAssertEqual(TempiLega.didascalia(giornata: "Giornata 3", scelta: true, comeConsigliato: false), "Giornata 3")
        XCTAssertEqual(TempiLega.didascalia(giornata: "Giornata 3", scelta: false, comeConsigliato: true), "Giornata 3 · modulo consigliato")
        XCTAssertEqual(TempiLega.didascalia(giornata: "Giornata 3", scelta: false, comeConsigliato: false), "Giornata 3 · modulo scelto")
    }

    func testFormazioneSenzaGiornataDiLega() throws {
        let f: Formazione = try Fixture.decodifica("formazione")
        XCTAssertEqual(f.etichettaGiornata, "Giornata \(f.giornata)")
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
        XCTAssertTrue(Aggiornamento.corpoCambioModulo(o, modulo: "3-5-2", punti: "66,0", moduloPrima: "4-3-3").hasPrefix("Mister, prossima giornata:"))
        XCTAssertFalse(FormazioneComando.fraseBase(o, modulo: "3-5-2", punti: "66,0").contains("nil"))
    }
}
