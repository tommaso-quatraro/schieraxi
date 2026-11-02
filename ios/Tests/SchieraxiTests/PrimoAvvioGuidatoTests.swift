import XCTest
@testable import Schieraxi

/// Configurazione guidata: lettura tollerante, quando parte da sola, quali passi si saltano, cosa si salva sul server.
final class PrimoAvvioGuidatoTests: XCTestCase {
    private func leggi(_ json: String) throws -> PrimoAvvioRisposta {
        try Decodifica.decodifica(Data(json.utf8))
    }

    private let tuttiIPassi = #""passi": ["server", "accesso", "rose", "squadra", "stemma", "pwa", "widget", "avvisi"]"#

    // MARK: lettura

    func testNonIniziatoEIniziato() throws {
        let nuovo = try leggi("{\"primo_avvio\": null, \(tuttiIPassi)}")
        XCTAssertNil(nuovo.primoAvvio)
        XCTAssertEqual(nuovo.passi.count, 8)
        let iniziato = try leggi("""
        {"primo_avvio": {"fatti": ["rose"], "saltati": ["widget"], "chiuso": false, "aggiornato": "2026-10-30T12:00:00", "campo_nuovo": 1}, \(tuttiIPassi)}
        """)
        XCTAssertEqual(iniziato.primoAvvio?.fatti, ["rose"])
        XCTAssertEqual(iniziato.primoAvvio?.saltati, ["widget"])
        XCTAssertEqual(iniziato.primoAvvio?.chiuso, false)
    }

