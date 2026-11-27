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
        XCTAssertEqual(vm.messaggio, "Aggiornato, ma con problemi: \nUnderstat non risponde")
    }

    /// #958: le frasi del server finiscono col punto (#956) e la web le mostra una per riga sotto la testa
    /// (`"\n" + errori.join("\n")`); prima l'iPhone le univa con «; » e si leggeva «…riprova più tardi.; I controlli…».
    func testAggiornamentoConPiuProblemiUnaFrasePerRigaComeLaWeb() async {
        let s = ServerDiProva { metodo, _, _ in
            metodo == "POST" ? Data(#"{"avviato": true}"#.utf8)
                : Data(#"{"in_corso": false, "errori": ["Sito Uno non risponde: riprova più tardi.", "I controlli sui dati hanno trovato un problema: 2 giocatori senza ruolo."]}"#.utf8)
        }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausa = 0
        await vm.avvia()
        XCTAssertEqual(vm.errori.count, 2)
        XCTAssertEqual(vm.messaggio, "Aggiornato, ma con problemi: \nSito Uno non risponde: riprova più tardi.\n"
                       + "I controlli sui dati hanno trovato un problema: 2 giocatori senza ruolo.")
        XCTAssertFalse(vm.messaggio?.contains("; ") ?? true, "mai più le frasi unite con «; »")
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
        XCTAssertFalse(vm.pulsanteSpento, "come la web, che dopo cinque tentativi riaccende il pulsante")
        XCTAssertNil(vm.fraseOccupato)
    }

    func testAggiornamentoPartitoDaQuiMostraLaFraseEIlMessaggioDellAvvioComeLaWeb() async {
        let finito = Scatola<Bool>()
        let s = ServerDiProva { metodo, _, _ in
            if metodo == "POST" { return Data(#"{"avviato": true}"#.utf8) }
            return Data((finito.valore == true ? #"{"in_corso": false, "errori": []}"# : #"{"in_corso": true, "errori": []}"#).utf8)
        }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausa = 10_000_000
        let tocco = Task { await vm.avvia() }
        await attendi("l'aggiornamento partito si segue", finche: { s.quante("GET /api/aggiorna") >= 1 })
        XCTAssertTrue(vm.inCorso)
        XCTAssertTrue(vm.pulsanteSpento)
        XCTAssertEqual(vm.fraseOccupato, Catalogo.Aggiorna.inCorso, "la frase della web anche con l'aggiornamento partito da qui")
        XCTAssertEqual(vm.messaggio, Catalogo.Aggiorna.avviato, "insieme al messaggio dell'avvio, come l'avviso della web")
        finito.valore = true
        await tocco.value
        XCTAssertFalse(vm.pulsanteSpento)
        XCTAssertNil(vm.fraseOccupato, "finito l'aggiornamento la frase sparisce")
        XCTAssertEqual(vm.messaggio, Catalogo.Aggiorna.ok)
    }

    func testAggiornamentoNonPartito() async {
        let vm = AggiornaDatiViewModel(server: ServerDiProva.chePrecipita(.server("Richiesta non permessa")))
        await vm.avvia()
        XCTAssertEqual(vm.messaggio, "Richiesta non permessa")
        XCTAssertFalse(vm.inCorso)
    }

    // MARK: server occupato con un aggiornamento partito altrove (#773, come la web con #772)

    func testServerOccupatoSpegneIlPulsanteConLaFraseELiberoLoRiaccende() async {
        let occupato = Scatola<Bool>()
        occupato.valore = true
        let s = ServerDiProva { _, percorso, _ in
            guard percorso == "/api/stato" else { throw ErroreApi.server("non serve a questo test") }
            return statoDelServer(occupato: occupato.valore ?? false)
        }
        let vm = LegaViewModel(server: s)
        await vm.info.ricarica()
        await attendi("il pulsante si spegne con lo stato «occupato»", finche: { vm.aggiornamento.pulsanteSpento })
        XCTAssertEqual(vm.aggiornamento.fraseOccupato, Catalogo.Aggiorna.inCorso)
        XCTAssertFalse(vm.aggiornamento.inCorso, "l'aggiornamento non è partito da qui: l'etichetta resta «Aggiorna i dati»")
        occupato.valore = false
        await vm.info.ricarica()
        await attendi("il pulsante si riaccende con lo stato libero", finche: { !vm.aggiornamento.pulsanteSpento })
        XCTAssertNil(vm.aggiornamento.fraseOccupato)
    }

    func testLaCopiaSalvataSulTelefonoNonSpegneIlPulsante() async {
        // una copia di /api/stato salvata mentre il server era occupato; la lettura nuova viene annullata (pagina lasciata) e il
        // Caricatore torna a mostrare la copia come dato caricato
        let s = ServerDiProva { _, _, _ in
            try await Task.sleep(for: .seconds(30))
            throw ErroreApi.rete("mai")
        }
        Cache.salva(statoDelServer(occupato: true), "/api/stato", indirizzo: s.indirizzo)
        let vm = LegaViewModel(server: s)
        let lettura = Task { await vm.info.ricarica() }
        await attendi("la richiesta al server è partita", finche: { s.quante("GET /api/stato") >= 1 })
        lettura.cancel()
        await lettura.value
        XCTAssertEqual(vm.info.dato?.aggiornamentoInCorso, true, "la copia salvata si mostra")
        XCTAssertNil(vm.info.errore, "una lettura annullata non è un errore")
        XCTAssertFalse(vm.aggiornamento.pulsanteSpento, "uno stato vecchio non spegne il pulsante")
        XCTAssertNil(vm.aggiornamento.fraseOccupato)
    }

    func testUnaLetturaAnnullataNonRimetteLoStatoDiPrima() async {
        // in Gestione il server era occupato e poi la rilettura l'ha trovato libero; tornando indietro e rientrando la lettura delle
        // Impostazioni si annulla, e il Caricatore rimette la sua ultima risposta («occupato»): non deve spegnere il pulsante
        let letture = Contatore()
        let s = ServerDiProva { _, percorso, _ in
            guard percorso == "/api/stato" else { throw ErroreApi.server("non serve a questo test") }
            switch letture.passo() {
            case 0: return statoDelServer(occupato: true)
            case 1: return statoDelServer(occupato: false)
            default:
                try await Task.sleep(for: .seconds(30))
                throw ErroreApi.rete("mai")
            }
        }
        let vm = LegaViewModel(server: s)
        await vm.info.ricarica()
        XCTAssertTrue(vm.aggiornamento.pulsanteSpento)
        vm.aggiornamento.pausaStato = .zero
        await vm.aggiornamento.segui()
        XCTAssertFalse(vm.aggiornamento.pulsanteSpento, "la rilettura ha trovato il server libero")
        let lettura = Task { await vm.info.ricarica() }
        await attendi("la terza richiesta è partita", finche: { s.quante("GET /api/stato") >= 3 })
        lettura.cancel()
        await lettura.value
        XCTAssertEqual(vm.info.dato?.aggiornamentoInCorso, true, "il Caricatore mostra di nuovo la sua ultima risposta")
        XCTAssertFalse(vm.aggiornamento.pulsanteSpento, "una risposta già usata non torna a spegnere il pulsante")
        XCTAssertNil(vm.aggiornamento.fraseOccupato)
    }

    func testServerOccupatoSiRileggeFinoAQuandoTornaLibero() async {
        let letture = Contatore()
        let s = ServerDiProva { _, _, _ in statoDelServer(occupato: letture.passo() < 2) }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausaStato = .zero
        vm.segna(occupato: true)
        await vm.segui()
        XCTAssertEqual(s.richieste, Array(repeating: "GET /api/stato", count: 3),
                       "subito, poi una lettura dopo l'altra finché il server non è libero")
        XCTAssertFalse(vm.pulsanteSpento)
        XCTAssertNil(vm.fraseOccupato)
    }

    func testServerLiberoNonSiRilegge() async {
        let s = ServerDiProva { _, _, _ in statoDelServer(occupato: false) }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausaStato = .zero
        vm.segna(occupato: false)
        await vm.segui()
        XCTAssertEqual(s.quante("GET /api/stato"), 0)
        XCTAssertFalse(vm.pulsanteSpento)
        XCTAssertNil(vm.fraseOccupato)
    }

    func testErroreDiReteSiRiprovaEIlPulsanteSiRiaccende() async {
        let letture = Contatore()
        let s = ServerDiProva { _, _, _ in
            if letture.passo() == 0 { throw ErroreApi.rete("giù") }
            return statoDelServer(occupato: false)
        }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausaStato = .zero
        vm.segna(occupato: true)
        await vm.segui()
        XCTAssertEqual(s.quante("GET /api/stato"), 2, "dopo un errore di rete si rilegge alla volta dopo")
        XCTAssertFalse(vm.pulsanteSpento, "un errore di rete non lascia il pulsante spento per sempre")
    }

    func testUscendoDallaPaginaSiSmetteDiRileggere() async {
        let s = ServerDiProva { _, _, _ in throw ErroreApi.rete("giù") }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausaStato = .milliseconds(20)
        vm.segna(occupato: true)
        let pagina = Task { await vm.segui() }
        await attendi("almeno due letture", finche: { s.quante("GET /api/stato") >= 2 })
        XCTAssertTrue(vm.pulsanteSpento, "senza risposta lo stato resta quello di prima, come la web")
        pagina.cancel()
        await pagina.value
        let fatte = s.quante("GET /api/stato")
        try? await Task.sleep(for: .milliseconds(150))
        XCTAssertEqual(s.quante("GET /api/stato"), fatte, "fuori dalla pagina lo stato non si rilegge")
    }

    func testGiaInCorsoAlToccoNonSpegneIlPulsante() async {
        let s = ServerDiProva { _, _, _ in Data(#"{"avviato": false, "messaggio": "Aggiornamento già in corso"}"#.utf8) }
        let vm = AggiornaDatiViewModel(server: s)
        await vm.avvia()
        XCTAssertEqual(vm.messaggio, "Aggiornamento già in corso", "il messaggio del server, come prima")
        XCTAssertFalse(vm.pulsanteSpento, "senza una rilettura dello stato il pulsante non resta spento")
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

    /// Un server dove un altro dispositivo archivia la stagione subito dopo la prima lettura dello stato: la prima risposta di
    /// `/api/stagione` dice ancora «nuova», le successive no. `POST /api/nuova-stagione` lancia `rifiuto`.
    private func archiviataAltrove(rifiuto: ErroreApi) -> ServerDiProva {
        let letture = Contatore()
        return ServerDiProva { metodo, _, _ in
            if metodo == "POST" { throw rifiuto }
            return letture.passo() == 0 ? Data(#"{"corrente": "2027-28", "rose": "2026-27", "nuova": true}"#.utf8)
                                        : Data(#"{"corrente": "2027-28", "rose": "2027-28", "nuova": false}"#.utf8)
        }
    }

    /// #731: il server rifiuta con 409 perché le rose sono già della stagione in corso (un altro dispositivo ha archiviato) e non
    /// scrive niente. Si mostra il suo messaggio così com'è e lo stato si rilegge: il passaggio sparisce, come sulla web.
    func testRifiutoPercheGiaArchiviataRileggeLoStatoETogliePassaggio() async {
        let messaggio = "Le rose sono già della stagione in corso: non c'è niente da archiviare."
        let s = archiviataAltrove(rifiuto: .server(messaggio))
        let vm = StagioneViewModel(server: s)
        await vm.carica()
        XCTAssertTrue(vm.puoArchiviare)
        await vm.archiviaERiparti()
        XCTAssertEqual(vm.errore, messaggio, "il messaggio del server, così com'è")
        XCTAssertFalse(vm.archiviata)
        XCTAssertEqual(s.quante("GET /api/stagione"), 2, "dopo il rifiuto lo stato della stagione si rilegge")
        XCTAssertFalse(vm.puoArchiviare, "le rose sono già della stagione in corso: il passaggio non c'è più")
        XCTAssertEqual(s.quante("POST /api/nuova-stagione"), 1)
    }

    /// #731: 412, le rose sono cambiate su un altro dispositivo e il server non ha scritto niente. Lo stato si rilegge e si dice
    /// che le rose sono cambiate, con la frase del catalogo che l'importazione delle rose usa per lo stesso caso.
    func testRoseCambiateAltroveRileggeLoStatoEDiceCheSonoCambiate() async {
        let s = archiviataAltrove(rifiuto: .conflitto)
        let vm = StagioneViewModel(server: s)
        await vm.carica()
        await vm.archiviaERiparti()
        XCTAssertEqual(vm.errore, Catalogo.Ar.cambiate)
        XCTAssertFalse(vm.archiviata)
        XCTAssertEqual(s.quante("GET /api/stagione"), 2, "dopo il 412 lo stato della stagione si rilegge")
        XCTAssertFalse(vm.puoArchiviare)
    }

    /// Senza risposta dal server (rete giù) non si sa niente di nuovo: lo stato non si rilegge, che sarebbe un'altra attesa a vuoto,
    /// e il passaggio resta per riprovare.
    func testSenzaRispostaDelServerLoStatoNonSiRilegge() async {
        let s = ServerDiProva { metodo, _, _ in
            if metodo == "POST" { throw ErroreApi.rete("giù") }
            return Data(#"{"corrente": "2027-28", "rose": "2026-27", "nuova": true}"#.utf8)
        }
        let vm = StagioneViewModel(server: s)
        await vm.carica()
        await vm.archiviaERiparti()
        XCTAssertEqual(vm.errore, ErroreApi.rete("giù").localizedDescription)
        XCTAssertEqual(s.quante("GET /api/stagione"), 1)
        XCTAssertTrue(vm.puoArchiviare)
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
        // dentro i limiti: un numero fuori (99) lo ferma l'app prima del server, come la web (#889, RegoleLimitiComeLaWebTests)
        vm.numero("bonus.assist").wrappedValue = 1.5
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
        XCTAssertEqual(vm.esito, Catalogo.Regole.scegliAlmenoModulo, "la frase della web")
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
        // la frase della web (`regole.valori_applicati_controlla`), con il nome del pulsante (#559)
        XCTAssertEqual(vm.esito, Catalogo.Regole.valoriApplicatiControlla)
        XCTAssertEqual(vm.esito, "Valori applicati: controlla e tocca «Salva le regole»")
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

    // la scelta della propria squadra (`LegaViewModel.scegliMiaSquadra`, #863) la prova `SceltaMiaSquadraTests`
}

/// Una risposta inventata di `GET /api/stato` con `aggiornamento_in_corso` (gli altri campi non servono a questi test).
private func statoDelServer(occupato: Bool) -> Data {
    Data(#"{"stagione": "2026-27", "versione": "1.0", "aggiornamento_in_corso": \#(occupato)}"#.utf8)
}
