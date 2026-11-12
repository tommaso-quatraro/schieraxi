import Foundation
import Testing
@testable import Schieraxi

/// Formazione: la scelta cambiata da un altro dispositivo (412) e i pulsanti durante un salvataggio (#477, note della #475).
/// Il riferimento è la web del 12/11/2026 (`mostraFormazione` in `fanta/web/app.js`, che non si legge più): dopo un 412 la
/// pagina si ricarica, quindi stile e modulo ripartono da quelli consigliati; durante un salvataggio (`sc.occupato`) si spengono
/// i pulsanti che salvano e «Annulla modifiche», mentre «Torna alla consigliata», i moduli e gli stili restano attivi.
@MainActor
@Suite("Formazione: scelta cambiata altrove e pulsanti durante il salvataggio")
struct SceltaCambiataAltroveTests {
    private var alle: Date? { Quando.data("2026-11-02T21:40:00") }
    private var alleAltro: Date? { Quando.data("2026-11-03T09:15:00") }

    /// Che cosa fa questo telefono quando il server risponde 412.
    enum Azione: CaseIterable, Sendable { case salva, tornaAllaConsigliata }
    /// Che cosa non risponde dopo il 412: tutto (rete caduta) o solo la lettura della scelta.
    enum Caduta: CaseIterable, Sendable { case tutto, soloLaScelta }
    /// Che cosa ha toccato questo telefono prima di salvare (fuori dalla modifica a mano).
    enum Tocco: CaseIterable, Sendable { case modulo, stile }
    /// Che cosa ha fatto l'altro dispositivo con la scelta salvata.
    enum AltroDispositivo: CaseIterable, Sendable { case cancellata, altraScelta }

    // MARK: punto 1: «ho ricaricato quella salvata» solo se è vero

