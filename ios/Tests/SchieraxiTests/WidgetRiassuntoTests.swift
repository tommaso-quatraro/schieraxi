import XCTest
@testable import Schieraxi

/// Il riassunto compatto dei widget (`GET /api/widget`): lettura, scelta di chi gioca, scarico con ETag e copia.
final class WidgetRiassuntoTests: XCTestCase {
    static let corpo = #"""
    {"giornata": 11, "prima_partita": "2026-10-31 18:30", "scadenza": "2026-10-31 18:30", "ore_mancanti": 5.5, "iniziata": false, "con_probabili": true,
     "squadra": "Schiera FC", "crediti_residui": 12,
     "formazione": {"modulo": "3-4-3", "punti_attesi": 73.7,
       "titolari": [{"id": 1, "nome": "Ivo Sorvani", "ruolo": "P", "punti_attesi": 6.1, "p_voto": 0.98, "avatar": {"c": 2, "b": 1}},
                    {"id": 2, "nome": "Alvise Bastrani", "ruolo": "D", "punti_attesi": 6.4, "p_voto": 0.96}],
       "panchina": [10, 11, 12]},
     "avvisi": [{"id": 5, "nome": "Leonel Marteni", "ruolo": "A", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.55},
                {"id": 7, "nome": "Riserva", "ruolo": "C", "tipo": "infortunato", "in_formazione": false}],
     "rosa": [{"id": 1, "nome": "Ivo Sorvani", "ruolo": "P", "avversario": "roma", "in_casa": true, "data_partita": "2026-10-31 20:45", "stato": "titolare", "percentuale": 98, "dubbio": false, "diffidato": false, "titolare": true, "rigorista": false, "punti_attesi": 6.1},
              {"id": 5, "nome": "Leonel Marteni", "ruolo": "A", "avversario": "milan", "in_casa": false, "data_partita": "2026-10-31 18:30", "stato": "titolare", "percentuale": 55, "dubbio": true, "diffidato": false, "titolare": true, "rigorista": true},
              {"id": 7, "nome": "Riserva", "ruolo": "C", "avversario": "lazio", "in_casa": true, "data_partita": "2026-10-31 15:00", "stato": "infortunato", "titolare": false},
              {"id": 8, "nome": "Senza Partita", "ruolo": "D", "stato": "non_convocato"}],
     "squalificati": [9], "diffidati": [2], "rigoristi": [5],
     "diario": [{"giornata": 10, "attesi": 66.0, "fatti": 63.5}, {"giornata": 9, "attesi": 67.0, "fatti": 71.0}],
     "osservati": [{"id": 30, "nome": "Osservato", "ruolo": "A", "voto_atteso": 6.8, "punti_attesi": 7.1, "avversario": "inter", "in_casa": true, "data_partita": "2026-11-01 12:30", "stato": "titolare", "percentuale": 90}],
     "dati": {"ultimo_aggiornamento": "2026-10-30 14:32"},
     "scambio": {"mia": "Schiera FC", "altra": "Real Madrink", "do": [{"id": 1, "nome": "A", "ruolo": "C"}], "ricevo": [{"id": 2, "nome": "B", "ruolo": "C"}], "guadagno_mio": 2.4, "guadagno_loro": 1.1},
     "svincolato": {"esce": {"id": 7, "nome": "Riserva", "ruolo": "C"}, "entra": {"id": 40, "nome": "Svincolato", "ruolo": "C", "quotazione": 12}, "guadagno": 2.5, "fattibile": true},
     "mancano": []}
    """#

    private func riassunto() throws -> RiassuntoWidget {
        try XCTUnwrap(RiassuntoWidget.leggi(Data(Self.corpo.utf8)))
    }

    func testWidgetTuaSceltaTollerante() throws {
        func leggi(_ campo: String) throws -> RiassuntoWidget {
            let corpo = #"{"giornata": 11, "formazione": {"modulo": "4-4-2", "punti_attesi": 71.7\#(campo)}}"#
            return try XCTUnwrap(RiassuntoWidget.leggi(Data(corpo.utf8)))
        }
        XCTAssertEqual(try leggi(#", "tua_scelta": true"#).formazione?.tuaScelta, true)
        XCTAssertNotEqual(try leggi("").formazione?.tuaScelta, true, "senza il campo è la consigliata")
        let strano = try leggi(#", "tua_scelta": "forse""#).formazione
        XCTAssertNotEqual(strano?.tuaScelta, true)
        XCTAssertEqual(strano?.modulo, "4-4-2", "un campo strano non rompe il resto")
    }

    func testSiLeggeTuttoIlContratto() throws {
        let w = try riassunto()
        XCTAssertEqual(w.giornata, 11)
        XCTAssertEqual(w.formazione?.modulo, "3-4-3")
        XCTAssertEqual(w.formazione?.titolari?.count, 2)
        XCTAssertEqual(w.formazione?.titolari?.first?.avatar?.c, 2, "i tratti del volto arrivano col giocatore")
        XCTAssertEqual(w.creditiResidui, 12)
        XCTAssertEqual(w.diario?.count, 2)
        XCTAssertEqual(w.diario?.first?.fatti, 63.5)
        XCTAssertEqual(w.scambio?.guadagnoMio, 2.4)
        XCTAssertEqual(w.svincolato?.entra?.quotazione, 12)
        XCTAssertEqual(w.dati?.ultimoAggiornamento, "2026-10-30 14:32")
        XCTAssertEqual(w.osservati?.first?.votoAtteso, 6.8)
        XCTAssertEqual(w.squalificati, [9])
        XCTAssertNotNil(w.inizio)
    }

    func testUnServerSenzaLeParti() throws {
        let minimo = #"{"giornata": 3, "formazione": {"modulo": "4-4-2"}}"#
        let w = try XCTUnwrap(RiassuntoWidget.leggi(Data(minimo.utf8)))
        XCTAssertNil(w.scambio)
        XCTAssertNil(w.svincolato)
        XCTAssertTrue(w.daControllare.isEmpty)
        XCTAssertTrue(w.giocanoPresto().isEmpty)
    }

    func testIRispostaStranaNonRompe() {
        XCTAssertNil(RiassuntoWidget.leggi(Data()))
        XCTAssertNil(RiassuntoWidget.leggi(Data("non json".utf8)))
        XCTAssertNil(RiassuntoWidget.leggi(Data(repeating: 0x20, count: 300_000)))
    }

    func testChiGiocaPrestoEInOrdineDiOrarioSenzaInfortunati() throws {
        let w = try riassunto()
        let adesso = try XCTUnwrap(Quando.data("2026-10-31 12:00"))
        let giocano = w.giocanoPresto(dopo: adesso)
        XCTAssertEqual(giocano.map(\.id), [5, 1], "prima Leonel (18:30), poi Sorvani (20:45); l'infortunato e chi non ha partita no")
        XCTAssertEqual(giocano.first?.oraBreve, "18:30")
        XCTAssertEqual(giocano.first?.partitaBreve, "@ MIL · 18:30")
        XCTAssertEqual(giocano.last?.partitaBreve, "vs ROM · 20:45")
        XCTAssertEqual(w.giocanoPresto(dopo: adesso, massimo: 1).count, 1)
    }

    func testChiHaGiaGiocatoDaOreNonCompare() throws {
        let w = try riassunto()
        let tardi = try XCTUnwrap(Quando.data("2026-10-31 23:30"))
        XCTAssertTrue(w.giocanoPresto(dopo: tardi).isEmpty)
        let appenaFinita = try XCTUnwrap(Quando.data("2026-10-31 19:00"))
        XCTAssertEqual(w.giocanoPresto(dopo: appenaFinita).map(\.id), [5, 1], "una partita iniziata da meno di 2 ore e' ancora in corso")
    }

    func testLoStatoInUnaRiga() throws {
        let w = try riassunto()
        XCTAssertEqual(w.rosa?[1].descrizioneStato, "Dubbio 55%")
        XCTAssertEqual(w.rosa?[2].descrizioneStato, "Infortunato")
        XCTAssertEqual(w.rosa?[0].descrizioneStato, "", "titolare: niente da segnalare")
        XCTAssertEqual(w.rosa?[3].descrizioneStato, "Non convocato", "senza trattino basso")
        XCTAssertEqual(w.avvisi?.first?.descrizioneStato, "Dubbio 55%")
    }

    func testGliStatiVeriDelServer() throws {
        func stato(_ json: String) throws -> String {
            let d = JSONDecoder()
            d.keyDecodingStrategy = .convertFromSnakeCase
            return try d.decode(GiocatoreWidget.self, from: Data(json.utf8)).descrizioneStato
        }
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "titolare"}"#), "")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "panchina"}"#), "Panchina")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "non_convocato"}"#), "Non convocato")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "infortunato", "dubbio": true}"#), "Infortunato", "l'assenza vince sul dubbio")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "squalificato"}"#), "Squalificato")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "titolare", "dubbio": true, "percentuale": 60}"#), "Dubbio 60%")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "titolare", "dubbio": true}"#), "Dubbio")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A", "stato": "stato_nuovo"}"#), "Stato nuovo")
        XCTAssertEqual(try stato(#"{"id": 1, "nome": "A"}"#), "")
    }

    func testIlRiassuntoVecchioDeiWidgetViene() throws {
        let w = try riassunto()
        let r = try XCTUnwrap(w.comeRiassuntoOggi())
        XCTAssertEqual(r.giornata, 11)
        XCTAssertEqual(r.modulo, "3-4-3")
        XCTAssertEqual(r.punti, 73.7)
        XCTAssertEqual(r.daControllare, 1)
        XCTAssertEqual(r.dubbi?.first?.id, 5)
        XCTAssertEqual(r.probabili, true)
    }

    func testIlMiglioreScambioSiLegge() throws {
        let s = try XCTUnwrap(try riassunto().scambio)
        XCTAssertEqual(s.altra, "Real Madrink")
        XCTAssertEqual(s.daiTesto, "A")
        XCTAssertEqual(s.ricevoTesto, "B")
        XCTAssertEqual(s.guadagnoLoro, 1.1)
        XCTAssertTrue(s.frase.contains("Real Madrink"))
    }

    func testUnoScambioStranoNonRompeIlResto() throws {
        // «do» e' un numero invece di un elenco: lo scambio si ignora, il resto del riassunto resta.
        let strano = #"{"giornata": 4, "formazione": {"modulo": "4-3-3"}, "scambio": {"altra": "X", "do": 5}, "svincolato": "no"}"#
        let w = try XCTUnwrap(RiassuntoWidget.leggi(Data(strano.utf8)))
        XCTAssertEqual(w.giornata, 4)
        XCTAssertEqual(w.formazione?.modulo, "4-3-3")
        XCTAssertNil(w.scambio)
        XCTAssertNil(w.svincolato)
    }

    func testLeGiornateGiocateDalDiario() throws {
        let w = try riassunto()
        XCTAssertEqual(w.giornateGiocate.map(\.giornata), [10, 9], "dalla piu' recente")
        XCTAssertEqual(try XCTUnwrap(w.giornateGiocate.first).scarto, -2.5)
        XCTAssertEqual(try XCTUnwrap(w.giornateGiocate.first).descrizione, "Giornata 10: 63,5 punti fatti, 66,0 attesi")
    }

    func testLePartiteLiveEIMieiTitolari() throws {
        let corpo = #"""
        {"giornata": 11, "formazione": {"modulo": "3-4-3", "titolari": [{"id": 5, "nome": "Leonel Marteni", "ruolo": "A"}]},
         "rosa": [{"id": 5, "nome": "Leonel Marteni", "ruolo": "A", "avversario": "roma", "in_casa": true, "titolare": true},
                  {"id": 6, "nome": "Altro", "ruolo": "D", "avversario": "milan", "in_casa": false, "titolare": false}],
         "live": {"aggiornato_il": "2026-10-31 15:20:04", "fonte": "espn", "in_corso": 1, "partite": [
           {"casa": "lazio", "trasferta": "juve", "data": "2026-10-31 20:45", "stato": "da_giocare", "gol_casa": null, "gol_trasferta": null, "eventi": []},
           {"casa": "inter", "trasferta": "roma", "data": "2026-10-31 15:00", "stato": "secondo_tempo", "minuto": "63'", "gol_casa": 2, "gol_trasferta": 0,
            "eventi": [{"tipo": "gol", "minuto": "10'", "squadra": "casa", "chi": "M. Thorvan"}]},
           {"casa": "napoli", "trasferta": "genoa", "data": "2026-10-31 12:30", "stato": "finita", "gol_casa": 1, "gol_trasferta": 1},
           {"casa": "x", "trasferta": "y", "data": "2026-10-31 15:30", "stato": "stato_nuovo", "gol_casa": 0, "gol_trasferta": 0}]}}
        """#
        let w = try XCTUnwrap(RiassuntoWidget.leggi(Data(corpo.utf8)))
        XCTAssertEqual(w.live?.inCorso, 1)
        XCTAssertEqual(w.partiteLive.first?.casa, "inter", "prima quelle in gioco")
        XCTAssertEqual(w.partiteLive.last?.casa, "napoli", "per ultime le finite")
        XCTAssertEqual(w.partiteInGioco.count, 2, "uno stato sconosciuto con un punteggio conta come in corso")
        let inter = try XCTUnwrap(w.partiteLive.first { $0.casa == "inter" })
        XCTAssertEqual(inter.punteggio, "2–0")
        XCTAssertEqual(inter.etichetta, "63'")
        XCTAssertEqual(w.partiteLive.first { $0.casa == "lazio" }?.etichetta, "20:45")
        XCTAssertEqual(w.partiteLive.first { $0.casa == "napoli" }?.etichetta, "Finita")
        XCTAssertEqual(w.mieiTitolari(in: inter).map(\.id), [5], "Leonel gioca in casa contro la Roma")
        XCTAssertTrue(w.mieiTitolari(in: try XCTUnwrap(w.partiteLive.first { $0.casa == "lazio" })).isEmpty)
        let prima = try XCTUnwrap(Quando.data("2026-10-31 14:00"))
        XCTAssertTrue(w.finestraLive(adesso: prima), "c'e' una partita in gioco")
        XCTAssertEqual(w.prossimaPartita(dopo: prima)?.casa, "lazio")
    }

    func testLIntervalloDeiPuntiAttesi() throws {
        let c = #"{"giornata": 3, "formazione": {"modulo": "4-3-3", "punti_attesi": 70, "intervallo": {"basso": 62.2, "alto": 84.6, "confidenza": 0.8, "indicativo": true}}}"#
        let i = try XCTUnwrap(try XCTUnwrap(RiassuntoWidget.leggi(Data(c.utf8))).formazione?.intervallo)
        XCTAssertEqual(i.testo, "tra 62 e 85")
        XCTAssertEqual(i.testoLungo, "tra 62 e 85 (8 volte su 10), indicativo")
        XCTAssertNil(IntervalloWidget(basso: 60).testo, "senza l'estremo alto niente testo")
        let senza = try XCTUnwrap(RiassuntoWidget.leggi(Data(#"{"giornata": 3, "formazione": {"modulo": "4-3-3"}}"#.utf8)))
        XCTAssertNil(senza.formazione?.intervallo, "un server vecchio non lo manda")
    }

    func testLaFasciaDelDiarioEDoveSonoCadutiIPunti() throws {
        let c = #"""
        {"giornata": 11, "diario": [
          {"giornata": 10, "attesi": 66, "fatti": 63.5, "intervallo": {"basso": 55, "alto": 77, "confidenza": 0.8}},
          {"giornata": 9, "attesi": 67, "fatti": 90, "intervallo": {"basso": 56, "alto": 78}},
          {"giornata": 8, "attesi": 69, "fatti": 50, "intervallo": {"basso": 58, "alto": 80}},
          {"giornata": 7, "attesi": 70, "fatti": 64, "intervallo": "strano"},
          {"giornata": 6, "attesi": 70, "fatti": 64}]}
        """#
        let w = try XCTUnwrap(RiassuntoWidget.leggi(Data(c.utf8)))
        let g = w.giornateGiocate
        XCTAssertEqual(g.map(\.postoNellaFascia), [.dentro, .sopra, .sotto, nil, nil])
        XCTAssertEqual(g.first?.fasciaTesto, "dentro la fascia")
        XCTAssertEqual(g.first?.descrizione, "Giornata 10: 63,5 punti fatti, 66,0 attesi, dentro la fascia prevista, tra 55 e 77")
        XCTAssertEqual(g[3].descrizione, "Giornata 7: 64,0 punti fatti, 70,0 attesi", "una fascia con la forma sbagliata si ignora")
        let q = RiassuntoWidget.quanteDentro(g)
        XCTAssertEqual(q.dentro, 1)
        XCTAssertEqual(q.su, 3)
    }

    func testIlGiocatoreOsservatoScelto() throws {
        let w = try riassunto()
        XCTAssertEqual(w.osservato(30)?.id, 30, "tra gli osservati")
        XCTAssertEqual(w.osservato(5)?.id, 5, "tra i miei giocatori")
        XCTAssertEqual(w.osservato(1)?.id, 1, "tra i titolari")
        XCTAssertEqual(w.osservato(999)?.id, 30, "se non c'e' piu' il primo osservato")
        XCTAssertEqual(w.osservato(nil)?.id, 30, "senza scelta il primo osservato")
        let senza = try XCTUnwrap(RiassuntoWidget.leggi(Data(#"{"giornata": 3}"#.utf8)))
        XCTAssertNil(senza.osservato(nil))
    }

    func testIlLiveMancanteOStranoNonRompe() throws {
        let senza = try XCTUnwrap(RiassuntoWidget.leggi(Data(#"{"giornata": 3}"#.utf8)))
        XCTAssertNil(senza.live)
        XCTAssertTrue(senza.partiteLive.isEmpty)
        XCTAssertFalse(senza.finestraLive())
        let strano = try XCTUnwrap(RiassuntoWidget.leggi(Data(#"{"giornata": 3, "live": {"partite": "no"}}"#.utf8)))
        XCTAssertNil(strano.live)
    }

    func testIlCognome() {
        XCTAssertEqual(GiocatoreWidget(id: 1, nome: "Alvise Bastrani").cognome, "Bastrani")
        XCTAssertEqual(GiocatoreWidget(id: 1, nome: "Pelayo").cognome, "Pelayo")
    }
}

final class ScaricoWidgetTests: XCTestCase {
    private func sessione(_ gestore: @escaping (URLRequest) -> (Int, [String: String], Data)) -> URLSession {
        let c = URLSessionConfiguration.ephemeral
        c.protocolClasses = [ProtocolloFinto.self]
        ProtocolloFinto.gestore = { r in
            let (codice, intestazioni, dati) = gestore(r)
            return (HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: intestazioni) ?? HTTPURLResponse(), dati)
        }
        return URLSession(configuration: c)
    }

    override func tearDown() {
        ProtocolloFinto.gestore = nil
        super.tearDown()
    }

    func testScaricaConLEtagEIlTokenDelWidget() async {
        let visto = Scatola<[String]>()
        let s = sessione { r in
            visto.valore = [r.value(forHTTPHeaderField: "If-None-Match") ?? "-", r.value(forHTTPHeaderField: "Authorization") ?? "-", r.url?.path ?? ""]
            return (200, ["ETag": "\"abc\""], Data(WidgetRiassuntoTests.corpo.utf8))
        }
        let e = await ScaricoWidget.scarica(base: "https://prova-widget.invalid", token: "fw_tokenDiProva123456", etag: "\"vecchio\"", sessione: s)
        guard case .dati(let w, _, let etag) = e else { return XCTFail("atteso 200: \(e)") }
        XCTAssertEqual(w.giornata, 11)
        XCTAssertEqual(etag, "\"abc\"")
        XCTAssertEqual(visto.valore, ["\"vecchio\"", "Bearer fw_tokenDiProva123456", "/api/widget"])
    }

    func testSiChiedeSempreLItalianoEL_ETagConSuffissoNonSiTocca() async {
        let visto = Scatola<[String]>()
        let s = sessione { r in
            visto.valore = [r.value(forHTTPHeaderField: "Accept-Language") ?? "-", r.value(forHTTPHeaderField: "If-None-Match") ?? "-"]
            return (304, [:], Data())
        }
        _ = await ScaricoWidget.scarica(base: "https://prova-widget.invalid", token: nil, etag: "\"abc-en\"", sessione: s)
        XCTAssertEqual(visto.valore, ["it", "\"abc-en\""])
    }

    func testLeFunzioniSpenteSiLeggonoEUnaChiaveAssenteValeAcceso() throws {
        let con = #"{"giornata": 3, "funzioni": {"live": false, "widget_extra": false, "seguiti": true}}"#
        let w = try XCTUnwrap(RiassuntoWidget.leggi(Data(con.utf8)))
        XCTAssertFalse(w.acceso(FunzioneWidget.extra))
        XCTAssertFalse(w.acceso("live"))
        XCTAssertTrue(w.acceso("seguiti"))
        XCTAssertTrue(w.acceso("diario"))
        let senza = try XCTUnwrap(RiassuntoWidget.leggi(Data(#"{"giornata": 3}"#.utf8)))
        XCTAssertTrue(senza.acceso(FunzioneWidget.extra))
        let accesa = try XCTUnwrap(RiassuntoWidget.leggi(Data(#"{"funzioni": {"widget_extra": true}}"#.utf8)))
        XCTAssertTrue(accesa.acceso(FunzioneWidget.extra))
    }

    func testIlCodiceDelServerSiTraduce() async {
        let casi: [(Int, String)] = [(304, "nonCambiato"), (202, "inCalcolo"), (401, "accessoRichiesto"), (404, "nonDisponibile"), (403, "nonDisponibile"), (500, "errore")]
        for (codice, nome) in casi {
            let s = sessione { _ in (codice, [:], Data("{}".utf8)) }
            let e = await ScaricoWidget.scarica(base: "https://prova-widget.invalid", token: nil, etag: nil, sessione: s)
            XCTAssertEqual("\(e)", nome, "codice \(codice)")
        }
    }

    func testUnCorpoRovinatoEUnErrore() async {
        let s = sessione { _ in (200, [:], Data("non json".utf8)) }
        let e = await ScaricoWidget.scarica(base: "https://prova-widget.invalid", token: nil, etag: nil, sessione: s)
        XCTAssertEqual("\(e)", "errore")
    }

    func testIndirizzoNonValidoEUnErrore() async {
        let e = await ScaricoWidget.scarica(base: "", token: nil, etag: nil)
        XCTAssertEqual("\(e)", "errore")
    }

    func testLaCopiaSiRicordaEPoiSiDimentica() throws {
        let cartella = FileManager.default.temporaryDirectory.appendingPathComponent("copia-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        Condiviso.cartellaDiProva = cartella
        defer { Condiviso.cartellaDiProva = nil; try? FileManager.default.removeItem(at: cartella); MemoriaWidget.dimentica() }
        XCTAssertNil(MemoriaWidget.leggi())
        MemoriaWidget.salva(CopiaWidget(dati: Data(WidgetRiassuntoTests.corpo.utf8), etag: "\"e1\"", scaricatoIl: Date()))
        let c = try XCTUnwrap(MemoriaWidget.leggi())
        XCTAssertEqual(c.etag, "\"e1\"")
        XCTAssertEqual(c.riassunto?.giornata, 11)
        MemoriaWidget.dimentica()
        XCTAssertNil(MemoriaWidget.leggi())
    }
}
