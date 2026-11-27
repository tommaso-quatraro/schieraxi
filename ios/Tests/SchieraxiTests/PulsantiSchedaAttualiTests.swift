import Foundation
import Testing
@testable import Schieraxi

/// La scheda aperta dalla Formazione legge lo stato di adesso, come la web (collaudo del 26/11): «Sostituisci» e «Metti in campo»
/// ci sono appena il giocatore si può spostare (`siSposta` della web: la tua formazione, aperta, lui non fermo) e restano spenti
/// finché i dati non sono arrivati (`pronta()` della web); arrivati, si accendono anche nella scheda già aperta. Prima la scheda
/// teneva la fotografia presa all'apertura: toccato un giocatore mentre arrivavano i dati, i due pulsanti non comparivano più.
@MainActor
@Suite("La scheda aperta dalla Formazione: i pulsanti seguono lo stato di adesso")
struct PulsantiSchedaAttualiTests {
    /// Attaccante titolare del 4-3-3 della fixture.
    static let titolare = 7525
    /// Centrocampista in panchina.
    static let panchinaro = 5307

    @Test("Toccato un giocatore mentre arrivano i dati: i pulsanti ci sono subito, spenti, e la scheda aperta li accende all'arrivo")
    func spentiPoiAccesi() async throws {
        let cancello = Cancello()
        let vm = try Self.formazione(cancello: cancello)
        let lettura = Task { await vm.carica() }
        await cancello.richiestaArrivata()                  // la Formazione c'è, la scelta salvata sta arrivando
        try #require(vm.formazione != nil && vm.comandiSpenti)
        let titolare = try #require(vm.contestoScheda(Self.titolare))
        let panchinaro = try #require(vm.contestoScheda(Self.panchinaro))
        #expect(titolare.sostituibile && !titolare.pronta, "«Sostituisci» c'è, spento")
        #expect(panchinaro.entrabile && !panchinaro.pronta, "«Metti in campo» c'è, spento")
        await cancello.apri()
        await lettura.value
        try #require(!vm.comandiSpenti)
        let dopo = vm.contestoAttuale(Self.titolare, aperta: titolare)
        #expect(dopo.sostituibile && dopo.pronta, "arrivati i dati, la scheda già aperta ha «Sostituisci» acceso")
        let dopoPanchinaro = vm.contestoAttuale(Self.panchinaro, aperta: panchinaro)
        #expect(dopoPanchinaro.entrabile && dopoPanchinaro.pronta, "e «Metti in campo» acceso")
    }

    @Test("Con i pulsanti spenti gli elenchi non partono; «Sostituisci» toccato un attimo prima lo dice sotto il campo")
    func spentiNonApronoNiente() async throws {
        let cancello = Cancello()
        let vm = try Self.formazione(cancello: cancello)
        let lettura = Task { await vm.carica() }
        await cancello.richiestaArrivata()
        await vm.sostituisci(Self.titolare)
        await vm.mettiInCampo(Self.panchinaro)
        #expect(vm.elencoSostituti == nil && vm.elencoEntra == nil)
        // toccato quando era acceso, il foglio della scheda sparisce mentre parte una rilettura
        vm.chiediSostituzione(Self.titolare)
        vm.apriSostituzioneInAttesa()
        #expect(vm.elencoSostituti == nil)
        #expect(vm.messaggio == Catalogo.Formazione.stoAncoraRicalcolando, "mai un tocco che non fa niente senza dirlo")
        await cancello.apri()
        await lettura.value
    }

    @Test("La scheda aperta di un giocatore che la Formazione non ha più: la previsione dell'apertura, senza pulsanti")
    func giocatoreSparito() async throws {
        let vm = try Self.formazione()
        await vm.carica()
        let estraneo: Giocatore = try Decodifica.decodifica(Data(#"{"id": 999999, "nome": "Mario Prova", "ruolo": "A"}"#.utf8))
        let aperta = ContestoScheda(previsione: estraneo, sostituibile: true, pronta: true)
        let ora = vm.contestoAttuale(estraneo.id, aperta: aperta)
        #expect(ora.previsione.id == estraneo.id)
        #expect(!ora.sostituibile && !ora.entrabile && !ora.fermo)
    }

    // MARK: aiuti

    /// La Formazione della fixture, senza scelta salvata. `cancello`: la lettura della scelta aspetta il test.
    private static func formazione(cancello: Cancello? = nil) throws -> FormazioneViewModel {
        let dati = try Fixture.dati("formazione")
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scelta") {
                if let cancello { await cancello.passa() }
                return Data("null".utf8)
            }
            if percorso.hasPrefix("/api/formazione/") { return Data("{}".utf8) }
            return dati
        }
        return FormazioneViewModel(server: srv)
    }
}
