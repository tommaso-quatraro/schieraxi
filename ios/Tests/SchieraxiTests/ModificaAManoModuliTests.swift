import Foundation
import Testing
@testable import Schieraxi

/// In modifica a mano moduli e stili restano sullo schermo, come la web (#463): al posto della frase dello stile c'è
/// `formazione.modificata_mano` del catalogo comune con la web (`Catalogo.Formazione`), e un tocco su un modulo o uno stile esce dalla modifica a mano e torna alla
/// proposta del server SENZA cancellare la scelta salvata (`data-modulo` e `data-stile` di `mostraFormazione` in `fanta/web/app.js`).
/// I pulsanti dipendono dallo stato della scelta, come `rigaStatoScelta` della web: con una scelta salvata e un'altra formazione
/// sullo schermo la riga dice «Modifiche non salvate» con «Salva le modifiche», «Annulla modifiche» e «Torna alla consigliata».
@MainActor
@Suite("Modifica a mano: moduli e stili come la web")
struct ModificaAManoModuliTests {
    private var alle: Date? { Quando.data("2026-11-02T21:40:00") }

    // MARK: frasi e pulsanti

    @Test("In modifica a mano, al posto della frase dello stile, «Modificata a mano. Tocca un modulo o uno stile …» della web")
    func fraseModificataAMano() {
        #expect(FormazioneView.testoModificataAMano == Catalogo.Formazione.modificataMano)
    }

    @Test("I pulsanti hanno le parole della web (catalogo comune)", arguments: [
        ("formazione.salva_questa", Catalogo.Formazione.salvaQuesta),
        ("formazione.salva_modifiche", Catalogo.Formazione.salvaModifiche),
        ("formazione.salva_come_mia", Catalogo.Formazione.salvaComeMia),
        ("formazione.annulla_modifiche", Catalogo.Formazione.annullaModifiche),
        ("formazione.torna_alla_consigliata", Catalogo.Formazione.tornaAllaConsigliata),
        ("formazione.modifica_mano", Catalogo.Formazione.modificaMano),
    ])
    func paroleDeiPulsanti(chiave: String, catalogo: String) throws {
        let iPhone = try #require(paroleIPhone(chiave), "manca il pulsante dell'iPhone per \(chiave)")
        #expect(iPhone == catalogo)
    }

    @Test("I pulsanti di ogni stato sono quelli di `rigaStatoScelta` in app.js, nello stesso ordine; «Modifica a mano» dove la web la mette")
    func pulsantiComeLaWeb() {
        let web = Self.pulsantiWeb
        // gli stati della web (`statoScelta` di app.js) e quelli dell'iPhone che li mostrano
        let stati: [String: [StatoScelta]] = [
            "consigliata": [.consigliata], "altra": [.altra], "salvata": [.salvata(alle)], "modificata": [.modificata(alle)],
            "mano": [.bozza], "non_valida": [.nonValida], "chiusa": [.chiusa(tua: true), .chiusa(tua: false), .chiusaNonValida],
        ]
        #expect(Set(web.keys) == Set(stati.keys), "gli stati di `rigaStatoScelta` sono cambiati: \(web.keys.sorted())")
        let comeIPhone: [String: StatoScelta.Pulsante] = ["salva-questa": .salvaQuesta, "salva-scelta": .salva,
                                                          "annulla-modifiche": .annulla, "torna-consigliata": .torna]
        for (chiave, ids) in web {
            let attesi = ids.filter { $0 != "modifica" }.compactMap { id -> StatoScelta.Pulsante? in
                if comeIPhone[id] == nil { Issue.record("pulsante della web che l'iPhone non conosce: \(id)") }
                return comeIPhone[id]
            }
            for stato in stati[chiave] ?? [] {
                #expect(stato.pulsanti == attesi, "pulsanti con \(stato) (web: \(chiave) \(ids))")
                #expect(stato.conModificaAMano == ids.contains("modifica"), "«Modifica a mano» con \(stato) (web: \(chiave))")
            }
        }
        // senza riga (un'altra squadra, scelta non ancora letta) la web mette «Modifica a mano» fuori dalla riga
        #expect(StatoScelta.sconosciuto.pulsanti.isEmpty)
        #expect(StatoScelta.sconosciuto.conModificaAMano)
    }

