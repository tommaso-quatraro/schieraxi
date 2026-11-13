import Foundation
import Testing
@testable import Schieraxi

/// Formazione dopo la scadenza (`iniziata` del server), come la web (#616, #673): per la tua squadra la riga dello stato con una
/// delle tre frasi della giornata chiusa (`formazione.stato_chiusa*`), in campo quella che vale, e niente che scriva: né modulo,
/// né «Sostituisci», né «Torna alla consigliata», né la spunta. La formazione di un'altra squadra non ha la riga dello stato.
@MainActor
@Suite("Formazione chiusa come la web")
struct FormazioneChiusaTests {
    @Test("La tua formazione salvata a giornata chiusa: «vale quella che hai salvato», in campo lei, niente scritture")
    func salvataASolaLettura() async throws {
        let srv = try serverChiuso(scelta: .altroModulo)
        let (vm, f) = try await caricata(srv)
        #expect(vm.chiusa)
        #expect(vm.statoScelta == .chiusa(.tua))
        #expect(vm.statoScelta.frase == Catalogo.Formazione.statoChiusaTua)
        let salvati = try Self.altroModulo()
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(salvati), "si vede la formazione salvata")
        // niente cambi: modulo, sostituzione, spunta, «Torna alla consigliata»
        let consigliato = try #require(vm.consigliato(f))
        await vm.scegliModulo(consigliato.modulo)
        let uscente = try #require(vm.vista(f).titolari.first { $0.ruolo == "D" })
        let titolari = Set(vm.vista(f).titolari.map(\.id))
        let entrante = try #require(f.schede?.values.first { $0.ruolo == "D" && !titolari.contains($0.id) })
        let fatto = await vm.sostituisciTitolare(uscente.id, con: entrante.id)
        await vm.segnaMessa(true)
        await vm.tornaAllaConsigliata()
        #expect(!fatto)
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(salvati))
        #expect(srv.quante("DELETE /api/scelta") == 0)
        #expect(Self.salvataggi(srv) == 0, "a giornata chiusa non si prova nemmeno a salvare")
        #expect(!vm.sostituibile(uscente.id) && vm.percheTitolare(uscente.id) == nil)
    }

    @Test("Senza scelta salvata a giornata chiusa: la frase senza «vale quella che hai salvato», in campo la consigliata")
    func senzaScelta() async throws {
        let srv = try serverChiuso(scelta: .nessuna)
        let (vm, f) = try await caricata(srv)
        #expect(vm.statoScelta == .chiusa(.senzaScelta))
        #expect(vm.statoScelta.frase == Catalogo.Formazione.statoChiusa)
        #expect(vm.manuale == nil)
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(vm.consigliati(f)))
        let altro = try #require(vm.moduli(f).first { $0.modulo != vm.consigliato(f)?.modulo })
        await vm.scegliModulo(altro.modulo)
        #expect(vm.manuale == nil)
        #expect(Self.salvataggi(srv) == 0)
    }

    @Test("La scelta salvata non vale più (`stato_scelta` del server): «vale la consigliata, la tua non è più valida»")
    func nonValidaAChiusura() async throws {
        let srv = try serverChiuso(scelta: .altroModulo, statoScelta: "non_valida")
        let (vm, f) = try await caricata(srv)
        #expect(vm.statoScelta == .chiusa(.nonValida))
        #expect(vm.statoScelta.frase == Catalogo.Formazione.statoChiusaNonValida)
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(vm.consigliati(f)), "in campo la consigliata")
        #expect(srv.quante("POST /api/formazione/valuta") == 0, "il server ha già detto che non vale: niente valutazione")
    }

    @Test("La formazione di un'altra squadra a giornata chiusa: nessuna riga dello stato, la scelta non si legge")
    func altraSquadra() async throws {
        let srv = try serverChiuso(scelta: .altroModulo)
        let vm = FormazioneViewModel(server: srv)
        vm.vediSquadra("Gli Amici")
        await vm.carica()
        #expect(vm.chiusa)
        #expect(vm.statoScelta == .nessuno)
        #expect(srv.quante("GET /api/scelta") == 0, "la scelta salvata è solo della tua squadra")
    }

    @Test("Se la giornata si chiude con la schermata aperta: la frase del server (`err.formazione_chiusa`) e si rilegge")
    func siChiudeMentreCambi() async throws {
        // il server dice «aperta» ma rifiuta il salvataggio con 409 formazione_chiusa (scadenza passata con la pagina aperta)
        let web = try TestiWeb().italiano("err.formazione_chiusa")
        let srv = ServerDiProva { _, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if Self.salva(corpo) { throw ErroreApi.codificato(codice: FormazioneViewModel.codiceChiusa, messaggio: web) }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let (vm, f) = try await caricata(srv)
        let altro = try #require(vm.moduli(f).first { $0.modulo != vm.consigliato(f)?.modulo })
        await vm.scegliModulo(altro.modulo)
        #expect(vm.messaggio == web)
        #expect(srv.quante("GET /api/formazione") == 2, "si rilegge per sapere che è chiusa")
        #expect(vm.manuale == nil, "il cambio rifiutato non resta in campo")
        #expect(!vm.occupato)
    }

    // MARK: aiuti

    enum Scelta { case nessuna, altroModulo }

    /// Gli 11 del secondo modulo dello stile equilibrato della fixture: una scelta salvata diversa dalla consigliata.
    static func altroModulo() throws -> [Int] {
        let f: Formazione = try Fixture.decodifica("formazione")
        let livello = try #require(f.livelli?.first { $0.rischio == 0 })
        return try #require(livello.moduli.first { $0.modulo != livello.modulo }).titolari
    }

    /// La richiesta salva la scelta (`salva: true` nel corpo di `POST /api/formazione/valuta`).
    nonisolated static func salva(_ corpo: Data?) -> Bool {
        corpo.map { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") } == true
    }

    static func salvataggi(_ srv: ServerDiProva) -> Int {
        srv.corpiInviati(a: "POST /api/formazione/valuta").filter { salva($0) }.count
    }

    /// Un server con la giornata chiusa (`iniziata: true`), con o senza scelta salvata e lo `stato_scelta` del server; le scritture
    /// rispondono 409 `formazione_chiusa`, come il server vero.
    private func serverChiuso(scelta: Scelta, statoScelta: String? = nil) throws -> ServerDiProva {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        formazione["iniziata"] = true
        if let statoScelta { formazione["stato_scelta"] = statoScelta }
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let ids = try Self.altroModulo().map(String.init).joined(separator: ",")
        let risposta = Data((scelta == .altroModulo ? "{\"titolari\": [\(ids)], \"salvata\": \"2026-10-31T13:09:00\"}" : "null").utf8)
        return ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if Self.salva(corpo) { throw ErroreApi.codificato(codice: FormazioneViewModel.codiceChiusa, messaggio: "Formazione chiusa") }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") {
                if metodo == "DELETE" { throw ErroreApi.codificato(codice: FormazioneViewModel.codiceChiusa, messaggio: "Formazione chiusa") }
                return risposta
            }
            return dati
        }
    }

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}