    @Test("412 e rilettura non riuscita: niente «ho ricaricato quella salvata», la riga non dice niente e in campo c'è la consigliata; tornata la rete, si rilegge la scelta dell'altro dispositivo",
          arguments: Azione.allCases, Caduta.allCases)
    func ricaricaNonRiuscita(azione: Azione, caduta: Caduta) async throws {
        let (s, s2) = try dueScelte()
        let salvata = Scatola<String>()
        salvata.valore = scelta(s, "2026-11-02T21:40:00")
        let giu = Scatola<Bool>()
        let srv = try serverAltroDispositivo(salvata, caduta: caduta, giu: giu)
        let (vm, f) = try await caricata(srv)
        #expect(vm.statoScelta == .salvata(alle))
        salvata.valore = scelta(s2, "2026-11-03T09:15:00")   // l'altro dispositivo salva un'altra formazione
        vm.scegliModulo(try moduloDaToccare(f, evitando: [s, s2]).modulo)   // la modifica di questo telefono
        try #require(vm.statoScelta == .modificata(alle))
        switch azione {
        case .salva: await vm.salvaQuesta(f)
        case .tornaAllaConsigliata: await vm.tornaAllaConsigliata(f)
        }
        try #require(giu.valore == true, "il server ha risposto 412")
        #expect(vm.messaggio == FormazioneViewModel.sceltaCambiataSenzaRicarica)
        #expect(vm.statoScelta == .sconosciuto, "la scelta sul server è cambiata e non si sa com'è: niente «salvata» con quella vecchia")
        #expect(vm.manuale == nil)
        #expect(vm.moduloScelto == nil, "non resta in vista il modulo toccato")
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(f.titolari.map(\.id)), "in campo la consigliata")
        #expect(!vm.salvataggioInCorso)
        // torna la rete: rileggendo (tira per aggiornare) in campo c'è la scelta dell'altro dispositivo
        giu.valore = false
        await vm.carica()
        #expect(Set(vm.manuale ?? []) == Set(s2))
        #expect(vm.statoScelta == .salvata(alleAltro))
    }

    @Test("Scelta mai letta (il server non la dà) e 412: si rileggono formazione e scelta, ma senza la scelta niente «ho ricaricato quella salvata»",
          arguments: Azione.allCases)
    func sceltaMaiLetta(azione: Azione) async throws {
        let dati = try Fixture.dati("formazione")
        let srv = ServerDiProva { metodo, percorso, corpo in
            if metodo == "DELETE" || chiedeDiSalvare(corpo) { throw ErroreApi.conflitto }
            if percorso.hasPrefix("/api/formazione/valuta") { return valutazioneFinta }
            if percorso.hasPrefix("/api/scelta") { throw ErroreApi.server("nessuna scelta salvata") }
            return dati
        }
        let (vm, f) = try await caricata(srv)
        switch azione {
        case .salva: await vm.salvaQuesta(f)
        case .tornaAllaConsigliata: await vm.tornaAllaConsigliata(f)
        }
        #expect(srv.quante("GET /api/formazione") == 2, "si ricarica la formazione")
        #expect(srv.quante("GET /api/scelta") == 2, "e si prova a rileggere la scelta (con il suo ETag)")
        #expect(vm.messaggio == FormazioneViewModel.sceltaCambiataSenzaRicarica)
        #expect(vm.manuale == nil, "la modifica di questo telefono non si salva sopra quella dell'altro")
        #expect(vm.statoScelta == .sconosciuto)
    }

    // MARK: punti 2 e 4: 412 dopo un modulo o uno stile toccato

    @Test("412 dopo un modulo o uno stile toccato (non a mano): stile e modulo tornano i consigliati, come la web che ricarica la pagina",
          arguments: Tocco.allCases, AltroDispositivo.allCases)
    func conflittoDopoUnTocco(tocco: Tocco, altro: AltroDispositivo) async throws {
        let (s, s2) = try dueScelte()
        let salvata = Scatola<String>()
        salvata.valore = scelta(s, "2026-11-02T21:40:00")
        let srv = try serverAltroDispositivo(salvata)
        let (vm, f) = try await caricata(srv)
        switch tocco {
        case .modulo: vm.scegliModulo(try moduloDaToccare(f, evitando: [s, s2]).modulo)
        case .stile: vm.scegliStile(1)
        }
        try #require(vm.manuale == nil, "fuori dalla modifica a mano")
        try #require(vm.statoScelta == .modificata(alle))
        switch altro {
        case .cancellata: salvata.valore = nil
        case .altraScelta: salvata.valore = scelta(s2, "2026-11-03T09:15:00")
        }
        await vm.salvaQuesta(f)
        #expect(srv.quante("GET /api/formazione") == 2, "dopo il 412 si ricarica la formazione")
        #expect(srv.quante("GET /api/scelta") == 2, "e si rilegge la scelta")
        #expect(vm.messaggio == FormazioneViewModel.sceltaCambiata)
        #expect(vm.rischio == 0, "lo stile consigliato della fixture")
        #expect(vm.moduloScelto == nil, "il modulo proposto dallo stile")
        switch altro {
        case .cancellata:
            #expect(vm.manuale == nil)
            #expect(vm.statoScelta == .consigliata, "la scelta non c'è più: la consigliata, non «un modulo diverso»")
            #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(f.titolari.map(\.id)))
        case .altraScelta:
            #expect(Set(vm.manuale ?? []) == Set(s2), "in campo la scelta salvata dall'altro dispositivo")
            #expect(vm.statoScelta == .salvata(alleAltro))
        }
    }

    @Test("412 e rilettura che cambia lo stile consigliato: si accende quello nuovo, non quello di prima della rilettura")
    func stileConsigliatoDellaRilettura() async throws {
        let (s, s2) = try dueScelte()
        var json = try #require(try JSONSerialization.jsonObject(with: try Fixture.dati("formazione")) as? [String: Any])
        json["stile_consigliato"] = 1
        let nuova = try JSONSerialization.data(withJSONObject: json)
        let vecchia = try Fixture.dati("formazione")
        let salvata = Scatola<String>()
        salvata.valore = scelta(s, "2026-11-02T21:40:00")
        let dopo412 = Scatola<Bool>()
        let srv = ServerDiProva { metodo, percorso, corpo in
            if metodo == "DELETE" || chiedeDiSalvare(corpo) {
                dopo412.valore = true
                throw ErroreApi.conflitto
            }
            if percorso.hasPrefix("/api/formazione/valuta") { return valutazioneFinta }
            if percorso.hasPrefix("/api/scelta") { return Data((salvata.valore ?? "null").utf8) }
            return dopo412.valore == true ? nuova : vecchia
        }
        let (vm, f) = try await caricata(srv)
        try #require(f.stileConsigliato == nil, "prima della rilettura lo stile consigliato è lo 0 (campo assente)")
        vm.scegliModulo(try moduloDaToccare(f, evitando: [s, s2]).modulo)
        salvata.valore = nil                                   // l'altro dispositivo cancella la scelta
        await vm.salvaQuesta(f)
        #expect(vm.formazione?.stileConsigliato == 1, "la formazione riletta")
        #expect(vm.rischio == 1, "lo stile consigliato della formazione riletta")
        #expect(vm.moduloScelto == nil)
        #expect(vm.statoScelta == .consigliata)
        #expect(vm.messaggio == FormazioneViewModel.sceltaCambiata)
    }

    // MARK: punto 4: i pulsanti dopo un errore

    @Test("Dopo un salvataggio non riuscito i pulsanti tornano attivi e un altro tocco su Salva manda un altro salvataggio",
          arguments: [ErroreApi.rete("spento"), .timeout, .server("Il server ha un problema: riprova tra poco."), .conflitto])
    func pulsantiAttiviDopoUnErrore(errore: ErroreApi) async throws {
        let cancello = Cancello()
        let dati = try Fixture.dati("formazione")
        let srv = ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if chiedeDiSalvare(corpo) {
                    await cancello.passa()
                    throw errore
                }
                return valutazioneFinta
            }
            if percorso.hasPrefix("/api/scelta") { return metodo == "GET" ? Data("null".utf8) : Data("{\"ok\": true}".utf8) }
            return dati
        }
        let (vm, f) = try await caricata(srv)
        let primo = Task { await vm.salvaQuesta(f) }
        await cancello.richiestaArrivata()
        #expect(vm.salvataggioInCorso, "durante il salvataggio Salva e «Annulla modifiche» sono spenti")
        await cancello.apri()
        await primo.value
        #expect(!vm.salvataggioInCorso, "dopo l'errore i pulsanti tornano attivi")
        #expect(vm.messaggio != nil, "e si dice che cosa è successo")
        await vm.salvaQuesta(f)
        #expect(salvataggi(srv) == 2, "il secondo tocco su Salva parte davvero")
    }

    // MARK: punto 3: durante un salvataggio, come la web

    /// Sulla web del 12/11/2026 i gestori di «Salva questa», «Salva le modifiche» e «Annulla modifiche» guardavano `sc.occupato`,
    /// quello di «Torna alla consigliata» no; moduli e stili restavano attivi (sull'iPhone i chip non si spengono mai).
    @Test("Durante un salvataggio si spengono gli stessi pulsanti della web: Salva e «Annulla modifiche» sì, «Torna alla consigliata» no")
    func pulsantiSpentiComeLaWeb() {
        #expect(!StatoScelta.Pulsante.torna.spentoSalvando, "«Torna alla consigliata» resta attivo")
        #expect(StatoScelta.Pulsante.salvaQuesta.spentoSalvando)
        #expect(StatoScelta.Pulsante.salva.spentoSalvando)
        #expect(StatoScelta.Pulsante.annulla.spentoSalvando)
    }

    @Test("Durante un salvataggio un tocco su un modulo cambia la formazione sullo schermo, e la risposta che arriva dopo non la copre")
    func moduloDuranteIlSalvataggio() async throws {
        let cancello = Cancello()
        let srv = try serverLento(cancello, scelta: nil)
        let (vm, f) = try await caricata(srv)
        let altro = try moduloDaToccare(f, evitando: [])
        let salvataggio = Task { await vm.salvaQuesta(f) }
        await cancello.richiestaArrivata()
        try #require(vm.salvataggioInCorso)
        vm.scegliModulo(altro.modulo)
        #expect(vm.manuale == nil)
        #expect(vm.moduloScelto == altro.modulo)
        await cancello.apri()
        await salvataggio.value
        #expect(vm.manuale == nil, "la risposta arrivata dopo non rimette gli undici di prima")
        #expect(vm.moduloScelto == altro.modulo)
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(altro.titolari))
        #expect(!vm.salvataggioInCorso)
    }

    @Test("Durante un salvataggio «Torna alla consigliata» funziona: toglie la scelta salvata e rimette la consigliata")
    func tornaDuranteIlSalvataggio() async throws {
        let (s, s2) = try dueScelte()
        let cancello = Cancello()
        let srv = try serverLento(cancello, scelta: s)
        let (vm, f) = try await caricata(srv)
        vm.scegliModulo(try moduloDaToccare(f, evitando: [s, s2]).modulo)
        let salvataggio = Task { await vm.salvaQuesta(f) }
        await cancello.richiestaArrivata()
        try #require(vm.salvataggioInCorso)
        await vm.tornaAllaConsigliata(f)
        #expect(srv.quante("DELETE /api/scelta") == 1)
        #expect(vm.manuale == nil)
        #expect(vm.moduloScelto == nil)
        #expect(vm.statoScelta == .consigliata)
        await cancello.apri()
        await salvataggio.value
        #expect(!vm.salvataggioInCorso)
    }

    // MARK: aiuti

    /// Due scelte salvate diverse dalla consigliata e tra loro: due moduli dello stile consigliato della fixture.
    private func dueScelte() throws -> (s: [Int], s2: [Int]) {
        let f: Formazione = try Fixture.decodifica("formazione")
        let livello = try #require(f.livelli?.first { $0.rischio == (f.stileConsigliato ?? 0) })
        let consigliata = Set(f.titolari.map(\.id))
        let diversi = livello.moduli.map(\.titolari).filter { Set($0) != consigliata }
        let s = try #require(diversi.first)
        let s2 = try #require(diversi.first { Set($0) != Set(s) })
        return (s, s2)
    }

    /// Un modulo dello stile consigliato diverso da quello proposto, con undici diversi dalla consigliata e dalle scelte `evitando`.
    private func moduloDaToccare(_ f: Formazione, evitando: [[Int]]) throws -> OpzioneModulo {
        let livello = try #require(f.livelli?.first { $0.rischio == (f.stileConsigliato ?? 0) })
        let esclusi = Set(evitando.map { Set($0) } + [Set(f.titolari.map(\.id))])
        return try #require(livello.moduli.first { $0.modulo != livello.modulo && !esclusi.contains(Set($0.titolari)) },
                            "nella fixture manca un modulo da toccare")
    }

    /// La risposta di `GET /api/scelta` per questi titolari, salvati a quell'ora.
    private func scelta(_ titolari: [Int], _ salvata: String) -> String {
        "{\"titolari\": [\(titolari.map(String.init).joined(separator: ","))], \"salvata\": \"\(salvata)\"}"
    }

    /// Un server con la scelta salvata in `salvata` (nil = nessuna; un altro dispositivo la può cambiare): salvataggi e
    /// cancellazioni rispondono 412, come il server vero quando la scelta è cambiata dopo l'ultima lettura. Con `caduta`, al 412
    /// si accende `giu`: finché resta acceso non risponde niente (`tutto`) o solo la lettura della scelta (`soloLaScelta`).
    private func serverAltroDispositivo(_ salvata: Scatola<String>, caduta: Caduta? = nil,
                                        giu: Scatola<Bool> = Scatola()) throws -> ServerDiProva {
        let dati = try Fixture.dati("formazione")
        return ServerDiProva { metodo, percorso, corpo in
            if metodo == "DELETE" || chiedeDiSalvare(corpo) {
                if caduta != nil { giu.valore = true }
                throw ErroreApi.conflitto
            }
            if giu.valore == true, caduta == .tutto || percorso.hasPrefix("/api/scelta") { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/formazione/valuta") { return valutazioneFinta }
            if percorso.hasPrefix("/api/scelta") { return Data((salvata.valore ?? "null").utf8) }
            return dati
        }
    }

    /// Un server il cui salvataggio resta fermo al cancello finché il test non lo apre; con una scelta salvata (`scelta`) o senza.
    private func serverLento(_ cancello: Cancello, scelta: [Int]?) throws -> ServerDiProva {
        let dati = try Fixture.dati("formazione")
        let salvata = Data((scelta.map { self.scelta($0, "2026-11-02T21:40:00") } ?? "null").utf8)
        return ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if chiedeDiSalvare(corpo) { await cancello.passa() }
                return valutazioneFinta
            }
            if percorso.hasPrefix("/api/scelta") { return metodo == "GET" ? salvata : Data("{\"ok\": true}".utf8) }
            return dati
        }
    }

    /// Quanti salvataggi (valutazioni con `salva: true`) ha ricevuto il server.
    private func salvataggi(_ srv: ServerDiProva) -> Int {
        srv.corpiInviati(a: "POST /api/formazione/valuta").filter { chiedeDiSalvare($0) }.count
    }

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}

/// La risposta di `POST /api/formazione/valuta` dei server finti di questa prova.
private let valutazioneFinta = Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)

/// La richiesta salva la scelta (`salva: true` nel corpo di `POST /api/formazione/valuta`).
private func chiedeDiSalvare(_ corpo: Data?) -> Bool {
    corpo.map { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") } == true
}
