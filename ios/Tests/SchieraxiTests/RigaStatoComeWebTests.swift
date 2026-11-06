import Foundation
import Testing
@testable import Schieraxi

/// La riga di stato della Formazione con gli stati e le frasi della web (`statoScelta` e `rigaStatoScelta` di `fanta/web/app.js`,
/// frasi `formazione.stato_*` di `fanta/web/testi.js`): consigliata, altra, salvata, modificata, a mano, non valida. Le frasi
/// si confrontano con quelle di `testi.js`, così una frase cambiata su un lato solo fa fallire il test. La giornata chiusa
/// sta in `FormazioneChiusaTests`.
@MainActor
@Suite("Riga di stato della Formazione come la web")
struct RigaStatoComeWebTests {
    private let scelti = Array(1...11)

    // MARK: frasi

    @Test("Le frasi senza ora sono quelle della web",
          arguments: zip([StatoScelta.consigliata, .altra, .bozza, .nonValida, .salvata(nil), .modificata(nil)],
                         ["formazione.stato_consigliata", "formazione.stato_altra", "formazione.stato_mano",
                          "formazione.stato_non_valida", "formazione.stato_salvata", "formazione.stato_modificata"]))
    func fraseSenzaOra(stato: StatoScelta, chiave: String) throws {
        let atteso = try web(chiave)
        #expect(stato.titolo() == atteso)
    }

    @Test("«La tua formazione è salvata (…)»: oggi, ieri e un altro giorno come `quandoSalvata` della web")
    func fraseSalvataConOra() throws {
        let adesso = try data("2026-11-02T22:00:00")   // lunedì
        let oggi = try data("2026-11-02T21:40:00"), ieri = try data("2026-11-01T09:05:00"), sabato = try data("2026-10-31T21:40:00")
        let attesoOggi = try web("formazione.stato_salvata_quando", ["quando": giornoAlle(web("tempo.oggi"), "21:40")])
        let attesoIeri = try web("formazione.stato_salvata_quando", ["quando": giornoAlle(web("tempo.ieri"), "09:05")])
        // sabato 31 ottobre: «sab 31 alle 21:40», senza il mese
        let attesoSabato = try web("formazione.stato_salvata_quando", ["quando": giornoAlle(web("tempo.giorno_6") + " 31", "21:40")])
        #expect(StatoScelta.salvata(oggi).titolo(adesso: adesso) == attesoOggi)
        #expect(StatoScelta.salvata(ieri).titolo(adesso: adesso) == attesoIeri)
        #expect(StatoScelta.salvata(sabato).titolo(adesso: adesso) == attesoSabato)
    }

    @Test("«Modifiche non salvate · salvata …»: oggi solo l'ora (forma breve), poi ieri e un altro giorno")
    func fraseModificataConOra() throws {
        let adesso = try data("2026-11-02T22:00:00")
        let oggi = try data("2026-11-02T21:40:00"), ieri = try data("2026-11-01T09:05:00"), sabato = try data("2026-10-31T21:40:00")
        let attesoOggi = try web("formazione.stato_modificata_quando", ["quando": web("formazione.alle", ["ora": "21:40"])])
        let attesoIeri = try web("formazione.stato_modificata_quando", ["quando": giornoAlle(web("tempo.ieri"), "09:05")])
        let attesoSabato = try web("formazione.stato_modificata_quando", ["quando": giornoAlle(web("tempo.giorno_6") + " 31", "21:40")])
        #expect(StatoScelta.modificata(oggi).titolo(adesso: adesso) == attesoOggi)
        #expect(StatoScelta.modificata(ieri).titolo(adesso: adesso) == attesoIeri)
        #expect(StatoScelta.modificata(sabato).titolo(adesso: adesso) == attesoSabato)
    }

