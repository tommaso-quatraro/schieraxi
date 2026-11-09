import XCTest
@testable import Schieraxi

/// ViewModel della sezione Lega: aggiornamento dei dati, passaggio di stagione, regole, importazione, crediti, avvisi, movimenti.
@MainActor
final class LegaViewModelTests: XCTestCase {
    // MARK: aggiornamento dei dati

    func testAggiornamentoRiuscitoSeguitoFinoAllaFine() async throws {
        let sondaggi = Contatore()
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "POST" { return Data(#"{"avviato": true}"#.utf8) }
            // le prime due domande: ancora in corso; la terza: finito
            if sondaggi.passo() < 2 { return Data(#"{"in_corso": true, "righe": [], "errori": []}"#.utf8) }
            return Data(#"{"in_corso": false, "righe": ["ok"], "errori": []}"#.utf8)
        }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausa = 0
        let ricaricate = Contatore()
        let osservatore = NotificationCenter.default.addObserver(forName: .aggiornaTutto, object: nil, queue: .main) { _ in _ = ricaricate.passo() }
        defer { NotificationCenter.default.removeObserver(osservatore) }
        await vm.avvia()
        XCTAssertFalse(vm.inCorso)
        XCTAssertEqual(vm.messaggio, Catalogo.Aggiorna.ok)
        XCTAssertTrue(vm.errori.isEmpty)
        XCTAssertEqual(s.quante("POST /api/aggiorna"), 1)
        XCTAssertEqual(s.quante("GET /api/aggiorna"), 3)
        XCTAssertGreaterThanOrEqual(ricaricate.valore, 1, "alla fine tutte le schermate si ricaricano")
    }

    func testAggiornamentoConProblemi() async {
        let s = ServerDiProva { metodo, _, _ in
            metodo == "POST" ? Data(#"{"avviato": true}"#.utf8) : Data(#"{"in_corso": false, "errori": ["Understat non risponde"]}"#.utf8)
        }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausa = 0
        await vm.avvia()
        XCTAssertEqual(vm.errori, ["Understat non risponde"])
        XCTAssertEqual(vm.messaggio, "Aggiornato, ma con problemi: Understat non risponde")
    }

    func testAggiornamentoGiaInCorsoSulServer() async {
        let s = ServerDiProva { _, _, _ in Data(#"{"avviato": false, "messaggio": "Aggiornamento già in corso"}"#.utf8) }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausa = 0
        await vm.avvia()
        XCTAssertEqual(vm.messaggio, "Aggiornamento già in corso")
        XCTAssertEqual(s.quante("GET /api/aggiorna"), 0, "se non è partito non si sta ad aspettare")
    }

    func testAggiornamentoSeIlServerNonRisponde() async {
        let s = ServerDiProva { metodo, _, _ in
            if metodo == "POST" { return Data(#"{"avviato": true}"#.utf8) }
            throw ErroreApi.rete("giù")
        }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausa = 0
        await vm.avvia()
        XCTAssertEqual(vm.messaggio, Catalogo.Aggiorna.nonSo)
        XCTAssertEqual(s.quante("GET /api/aggiorna"), 5, "dopo cinque tentativi a vuoto si smette")
        XCTAssertFalse(vm.inCorso)
    }

    func testAggiornamentoNonPartito() async {
        let vm = AggiornaDatiViewModel(server: ServerDiProva.chePrecipita(.server("Richiesta non permessa")))
        await vm.avvia()
        XCTAssertEqual(vm.messaggio, "Richiesta non permessa")
        XCTAssertFalse(vm.inCorso)
    }

    // MARK: stagione

    func testPassaggioDiStagioneSoloConLeRoseVecchie() async {
        let adesso = ServerDiProva { metodo, percorso, _ in
            if percorso.hasPrefix("/api/stagione") { return Data(#"{"corrente": "2027-28", "rose": "2026-27", "nuova": true}"#.utf8) }
            return Data("{}".utf8)
        }
        let vm = StagioneViewModel(server: adesso)
        XCTAssertFalse(vm.puoArchiviare, "prima di sapere lo stato non si archivia")
        await vm.carica()
        XCTAssertTrue(vm.puoArchiviare)
        VersioniRisorse.condivise.imposta("\"vecchia\"", server: adesso.indirizzo, risorsa: "scelta:9")
        await vm.archiviaERiparti()
        XCTAssertTrue(vm.archiviata)
        XCTAssertNil(VersioniRisorse.condivise.leggi(server: adesso.indirizzo, risorsa: "scelta:9"),
                     "dopo la nuova stagione gli ETag ricordati sono vecchi: si dimenticano")
        XCTAssertEqual(adesso.quante("POST /api/nuova-stagione"), 1)
        XCTAssertFalse(vm.puoArchiviare, "una volta archiviata non si archivia di nuovo")
        await vm.archiviaERiparti()
        XCTAssertEqual(adesso.quante("POST /api/nuova-stagione"), 1)
    }

    func testStagioneInCorsoNonSiArchivia() async {
        let s = ServerDiProva.conFixture(["/api/stagione": "stagione"])
        let vm = StagioneViewModel(server: s)
        await vm.carica()
        XCTAssertFalse(vm.puoArchiviare)
        await vm.archiviaERiparti()
        XCTAssertEqual(s.quante("POST"), 0, "con le rose della stagione in corso non parte nessuna archiviazione")
    }

    func testErroreNellArchiviazione() async {
        let s = ServerDiProva { metodo, _, _ in
            if metodo == "POST" { throw ErroreApi.server("Nessuna rosa importata") }
            return Data(#"{"corrente": "2027-28", "rose": "2026-27", "nuova": true}"#.utf8)
        }
        let vm = StagioneViewModel(server: s)
        await vm.carica()
        await vm.archiviaERiparti()
        XCTAssertFalse(vm.archiviata)
        XCTAssertEqual(vm.errore, "Nessuna rosa importata")
    }

    func testLegaSaSeServeIlPassaggioDiStagione() async {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/stagione") { return Data(#"{"corrente": "2027-28", "rose": "2026-27", "nuova": true}"#.utf8) }
            if percorso.hasPrefix("/api/stato") { return try Fixture.dati("stato") }
            throw ErroreApi.server("no")
        }
        let vm = LegaViewModel(server: s)
        XCTAssertFalse(vm.nuovaStagione)
        await vm.info.ricarica()
        await vm.stagione.ricarica()
        XCTAssertTrue(vm.nuovaStagione)
        XCTAssertEqual(vm.info.dato?.miaSquadra, "Nuvola Ovest")
    }

    // MARK: regole

    private func regole(salvataggio: (@Sendable (Data) -> Data)? = nil) -> ServerDiProva {
        ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/regole/riconosci") { return try Fixture.dati("riconosci") }
            if metodo == "PUT" {
                if let salvataggio, let corpo { return salvataggio(corpo) }
                throw ErroreApi.server("Regole non valide:\n- prova")
            }
            return try Fixture.dati("regole")
        }
    }

    func testRegoleCaricateESubitoNonModificate() async {
        let vm = RegoleEditorViewModel(server: regole())
        XCTAssertFalse(vm.caricato)
        await vm.carica()
        XCTAssertTrue(vm.caricato)
        XCTAssertFalse(vm.modificato, "il caricamento non conta come modifica")
        XCTAssertEqual(vm.fasce.count, 6)
        XCTAssertEqual(vm.numero("bonus.assist").wrappedValue, 1)
        XCTAssertEqual(vm.moduliAttivi.count, 7)
        XCTAssertEqual(vm.postiFissi.wrappedValue, true)
        XCTAssertEqual(vm.votoUfficioAttivo.wrappedValue, false)
    }

    func testModificaDeiCampiESalvataggio() async throws {
        let ricevuto = Scatola<JSONValue>()
        let esito = regole { corpo in
            ricevuto.valore = try? JSONDecoder().decode(JSONValue.self, from: corpo)
            return corpo
        }
        let vm = RegoleEditorViewModel(server: esito)
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        XCTAssertTrue(vm.modificato)
        vm.alternaModulo("4-4-2")
        XCTAssertFalse(vm.moduliAttivi.contains("4-4-2"), "era attivo: si toglie")
        vm.alternaModulo("3-6-1")
        XCTAssertTrue(vm.moduliAttivi.contains("3-6-1"))
        vm.numero("panchina.posti.P").wrappedValue = 3     // 3 + 3 + 3 + 3 = 12 in panchina
        vm.votoUfficioAttivo.wrappedValue = true
        XCTAssertEqual(vm.valore.valore("voto_senza_sostituto")?.numero, 4)
        await vm.salva()
        XCTAssertEqual(vm.esito, Catalogo.Regole.regoleSalvateConsigli)
        XCTAssertTrue(vm.esitoRiuscito)
        XCTAssertFalse(vm.modificato)
        let r = try XCTUnwrap(ricevuto.valore)
        XCTAssertEqual(r.valore("bonus.assist")?.numero, 1.5)
        XCTAssertEqual(r.valore("panchina.numero")?.numero, 12, "con i posti fissi il numero è la somma dei posti")
        XCTAssertEqual(r.valore("crediti_iniziali"), .intero(500), "gli interi restano interi")
        XCTAssertNotNil(r.valore("soglia_primo_gol"), "i campi che l'app non mostra non si perdono")
    }

    func testErroreDalServerNelSalvataggio() async {
        let vm = RegoleEditorViewModel(server: regole())   // il PUT risponde con un errore
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 99
        await vm.salva()
        XCTAssertFalse(vm.esitoRiuscito)
        XCTAssertTrue(vm.esito?.contains("Regole non valide") == true, vm.esito ?? "")
        XCTAssertTrue(vm.modificato, "la modifica resta da salvare")
    }

    func testNessunModuloNonSiSalva() async {
        let s = regole { $0 }
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        for m in vm.moduliAttivi { vm.alternaModulo(m) }
        await vm.salva()
        XCTAssertEqual(vm.esito, "Scegli almeno un modulo.")
        XCTAssertEqual(s.quante("PUT"), 0, "non parte nessuna richiesta se il controllo fallisce")
    }

    func testFasceAggiungiETogli() async {
        let vm = RegoleEditorViewModel(server: regole())
        await vm.carica()
        vm.aggiungiFascia()
        XCTAssertEqual(vm.fasce.count, 7)
        XCTAssertTrue(vm.modificato)
        XCTAssertEqual(RegoleLogica.fasce(vm.valore).count, 7, "la fascia nuova è nel JSON")
        XCTAssertEqual(vm.fasce.last?.media, 7.75, "mezzo punto sopra l'ultima")
        let daTogliere = vm.fasce[0].id
        vm.togliFascia(daTogliere)
        XCTAssertEqual(RegoleLogica.fasce(vm.valore).count, 6)
        // la prova usa le fasce attuali
        vm.votiProva = [7, 7, 7, 7]
        XCTAssertEqual(vm.mediaProva, 7)
        XCTAssertEqual(vm.bonusProva, 3)
    }

    func testImportaDalRegolamentoDiLeghe() async throws {
        let vm = RegoleEditorViewModel(server: regole())
        await vm.carica()
        await vm.riconosci()
        XCTAssertEqual(vm.erroreRiconoscimento, Catalogo.Regole.incollaPrimaTesto)
        vm.testoRegolamento = "Rigore parato 4 punti"
        await vm.riconosci()
        XCTAssertEqual(vm.riconoscimento?.modifiche.count, 1)
        XCTAssertFalse(vm.modificato, "riconoscere non cambia niente")
        vm.applicaRiconosciute()
        XCTAssertEqual(vm.valore.valore("bonus.rigore_parato")?.numero, 3)
        XCTAssertTrue(vm.modificato)
        XCTAssertNil(vm.riconoscimento)
        XCTAssertEqual(vm.esito, "Valori applicati: controlla e tocca «Salva le regole».")
    }

    // MARK: importazione, crediti, avvisi, movimenti, squadre

    func testImportazioneDaTesto() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/rose/anteprima") {
                return Data(#"{"squadre": [{"nome": "A", "giocatori": [{"testo": "Prova", "stato": "sicuro", "id": 1, "nome": "Prova"}]}], "mia_squadra": "A"}"#.utf8)
            }
            return Data(#"{"squadre_importate": ["A"], "totale_squadre": 10, "avvisi": ["B: 24 giocatori"], "riepilogo": "A prende X", "differenze": {"nessuna_differenza": false, "svincolati_presi": [{"squadra": "A", "giocatori": [{"id": 1, "nome": "Prova"}]}], "testo": "A prende X"}}"#.utf8)
        }
        let vm = ImportaExcelViewModel(server: s)
        await vm.importaTesto()
        XCTAssertEqual(vm.errore, "Incolla prima il testo delle rose", "come la web (lega.incolla_prima_testo)")
        vm.testoRose = "Squadra A\nPortieri: ..."
        vm.sostituisciTutto = true
        await vm.importaTesto()
        XCTAssertNil(vm.errore)
        XCTAssertEqual(vm.anteprima?.squadre.map(\.nome), ["A"])
        XCTAssertEqual(s.quante("POST /api/rose/testo"), 0, "l'anteprima non salva")
        await vm.conferma()
        XCTAssertNil(vm.errore)
        XCTAssertEqual(vm.esito?.totaleSquadre, 10)
        XCTAssertEqual(vm.esito?.differenze?.svincolatiPresi?.first?.giocatori.first?.nome, "Prova")
        let corpo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "POST /api/rose/testo").last), as: UTF8.self)
        XCTAssertTrue(corpo.contains("\"sostituisci_tutto\":true"), corpo)
        XCTAssertEqual(vm.percorsoFile, "/api/rose/file?sostituisci_tutto=true")
        vm.sostituisciTutto = false
        XCTAssertEqual(vm.percorsoFile, "/api/rose/file?sostituisci_tutto=false")
    }

    func testImportazioneConErroreDelServer() async {
        let vm = ImportaExcelViewModel(server: ServerDiProva.chePrecipita(.server("Nessuna rosa trovata")))
        vm.testoRose = "boh"
        await vm.importaTesto()
        XCTAssertNil(vm.esito)
        XCTAssertEqual(vm.errore, "Nessuna rosa trovata")
    }

    func testMovimenti() async throws {
        let s = ServerDiProva { _, _, _ in
            Data(#"[{"quando": "2026-10-26T19:19:33", "scambi": [{"squadre": ["A", "B"], "da_a": [{"id": 1, "nome": "X"}], "da_b": []}], "svincolati_presi": [], "tagliati": [], "crediti": [{"squadra": "A", "prima": 30, "dopo": 22}], "testo": "Passaggio da A a B: X"}]"#.utf8)
        }
        let vm = MovimentiViewModel(server: s)
        await vm.carica()
        let m = try XCTUnwrap(vm.caricatore.dato?.first)
        XCTAssertEqual(m.scambi?.first?.squadre, ["A", "B"])
        XCTAssertEqual(m.scambi?.first?.daA.first?.nome, "X")
        XCTAssertEqual(m.crediti?.first?.dopo, 22)
        XCTAssertEqual(s.quante("GET /api/movimenti?limite=30"), 1)
    }

    func testMiaSquadraECrediti() async throws {
        let s = ServerDiProva.conFixture(["/api/squadre": "squadre"])
        let squadre = SquadreViewModel(server: s)
        await squadre.carica()
        XCTAssertEqual(squadre.mia, "Nuvola Ovest", "la squadra segnata come «mia» nella fixture")
        await squadre.impostaMia("Borgo Alto")
        let corpo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "PUT /api/mia-squadra").last), as: UTF8.self)
        XCTAssertEqual(corpo, "{\"nome\":\"Borgo Alto\"}")
        XCTAssertEqual(s.quante("GET /api/squadre"), 2, "dopo la scelta l'elenco si ricarica")

        let crediti = CreditiViewModel(server: s)
        await crediti.carica()
        crediti.valori["Borgo Alto"] = "120"
        crediti.valori["Altra"] = "boh"   // non è un numero: non si manda
        await crediti.salva()
        let c = String(decoding: try XCTUnwrap(s.corpiInviati(a: "PUT /api/crediti").last), as: UTF8.self)
        XCTAssertTrue(c.contains("\"Borgo Alto\":120"), c)
        XCTAssertFalse(c.contains("Altra"), c)
        XCTAssertEqual(crediti.messaggio, Catalogo.Lega.creditiSalvati)
    }

    func testAvvisiConAppNativa() async throws {
        let s = ServerDiProva.conFixture(["/api/avvisi": "avvisi"])
        let vm = AvvisiServerViewModel(server: s)
        await vm.carica()
        XCTAssertEqual(vm.impostazioni?.app_nativa, false)
        vm.impostazioni?.app_nativa = true
        await vm.salva()
        let corpo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "PUT /api/avvisi").last), as: UTF8.self)
        XCTAssertTrue(corpo.contains("\"app_nativa\":true"), corpo)
        XCTAssertTrue(corpo.contains("\"promemoria_60\":true"), corpo)
        await vm.provaAvviso()
        XCTAssertEqual(vm.messaggio, "Avviso di prova inviato.")
        XCTAssertNil(vm.erroreSalvataggio)
    }

    func testAvvisiSalvataggioFallitoSiVedeETornaComePrima() async throws {
        let rotto = Scatola<Bool>()
        rotto.valore = true
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", rotto.valore == true { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/avvisi") { return try Fixture.dati("avvisi") }
            return Data("{}".utf8)
        }
        let vm = AvvisiServerViewModel(server: s)
        await vm.carica()
        let prima = try XCTUnwrap(vm.impostazioni?.riepilogo)
        vm.impostazioni?.riepilogo = !prima
        await vm.salva()
        XCTAssertEqual(vm.erroreSalvataggio, "Non ho salvato la modifica. " + ErroreApi.testoNonRaggiungibile)
        XCTAssertEqual(vm.impostazioni?.riepilogo, prima, "l'interruttore torna come lo ha il server")
        XCTAssertTrue(vm.puoRiprovare)

        // la rete torna: «Riprova» manda la scelta di prima e l'errore sparisce
        rotto.valore = false
        await vm.riprova()
        XCTAssertNil(vm.erroreSalvataggio)
        XCTAssertEqual(vm.impostazioni?.riepilogo, !prima)
        let corpo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "PUT /api/avvisi").last), as: UTF8.self)
        XCTAssertTrue(corpo.contains("\"riepilogo\":\(!prima)"), corpo)
        XCTAssertFalse(vm.puoRiprovare)
    }

    func testAvvisiConflittoRileggeSenzaRiprova() async throws {
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT" { throw ErroreApi.conflitto }
            if percorso.hasPrefix("/api/avvisi") { return try Fixture.dati("avvisi") }
            return Data("{}".utf8)
        }
        let vm = AvvisiServerViewModel(server: s)
        await vm.carica()
        vm.impostazioni?.riepilogo.toggle()
        await vm.salva()
        XCTAssertNotNil(vm.erroreSalvataggio)
        XCTAssertFalse(vm.puoRiprovare, "dopo un conflitto si vedono già i dati nuovi del server")
        XCTAssertEqual(s.quante("GET /api/avvisi"), 2, "si rilegge")
    }
}
