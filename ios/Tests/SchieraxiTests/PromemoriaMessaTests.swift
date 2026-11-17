import Foundation
import Testing
@testable import Schieraxi

/// I promemoria del telefono seguono la riga sotto «Avvisi su questo dispositivo» (`imp.avvisi_qui_aiuto`: «un promemoria prima
/// della scadenza, se non hai spuntato "L'ho messa"»), come il server (`promemoria` di `fanta/notifiche.py`): con la spunta della
/// giornata i promemoria di un'ora e di un quarto d'ora non partono; togliendola, o cambiando gli 11 (che la tolgono), tornano.
/// La decisione è del server (`serve_promemoria` di Oggi, `PromemoriaDalServerTests`): il telefono ricorda solo la spunta appena
/// toccata, finché non arriva una lettura di Oggi partita dopo il tocco.
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

    @Test("Quando il promemoria tace (spunta della giornata) non ne parte nessuno; altrimenti sì")
    func spuntaFermaIPromemoria() {
        let adesso = Date(timeIntervalSince1970: 1_793_500_000)
        let inizio = adesso.addingTimeInterval(5 * 3600)
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [60, 15], tace: false, adesso: adesso)
            .map(\.minuti) == [60, 15])
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [60, 15], tace: true, adesso: adesso).isEmpty)
    }

    @Test("Il tocco si ricorda per la sua giornata, e una lettura di Oggi partita dopo lo dimentica")
    func archivio() throws {
        let m = try memoria()
        let tocco = Date(timeIntervalSince1970: 1_793_500_000)
        #expect(ArchivioMessa.toccata(giornata: 9, m) == nil)
        ArchivioMessa.ricorda(giornata: 9, messa: true, m, il: tocco)
        #expect(ArchivioMessa.toccata(giornata: 9, m) == true)
        #expect(ArchivioMessa.toccata(giornata: 10, m) == nil, "un'altra giornata: decide il server")
        #expect(ArchivioMessa.toccata(giornata: nil, m) == nil)
        ArchivioMessa.ricorda(giornata: 9, messa: false, m, il: tocco)
        #expect(ArchivioMessa.toccata(giornata: 9, m) == false, "spunta tolta: si ricorda anche questo")
        ArchivioMessa.dimentica(primaDi: tocco.addingTimeInterval(-1), m)
        #expect(ArchivioMessa.toccata(giornata: 9, m) == false, "una lettura partita prima del tocco non lo cancella")
        ArchivioMessa.dimentica(primaDi: tocco.addingTimeInterval(1), m)
        #expect(ArchivioMessa.toccata(giornata: 9, m) == nil)
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
        #expect(ArchivioMessa.toccata(giornata: f.giornata, m) == true)
        #expect(contatore.volte == prima + 1, "spuntata: i promemoria si tolgono")
        await vm.segnaMessa(false)
        #expect(ArchivioMessa.toccata(giornata: f.giornata, m) == false)
        #expect(contatore.volte == prima + 2, "tolta la spunta: i promemoria tornano")
        await vm.segnaMessa(true)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(!vm.messa)
        #expect(ArchivioMessa.toccata(giornata: f.giornata, m) == false, "gli 11 cambiati tolgono la spunta: i promemoria tornano")
        #expect(contatore.volte == prima + 4)
    }

    @Test("Leggere la scelta salvata non tocca la spunta del telefono né i promemoria: per quelli vale il server")
    func letturaNonTocca() async throws {
        let m = try memoria()
        let salvata = Scatola<String>()
        let srv = try SalvataggioAutomaticoTests.server(salvata: salvata)
        let primo = FormazioneViewModel(server: srv, memoria: m, promemoria: {})
        await primo.carica()
        let f = try #require(primo.formazione)
        let ids = primo.vista(f).titolari.map(\.id).map(String.init).joined(separator: ",")
        salvata.valore = "{\"titolari\": [\(ids)], \"salvata\": \"2026-11-02T21:40:00\", \"messa\": true}"
        let contatore = Contatore()
        let vm = FormazioneViewModel(server: srv, memoria: m, promemoria: { contatore.volte += 1 })
        await vm.carica()
        #expect(vm.messa, "la spunta letta dal server si vede")
        #expect(ArchivioMessa.toccata(giornata: f.giornata, m) == nil)
        #expect(contatore.volte == 0)
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