    @Test("Senza modifica a mano lo stato confronta gli undici sullo schermo con quelli salvati (l'ordine non conta)")
    func statoDaiTitolariMostrati() {
        let salvati = Array(1...11)
        var altri = salvati
        altri[0] = 99
        #expect(StatoScelta.calcola(letta: true, salvati: salvati, salvataIl: alle, manuale: nil, mostrati: salvati.reversed()) == .salvata(alle))
        #expect(StatoScelta.calcola(letta: true, salvati: salvati, salvataIl: alle, manuale: nil, mostrati: altri) == .modificata(alle))
        #expect(StatoScelta.calcola(letta: true, salvati: salvati, salvataIl: alle, manuale: altri, mostrati: salvati) == .modificata(alle),
                "a mano contano gli undici scelti a mano")
        #expect(StatoScelta.calcola(letta: true, salvati: salvati, salvataIl: alle, manuale: nil, mostrati: salvati, nonValida: true) == .nonValida,
                "la scelta che non vale più resta «non valida» finché non la rifai")
    }

    // MARK: schermata

    @Test("Senza scelta salvata: in modifica a mano un tocco su uno stile torna alla sua proposta, senza cancellare niente")
    func stileEsceDallaModificaAMano() async throws {
        let srv = try server(scelta: nil)
        let (vm, f) = try await caricata(srv)
        vm.iniziaModificaManuale(f)
        #expect(vm.statoScelta == .bozza)
        vm.scegliStile(1)
        #expect(vm.manuale == nil, "fuori dalla modifica a mano")
        #expect(vm.rischio == 1)
        #expect(vm.moduloScelto == nil)
        let rischiosa = try #require(f.livelli?.first { $0.rischio == 1 })
        let proposto = try #require(rischiosa.moduli.first { $0.modulo == rischiosa.modulo })
        #expect(vm.vista(f).titolari.map(\.id) == proposto.titolari)
        #expect(vm.statoScelta == .altra)
        // di nuovo a mano, poi lo stile consigliato: è la consigliata
        vm.iniziaModificaManuale(f)
        vm.scegliStile(0)
        #expect(vm.manuale == nil)
        #expect(vm.statoScelta == .consigliata)
        #expect(srv.quante("DELETE /api/scelta") == 0, "non c'è niente da togliere")
    }

    @Test("Senza scelta salvata: in modifica a mano un tocco su un modulo torna a quel modulo dello stile")
    func moduloEsceDallaModificaAMano() async throws {
        let (vm, f) = try await caricata(try server(scelta: nil))
        let (base, altro) = try moduli(f)
        vm.iniziaModificaManuale(f)
        vm.scegliModulo(altro.modulo)
        #expect(vm.manuale == nil)
        #expect(vm.moduloScelto == altro.modulo)
        #expect(vm.vista(f).titolari.map(\.id) == altro.titolari)
        #expect(vm.statoScelta == .altra)
        vm.iniziaModificaManuale(f)
        vm.scegliModulo(base.modulo)
        #expect(vm.statoScelta == .consigliata, "il modulo proposto dallo stile consigliato è la consigliata")
    }

    @Test("Con la scelta salvata: un altro modulo è «Modifiche non salvate» con Salva, Annulla e Torna, e la scelta resta sul server; il modulo dello stile consigliato torna «salvata»")
    func moduloConSceltaSalvata() async throws {
        let salvata = try consigliata()
        let srv = try server(scelta: salvata)
        let (vm, f) = try await caricata(srv)
        #expect(vm.statoScelta == .salvata(alle))
        #expect(vm.manuale != nil, "si riparte dalla scelta salvata, in modifica a mano")
        let (base, altro) = try moduli(f)
        vm.scegliModulo(altro.modulo)
        #expect(vm.manuale == nil)
        #expect(vm.statoScelta == .modificata(alle))
        #expect(vm.statoScelta.pulsanti == [.salva, .annulla, .torna])
        #expect(Set(vm.salvati ?? []) == Set(salvata), "la scelta salvata non si tocca")
        #expect(srv.quante("DELETE /api/scelta") == 0)
        // il modulo proposto dallo stile consigliato: sono proprio gli undici salvati
        vm.scegliModulo(base.modulo)
        #expect(vm.statoScelta == .salvata(alle))
    }

    @Test("«Annulla modifiche» fuori dalla modifica a mano rimette gli undici salvati")
    func annullaFuoriDallaModificaAMano() async throws {
        let salvata = try consigliata()
        let (vm, _) = try await caricata(try server(scelta: salvata))
        vm.scegliStile(1)
        #expect(vm.statoScelta == .modificata(alle))
        vm.annullaModifiche()
        #expect(Set(vm.manuale ?? []) == Set(salvata))
        #expect(vm.statoScelta == .salvata(alle))
    }

    @Test("«Salva le modifiche» fuori dalla modifica a mano salva gli undici del modulo sullo schermo")
    func salvaFuoriDallaModificaAMano() async throws {
        let srv = try server(scelta: try consigliata())
        let (vm, f) = try await caricata(srv)
        let (_, altro) = try moduli(f)
        vm.scegliModulo(altro.modulo)
        await vm.salvaQuesta(f)
        let corpo = try #require(srv.corpiInviati(a: "POST /api/formazione/valuta").last)
        let richiesta = try #require(try JSONSerialization.jsonObject(with: corpo) as? [String: Any])
        #expect(richiesta["salva"] as? Bool == true)
        #expect((richiesta["titolari"] as? [Int]).map { Set($0) } == Set(altro.titolari))
        #expect(Set(vm.salvati ?? []) == Set(altro.titolari))
        guard case .salvata = vm.statoScelta else {
            Issue.record("dopo il salvataggio la riga dice «salvata»: \(vm.statoScelta)")
            return
        }
    }

    @Test("Ricaricando (ritorno sulla Formazione, tira per aggiornare) il modulo toccato resta: la scelta salvata non lo copre")
    func ricaricandoIlModuloResta() async throws {
        let (vm, f) = try await caricata(try server(scelta: try consigliata()))
        let (_, altro) = try moduli(f)
        vm.scegliModulo(altro.modulo)
        await vm.carica()
        #expect(vm.manuale == nil)
        #expect(vm.moduloScelto == altro.modulo)
        #expect(vm.statoScelta == .modificata(alle))
    }

    @Test("A giornata chiusa un tocco su uno stile non toglie la formazione che vale")
    func chiusaLaFormazioneResta() async throws {
        let (vm, _) = try await caricata(try server(scelta: try consigliata(), iniziata: true))
        let prima = try #require(vm.manuale)
        vm.scegliStile(1)
        #expect(vm.manuale == prima)
    }

    // MARK: la scelta cambiata altrove (412) e il ritorno alla tua squadra

    @Test("Salvi a mano ma un altro dispositivo ha già salvato un'altra scelta (412): in campo la sua, «salvata», niente in sospeso")
    func conflittoAlSalvataggio() async throws {
        let (s, s2) = try dueScelte()
        let salvata = Scatola<String>()
        salvata.valore = scelta(s, "2026-11-02T21:40:00")
        let srv = try serverAltroDispositivo(salvata)
        let (vm, f) = try await caricata(srv)
        #expect(Set(vm.manuale ?? []) == Set(s))
        salvata.valore = scelta(s2, "2026-11-03T09:15:00")   // l'altro dispositivo salva un'altra formazione
        vm.manuale = f.titolari.map(\.id)                      // la modifica a mano di questo telefono
        #expect(vm.statoScelta == .modificata(alle))
        await vm.salvaQuesta(f)
        #expect(srv.quante("GET /api/scelta") == 2, "dopo il 412 si rilegge la scelta")
        #expect(Set(vm.manuale ?? []) == Set(s2), "in campo la scelta salvata dall'altro dispositivo")
        #expect(vm.statoScelta == .salvata(Quando.data("2026-11-03T09:15:00")))
        #expect(!vm.statoScelta.daSalvare, "niente modifiche in sospeso: «Salva» non scriverebbe sopra la scelta nuova")
        #expect(vm.messaggio == FormazioneViewModel.sceltaCambiata)
    }

    @Test("«Torna alla consigliata» ma un altro dispositivo ha già salvato un'altra scelta (412): in campo la sua, «salvata»")
    func conflittoTornandoAllaConsigliata() async throws {
        let (s, s2) = try dueScelte()
        let salvata = Scatola<String>()
        salvata.valore = scelta(s, "2026-11-02T21:40:00")
        let srv = try serverAltroDispositivo(salvata)
        let (vm, f) = try await caricata(srv)
        salvata.valore = scelta(s2, "2026-11-03T09:15:00")
        await vm.tornaAllaConsigliata(f)
        #expect(srv.quante("DELETE /api/scelta") == 1)
        #expect(Set(vm.manuale ?? []) == Set(s2), "in campo la scelta salvata dall'altro dispositivo")
        #expect(vm.statoScelta == .salvata(Quando.data("2026-11-03T09:15:00")))
        #expect(vm.messaggio == FormazioneViewModel.sceltaCambiata)
    }

    @Test("Guardata la formazione di un'altra squadra, «Torna alla tua» rimette in campo la tua scelta salvata")
    func tornaAllaTuaConLaScelta() async throws {
        let (s, _) = try dueScelte()
        let salvata = Scatola<String>()
        salvata.valore = scelta(s, "2026-11-02T21:40:00")
        let srv = try serverAltroDispositivo(salvata)
        let (vm, _) = try await caricata(srv)
        vm.vediSquadra("Inter Nos")
        await aspetta { srv.quante("GET /api/formazione?squadra=") == 1 && vm.formazione != nil }
        try await Task.sleep(nanoseconds: 100_000_000)        // finisce il caricamento della squadra guardata
        vm.tornaAllaMia()
        await aspetta { vm.manuale != nil && !vm.provaSalvata }   // rimessa in campo e provata dal server
        #expect(Set(vm.manuale ?? []) == Set(s), "in campo la tua scelta salvata")
        #expect(vm.statoScelta == .salvata(alle))
    }

    @Test("Due tocchi di fila su Salva (o ⌘S): un solo salvataggio, come `sc.occupato` della web")
    func unSoloSalvataggioAllaVolta() async throws {
        let dati = try Fixture.dati("formazione")
        let srv = ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if corpo.map({ String(decoding: $0, as: UTF8.self).contains("\"salva\":true") }) == true {
                    try await Task.sleep(nanoseconds: 200_000_000)   // un salvataggio che dura un po', come sulla rete vera
                }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return metodo == "GET" ? Data("null".utf8) : Data("{\"ok\": true}".utf8) }
            return dati
        }
        let (vm, f) = try await caricata(srv)
        let primo = Task { await vm.salvaQuesta(f) }
        let secondo = Task { await vm.salvaQuesta(f) }
        await primo.value
        await secondo.value
        let salvataggi = srv.corpiInviati(a: "POST /api/formazione/valuta")
            .filter { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") }
        #expect(salvataggi.count == 1)
        #expect(!vm.salvataggioInCorso, "finito il salvataggio i pulsanti tornano attivi")
        guard case .salvata = vm.statoScelta else {
            Issue.record("dopo il salvataggio la riga dice «salvata»: \(vm.statoScelta)")
            return
        }
    }

    // MARK: foto

    @Test("La foto «formazione-modificata»: la scelta salvata della demo e un altro modulo toccato, «Modifiche non salvate» con Salva, Annulla e Torna")
    func fotoFormazioneModificata() async throws {
        let server = try #require(FinteServer.demoFase("formazione-modificata", adesso: Date(timeIntervalSinceReferenceDate: 815_000_000)),
                                  "manca la demo della foto")
        let vm = FormazioneViewModel(server: server)
        await vm.carica()
        let f = try #require(vm.formazione)
        guard case .salvata = vm.statoScelta else {
            Issue.record("la demo parte dalla scelta salvata: \(vm.statoScelta)")
            return
        }
        let modulo = try #require(Demo.moduloDaToccare(f, rischio: vm.rischio, salvati: vm.salvati), "nessun modulo da toccare")
        vm.scegliModulo(modulo)
        guard case .modificata = vm.statoScelta else {
            Issue.record("dopo il tocco la riga dice «Modifiche non salvate»: \(vm.statoScelta)")
            return
        }
        #expect(vm.statoScelta.pulsanti == [.salva, .annulla, .torna])
    }

    // MARK: aiuti

    /// La parola dell'iPhone per una chiave del catalogo (nil = chiave che questo test non conosce).
    private func paroleIPhone(_ chiave: String) -> String? {
        switch chiave {
        case "formazione.salva_questa": return RigaStatoScelta.testoSalvaQuesta
        case "formazione.salva_modifiche": return FormazioneView.etichettaSalva(.modificata(nil))
        case "formazione.salva_come_mia": return FormazioneView.etichettaSalva(.bozza)
        case "formazione.annulla_modifiche": return RigaStatoScelta.testoAnnulla
        case "formazione.torna_alla_consigliata": return RigaStatoScelta.testoTorna
        case "formazione.modifica_mano": return FormazioneView.testoModificaAMano
        default: return nil
        }
    }

    /// Gli undici della consigliata della fixture (stile equilibrato, modulo proposto).
    private func consigliata() throws -> [Int] {
        let base: Formazione = try Fixture.decodifica("formazione")
        return base.titolari.map(\.id)
    }

    /// Il modulo proposto dallo stile consigliato e un altro modulo dello stesso stile (undici diversi).
    private func moduli(_ f: Formazione) throws -> (base: OpzioneModulo, altro: OpzioneModulo) {
        let livello = try #require(f.livelli?.first { $0.rischio == (f.stileConsigliato ?? 0) })
        let base = try #require(livello.moduli.first { $0.modulo == livello.modulo })
        let altro = try #require(livello.moduli.first { $0.modulo != livello.modulo && Set($0.titolari) != Set(base.titolari) })
        return (base, altro)
    }

    /// Un server con la formazione della fixture (aperta o chiusa) e una scelta salvata (`scelta`; nil = nessuna). A giornata
    /// chiusa le scritture rispondono 409 `formazione_chiusa`, come il server vero.
    private func server(scelta: [Int]?, iniziata: Bool = false) throws -> ServerDiProva {
        var dati = try Fixture.dati("formazione")
        if iniziata {
            var json = try #require(try JSONSerialization.jsonObject(with: dati) as? [String: Any])
            json["iniziata"] = true
            dati = try JSONSerialization.data(withJSONObject: json)
        }
        let formazione = dati
        let codiceChiusa = FormazioneViewModel.codiceChiusa
        let salvata = Data((scelta.map { "{\"titolari\": [\($0.map(String.init).joined(separator: ","))], \"salvata\": \"2026-11-02T21:40:00\"}" } ?? "null").utf8)
        return ServerDiProva { metodo, percorso, corpo in
            let scrive = metodo == "DELETE" || corpo.map { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") } == true
            if iniziata, scrive { throw ErroreApi.codificato(codice: codiceChiusa, messaggio: "Formazione chiusa") }
            if percorso.hasPrefix("/api/formazione/valuta") { return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8) }
            if percorso.hasPrefix("/api/scelta") { return metodo == "GET" ? salvata : Data("{\"ok\": true}".utf8) }
            return formazione
        }
    }

    /// I pulsanti di ogni stato in `rigaStatoScelta` di `fanta/web/app.js` (`const pulsanti = { stato: b("id", …) + … }`), con gli
    /// id dei pulsanti nell'ordine della web: una copia ferma del 12/11/2026, prima del rifacimento della web (il codice della web
    /// non si legge più; l'app resta com'è finché il proprietario non decide).
    private static let pulsantiWeb: [String: [String]] = [
        "consigliata": ["salva-questa", "modifica"],
        "altra": ["salva-questa", "modifica", "torna-consigliata"],
        "salvata": ["torna-consigliata"],
        "modificata": ["salva-scelta", "annulla-modifiche", "torna-consigliata"],
        "mano": ["salva-scelta", "torna-consigliata"],
        "non_valida": ["modifica", "torna-consigliata"],
        "chiusa": [],
    ]

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

    /// La risposta di `GET /api/scelta` per questi titolari, salvati a quell'ora.
    private func scelta(_ titolari: [Int], _ salvata: String) -> String {
        "{\"titolari\": [\(titolari.map(String.init).joined(separator: ","))], \"salvata\": \"\(salvata)\"}"
    }

    /// Un server con la scelta salvata in `salvata` (un altro dispositivo la può cambiare): un salvataggio o una cancellazione
    /// rispondono 412 (`ErroreApi.conflitto`), come il server vero quando la scelta è cambiata dopo l'ultima lettura.
    private func serverAltroDispositivo(_ salvata: Scatola<String>) throws -> ServerDiProva {
        let dati = try Fixture.dati("formazione")
        return ServerDiProva { metodo, percorso, corpo in
            let scrive = metodo == "DELETE" || corpo.map { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") } == true
            if scrive { throw ErroreApi.conflitto }
            if percorso.hasPrefix("/api/formazione/valuta") { return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8) }
            if percorso.hasPrefix("/api/scelta") { return Data((salvata.valore ?? "null").utf8) }
            return dati
        }
    }

    /// Aspetta (al massimo 3 secondi) che una condizione diventi vera: per le azioni che partono in un `Task`.
    private func aspetta(_ condizione: () -> Bool) async {
        var giri = 0
        while !condizione(), giri < 300 {
            try? await Task.sleep(nanoseconds: 10_000_000)
            giri += 1
        }
    }

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}
