import Foundation
import Testing
@testable import Schieraxi

/// Impostazioni > Avvisi come la web (#673 passo 3, #693): un interruttore solo, «Avvisi su questo dispositivo», che accende o spegne
/// il permesso di iOS e i promemoria locali dell'app (le scelte per singolo avviso non si usano più), e «Ore tranquille», che manda
/// al server il solo `silenzio`. Il telefono vero (permesso, promemoria) è sostituito da una versione che annota le chiamate.
@MainActor
@Suite("Avvisi su questo dispositivo")
struct AvvisiDispositivoTests {
    /// Il telefono finto: il permesso che darebbe iOS e le chiamate ricevute.
    @MainActor
    final class Telefono {
        var permesso = false
        var concede = true
        var richieste = 0
        var tolti = 0
        var riprogrammati = 0
        var oreRicordate: [OreTranquille] = []

        var avvisi: TelefonoAvvisi {
            TelefonoAvvisi(
                permesso: { self.permesso },
                chiediPermesso: {
                    self.richieste += 1
                    self.permesso = self.concede
                    return self.concede
                },
                ricordaOre: { self.oreRicordate.append($0) },
                togliTutti: { self.tolti += 1 },
                riprogramma: { self.riprogrammati += 1 })
        }
    }

    private func memoria() throws -> UserDefaults {
        try #require(UserDefaults(suiteName: "prova-avvisi-qui-\(UUID().uuidString)"))
    }

