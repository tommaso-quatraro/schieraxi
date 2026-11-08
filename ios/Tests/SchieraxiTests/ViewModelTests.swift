import XCTest
@testable import Schieraxi

/// ViewModel di Oggi, Formazione, Scambi e Mercato con un server finto che risponde con le fixture (risposte vere del server).
@MainActor
final class OggiViewModelTests: XCTestCase {
    private func vm(_ server: ServerDiProva) -> OggiViewModel { OggiViewModel(server: server, conPromemoria: false) }

    func testCaricaLaGiornataEDividiGliAvvisi() async throws {
        let server = ServerDiProva.conFixture(["/api/oggi": "oggi", "/api/stato": "stato"])
        let vm = vm(server)
        XCTAssertNil(vm.oggi)
        await vm.carica()
        XCTAssertEqual(vm.oggi?.giornata, 9)
        XCTAssertNil(vm.errore)
        XCTAssertEqual(vm.daControllare.count, 2, "i due dubbi in formazione")
        XCTAssertEqual(vm.indisponibili.count, 6, "sei infortunati fuori formazione")
        XCTAssertEqual(vm.diffidati.count, 0)
        XCTAssertGreaterThanOrEqual(vm.partitePerGiorno.count, 2)
        XCTAssertEqual(vm.partitePerGiorno.reduce(0) { $0 + $1.partite.count }, 10)
        XCTAssertEqual(server.quante("GET /api/oggi"), 1)
    }

    func testIlBannerDelleNovitaSiVedeSoloSeLaVersioneECambiata() async throws {
        let vm = vm(.conFixture(["/api/oggi": "oggi", "/api/stato": "stato"]))
        await vm.carica()
        XCTAssertEqual(vm.novitaDaVedere(ultimaVista: ""), "1.14")
        XCTAssertEqual(vm.novitaDaVedere(ultimaVista: "1.13"), "1.14")
        XCTAssertNil(vm.novitaDaVedere(ultimaVista: "1.14"), "già guardate")
    }

    func testServerSpentoMostraUnErroreInItaliano() async throws {
        let vm = vm(.chePrecipita())
        await vm.carica()
        XCTAssertNil(vm.oggi)
        XCTAssertEqual(vm.errore, "Non riesco a collegarmi a SchieraXI. Controlla la connessione e riprova.")
    }

    func testIlComandoAggiornaRicaricaOggi() async throws {
        let server = ServerDiProva.conFixture(["/api/oggi": "oggi", "/api/stato": "stato"])
        let vm = vm(server)
        await vm.carica()
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        await attendi("seconda richiesta di /api/oggi", finche: { server.quante("GET /api/oggi") >= 2 })
        withExtendedLifetime(vm) {}
    }
}

