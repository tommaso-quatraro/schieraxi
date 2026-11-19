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

    /// Le letture della giornata passate a promemoria e widget (l'ora in cui sono partite) e quelle non riuscite.
    @MainActor
    final class Letture {
        var fresche: [Date] = []
        var nonRiuscite = 0
    }

    /// Il server dei salvataggi (`SalvataggioAutomaticoTests.server`) con in più la giornata della fixture; `giornataGiu`: `/api/oggi`
    /// non risponde.
    static func conGiornata(giornataGiu: Bool = false) throws -> ServerDiProva {
        let base = try SalvataggioAutomaticoTests.server()
        let datiGiornata = try Fixture.dati("oggi")
        return ServerDiProva { metodo, percorso, corpo in
            if percorso.hasPrefix("/api/oggi") {
                if giornataGiu { throw ErroreApi.rete("spento") }
                return datiGiornata
            }
            return try await base.richiesta(metodo, percorso, corpo: corpo)
        }
    }

    /// La giornata come nell'app, ma quello che andrebbe a promemoria e widget finisce in `letture`.
    private func giornata(_ srv: ServerDiProva, _ letture: Letture) -> OggiViewModel {
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        oggi.dopoLetturaFresca = { _, chiestaIl in letture.fresche.append(chiestaIl) }
        oggi.dopoLetturaNonRiuscita = { letture.nonRiuscite += 1 }
        return oggi
    }

    @Test("Dopo ogni salvataggio e «Torna alla consigliata» la giornata si rilegge, anche se la spunta non cambia: decide il server")
    func salvataggioRileggeLaGiornata() async throws {
        let m = try memoria()
        let srv = try Self.conGiornata()
        let letture = Letture()
        let vm = FormazioneViewModel(server: srv, oggi: giornata(srv, letture), memoria: m, promemoria: {})
        await vm.carica()
        let f = try #require(vm.formazione)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(letture.fresche.count == 1, "la spunta non c'era e non c'è: la giornata si rilegge lo stesso")
        await vm.segnaMessa(true)
        #expect(letture.fresche.count == 2)
        let tocco = try #require(m.dictionary(forKey: ArchivioMessa.chiave)?["il"] as? Double)
        let lettura = try #require(letture.fresche.last)
        #expect(lettura.timeIntervalSince1970 >= tocco, "la lettura parte dopo il tocco: da lì decide il server")
        await vm.tornaAllaConsigliata()
        #expect(letture.fresche.count == 3)
        #expect(srv.quante("GET /api/oggi") == 3)
        #expect(letture.nonRiuscite == 0)
    }

    @Test("Se dopo il salvataggio la giornata non si rilegge, i promemoria tornano in programma con la copia salvata e partono")
    func riletturaNonRiuscita() async throws {
        let srv = try Self.conGiornata(giornataGiu: true)
        let letture = Letture()
        let vm = FormazioneViewModel(server: srv, oggi: giornata(srv, letture), memoria: try memoria(), promemoria: {})
        await vm.carica()
        let f = try #require(vm.formazione)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(letture.fresche.isEmpty)
        #expect(letture.nonRiuscite == 1)
    }

    /// Le decisioni sui promemoria prese con le letture di Oggi arrivate a promemoria e widget (vero = tacciono), nell'ordine.
    @MainActor
    final class Esiti {
        var tace: [Bool] = []
        var nonRiuscite = 0
    }

    /// La giornata della fixture con `serve_promemoria` = `serve`.
    static func giornataCon(serve: Bool) throws -> Data {
        guard var o = try JSONSerialization.jsonObject(with: Fixture.dati("oggi")) as? [String: Any] else {
            throw ErroreApi.server("fixture della giornata")
        }
        o["serve_promemoria"] = serve
        return try JSONSerialization.data(withJSONObject: o)
    }

    /// Un server che risponde a `/api/oggi` con `risposte`, nell'ordine; la richiesta numero i aspetta `cancelli[i]`, se c'è.
    static func giornate(_ risposte: [Data], cancelli: [Cancello?]) -> ServerDiProva {
        let arrivate = Scatola<Int>()
        return ServerDiProva { _, percorso, _ in
            guard percorso.hasPrefix("/api/oggi") else { throw ErroreApi.server("solo la giornata") }
            let i = arrivate.valore ?? 0
            arrivate.valore = i + 1
            if i < cancelli.count, let cancello = cancelli[i] { await cancello.passa() }
            return risposte[min(i, risposte.count - 1)]
        }
    }

    /// La giornata come nell'app, ma ogni lettura arrivata a promemoria e widget decide con la regola vera (`promemoriaTace`) e la
    /// decisione finisce in `esiti`.
    private func giornata(_ srv: ServerDiProva, _ esiti: Esiti, _ m: UserDefaults) -> OggiViewModel {
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        oggi.dopoLetturaFresca = { giornata, chiestaIl in
            esiti.tace.append(Aggiornamento.promemoriaTace(giornata, lettura: .fresca(chiestaIl: chiestaIl), memoria: m))
        }
        oggi.dopoLetturaNonRiuscita = { esiti.nonRiuscite += 1 }
        return oggi
    }

    @Test("Due letture di Oggi insieme: quella partita prima e arrivata dopo non decide i promemoria")
    func letturaVecchiaArrivataDopo() async throws {
        let m = try memoria()
        let cancello = Cancello()
        let srv = try Self.giornate([Self.giornataCon(serve: false), Self.giornataCon(serve: true)], cancelli: [cancello])
        let esiti = Esiti()
        let oggi = giornata(srv, esiti, m)
        let a = Task { await oggi.carica() }                    // A: apro la Formazione con la spunta messa (vedrà «non serve»)
        await cancello.richiestaArrivata()
        ArchivioMessa.ricorda(giornata: 9, messa: false, m)     // cambio un titolare dal telefono: la spunta cade
        await oggi.rileggiDopoUnSalvataggio()                   // B: parte dopo il salvataggio e torna prima di A
        #expect(esiti.tace == [false], "B dice che il promemoria serve")
        await cancello.apri()
        await a.value
        #expect(esiti.tace == [false], "A, partita prima e arrivata dopo, non toglie i promemoria")
        #expect(esiti.nonRiuscite == 0, "una lettura superata non è una lettura non riuscita")
    }

    @Test("Due letture di Oggi insieme: quella partita prima, se arriva mentre l'altra è in viaggio, non cancella il tocco")
    func letturaVecchiaArrivataPrima() async throws {
        let m = try memoria()
        let cancelloA = Cancello()
        let cancelloB = Cancello()
        let srv = try Self.giornate([Self.giornataCon(serve: false), Self.giornataCon(serve: true)], cancelli: [cancelloA, cancelloB])
        let esiti = Esiti()
        let oggi = giornata(srv, esiti, m)
        let a = Task { await oggi.carica() }
        await cancelloA.richiestaArrivata()
        ArchivioMessa.ricorda(giornata: 9, messa: false, m)
        let b = Task { await oggi.rileggiDopoUnSalvataggio() }
        await cancelloB.richiestaArrivata()
        await cancelloA.apri()
        await a.value
        #expect(esiti.tace.isEmpty, "A è superata da B: non decide niente")
        #expect(ArchivioMessa.toccata(giornata: 9, m) == false, "il tocco resta finché non arriva B")
        await cancelloB.apri()
        await b.value
        #expect(esiti.tace == [false])
        #expect(ArchivioMessa.toccata(giornata: 9, m) == nil, "B, partita dopo il tocco, lo comprende")
        #expect(esiti.nonRiuscite == 0)
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
