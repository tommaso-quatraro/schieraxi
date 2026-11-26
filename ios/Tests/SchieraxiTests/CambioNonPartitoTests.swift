import Foundation
import Testing
@testable import Schieraxi

/// Un sostituto, o un titolare, toccato nell'elenco quando il cambio non si può fare non sparisce in silenzio (collaudo del 26/11):
/// l'elenco spegne le righe con la frase del catalogo (`motivoCambiSpenti`: si sta rileggendo, la formazione si è chiusa) e, se il
/// tocco arriva lo stesso, l'elenco si chiude e la frase si legge sotto il campo. Prima l'elenco si chiudeva, il cambio non si
/// faceva e nessun messaggio lo diceva. Se una rilettura porta in campo altri 11, l'elenco aperto si chiude, come
/// `chiudiSostituzione` della web: i suoi numeri erano di un'altra formazione (revisione della #946).
@MainActor
@Suite("Un cambio che non parte lo si dice")
struct CambioNonPartitoTests {
    /// Difensore titolare del 4-3-3 della fixture e un difensore in panchina che può entrare al suo posto.
    static let titolare = 6523
    static let sostituto = 6994
    /// Centrocampista in panchina e un centrocampista titolare che può lasciargli il posto.
    static let panchinaro = 5307
    static let esce = 2404
    /// Gli 11 del 5-3-2 della fixture, un altro modulo del menu (6523 resta titolare, 5307 resta fuori).
    static let titolari532 = [7575, 4510, 7318, 6994, 6523, 7457, 2404, 6822, 5680, 7525, 7537]

    @Test("A dati letti le righe sono accese; durante una rilettura spente con «Sto ancora ricalcolando», e il tocco lo dice")
    func duranteUnaRilettura() async throws {
        let cancello = Cancello()
        let blocca = Scatola<Bool>()
        let (vm, srv) = try await Self.caricata(cancello: cancello, blocca: blocca)
        await vm.sostituisci(Self.titolare)
        try #require(vm.elencoSostituti?.stato.righe?.map(\.entra.id) == [Self.sostituto])
        #expect(vm.motivoCambiSpenti == nil, "a dati letti le righe sono accese")
        blocca.valore = true
        let rilettura = Task { await vm.carica() }
        await cancello.richiestaArrivata()
        #expect(vm.motivoCambiSpenti == Catalogo.Formazione.stoAncoraRicalcolando, "la frase sopra le righe spente")
        let fatto = await vm.scegliSostituto(Self.sostituto)
        #expect(!fatto)
        #expect(vm.elencoSostituti == nil)
        #expect(vm.messaggio == Catalogo.Formazione.stoAncoraRicalcolando, "il cambio non è partito: lo si dice sotto il campo")
        #expect(SalvataggioAutomaticoTests.salvataggi(srv) == 0)
        await cancello.apri()
        await rilettura.value
        #expect(vm.motivoCambiSpenti == nil, "riletti i dati, i cambi si fanno di nuovo")
    }

    @Test("La formazione si chiude con l'elenco aperto: righe spente con la frase della formazione chiusa, e il tocco lo dice")
    func formazioneChiusa() async throws {
        let chiusa = Scatola<Bool>()
        let (vm, srv) = try await Self.caricata(chiusa: chiusa)
        await vm.mettiInCampo(Self.panchinaro)
        try #require(vm.elencoEntra?.stato.righe?.map(\.esce.id) == [Self.esce])
        chiusa.valore = true
        await vm.carica()                                   // la rilettura allo scadere: la giornata è iniziata
        try #require(vm.chiusa)
        // la frase della web e del 409 del server (`err.formazione_chiusa`), non `formazione.chiusa`
        #expect(vm.motivoCambiSpenti == Catalogo.Err.formazioneChiusa)
        #expect(Catalogo.Err.formazioneChiusa == "La giornata è già iniziata: la formazione non si può più cambiare.")
        #expect(vm.elencoEntra != nil, "gli 11 in campo sono gli stessi: l'elenco resta, con le righe spente")
        let fatto = await vm.scegliChiEsce(Self.esce)
        #expect(!fatto && vm.elencoEntra == nil)
        #expect(vm.messaggio == Catalogo.Err.formazioneChiusa)
        #expect(SalvataggioAutomaticoTests.salvataggi(srv) == 0)
    }

    // MARK: gli 11 cambiati con l'elenco aperto (come `chiudiSostituzione` della web)