    @Test("VoiceOver legge la frase senza il «·»: al suo posto una virgola")
    func voceSenzaPuntoCentrale() throws {
        let adesso = try data("2026-11-02T22:00:00")
        let stato = StatoScelta.modificata(try data("2026-11-02T21:40:00"))
        let voce = stato.voce(adesso: adesso)
        #expect(!voce.contains("·"))
        #expect(voce == stato.titolo(adesso: adesso).replacingOccurrences(of: " · ", with: ", "))
        #expect(StatoScelta.chiusa(tua: true).voce() == "Giornata iniziata: la formazione è chiusa, vale quella che hai salvato")
    }

    // MARK: stati

    @Test("Gli stati come `statoScelta` della web")
    func stati() throws {
        let alle = try data("2026-11-02T21:40:00")
        var altri = scelti
        altri[0] = 99
        #expect(StatoScelta.calcola(letta: false, salvati: scelti, salvataIl: alle, manuale: scelti) == .sconosciuto)
        #expect(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: nil) == .consigliata)
        #expect(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: nil, altra: true) == .altra)
        #expect(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: scelti) == .bozza)
        #expect(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: scelti, altra: true) == .bozza, "a mano conta la modifica")
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: scelti.reversed()) == .salvata(alle),
                "l'ordine dei titolari non conta")
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: altri) == .modificata(alle))
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: nil) == .modificata(alle))
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: nil, altra: true) == .modificata(alle),
                "con una scelta salvata «altra» non c'è: è una modifica")
        // la scelta salvata non vale più: lo si dice finché non la rifai (dopo «Modifica a mano» si può salvare la nuova)
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: nil, nonValida: true) == .nonValida)
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: scelti, nonValida: true) == .nonValida,
                "gli undici che non valgono più non sono «salvata»")
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: altri, nonValida: true) == .modificata(alle))
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: alle, manuale: nil, chiusa: true, nonValida: true) == .chiusaNonValida,
                "a giornata chiusa vale la consigliata")
        #expect(StatoScelta.calcola(letta: false, salvati: nil, salvataIl: nil, manuale: nil, chiusa: true, nonValida: true) == .chiusaNonValida,
                "lo dice il server (`stato_scelta`) anche prima di leggere la scelta")
    }

    @Test("Giornata chiusa con la scelta salvata non più valida: la frase della web, lucchetto, grigia, nessun pulsante")
    func fraseChiusaNonValida() throws {
        let stato = StatoScelta.chiusaNonValida
        let web = try fraseChiusaNonValidaWeb()
        #expect(stato.titolo() == web)
        #expect(stato.simbolo == "lock.fill")
        #expect(stato.tono == .neutro)
        #expect(!stato.daSalvare && stato.pulsanti.isEmpty)
    }

    @Test("Segno, colore e pulsanti della riga come la web")
    func segniEPulsanti() {
        let tutti: [StatoScelta] = [.consigliata, .altra, .bozza, .salvata(nil), .modificata(nil), .nonValida, .chiusa(tua: false), .chiusaNonValida]
        for s in tutti { #expect(!s.simbolo.isEmpty, "\(s): lo stato non si legge dal solo colore") }
        #expect(StatoScelta.altra.tono == .neutro)
        #expect(StatoScelta.nonValida.tono == .malus, "il «!» rosso della web")
        #expect(StatoScelta.salvata(nil).tono == .bene)
        #expect(StatoScelta.modificata(nil).tono == .attenzione)
        #expect(!StatoScelta.altra.daSalvare)
        #expect(!StatoScelta.nonValida.daSalvare)
        #expect(!StatoScelta.salvata(nil).daSalvare)
        #expect(StatoScelta.modificata(nil).daSalvare)
        // i pulsanti della riga, stato per stato, li prova `ModificaAManoModuliTests.pulsantiPerStato` (#463)
    }

    // MARK: schermata

    @Test("Un altro stile o un altro modulo senza niente di salvato: «altra»; «Torna alla consigliata» rimette stile e modulo, senza cancellare niente")
    func altroStileOModulo() async throws {
        let srv = try server(scelta: nil)
        let (vm, f) = try await caricata(srv)
        let frase = try web("formazione.stato_altra")
        #expect(vm.statoScelta == .consigliata)
        let livelli = try #require(f.livelli)
        let base = try #require(livelli.first { $0.rischio == 0 })
        let altroModulo = try #require(base.moduli.first { $0.modulo != base.modulo })
        vm.scegliStile(1)
        #expect(vm.statoScelta == .altra)
        #expect(vm.statoScelta.titolo() == frase)
        vm.scegliStile(0)
        #expect(vm.statoScelta == .consigliata)
        vm.scegliModulo(altroModulo.modulo)
        #expect(vm.statoScelta == .altra)
        vm.scegliModulo(base.modulo)
        #expect(vm.statoScelta == .consigliata, "il modulo proposto dallo stile consigliato è la consigliata")
        vm.scegliStile(-1)
        vm.scegliModulo(altroModulo.modulo)
        #expect(vm.statoScelta == .altra)
        await vm.tornaAllaConsigliata(f)
        #expect(vm.rischio == 0)
        #expect(vm.moduloScelto == nil)
        #expect(vm.statoScelta == .consigliata)
        #expect(srv.quante("DELETE /api/scelta") == 0, "non c'era niente di salvato da togliere")
    }

    @Test("Una scelta salvata fuori dalla rosa non si cancella da sola: la riga dice che non è più valida e si vede la consigliata")
    func nonValidaPerLaRosa() async throws {
        let frase = try web("formazione.stato_non_valida")
        let srv = try server(scelta: try dieciTitolari())
        let (vm, f) = try await caricata(srv)
        #expect(vm.statoScelta == .nonValida)
        #expect(vm.statoScelta.titolo() == frase)
        #expect(srv.quante("DELETE /api/scelta") == 0, "i client non cancellano la scelta da soli")
        #expect(vm.manuale == nil, "si vede la consigliata")
        #expect(vm.messaggio == nil, "lo dice già la riga: niente seconda frase")
        // «Modifica a mano»: si rifà partendo dalla consigliata («Modifiche non salvate»); «Annulla modifiche» torna lì
        vm.iniziaModificaManuale(f)
        #expect(vm.statoScelta == .modificata(Quando.data("2026-11-02T21:40:00")))
        vm.annullaModifiche()
        #expect(vm.statoScelta == .nonValida)
        #expect(vm.manuale == nil, "gli undici che non valgono più non tornano in campo")
    }

    @Test("Dalla scelta non più valida si salva una formazione nuova: la riga torna «salvata»")
    func nonValidaPoiSalvata() async throws {
        let (vm, f) = try await caricata(try server(scelta: try dieciTitolari()))
        #expect(vm.statoScelta == .nonValida)
        await vm.salvaQuesta(f)
        guard case .salvata = vm.statoScelta else {
            Issue.record("dopo il salvataggio la riga dice «salvata»: \(vm.statoScelta)")
            return
        }
    }

    @Test("Dalla scelta non più valida, «Torna alla consigliata» la toglie dal server")
    func nonValidaTornaAllaConsigliata() async throws {
        let srv = try server(scelta: try dieciTitolari())
        let (vm, f) = try await caricata(srv)
        #expect(vm.statoScelta == .nonValida)
        await vm.tornaAllaConsigliata(f)
        #expect(srv.quante("DELETE /api/scelta?giornata=9") == 1)
        #expect(vm.statoScelta == .consigliata)
    }

    @Test("Il server dice che la scelta salvata non vale più (il codice, non il testo): stessa riga, niente cancellazione")
    func nonValidaPerIlServer() async throws {
        let conCodice = try server(scelta: try titolariBase(), valuta: {
            throw ErroreApi.codificato(codice: ValiditaScelta.codiceNonValida, messaggio: "Il modulo 2-5-3 non è ammesso nella tua lega")
        })
        let (vm, _) = try await caricata(conCodice)
        #expect(vm.statoScelta == .nonValida)
        #expect(conCodice.quante("DELETE /api/scelta") == 0)
        #expect(vm.manuale == nil)
        #expect(vm.messaggio == nil, "il testo del server non si mostra: lo dice la riga")
        // il solo testo «Servono 11…» non basta: la scelta resta quella salvata
        let soloTesto = try server(scelta: try titolariBase(), valuta: { throw ErroreApi.server("Servono 11 titolari diversi, tutti della rosa") })
        let (vm1, _) = try await caricata(soloTesto)
        #expect(vm1.statoScelta == .salvata(Quando.data("2026-11-02T21:40:00")))
        #expect(vm1.manuale != nil)
        #expect(soloTesto.quante("DELETE /api/scelta") == 0)
    }

    @Test("Il server ha detto che la scelta non vale più: rileggendo (ritorno sulla Formazione, tira per aggiornare) resta «non valida», mai «salvata» nel frattempo, nessun messaggio, la prova una volta sola")
    func nonValidaResta() async throws {
        let ids = try titolariBase()
        let dati = try Fixture.dati("formazione")
        let scelta = Data("{\"titolari\": [\(ids.map(String.init).joined(separator: ","))], \"salvata\": \"2026-11-02T21:40:00\"}".utf8)
        let modello = Scatola<FormazioneViewModel>()
        let visti = Scatola<[StatoScelta]>()
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/formazione/valuta") {
                // la riga mentre il server prova la scelta salvata: è quello che si vede in quel momento
                if let stato = await MainActor.run(body: { modello.valore?.statoScelta }) { visti.valore = (visti.valore ?? []) + [stato] }
                throw ErroreApi.codificato(codice: ValiditaScelta.codiceNonValida, messaggio: "Il modulo 2-5-3 non è ammesso nella tua lega")
            }
            if percorso.hasPrefix("/api/scelta") { return scelta }
            return dati
        }
        let vm = FormazioneViewModel(server: srv)
        modello.valore = vm
        await vm.carica()
        #expect(vm.statoScelta == .nonValida)
        #expect(vm.messaggio == nil)
        await vm.carica()
        #expect(vm.statoScelta == .nonValida)
        #expect(vm.messaggio == nil, "nessun errore del server a ogni ritorno sulla Formazione")
        #expect(vm.manuale == nil, "gli undici che non valgono più non tornano in campo")
        #expect(srv.quante("POST /api/formazione/valuta") == 1, "la stessa scelta salvata non si riprova")
        let durante = visti.valore ?? []
        let salvataVista = durante.contains { if case .salvata = $0 { return true } else { return false } }
        #expect(!salvataVista, "mai «salvata» mentre il server la prova: \(durante)")
    }

    @Test("Senza la rosa una scelta strana non si giudica: resta salvata")
    func senzaRosaNonSiGiudica() async throws {
        let srv = try server(scelta: try dieciTitolari(), senzaSchede: true)
        let (vm, _) = try await caricata(srv)
        #expect(srv.quante("DELETE /api/scelta") == 0)
        #expect(vm.statoScelta == .salvata(Quando.data("2026-11-02T21:40:00")))
    }

    @Test("Giornata chiusa con una scelta salvata fuori dalla rosa: «vale la consigliata», la consigliata in campo, senza provare a cancellarla")
    func chiusaConSceltaNonValida() async throws {
        let frase = try fraseChiusaNonValidaWeb()
        let srv = try server(scelta: try dieciTitolari(), iniziata: true)
        let (vm, _) = try await caricata(srv)
        #expect(vm.statoScelta == .chiusaNonValida)
        #expect(vm.statoScelta.titolo() == frase)
        #expect(vm.manuale == nil, "in campo la consigliata")
        #expect(srv.quante("DELETE /api/scelta") == 0)
        #expect(vm.messaggio == nil, "niente errore del server per una cancellazione rifiutata")
    }

    @Test("A giornata chiusa decide `stato_scelta` del server: «non_valida» → vale la consigliata (senza riprovarla), «valida» → la tua",
          arguments: zip(["non_valida", "valida"], [true, false]))
    func chiusaConStatoDelServer(statoServer: String, nonValida: Bool) async throws {
        let srv = try server(scelta: try titolariBase(), iniziata: true, statoScelta: statoServer)
        let (vm, _) = try await caricata(srv)
        if nonValida {
            #expect(vm.statoScelta == .chiusaNonValida)
            #expect(vm.manuale == nil, "in campo la consigliata")
            #expect(srv.quante("POST /api/formazione/valuta") == 0, "lo sa già il server: non si riprova")
        } else {
            #expect(vm.statoScelta == .chiusa(tua: true))
            #expect(vm.manuale != nil, "in campo la tua")
        }
    }

    @Test("Prima della scadenza `stato_scelta` non cambia la riga (come la web): conta la prova della scelta letta")
    func apertaIgnoraStatoDelServer() async throws {
        let srv = try server(scelta: try titolariBase(), statoScelta: "non_valida")
        let (vm, _) = try await caricata(srv)
        #expect(vm.statoScelta == .salvata(Quando.data("2026-11-02T21:40:00")))
    }

    // MARK: aiuti

    /// Una frase italiana della web con i segnaposto riempiti, come `t(chiave, {…})` di `app.js`.
    private func web(_ chiave: String, _ valori: [String: String] = [:]) throws -> String {
        var testo = try TestiWeb().italiano(chiave)
        for (nome, valore) in valori { testo = testo.replacingOccurrences(of: "{\(nome)}", with: valore) }
        return testo
    }

    /// `formazione.stato_chiusa_non_valida` della web. La chiave arriva con la PR del server e della web (#320): finché
    /// `testi.js` non ce l'ha, si confronta con la frase scritta lì; dopo l'unione il confronto è con `testi.js`.
    private func fraseChiusaNonValidaWeb() throws -> String {
        let scrittaNellaPR = "Giornata iniziata: la formazione è chiusa · vale la consigliata, la tua non è più valida"
        guard let testi = try? TestiWeb(), let frase = try? testi.italiano("formazione.stato_chiusa_non_valida") else {
            return scrittaNellaPR
        }
        return frase
    }

    /// «oggi alle 21:40», «sab 31 alle 21:40» con `formazione.giorno_alle` della web.
    private func giornoAlle(_ giorno: String, _ ora: String) throws -> String {
        try web("formazione.giorno_alle", ["giorno": giorno, "ora": ora])
    }

    private func data(_ testo: String) throws -> Date { try #require(Quando.data(testo)) }

    private func titolariBase() throws -> [Int] {
        let base: Formazione = try Fixture.decodifica("formazione")
        return base.titolari.map(\.id)
    }

    /// Dieci titolari della rosa: una scelta che non vale più.
    private func dieciTitolari() throws -> [Int] { Array(try titolariBase().prefix(10)) }

    /// Un server con la formazione della fixture (aperta o chiusa, con o senza `schede`) e una scelta salvata (`scelta`; nil =
    /// nessuna). A giornata chiusa le scritture rispondono 409 `formazione_chiusa`, come il server vero.
    private func server(scelta: [Int]?, iniziata: Bool = false, senzaSchede: Bool = false, statoScelta: String? = nil,
                        valuta: @escaping @Sendable () throws -> Data = { Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8) })
    throws -> ServerDiProva {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        if iniziata { formazione["iniziata"] = true }
        if let statoScelta { formazione["stato_scelta"] = statoScelta }
        if senzaSchede { formazione["schede"] = nil }
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let salvata = Data((scelta.map { "{\"titolari\": [\($0.map(String.init).joined(separator: ","))], \"salvata\": \"2026-11-02T21:40:00\"}" } ?? "null").utf8)
        return ServerDiProva { metodo, percorso, corpo in
            let scrive = metodo == "DELETE" || corpo.map { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") } == true
            if iniziata, scrive { throw ErroreApi.codificato(codice: FormazioneViewModel.codiceChiusa, messaggio: "Formazione chiusa") }
            if percorso.hasPrefix("/api/formazione/valuta") { return try valuta() }
            if percorso.hasPrefix("/api/scelta") { return metodo == "GET" ? salvata : Data("{\"ok\": true}".utf8) }
            return dati
        }
    }

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}
