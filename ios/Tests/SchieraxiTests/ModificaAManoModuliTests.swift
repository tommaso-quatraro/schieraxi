import Foundation
import Testing
@testable import Schieraxi

/// In modifica a mano moduli e stili restano sullo schermo, come la web (#463): al posto della frase dello stile c'è
/// `formazione.modificata_mano` di `fanta/web/testi.js`, e un tocco su un modulo o uno stile esce dalla modifica a mano e torna alla
/// proposta del server SENZA cancellare la scelta salvata (`data-modulo` e `data-stile` di `mostraFormazione` in `fanta/web/app.js`).
/// I pulsanti dipendono dallo stato della scelta, come `rigaStatoScelta` della web: con una scelta salvata e un'altra formazione
/// sullo schermo la riga dice «Modifiche non salvate» con «Salva le modifiche», «Annulla modifiche» e «Torna alla consigliata».
@MainActor
@Suite("Modifica a mano: moduli e stili come la web")
struct ModificaAManoModuliTests {
    private var alle: Date? { Quando.data("2026-11-02T21:40:00") }

    // MARK: frasi e pulsanti

    @Test("In modifica a mano, al posto della frase dello stile, «Modificata a mano. Tocca un modulo o uno stile …» della web")
    func fraseModificataAMano() throws {
        #expect(FormazioneView.testoModificataAMano == (try web("formazione.modificata_mano")))
    }

    @Test("I pulsanti hanno le parole della web",
          arguments: ["formazione.salva_questa", "formazione.salva_modifiche", "formazione.salva_come_mia",
                      "formazione.annulla_modifiche", "formazione.torna_alla_consigliata", "formazione.modifica_mano"])
    func paroleDeiPulsanti(chiave: String) throws {
        let iPhone = try #require(paroleIPhone(chiave), "manca il pulsante dell'iPhone per \(chiave)")
        #expect(iPhone == (try web(chiave)))
    }

    @Test("I pulsanti di ogni stato sono quelli di `rigaStatoScelta` della web, nello stesso ordine; «Modifica a mano» dove la web la offre")
    func pulsantiPerStato() {
        let attesi: [(stato: StatoScelta, pulsanti: [StatoScelta.Pulsante], modifica: Bool)] = [
            (.consigliata, [.salvaQuesta], true),
            (.altra, [.salvaQuesta, .torna], true),
            (.salvata(alle), [.torna], false),
            (.modificata(alle), [.salva, .annulla, .torna], false),
            (.bozza, [.salva, .torna], false),
            (.nonValida, [.torna], true),
            (.chiusa(tua: true), [], false),
            (.chiusa(tua: false), [], false),
            (.chiusaNonValida, [], false),
        ]
        for riga in attesi {
            #expect(riga.stato.pulsanti == riga.pulsanti, "pulsanti con \(riga.stato)")
            #expect(riga.stato.conModificaAMano == riga.modifica, "«Modifica a mano» con \(riga.stato)")
        }
        // senza riga (un'altra squadra, scelta non ancora letta) niente pulsanti nella riga; «Modifica a mano» resta, come la web
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

    // MARK: aiuti

    private func web(_ chiave: String) throws -> String { try TestiWeb().italiano(chiave) }

    /// La parola dell'iPhone per una chiave di `testi.js` (nil = chiave che questo test non conosce).
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

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}