    @Test("Dopo una rilettura con altri 11 in campo l'elenco di «Sostituisci» si chiude: i suoi numeri erano di un'altra formazione")
    func sostituisciChiusoSeCambiano() async throws {
        let scelta = Scatola<String>()
        let (vm, srv) = try await Self.caricata(scelta: scelta)
        await vm.sostituisci(Self.titolare)
        try #require(vm.elencoSostituti?.stato.righe != nil)
        await vm.carica()
        #expect(vm.elencoSostituti != nil, "riletti gli stessi 11, l'elenco resta aperto")
        scelta.valore = SalvataggioAutomaticoTests.json(Self.titolari532)   // salvata intanto da un altro dispositivo
        await vm.carica()
        try #require(vm.manuale == Self.titolari532, "in campo ora c'è il 5-3-2")
        #expect(vm.elencoSostituti == nil)
        #expect(SalvataggioAutomaticoTests.salvataggi(srv) == 0)
    }

    @Test("Dopo una rilettura con altri 11 in campo l'elenco di «Metti in campo» si chiude")
    func mettiInCampoChiusoSeCambiano() async throws {
        let scelta = Scatola<String>()
        let (vm, _) = try await Self.caricata(scelta: scelta)
        await vm.mettiInCampo(Self.panchinaro)
        try #require(vm.elencoEntra?.stato.righe != nil)
        scelta.valore = SalvataggioAutomaticoTests.json(Self.titolari532)
        await vm.carica()
        try #require(vm.manuale == Self.titolari532)
        #expect(vm.elencoEntra == nil)
    }

    // MARK: giocatori fermi

    @Test("Chi entra gioca ora una partita già cominciata: il tocco dice la frase della web sui giocatori fermi")
    func entraUnFermo() async throws {
        let fermo = Scatola<Bool>()
        let (vm, srv) = try await Self.caricata(fermo: fermo)
        await vm.sostituisci(Self.titolare)
        try #require(vm.elencoSostituti?.stato.righe?.map(\.entra.id) == [Self.sostituto])
        fermo.valore = true                                 // riletta, la Formazione mette chi entra fra i `bloccati`
        await vm.carica()
        try #require(vm.fermi.contains(Self.sostituto))
        let fatto = await vm.scegliSostituto(Self.sostituto)
        #expect(!fatto)
        #expect(vm.messaggio == Catalogo.Formazione.bloccati)
        #expect(SalvataggioAutomaticoTests.salvataggi(srv) == 0)
    }

    // MARK: aiuti

    /// La Formazione della fixture, già letta, con la scelta salvata in `scelta` (vuota = nessuna). Con `blocca` vero la lettura
    /// della Formazione aspetta `cancello`; con `chiusa` vero la giornata è iniziata; con `fermo` vero il sostituto gioca un
    /// anticipo già cominciato.
    private static func caricata(cancello: Cancello? = nil, blocca: Scatola<Bool> = Scatola(), chiusa: Scatola<Bool> = Scatola(),
                                 fermo: Scatola<Bool> = Scatola(),
                                 scelta: Scatola<String> = Scatola()) async throws -> (FormazioneViewModel, ServerDiProva) {
        let json = try JSONSerialization.jsonObject(with: try Fixture.dati("formazione"))
        var formazione = try #require(json as? [String: Any])
        let aperta = try JSONSerialization.data(withJSONObject: formazione)
        formazione["bloccati"] = [Self.sostituto]
        let conFermo = try JSONSerialization.data(withJSONObject: formazione)
        formazione["bloccati"] = nil
        formazione["iniziata"] = true
        let iniziata = try JSONSerialization.data(withJSONObject: formazione)
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/formazione/sostituisci") {
                return Data(#"{"giornata": 9, "esce": 6523, "entrate": [{"entra": 6994, "differenza": -0.1}]}"#.utf8)
            }
            if percorso.hasPrefix("/api/formazione/metti-in-campo") {
                return Data(#"{"giornata": 9, "entra": 5307, "uscite": [{"esce": 2404, "modulo": "4-3-3", "cambia_modulo": false, "differenza": 0.4}]}"#.utf8)
            }
            if percorso.hasPrefix("/api/formazione/valuta") {
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") { return Data((scelta.valore ?? "null").utf8) }
            if blocca.valore == true, let cancello { await cancello.passa() }
            if chiusa.valore == true { return iniziata }
            return fermo.valore == true ? conFermo : aperta
        }
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        return (vm, srv)
    }
}
