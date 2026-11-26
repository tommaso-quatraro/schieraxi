import Foundation
import Testing
@testable import Schieraxi

/// Un caso di `AvvisiDispositivoTests.serverMandaGia`: lo stato degli avvisi sul server e cosa deve ricordare il telefono.
struct CasoCanaleAvvisi: Sendable, CustomTestStringConvertible {
    let dispositivi: Int
    let appNativa: Bool
    let ntfy: Bool
    let atteso: Bool

    var testDescription: String { "dispositivi \(dispositivi), app nativa \(appNativa), ntfy \(ntfy)" }
}

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
        /// Per ogni stato degli avvisi ricordato: il server manda già i suoi avvisi a questo telefono?
        var serverManda: [Bool] = []
        /// Cosa risponde il telefono quando ricorda lo stato del server: è cambiato qualcosa per i promemoria?
        var cambia = false

        var avvisi: TelefonoAvvisi {
            TelefonoAvvisi(
                permesso: { self.permesso },
                chiediPermesso: {
                    self.richieste += 1
                    self.permesso = self.concede
                    return self.concede
                },
                ricorda: { stato in
                    self.oreRicordate.append(stato.impostazioni.oreTranquille)
                    self.serverManda.append(stato.mandaGiaIlServer)
                    return self.cambia
                },
                togliTutti: { self.tolti += 1 },
                riprogramma: { self.riprogrammati += 1 })
        }
    }

    private func memoria() throws -> UserDefaults {
        try #require(UserDefaults(suiteName: "prova-avvisi-qui-\(UUID().uuidString)"))
    }

    /// Come il server (`_stato_avvisi` di `fanta/server.py`): `canale` è vero con il canale ntfy configurato (`ntfy`) o con almeno
    /// un dispositivo con le notifiche della web accese (`dispositivi`); `appNativa` è «Avvisi anche per l'app nativa» e non lo tocca.
    /// `promemoriaDa`: il campo `promemoria_da` (nil = server di prima, che non lo manda).
    private func server(rotto: Bool = false, dispositivi: Int = 0, appNativa: Bool = false, ntfy: Bool = false,
                        promemoriaDa: String? = nil) -> ServerDiProva {
        let da = promemoriaDa.map { #","promemoria_da":"\#($0)""# } ?? ""
        return ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", rotto { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/avvisi") {
                return Data(#"{"impostazioni":{"cambi":true,"promemoria_60":false,"promemoria_15":false,"riepilogo":true,"silenzio":true,"silenzio_da":22,"silenzio_a":8,"app_nativa":\#(appNativa)},"canale":\#(ntfy || dispositivi > 0),"dispositivi":\#(dispositivi)\#(da)}"#.utf8)
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

    @Test("Avvisi anche per l'app nativa (Gestione): si manda solo `app_nativa`, poi i promemoria del telefono tornano in programma")
    func appNativa() async throws {
        let s = server()
        let telefono = Telefono()
        let vm = AvvisiDispositivoViewModel(server: s, telefono: telefono.avvisi, memoria: try memoria())
        await vm.carica()
        await vm.cambiaAppNativa(true)
        let corpo = String(decoding: try #require(s.corpiInviati(a: "PUT /api/avvisi").last), as: UTF8.self)
        #expect(corpo == #"{"app_nativa":true}"#)
        #expect(telefono.riprogrammati == 1, "con ntfy per l'app nativa i promemoria del telefono si tolgono (#906)")
    }

    @Test("Con ntfy per l'app nativa il telefono ricorda che il server manda già gli avvisi; con le notifiche della web no (#906)",
          arguments: [
            CasoCanaleAvvisi(dispositivi: 0, appNativa: true, ntfy: true, atteso: true),
            CasoCanaleAvvisi(dispositivi: 1, appNativa: true, ntfy: false, atteso: false),   // web solo sul computer: `canale` vero per la web
            CasoCanaleAvvisi(dispositivi: 1, appNativa: true, ntfy: true, atteso: false),    // il server manda alla web e a ntfy
            CasoCanaleAvvisi(dispositivi: 1, appNativa: false, ntfy: false, atteso: false),
            CasoCanaleAvvisi(dispositivi: 0, appNativa: true, ntfy: false, atteso: false),   // nessun canale: il server non manda niente
            CasoCanaleAvvisi(dispositivi: 0, appNativa: false, ntfy: false, atteso: false),
          ])
    func serverMandaGia(caso: CasoCanaleAvvisi) async throws {
        let telefono = Telefono()
        let vm = AvvisiDispositivoViewModel(server: server(dispositivi: caso.dispositivi, appNativa: caso.appNativa, ntfy: caso.ntfy),
                                            telefono: telefono.avvisi, memoria: try memoria())
        await vm.carica()
        #expect(telefono.serverManda.last == caso.atteso)
    }

    /// Un solo promemoria per telefono (26/11/2026): con la web app sulla Home che ha gli avvisi accesi il server manda già il
    /// suo promemoria (`promemoria_da` «web»), quindi il telefono non programma il suo e la riga sotto l'interruttore lo dice.
    /// Senza il campo (server di prima) vale la regola di prima: con le sole notifiche della web l'app programma i suoi.
    @Test("Promemoria già dalla web app o da ntfy: il telefono non programma i suoi; la riga d'aiuto lo dice solo per la web app",
          arguments: zip([Optional("web"), "ntfy", "app", nil], [true, true, false, false]))
    func promemoriaDa(da: String?, tace: Bool) async throws {
        let telefono = Telefono()
        let vm = AvvisiDispositivoViewModel(server: server(dispositivi: 1, promemoriaDa: da), telefono: telefono.avvisi,
                                            memoria: try memoria())
        await vm.carica()
        #expect(telefono.serverManda.last == tace)
        #expect(vm.aiutoQui == (da == "web" ? Catalogo.Imp.avvisiQuiAiutoWeb : Catalogo.Imp.avvisiQuiAiutoApp))
    }

    @Test("Aprendo la pagina degli avvisi, se per i promemoria è cambiato qualcosa sul server, i promemoria tornano in programma")
    func caricaRiprogrammaSeCambia() async throws {
        let cambiato = Telefono()
        cambiato.cambia = true
        await AvvisiDispositivoViewModel(server: server(appNativa: true, ntfy: true), telefono: cambiato.avvisi, memoria: try memoria())
            .carica()
        #expect(cambiato.riprogrammati == 1, "niente doppioni fino alla prossima lettura di Oggi")
        let uguale = Telefono()
        await AvvisiDispositivoViewModel(server: server(), telefono: uguale.avvisi, memoria: try memoria()).carica()
        #expect(uguale.riprogrammati == 0)
    }
}
