import Foundation
import Testing
@testable import Schieraxi

/// I promemoria del telefono seguono la riga sotto «Avvisi su questo dispositivo» (`imp.avvisi_qui_aiuto`: «un promemoria prima
/// della scadenza, se non hai spuntato "L'ho messa"»), come il server (`promemoria` di `fanta/notifiche.py`): con la spunta della
/// giornata i promemoria di un'ora e di un quarto d'ora non partono; togliendola, o cambiando gli 11 (che la tolgono), tornano.
@MainActor
@Suite("Promemoria del telefono e «L'ho messa»")
struct PromemoriaMessaTests {
    private func memoria() throws -> UserDefaults {
        try #require(UserDefaults(suiteName: "prova-messa-\(UUID().uuidString)"))
    }

    /// Conta le richieste di rimettere in programma i promemoria.
    @MainActor
    final class Contatore {
        var volte = 0
    }

    @Test("Con la spunta della giornata i promemoria non partono; senza sì")
    func spuntaFermaIPromemoria() {
        let adesso = Date(timeIntervalSince1970: 1_793_500_000)
        let inizio = adesso.addingTimeInterval(5 * 3600)
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [60, 15], messa: false, adesso: adesso)
            .map(\.minuti) == [60, 15])
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [60, 15], messa: true, adesso: adesso).isEmpty)
    }

    @Test("La spunta si ricorda per la sua giornata, e solo per quella")
    func archivio() throws {
        let m = try memoria()
        #expect(!ArchivioMessa.messa(giornata: 9, m))
        ArchivioMessa.salva(giornata: 9, messa: true, m)
        #expect(ArchivioMessa.messa(giornata: 9, m))
        #expect(!ArchivioMessa.messa(giornata: 10, m), "un'altra giornata: i promemoria partono")
        #expect(!ArchivioMessa.messa(giornata: nil, m))
        ArchivioMessa.salva(giornata: 9, messa: false, m)
        #expect(!ArchivioMessa.messa(giornata: 9, m))
    }

    @Test("Spuntare, togliere la spunta o cambiare gli 11 la ricorda e rimette in programma i promemoria")
    func dallaFormazione() async throws {
        let m = try memoria()
        let contatore = Contatore()
        let srv = try SalvataggioAutomaticoTests.server()
        let vm = FormazioneViewModel(server: srv, memoria: m, promemoria: { contatore.volte += 1 })
        await vm.carica()
        let f = try #require(vm.formazione)
        let prima = contatore.volte
        await vm.segnaMessa(true)
        #expect(ArchivioMessa.messa(giornata: f.giornata, m))
        #expect(contatore.volte == prima + 1, "spuntata: i promemoria si tolgono")
        await vm.segnaMessa(false)
        #expect(!ArchivioMessa.messa(giornata: f.giornata, m))
        #expect(contatore.volte == prima + 2, "tolta la spunta: i promemoria tornano")
        await vm.segnaMessa(true)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(!vm.messa)
        #expect(!ArchivioMessa.messa(giornata: f.giornata, m), "gli 11 cambiati tolgono la spunta: i promemoria tornano")
        #expect(contatore.volte == prima + 4)
    }

    @Test("«C'è una versione nuova» si segna come avvisata solo se l'avviso è partito davvero")
    func versioneNuova() async throws {
        let m = try memoria()
        let esito = NuovaVersione.Esito(build: 300, nome: "build-300")
        var mandati = 0
        await NuovaVersione.avvisaSeServe(esito, memoria: m) { _ in mandati += 1; return false }   // avvisi spenti: non parte
        await NuovaVersione.avvisaSeServe(esito, memoria: m) { _ in mandati += 1; return true }    // riaccesi: parte
        await NuovaVersione.avvisaSeServe(esito, memoria: m) { _ in mandati += 1; return true }    // già avvisata: niente
        #expect(mandati == 2)
    }
}