@MainActor
final class FormazioneViewModelTests: XCTestCase {
    /// Un server con la formazione vera e una valutazione che risponde secondo i titolari ricevuti.
    private func server(scelta: Bool = false, ritardoDelPrimo: UInt64 = 0, primoId: Int? = nil) -> ServerDiProva {
        ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                var titolari: [Int] = []
                if let corpo, let o = try? JSONSerialization.jsonObject(with: corpo) as? [String: Any] { titolari = (o["titolari"] as? [Int]) ?? [] }
                // la risposta alla PRIMA richiesta (quella con il titolare originale) arriva in ritardo e con un punteggio diverso
                if let primoId, titolari.contains(primoId) {
                    try await Task.sleep(nanoseconds: ritardoDelPrimo)
                    return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 10.0, "dev": 4.0, "panchina": [], "differenza": -1.0, "consigliata": 71.1}"#.utf8)
                }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "dev": 4.0, "panchina": [], "differenza": -0.5, "consigliata_stesso_modulo": 71.1, "brutta_giornata": 60.0, "giornata_eccezionale": 80.0}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") {
                if metodo == "GET" && scelta {
                    let f: Formazione = try Fixture.decodifica("formazione")
                    let ids = f.titolari.map(\.id).map(String.init).joined(separator: ",")
                    return Data("{\"titolari\": [\(ids)], \"modulo\": \"4-3-3\", \"salvata\": \"2026-11-02T21:40:00\"}".utf8)
                }
                if metodo == "GET" { throw ErroreApi.server("nessuna scelta salvata") }
                return Data("{\"ok\": true}".utf8)
            }
            if percorso.hasPrefix("/api/formazione") { return try Fixture.dati("formazione") }
            throw ErroreApi.server("nessuna fixture per \(percorso)")
        }
    }

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        let f = try XCTUnwrap(vm.formazione)
        return (vm, f)
    }

    func testLaFormazioneConsigliata() async throws {
        let (vm, f) = try await caricata(server())
        let v = vm.vista(f)
        XCTAssertEqual(v.modulo, "4-3-3")
        XCTAssertEqual(v.titolari.count, 11)
        XCTAssertEqual(v.panchina.count, 11)
        XCTAssertEqual(try XCTUnwrap(v.punti), 71.1, accuracy: 0.01)
        XCTAssertNil(vm.manuale)
        XCTAssertEqual(vm.testo(f).components(separatedBy: "\n").first, "9ª giornata di Serie A · 4-3-3", "la fixture non ha `giornata_lega`")
        XCTAssertEqual(vm.fuori(f, v).count, 3, "25 in rosa, 11 titolari e 11 in panchina")
        XCTAssertEqual(vm.contestoConfronto, ContestoConfronto(livello: 0, modulo: "4-3-3", squadra: nil))
    }

    func testStileEModulo() async throws {
        let (vm, f) = try await caricata(server())
        vm.rischio = 2
        vm.cambiaStile()
        let audace = try XCTUnwrap(f.livelli?.first { $0.rischio == 2 })
        let atteso = try XCTUnwrap(audace.moduli.first { $0.modulo == audace.modulo })
        XCTAssertEqual(vm.vista(f).modulo, audace.modulo)
        XCTAssertEqual(try XCTUnwrap(vm.vista(f).punti), atteso.punteggioAtteso, accuracy: 0.001)
        XCTAssertEqual(vm.fascia(f), IntervalloPunti.frase(atteso.intervallo, dev: atteso.dev), "la fascia è quella del modulo scelto")
        // un altro modulo dello stesso stile
        let altro = try XCTUnwrap(audace.moduli.first { $0.modulo != audace.modulo })
        vm.scegliModulo(altro.modulo)
        XCTAssertEqual(vm.vista(f).modulo, altro.modulo)
        XCTAssertEqual(vm.vista(f).titolari.map(\.id), altro.titolari)
        XCTAssertEqual(vm.moduloAttivo(audace), altro.modulo)
        // cambiando stile si torna al modulo consigliato di quello stile
        vm.rischio = -1
        vm.cambiaStile()
        XCTAssertNil(vm.moduloScelto)
    }

    func testScegliereUnoStileAzzeraIlModuloEIPuntiSiRicalcolano() async throws {
        let (vm, f) = try await caricata(server())
        let livelli = try XCTUnwrap(f.livelli)
        let primo = try XCTUnwrap(livelli.first)
        // un modulo scelto a mano resta fisso (anche se si ricarica la vista)...
        let altro = try XCTUnwrap(primo.moduli.first { $0.modulo != primo.modulo })
        vm.rischio = primo.rischio
        vm.scegliModulo(altro.modulo)
        XCTAssertEqual(try XCTUnwrap(vm.vista(f).punti), altro.punteggioAtteso, accuracy: 0.001)
        XCTAssertEqual(vm.vista(f).modulo, altro.modulo)
        // ...finché si tocca uno stile, anche lo stesso: torna il modulo proposto e i punti di quello
        vm.scegliStile(primo.rischio)
        XCTAssertNil(vm.moduloScelto)
        XCTAssertEqual(vm.vista(f).modulo, primo.modulo)
        XCTAssertEqual(try XCTUnwrap(vm.vista(f).punti), primo.punteggioAtteso, accuracy: 0.001)
    }

    func testStileConDescrizioneESenza() throws {
        let nuovo = Data(#"""
        {"giornata": 9, "modulo": "4-3-3", "punteggio_atteso": 60.5, "titolari": [], "panchina": [], "stile_consigliato": 0,
         "livelli": [{"rischio": -1, "stile": -1, "nome": "Sicura", "descrizione": "Preferisce i titolari più sicuri.", "modulo": "5-3-2",
                      "punteggio_atteso": 59.0, "moduli": []}]}
        """#.utf8)
        let f: Formazione = try Decodifica.decodifica(nuovo, snake: true)
        XCTAssertEqual(f.stileConsigliato, 0)
        XCTAssertEqual(f.livelli?.first?.stile, -1)
        XCTAssertEqual(f.livelli?.first?.descrizione, "Preferisce i titolari più sicuri.")
        // un server vecchio non manda i campi nuovi: la formazione si legge lo stesso
        let vecchia: Formazione = try Fixture.decodifica("formazione")
        XCTAssertNotNil(vecchia.livelli)
    }

    func testModificaAManoESostituzione() async throws {
        let s = server()
        let (vm, f) = try await caricata(s)
        vm.iniziaModificaManuale(f)
        XCTAssertEqual(vm.manuale?.count, 11)
        await attendi("prima valutazione", finche: { vm.valutazione != nil })
        XCTAssertEqual(vm.valutazione?.punteggioAtteso, 20.0)
        XCTAssertEqual(vm.valutazione?.bruttaGiornata, 60.0)
        XCTAssertEqual(vm.valutazione?.giornataEccezionale, 80.0)
        XCTAssertEqual(vm.vista(f).punti, 20.0, "in modifica a mano si mostrano i punti calcolati dal server")

        // sostituisce un difensore con uno della rosa (non titolare)
        let uscente = try XCTUnwrap(vm.vista(f).titolari.first { $0.ruolo == "D" })
        let titolari = Set(vm.manuale ?? [])
        let entrante = try XCTUnwrap(f.schede?.values.first { $0.ruolo == "D" && !titolari.contains($0.id) })
        vm.sostituisci(uscente.id, con: entrante.id)
        XCTAssertTrue(vm.manuale?.contains(entrante.id) == true)
        XCTAssertFalse(vm.manuale?.contains(uscente.id) == true)
        await attendi("seconda valutazione", finche: { s.quante("POST /api/formazione/valuta") >= 2 })
    }

    func testUnaRispostaArrivataInRitardoNonSovrascriveQuellaNuova() async throws {
        // Il primo calcolo (con il titolare originale) arriva dopo 0,5 s con 10 punti; il secondo (dopo la sostituzione) arriva subito con 20.
        let f0: Formazione = try Fixture.decodifica("formazione")
        let uscente = try XCTUnwrap(f0.titolari.first { $0.ruolo == "D" })
        let s = server(ritardoDelPrimo: 500_000_000, primoId: uscente.id)
        let (vm, f) = try await caricata(s)
        vm.iniziaModificaManuale(f)
        let titolari = Set(vm.manuale ?? [])
        let entrante = try XCTUnwrap(f.schede?.values.first { $0.ruolo == "D" && !titolari.contains($0.id) })
        // il tempo di far partire la prima richiesta (quella lenta): poi la sostituzione fa partire la seconda
        await attendi("prima richiesta partita", finche: { s.quante("POST /api/formazione/valuta") >= 1 })
        vm.sostituisci(uscente.id, con: entrante.id)
        await attendi("risposta veloce", finche: { vm.valutazione?.punteggioAtteso == 20.0 })
        // si aspetta che anche la risposta lenta sia arrivata: non deve cambiare niente
        try await Task.sleep(nanoseconds: 900_000_000)
        XCTAssertEqual(s.quante("POST /api/formazione/valuta"), 2)
        XCTAssertEqual(vm.valutazione?.punteggioAtteso, 20.0, "la risposta vecchia (10 punti) va ignorata")
    }

    func testLaSceltaSalvataRiparteDaLa() async throws {
        let (vm, _) = try await caricata(server(scelta: true))
        await attendi("scelta salvata caricata", finche: { vm.valutazione != nil })
        XCTAssertEqual(vm.manuale?.count, 11)
    }

    func testSalvaEdEliminaLaScelta() async throws {
        let s = server()
        let (vm, f) = try await caricata(s)
        vm.iniziaModificaManuale(f)
        await attendi("valutazione", finche: { vm.valutazione != nil })
        await vm.valuta(salva: true)
        let corpo = try XCTUnwrap(s.corpiInviati(a: "POST /api/formazione/valuta").last)
        XCTAssertTrue(String(decoding: corpo, as: UTF8.self).contains("\"salva\":true"))
        guard case .salvata = vm.statoScelta else { return XCTFail("dopo il salvataggio la riga dice «salvata»: \(vm.statoScelta)") }
        XCTAssertFalse(vm.statoScelta.daSalvare, "niente pulsante «Salva» su una formazione già salvata")
        XCTAssertNil(vm.messaggio, "lo stato sta nella riga fissa, non in un messaggio che sparisce")
        await vm.tornaAllaConsigliata(f)
        XCTAssertNil(vm.manuale)
        XCTAssertNil(vm.valutazione)
        XCTAssertEqual(vm.statoScelta, .consigliata)
        XCTAssertEqual(s.quante("DELETE /api/scelta?giornata=9"), 1)
    }

    // Il 412 (scelta cambiata da un altro dispositivo) sta in `SceltaCambiataAltroveTests` (Swift Testing, #477).

    func testSeIlServerNonCancellaLaSceltaRestaDovEra() async throws {
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "DELETE" { throw ErroreApi.rete("giù") }
            if percorso.hasPrefix("/api/formazione/valuta") { return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8) }
            if percorso.hasPrefix("/api/scelta") { throw ErroreApi.server("niente") }
            return try Fixture.dati("formazione")
        }
        let (vm, f) = try await caricata(s)
        vm.iniziaModificaManuale(f)
        await vm.tornaAllaConsigliata(f)
        XCTAssertNotNil(vm.manuale, "la scelta salvata non è stata cancellata: resta la modifica a mano")
        XCTAssertNotNil(vm.messaggio)
    }

    // MARK: scelta salvata sempre visibile

    func testLaSceltaSalvataSiVedeAncheRiaprendo() async throws {
        let srv = server(scelta: true)
        let (vm, f) = try await caricata(srv)
        await attendi("scelta salvata calcolata", finche: { vm.valutazioneAttuale != nil })
        XCTAssertEqual(vm.statoScelta, .salvata(Quando.data("2026-11-02T21:40:00")))
        XCTAssertFalse(vm.statoScelta.daSalvare, "riaprendo non sembra di dover risalvare")
        // una sostituzione: «Modifiche non salvate»; «Annulla modifiche» torna a quella salvata
        let uscente = try XCTUnwrap(vm.vista(f).titolari.first { $0.ruolo == "D" })
        let titolari = Set(vm.manuale ?? [])
        let entrante = try XCTUnwrap(f.schede?.values.first { $0.ruolo == "D" && !titolari.contains($0.id) })
        vm.sostituisci(uscente.id, con: entrante.id)
        XCTAssertEqual(vm.statoScelta, .modificata(Quando.data("2026-11-02T21:40:00")))
        XCTAssertEqual(FormazioneView.etichettaSalva(vm.statoScelta), "Salva le modifiche")
        vm.annullaModifiche()
        XCTAssertEqual(vm.statoScelta, .salvata(Quando.data("2026-11-02T21:40:00")))
        // ricaricando (tornando sulla scheda) non si rifà la valutazione di una scelta già calcolata
        try await Task.sleep(nanoseconds: 500_000_000)   // finiscono i calcoli partiti con la sostituzione
        let prima = srv.quante("POST /api/formazione/valuta")
        await vm.carica()
        XCTAssertEqual(srv.quante("POST /api/formazione/valuta"), prima)
        XCTAssertEqual(vm.statoScelta, .salvata(Quando.data("2026-11-02T21:40:00")))
    }

    func testSenzaSceltaSalvataSiVedeLaConsigliataESiSalvaConUnTocco() async throws {
        let srv = ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") { return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 71.1, "panchina": []}"#.utf8) }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let (vm, f) = try await caricata(srv)
        XCTAssertEqual(vm.statoScelta, .consigliata)
        XCTAssertNil(vm.manuale)
        await vm.salvaQuesta(f)
        let corpo = String(decoding: try XCTUnwrap(srv.corpiInviati(a: "POST /api/formazione/valuta").last), as: UTF8.self)
        XCTAssertTrue(corpo.contains("\"salva\":true"), corpo)
        XCTAssertEqual(vm.manuale?.count, 11, "si salvano gli undici che si stavano guardando")
        guard case .salvata = vm.statoScelta else { return XCTFail("\(vm.statoScelta)") }
    }

    func testSeLaLetturaDellaSceltaNonRiesceNonSiDiceNiente() async throws {
        let (vm, _) = try await caricata(server())   // la lettura della scelta risponde con un errore
        XCTAssertEqual(vm.statoScelta, .sconosciuto, "non si dice «non hai salvato» se non lo si sa")
    }

    // MARK: (17) durante il calcolo niente punti della consigliata

    func testDuranteIlCalcoloSiVedeCalcoloENonIPuntiDellaConsigliata() async throws {
        let srv = ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                try await Task.sleep(nanoseconds: 400_000_000)
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let (vm, f) = try await caricata(srv)
        vm.iniziaModificaManuale(f)
        XCTAssertNil(vm.vista(f).punti, "mentre il server calcola, niente punti (prima c'erano quelli della consigliata)")
        XCTAssertTrue(vm.inCalcolo)
        XCTAssertEqual(vm.vista(f).modulo, "4-3-3", "il modulo si conta dai ruoli dei titolari")
        XCTAssertNil(vm.fascia(f))
        await attendi("calcolo finito", finche: { vm.vista(f).punti != nil })
        XCTAssertEqual(vm.vista(f).punti, 20.0)
        XCTAssertFalse(vm.inCalcolo)
    }

    func testSeIlCalcoloNonRiesceSiPuoRiprovare() async throws {
        let srv = ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") { throw ErroreApi.rete("giù") }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let (vm, f) = try await caricata(srv)
        vm.iniziaModificaManuale(f)
        await attendi("calcolo non riuscito", finche: { vm.calcoloNonRiuscito })
        XCTAssertNil(vm.vista(f).punti, "nessun punto della consigliata al posto di quelli non calcolati")
        XCTAssertFalse(vm.inCalcolo)
        XCTAssertNotNil(vm.messaggio)
    }

    // (18) una scelta salvata che non vale più non si cancella da sola: `RigaStatoComeWebTests`

    // giornata chiusa (dopo la scadenza): `FormazioneChiusaTests`

    func testFormazioneDiUnAltraSquadra() async throws {
        let s = server()
        let (vm, f) = try await caricata(s)
        vm.vediSquadra("Gli Amici")
        XCTAssertEqual(vm.squadraVista, "Gli Amici")
        XCTAssertEqual(vm.percorso, "/api/formazione?squadra=Gli%20Amici")
        // Non basta che la richiesta sia partita: finché la risposta non arriva il caricatore è in «loading» senza dati (indirizzo
        // nuovo) e `contestoConfronto` è nil. Si aspetta la formazione della squadra caricata davvero (prima il test falliva a volte).
        await attendi("caricamento della squadra", finche: {
            s.quante("GET /api/formazione?squadra=Gli%20Amici") >= 1 && !vm.caricatore.inCorso && vm.formazione != nil
        })
        XCTAssertEqual(vm.contestoConfronto?.squadra, "Gli Amici")
        // per un'altra squadra la scelta non si salva mai, anche se lo si chiede
        vm.iniziaModificaManuale(f)
        await attendi("valutazione", finche: { vm.valutazione != nil })
        await vm.valuta(salva: true)
        let ultimo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "POST /api/formazione/valuta").last), as: UTF8.self)
        XCTAssertTrue(ultimo.contains("\"salva\":false"), ultimo)
        XCTAssertTrue(ultimo.contains("\"squadra\":\"Gli Amici\""), ultimo)
        XCTAssertEqual(s.quante("GET /api/scelta"), 1, "la scelta salvata si legge solo per la propria squadra (una volta, all'inizio)")
        vm.tornaAllaMia()
        XCTAssertNil(vm.squadraVista)
        XCTAssertEqual(vm.percorso, "/api/formazione")
    }

    func testBallottaggioNelleFormazioneVera() async throws {
        let (vm, f) = try await caricata(server())
        let v = vm.vista(f)
        let incerti = v.titolari.filter { $0.titolarita != "titolare" }
        XCTAssertEqual(incerti.count, 5, "cinque titolari non sicuri (tutti in ballottaggio)")
        for g in incerti {
            let alt = vm.ballottaggio(per: g, f, v)
            XCTAssertLessThanOrEqual(alt.count, 2)
            XCTAssertTrue(alt.allSatisfy { a in a.giocatore.ruolo == g.ruolo && !v.titolari.contains { $0.id == a.giocatore.id } })
        }
        let sicuro = try XCTUnwrap(v.titolari.first { $0.titolarita == "titolare" })
        XCTAssertTrue(vm.ballottaggio(per: sicuro, f, v).isEmpty)
        // in modifica a mano i ballottaggi spariscono
        vm.manuale = v.titolari.map(\.id)
        XCTAssertTrue(vm.ballottaggio(per: incerti[0], f, v).isEmpty)
    }
}

@MainActor
final class ScambiViewModelTests: XCTestCase {
    func testIndirizzoDelleProposte() {
        let vm = ScambiViewModel(server: ServerDiProva.conFixture([:]))
        XCTAssertEqual(vm.indirizzoProposte, "/api/scambi/proposte?due=false")
        vm.due = true
        XCTAssertEqual(vm.indirizzoProposte, "/api/scambi/proposte?due=false", "il 2 contro 2 si chiede solo con una squadra scelta")
        vm.con = "Gli Amici & C."
        XCTAssertEqual(vm.indirizzoProposte, "/api/scambi/proposte?due=true&con=Gli%20Amici%20%26%20C.")
        vm.con = "Tutte"
        vm.due = false
        XCTAssertEqual(vm.indirizzoProposte, "/api/scambi/proposte?due=false")
    }

    func testProposteELeSquadrePiuPropense() async throws {
        let vm = ScambiViewModel(server: ServerDiProva.conFixture(["/api/scambi/proposte": "proposte", "/api/squadre": "squadre"]))
        await vm.caricaSquadre()
        await vm.caricaProposte()
        XCTAssertEqual(vm.proposte.dato?.proposte.count, 5)
        XCTAssertEqual(vm.altre.count, 9, "10 squadre, una è la mia")
        XCTAssertEqual(vm.propense.first?.nome, "Jolly Bianca")
    }

    func testOffertaRicevutaDaTesto() async throws {
        let s = ServerDiProva.conFixture(["/api/scambi/da-testo": "da-testo"])
        let vm = ScambiViewModel(server: s)
        await vm.valutaOfferta()
        XCTAssertEqual(vm.erroreOfferta, "Incolla prima il messaggio", "senza testo non si chiede niente (la frase della web, `scambio.incolla_prima_messaggio`)")
        XCTAssertEqual(s.quante("da-testo"), 0)
        vm.testoOfferta = "Ti do Barucci e tu mi dai Mangoni, ci stai?"
        await vm.valutaOfferta()
        XCTAssertNil(vm.erroreOfferta)
        XCTAssertEqual(vm.esitoOfferta?.con, "Lambda Rossa")
        XCTAssertEqual(vm.esitoOfferta?.`do`, ["Barucci"])
        XCTAssertNotNil(vm.esitoOfferta?.analisi)
        let corpo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "POST /api/scambi/da-testo").last), as: UTF8.self)
        XCTAssertTrue(corpo.contains("Ti do Barucci"), corpo)
    }

    func testOffertaConServerSpento() async {
        let vm = ScambiViewModel(server: ServerDiProva.chePrecipita(.server("Indica prima la tua squadra nella sezione Lega")))
        vm.testoOfferta = "Ti do X e tu mi dai Y"
        await vm.valutaOfferta()
        XCTAssertNil(vm.esitoOfferta)
        XCTAssertEqual(vm.erroreOfferta, "Indica prima la tua squadra nella sezione Lega")
    }

    func testBozzaCopiataNegliAppunti() throws {
        let vm = ScambiViewModel(server: ServerDiProva.conFixture([:]))
        let p: ProposteScambi = try Fixture.decodifica("proposte")
        vm.copiaBozza(p.proposte[0])
        XCTAssertEqual(UIPasteboard.general.string, ScambiLogica.bozza(p.proposte[0]))
        XCTAssertEqual(vm.messaggio, "Bozza copiata: incollala nel gruppo o in privato", "la frase della web, `mercato.bozza_copiata`")
    }

    func testAnalisiDiUnoScambioEArchivio() async throws {
        ArchivioScambi.svuota()
        defer { ArchivioScambi.svuota() }
        let s = ServerDiProva.conFixture(["/api/squadre": "squadre", "/api/rosa": "rosa", "/api/scambi/analizza": "analisi"])
        let vm = AnalizzaScambioViewModel(server: s)
        XCTAssertFalse(vm.puoAnalizzare)
        vm.altra = "Lambda Rossa"
        vm.doIds = [6523]
        vm.ricevoIds = [7485]
        XCTAssertTrue(vm.puoAnalizzare)
        await vm.analizza()
        XCTAssertEqual(vm.esito?.altra, "Lambda Rossa")
        XCTAssertNil(vm.errore)
        XCTAssertEqual(s.quante("GET /api/scambi/analizza?con=Lambda%20Rossa&do=6523&ricevo=7485&completo=true"), 1)
        XCTAssertEqual(ArchivioScambi.leggi().first?.dai, ["Barucci"], "lo scambio analizzato finisce nell'archivio")
    }
}

@MainActor
final class MercatoViewModelTests: XCTestCase {
    func testIndirizzoDellaClassifica() {
        let vm = MercatoViewModel(server: ServerDiProva.conFixture([:]))
        XCTAssertEqual(vm.percorsoClassifica, "/api/classifica?limite=60&liberi=true")
        vm.ruolo = "D"
        vm.soloLiberi = false
        XCTAssertEqual(vm.percorsoClassifica, "/api/classifica?limite=60&liberi=false&ruolo=D")
    }

    func testRicercaConPausaEAnnullamento() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/giocatori") { return Data(#"[{"id": 1, "nome": "Marco Rossi", "ruolo": "A", "squadra": "inter", "quotazione": 10}]"#.utf8) }
            throw ErroreApi.server("niente")
        }
        let vm = RicercaViewModel(server: s)
        vm.testo = "m"
        await vm.cerca()
        XCTAssertTrue(vm.risultati.isEmpty)
        XCTAssertEqual(s.quante("/api/giocatori"), 0, "con una sola lettera non si cerca")
        // la ricerca annullata (si continua a scrivere) non arriva al server
        vm.testo = "mar"
        let annullata = Task { await vm.cerca() }
        annullata.cancel()
        await annullata.value
        XCTAssertEqual(s.quante("/api/giocatori"), 0)
        // quella vera sì, con il nome codificato
        vm.testo = "mar co"
        await vm.cerca()
        XCTAssertEqual(vm.risultati.map(\.nome), ["Marco Rossi"])
        XCTAssertEqual(s.quante("GET /api/giocatori?limite=25&q=mar%20co"), 1)
        XCTAssertNil(vm.errore)
    }

    func testRicercaConErrore() async {
        let vm = RicercaViewModel(server: ServerDiProva.chePrecipita())
        vm.testo = "mar"
        await vm.cerca()
        XCTAssertNotNil(vm.errore)
        XCTAssertTrue(vm.risultati.isEmpty)
    }

    func testSchedaDelGiocatoreOsservatoESiPuoConfrontare() async throws {
        let s = ServerDiProva.conFixture(["/api/giocatore/": "giocatore", "/api/calendario": "calendario", "/api/osservati": "osservati",
                                          "/api/formazione": "formazione"])
        let vm = SchedaGiocatoreViewModel(id: 5585, server: s)
        await vm.carica()
        XCTAssertEqual(vm.caricatore.dato?.calciatore.nome, "Malvi")
        XCTAssertEqual(vm.osservato, false)
        XCTAssertFalse(vm.inFormazione, "Malvi non è nella rosa della fixture")
        XCTAssertEqual(vm.prossime.first?.avversario, "cagliari", "dal calendario della sua squadra (roma)")
        await vm.alternaOsservato()
        XCTAssertEqual(vm.osservato, true)
        XCTAssertEqual(s.quante("PUT /api/osservati/5585"), 1)
        await vm.alternaOsservato()
        XCTAssertEqual(vm.osservato, false)
        XCTAssertEqual(s.quante("DELETE /api/osservati/5585"), 1)
    }
}
