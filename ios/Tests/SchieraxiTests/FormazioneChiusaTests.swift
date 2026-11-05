import Foundation
import Testing
@testable import Schieraxi

/// Formazione dopo la scadenza (`iniziata` del server), con le frasi della web (`fanta/web/testi.js`) come dice
/// `docs/COERENZA-WEB-IPHONE.md`: per la tua squadra la riga di stato della scelta («Giornata iniziata: la formazione è
/// chiusa», con «· vale quella che hai salvato» se c'è una scelta salvata), per un'altra squadra la fascia `formazione.chiusa`.
/// La formazione resta in sola lettura.
@MainActor
@Suite("Formazione chiusa come la web")
struct FormazioneChiusaTests {
    // MARK: frasi e stato

    @Test("Riga di stato a giornata chiusa: la frase della web, con «vale quella che hai salvato» solo se c'è una scelta salvata",
          arguments: zip([true, false], ["formazione.stato_chiusa_tua", "formazione.stato_chiusa"]))
    func fraseDellaRiga(tua: Bool, chiave: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(StatoScelta.chiusa(tua: tua).titolo() == web)
    }

    @Test("A giornata chiusa lo stato è «chiusa», anche prima di leggere la scelta e con una modifica a mano lasciata a metà")
    func statoChiusa() {
        let scelti = Array(1...11)
        var altri = scelti
        altri[0] = 99
        #expect(StatoScelta.calcola(letta: false, salvati: nil, salvataIl: nil, manuale: nil, chiusa: true) == .chiusa(tua: false))
        #expect(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: nil, chiusa: true) == .chiusa(tua: false))
        #expect(StatoScelta.calcola(letta: true, salvati: nil, salvataIl: nil, manuale: scelti, chiusa: true) == .chiusa(tua: false))
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: nil, manuale: scelti, chiusa: true) == .chiusa(tua: true))
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: nil, manuale: altri, chiusa: true) == .chiusa(tua: true))
        // aperta: come prima
        #expect(StatoScelta.calcola(letta: true, salvati: scelti, salvataIl: nil, manuale: scelti, chiusa: false) == .salvata(nil))
        // niente da salvare, grigia come il «■» della web, con il lucchetto (lo stato non si legge dal solo colore)
        #expect(!StatoScelta.chiusa(tua: true).daSalvare)
        #expect(StatoScelta.chiusa(tua: true).tono == .neutro)
        #expect(StatoScelta.chiusa(tua: false).simbolo == "lock.fill")
    }

    // MARK: schermata

    @Test("La tua formazione salvata a giornata chiusa: una riga sola con la frase della web, niente fascia, sola lettura")
    func salvataASolaLettura() async throws {
        let web = try TestiWeb().italiano("formazione.stato_chiusa_tua")
        let srv = try serverChiuso()
        let (vm, f) = try await caricata(srv)
        #expect(vm.chiusa)
        #expect(vm.statoScelta == .chiusa(tua: true))
        #expect(vm.statoScelta.titolo() == web)
        #expect(vm.fasciaChiusa == nil, "la riga di stato dice già che è chiusa: niente seconda frase")
        let base: Formazione = try Fixture.decodifica("formazione")
        #expect(Set(vm.manuale ?? []) == Set(base.titolari.map(\.id)), "si vede la formazione salvata")
        let prima = vm.manuale
        // niente sostituzioni, niente «Salva», niente «Torna alla consigliata», niente ballottaggi
        let uscente = try #require(vm.vista(f).titolari.first { $0.ruolo == "D" })
        let titolari = Set(vm.manuale ?? [])
        let entrante = try #require(f.schede?.values.first { $0.ruolo == "D" && !titolari.contains($0.id) })
        vm.sostituisci(uscente.id, con: entrante.id)
        #expect(vm.manuale == prima)
        await vm.valuta(salva: true)
        await vm.tornaAllaConsigliata(f)
        #expect(srv.quante("DELETE /api/scelta") == 0)
        let salvataggi = srv.corpiInviati(a: "POST /api/formazione/valuta").filter { String(decoding: $0, as: UTF8.self).contains("\"salva\":true") }
        #expect(salvataggi.isEmpty, "a giornata chiusa non si prova nemmeno a salvare")
        #expect(vm.ballottaggio(per: uscente, f, vm.vista(f)).isEmpty)
    }

    @Test("Senza scelta salvata a giornata chiusa: la frase della web senza «vale quella che hai salvato», niente modifica a mano")
    func senzaSceltaNienteModificaAMano() async throws {
        let web = try TestiWeb().italiano("formazione.stato_chiusa")
        let (vm, f) = try await caricata(try serverChiuso(conScelta: false))
        #expect(vm.statoScelta == .chiusa(tua: false))
        #expect(vm.statoScelta.titolo() == web)
        #expect(vm.fasciaChiusa == nil)
        vm.iniziaModificaManuale(f)
        #expect(vm.manuale == nil)
        await vm.salvaQuesta(f)
        #expect(vm.manuale == nil)
        #expect(vm.statoScelta == .chiusa(tua: false))
    }

    @Test("La formazione di un'altra squadra a giornata chiusa: la fascia della web (`formazione.chiusa`), nessuna riga di stato")
    func altraSquadra() async throws {
        let web = try TestiWeb().italiano("formazione.chiusa")
        let srv = try serverChiuso()
        let vm = FormazioneViewModel(server: srv)
        vm.squadraVista = "Gli Amici"
        await vm.carica()
        #expect(vm.chiusa)
        #expect(vm.statoScelta == .sconosciuto)
        #expect(vm.fasciaChiusa == web)
        #expect(srv.quante("GET /api/scelta") == 0, "la scelta salvata è solo della tua squadra")
    }

    @Test("Prima della scadenza nessuna fascia di formazione chiusa")
    func apertaSenzaFascia() async throws {
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let (vm, _) = try await caricata(srv)
        #expect(!vm.chiusa)
        #expect(vm.fasciaChiusa == nil)
        #expect(vm.statoScelta == .consigliata)
    }

    @Test("Se la giornata si chiude mentre salvi: la frase della web (`err.formazione_chiusa`), mai il testo grezzo del server")
    func siChiudeMentreSalvi() async throws {
        // il server dice «aperta» ma rifiuta il salvataggio con 409 formazione_chiusa (scadenza passata con la pagina aperta)
        let srv = ServerDiProva { _, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if let corpo, String(decoding: corpo, as: UTF8.self).contains("\"salva\":true") {
                    throw ErroreApi.codificato(codice: FormazioneViewModel.codiceChiusa, messaggio: "testo tecnico")
                }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let web = try TestiWeb().italiano("err.formazione_chiusa")
        let (vm, f) = try await caricata(srv)
        await vm.salvaQuesta(f)
        #expect(vm.messaggio == web)
        #expect(srv.quante("GET /api/formazione") == 2, "si ricarica per sapere che è chiusa")
    }

    // MARK: aiuti

    /// Un server con la giornata chiusa (`iniziata: true`) e, se serve, una scelta salvata; le scritture rispondono 409 `formazione_chiusa`.
    private func serverChiuso(conScelta: Bool = true) throws -> ServerDiProva {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        formazione["iniziata"] = true
        let dati = try JSONSerialization.data(withJSONObject: formazione)
        let base: Formazione = try Fixture.decodifica("formazione")
        let ids = base.titolari.map(\.id).map(String.init).joined(separator: ",")
        let scelta = Data((conScelta ? "{\"titolari\": [\(ids)], \"salvata\": \"2026-10-31T13:09:00\"}" : "null").utf8)
        return ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/formazione/valuta") {
                if let corpo, String(decoding: corpo, as: UTF8.self).contains("\"salva\":true") {
                    throw ErroreApi.codificato(codice: FormazioneViewModel.codiceChiusa, messaggio: "Formazione chiusa")
                }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") {
                if metodo == "DELETE" { throw ErroreApi.codificato(codice: FormazioneViewModel.codiceChiusa, messaggio: "Formazione chiusa") }
                return scelta
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