    private func server(rotto: Bool = false) -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", rotto { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/avvisi") {
                return Data(#"{"impostazioni":{"cambi":true,"promemoria_60":false,"promemoria_15":false,"riepilogo":true,"silenzio":true,"silenzio_da":22,"silenzio_a":8},"canale":false,"dispositivi":0}"#.utf8)
            }
            return Data("{}".utf8)
        }
    }

    @Test("Senza una scelta salvata gli avvisi di questo dispositivo sono accesi, con i due promemoria")
    func predefinito() throws {
        let m = try memoria()
        #expect(ArchivioAvvisiQui.acceso(m))
        #expect(ArchivioAvvisiQui.minutiAttivi(m) == [60, 15])
        ArchivioAvvisiQui.salva(false, m)
        #expect(!ArchivioAvvisiQui.acceso(m))
        #expect(ArchivioAvvisiQui.minutiAttivi(m).isEmpty, "spento: nessun promemoria locale")

        let adesso = Date(timeIntervalSince1970: 1_793_500_000)
        let inizio = adesso.addingTimeInterval(5 * 3600)
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [60, 15], adesso: adesso).map(\.minuti) == [60, 15])
        #expect(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: ArchivioAvvisiQui.minutiAttivi(m),
                                               adesso: adesso).isEmpty, "spento: il telefono non programma niente")
    }

    @Test("L'interruttore è acceso solo con la scelta accesa e il permesso di iOS")
    func statoIniziale() async throws {
        let telefono = Telefono()
        let m = try memoria()
        let vm = AvvisiDispositivoViewModel(server: server(), telefono: telefono.avvisi, memoria: m)
        await vm.carica()
        #expect(!vm.qui, "senza permesso di iOS è spento")
        telefono.permesso = true
        await vm.carica()
        #expect(vm.qui)
        ArchivioAvvisiQui.salva(false, m)
        await vm.carica()
        #expect(!vm.qui, "spento dall'utente: resta spento anche con il permesso")
    }

    @Test("Acceso: chiede il permesso, ricorda la scelta e rimette in programma i promemoria")
    func accendi() async throws {
        let telefono = Telefono()
        let m = try memoria()
        ArchivioAvvisiQui.salva(false, m)
        let vm = AvvisiDispositivoViewModel(server: server(), telefono: telefono.avvisi, memoria: m)
        await vm.cambiaQui(true)
        #expect(telefono.richieste == 1)
        #expect(vm.qui)
        #expect(ArchivioAvvisiQui.acceso(m))
        #expect(telefono.riprogrammati == 1)
        #expect(vm.messaggio == nil)
    }

    @Test("Permesso negato: l'interruttore torna spento e dice dove abilitarlo")
    func permessoNegato() async throws {
        let telefono = Telefono()
        telefono.concede = false
        let m = try memoria()
        ArchivioAvvisiQui.salva(false, m)
        let vm = AvvisiDispositivoViewModel(server: server(), telefono: telefono.avvisi, memoria: m)
        await vm.cambiaQui(true)
        #expect(!vm.qui)
        #expect(!ArchivioAvvisiQui.acceso(m))
        #expect(telefono.riprogrammati == 0)
        #expect(vm.messaggio == Catalogo.Avv.permessoNegatoAbilita)
    }

    @Test("Spento: toglie subito i promemoria già programmati e non ne programma altri")
    func spegni() async throws {
        let telefono = Telefono()
        telefono.permesso = true
        let m = try memoria()
        let vm = AvvisiDispositivoViewModel(server: server(), telefono: telefono.avvisi, memoria: m)
        await vm.carica()
        await vm.cambiaQui(false)
        #expect(!vm.qui)
        #expect(!ArchivioAvvisiQui.acceso(m))
        #expect(telefono.tolti == 1)
        #expect(ArchivioAvvisiQui.minutiAttivi(m).isEmpty)
        #expect(vm.messaggio == Catalogo.Avv.notificheDisattivateQuesto)
    }

    @Test("Le scelte per singolo avviso del server non spengono i promemoria del telefono")
    func scelteVecchieIgnorate() async throws {
        let telefono = Telefono()
        telefono.permesso = true
        let m = try memoria()
        let vm = AvvisiDispositivoViewModel(server: server(), telefono: telefono.avvisi, memoria: m)
        await vm.carica()   // il server ha promemoria_60 e promemoria_15 spenti
        #expect(vm.qui)
        #expect(ArchivioAvvisiQui.minutiAttivi(m) == [60, 15])
    }

    @Test("Le ore tranquille lette dal server si ricordano sul telefono per i promemoria")
    func oreLette() async throws {
        let telefono = Telefono()
        let vm = AvvisiDispositivoViewModel(server: server(), telefono: telefono.avvisi, memoria: try memoria())
        await vm.carica()
        #expect(vm.oreTranquille == OreTranquille(attive: true, da: 22, a: 8))
        #expect(telefono.oreRicordate.last == OreTranquille(attive: true, da: 22, a: 8))
    }

    @Test("Ore tranquille: si manda solo `silenzio`, poi i promemoria tornano in programma")
    func oreTranquilleSoloSilenzio() async throws {
        let telefono = Telefono()
        let s = server()
        let vm = AvvisiDispositivoViewModel(server: s, telefono: telefono.avvisi, memoria: try memoria())
        await vm.carica()
        await vm.cambiaOreTranquille(false)
        let corpo = String(decoding: try #require(s.corpiInviati(a: "PUT /api/avvisi").last), as: UTF8.self)
        #expect(corpo == #"{"silenzio":false}"#)
        #expect(telefono.riprogrammati == 1)
        #expect(vm.erroreSalvataggio == nil)
    }

    @Test("Ore tranquille non salvate: l'interruttore torna come lo ha il server e lo dice")
    func oreTranquilleNonSalvate() async throws {
        let telefono = Telefono()
        let vm = AvvisiDispositivoViewModel(server: server(rotto: true), telefono: telefono.avvisi, memoria: try memoria())
        await vm.carica()
        await vm.cambiaOreTranquille(false)
        #expect(vm.oreTranquille.attive, "torna acceso, come sul server")
        #expect(vm.erroreSalvataggio != nil)
        #expect(telefono.riprogrammati == 0)
    }

    @Test("Avvisi anche per l'app nativa (Gestione): si manda solo `app_nativa`")
    func appNativa() async throws {
        let s = server()
        let vm = AvvisiDispositivoViewModel(server: s, telefono: Telefono().avvisi, memoria: try memoria())
        await vm.carica()
        await vm.cambiaAppNativa(true)
        let corpo = String(decoding: try #require(s.corpiInviati(a: "PUT /api/avvisi").last), as: UTF8.self)
        #expect(corpo == #"{"app_nativa":true}"#)
    }
}