    func testCampiMancantiOSbagliatiNonRompono() throws {
        let vuota = try leggi("{}")
        XCTAssertNil(vuota.primoAvvio)
        XCTAssertTrue(vuota.passi.isEmpty)
        let strana = try leggi(#"{"primo_avvio": {"fatti": "boh", "chiuso": 3}, "passi": 7}"#)
        XCTAssertEqual(strana.primoAvvio?.fatti, [])
        XCTAssertEqual(strana.primoAvvio?.chiuso, false)
        XCTAssertTrue(strana.passi.isEmpty)
    }

    // MARK: quando parte

    func testPartePerContoSuoSoloSenzaRoseEMaiIniziato() throws {
        let nuovo = try leggi("{\"primo_avvio\": null, \(tuttiIPassi)}")
        XCTAssertTrue(PrimoAvvioLogica.daAvviare(nuovo, roseImportate: false))
        XCTAssertFalse(PrimoAvvioLogica.daAvviare(nuovo, roseImportate: true), "chi ha già la lega non lo vede")
        XCTAssertFalse(PrimoAvvioLogica.daAvviare(nuovo, roseImportate: nil), "se non si sa, non parte")
        let iniziato = try leggi(#"{"primo_avvio": {"fatti": [], "saltati": [], "chiuso": false}}"#)
        XCTAssertFalse(PrimoAvvioLogica.daAvviare(iniziato, roseImportate: false), "già iniziato: non riparte da solo")
        XCTAssertFalse(PrimoAvvioLogica.daAvviare(nil, roseImportate: false))
    }

    // MARK: quali passi

    func testSaltaIPassiGiaFatti() {
        let stato = StatoConfigurazione(roseImportate: true, miaSquadra: "Schiera FC", stemmaEMaglia: false)
        XCTAssertEqual(PrimoAvvioLogica.daFare(nil, stato: stato), [.stemma, .widget, .avvisi])
        let avanz = AvanzamentoPrimoAvvio(fatti: ["widget"], saltati: ["avvisi"])
        XCTAssertEqual(PrimoAvvioLogica.daFare(avanz, stato: stato), [.stemma, .avvisi], "i saltati si riproporranno")
        let nulla = StatoConfigurazione()
        XCTAssertEqual(PrimoAvvioLogica.daFare(nil, stato: nulla), PassoGuidato.allCases)
        let tutto = StatoConfigurazione(roseImportate: true, miaSquadra: "A", stemmaEMaglia: true)
        XCTAssertEqual(PrimoAvvioLogica.daFare(AvanzamentoPrimoAvvio(fatti: ["widget", "avvisi"]), stato: tutto), [])
    }

    func testEsitoPerIlRiepilogo() {
        let stato = StatoConfigurazione(roseImportate: true)
        let avanz = AvanzamentoPrimoAvvio(fatti: [], saltati: ["widget"])
        XCTAssertEqual(PrimoAvvioLogica.esito(.rose, avanzamento: avanz, stato: stato), .fatto)
        XCTAssertEqual(PrimoAvvioLogica.esito(.widget, avanzamento: avanz, stato: stato), .saltato)
        XCTAssertEqual(PrimoAvvioLogica.esito(.avvisi, avanzamento: avanz, stato: stato), .daFare)
        XCTAssertEqual(PrimoAvvioLogica.esito(.avvisi, avanzamento: avanz, stato: stato, saltatiOra: [.avvisi]), .saltato)
    }

    // MARK: cosa si salva

    func testIlCorpoUnisceQuelloCheIlServerRicordaEnonTocca() {
        let prima = AvanzamentoPrimoAvvio(fatti: ["pwa", "rose"], saltati: ["widget", "avvisi"])
        let corpo = PrimoAvvioLogica.corpo(precedente: prima, passiAmmessi: ["server", "rose", "squadra", "pwa", "widget", "avvisi"],
                                           fatti: [.widget], saltati: [.squadra], chiuso: false)
        XCTAssertEqual(corpo.fatti, ["rose", "pwa", "widget"], "i passi di un altro dispositivo (pwa) restano")
        XCTAssertEqual(corpo.saltati, ["squadra", "avvisi"], "widget ora è fatto, quindi non è più saltato")
        XCTAssertFalse(corpo.chiuso)
    }

    func testIlCorpoNonManda_nomiSconosciutiNeTroppeVoci() {
        let prima = AvanzamentoPrimoAvvio(fatti: ["passo_nuovo", "rose"])
        let corpo = PrimoAvvioLogica.corpo(precedente: prima, passiAmmessi: ["rose", "squadra"], fatti: [.stemma], saltati: [], chiuso: true)
        XCTAssertEqual(corpo.fatti, ["rose"], "«stemma» e «passo_nuovo» il server non li ammette: non si mandano")
        XCTAssertTrue(corpo.chiuso)
        let molti = PrimoAvvioLogica.corpo(precedente: AvanzamentoPrimoAvvio(fatti: (0..<20).map { "p\($0)" }),
                                           passiAmmessi: (0..<20).map { "p\($0)" }, fatti: [], saltati: [], chiuso: false)
        XCTAssertLessThanOrEqual(molti.fatti.count, PrimoAvvioLogica.massimoVoci)
    }

    func testSenzaElencoDelServerSiUsanoIPassiNoti() {
        let corpo = PrimoAvvioLogica.corpo(precedente: nil, passiAmmessi: [], fatti: [.rose, .avvisi], saltati: [.widget], chiuso: false)
        XCTAssertEqual(corpo.fatti, ["rose", "avvisi"])
        XCTAssertEqual(corpo.saltati, ["widget"])
    }

    // MARK: schermata

    private func server(roseImportate: Bool, avanzamento: String = "null", putRiuscito: Bool = true) -> ServerDiProva {
        let squadra = roseImportate ? "\"Squadra di prova\"" : "null"
        return ServerDiProva { metodo, percorso, _ in
            if percorso.hasPrefix("/api/primo-avvio") {
                if metodo == "PUT" {
                    if putRiuscito { return Data("{}".utf8) }
                    throw ErroreApi.server("no")
                }
                return Data("{\"primo_avvio\": \(avanzamento), \"passi\": [\"server\",\"accesso\",\"rose\",\"squadra\",\"stemma\",\"pwa\",\"widget\",\"avvisi\"]}".utf8)
            }
            if percorso.hasPrefix("/api/stato") {
                return Data("{\"rose_importate\": \(roseImportate), \"mia_squadra\": \(squadra)}".utf8)
            }
            if percorso.hasPrefix("/api/squadre") {
                return Data(#"[{"nome": "Squadra di prova", "mia": true, "immagini": {"stemma": true, "maglia": false}}]"#.utf8)
            }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    @MainActor
    func testSenzaRoseParteESaltaIPassiGiaFatti() async throws {
        let s = server(roseImportate: false)
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s)
        XCTAssertTrue(parte)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        XCTAssertEqual(vm.passi, PassoGuidato.allCases)
        XCTAssertEqual(vm.passoCorrente, .rose)

        let conRose = server(roseImportate: true)
        let nonParte = await ConfigurazioneGuidataViewModel.devePartire(server: conRose)
        XCTAssertFalse(nonParte)
        let vm2 = ConfigurazioneGuidataViewModel(server: conRose)
        await vm2.carica()
        XCTAssertEqual(vm2.passi, [.stemma, .widget, .avvisi], "rose e squadra già fatte, la maglia manca")
    }

    @MainActor
    func testFattoESaltatoSiSalvanoESiArrivaAlRiepilogo() async throws {
        let s = server(roseImportate: true)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.segnaFatto(.stemma)
        await vm.salta(.widget)
        XCTAssertEqual(vm.passoCorrente, .avvisi)
        await vm.segnaFatto(.avvisi)
        XCTAssertTrue(vm.eRiepilogo)
        XCTAssertEqual(vm.esito(.stemma), .fatto)
        XCTAssertEqual(vm.esito(.widget), .saltato)
        await vm.termina()
        let ultimo = try XCTUnwrap(s.corpiInviati(a: "/api/primo-avvio").last)
        let corpo = try JSONDecoder().decode(CorpoPrimoAvvio.self, from: ultimo)
        XCTAssertEqual(corpo.saltati, ["widget"])
        XCTAssertTrue(corpo.fatti.contains("stemma") && corpo.fatti.contains("avvisi"))
        XCTAssertTrue(corpo.chiuso)
        XCTAssertEqual(s.quante("PUT /api/primo-avvio"), 4, "uno per ogni passo e uno alla fine")
    }

    @MainActor
    func testPiuTardiLasciaDaRiprendereIPassiRimasti() async throws {
        let s = server(roseImportate: true)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.segnaFatto(.stemma)
        await vm.piuTardi()
        let corpo = try JSONDecoder().decode(CorpoPrimoAvvio.self, from: try XCTUnwrap(s.corpiInviati(a: "/api/primo-avvio").last))
        XCTAssertEqual(corpo.saltati, ["widget", "avvisi"])
        XCTAssertFalse(corpo.chiuso, "non chiuso: in Oggi resta «Riprendi»")
    }

    @MainActor
    func testUnSalvataggioFallitoNonBloccaIlPercorso() async throws {
        let s = server(roseImportate: true, putRiuscito: false)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.segnaFatto(.stemma)
        XCTAssertEqual(vm.passoCorrente, .widget, "si va avanti lo stesso")
        XCTAssertEqual(vm.avviso, ConfigurazioneGuidataViewModel.erroreSalvataggio)
    }

    @MainActor
    func testServerVecchioSenzaLaRottaDaErroreSenzaCrash() async throws {
        let vm = ConfigurazioneGuidataViewModel(server: ServerDiProva { _, _, _ in throw ErroreApi.server("non trovato") })
        await vm.carica()
        guard case .errore = vm.fase else { return XCTFail("doveva essere un errore") }
        let s = ServerDiProva { _, _, _ in throw ErroreApi.server("non trovato") }
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s)
        XCTAssertFalse(parte)
    }
}
