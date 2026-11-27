import Foundation
import Testing
@testable import Schieraxi

/// La riga sotto il titolo di Giornate (#863), come la riga di stato della web (`rigaStato` e `caricaInfo` di `app.js`):
/// «Giornata 13 · 13ª di Serie A · Real Esempio · dati del 26 ott 23:55», con i dati di `GET /api/stato` e i testi del catalogo
/// (`testata.*`). Se `/api/stato` non risponde, «Server non raggiungibile». Dati inventati.
@MainActor
@Suite("Giornate: la riga sotto il titolo come la web (#863)")
struct RigaStatoGiornateTests {
    private func info(_ json: String) throws -> InfoServer {
        try Decodifica.decodifica(Data(json.utf8))
    }

    @Test("Giornata della lega e di Serie A, la mia squadra e la data dei dati, separati da « · »")
    func rigaIntera() throws {
        let i = try info(#"""
            {"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest",
             "ultimo_aggiornamento": "2026-10-26T23:55:13"}
            """#)
        let riga = try #require(RigaStato(info: i, nonRaggiungibile: false))
        #expect(riga.pezzi == ["Giornata 8 · 11ª di Serie A", "Nuvola Ovest", "dati del 26 ott 23:55"])
        #expect(riga.testo == "Giornata 8 · 11ª di Serie A · Nuvola Ovest · dati del 26 ott 23:55")
        #expect(riga.voce == "Giornata 8, 11ª di Serie A, Nuvola Ovest, dati del 26 ott 23:55")
        #expect(riga.squadra == "Nuvola Ovest", "lo stemma davanti è quello della mia squadra")
    }

    @Test("La data dei dati è la frase del catalogo senza « · » davanti, come la web")
    func dataDalCatalogo() throws {
        let riga = try #require(RigaStato(info: try info(#"{"ultimo_aggiornamento": "2026-03-01 08:05"}"#), nonRaggiungibile: false))
        #expect(" · " + riga.testo == Catalogo.Testata.datiDel(data: "1 mar", ora: "08:05"))
    }

    @Test("Un server senza la giornata della lega: «11ª giornata di Serie A», come `nomeGiornata` della web")
    func senzaGiornataDellaLega() throws {
        let i = try info(#"{"prossima_giornata": 11, "mia_squadra": "Nuvola Ovest", "ultimo_aggiornamento": "2026-10-26T23:55:13"}"#)
        let riga = try #require(RigaStato(info: i, nonRaggiungibile: false))
        #expect(riga.testo == "11ª giornata di Serie A · Nuvola Ovest · dati del 26 ott 23:55")
    }

    @Test("Dati mai aggiornati o con una data che non si capisce: «dati mai aggiornati»", arguments: [
        #"{"prossima_giornata": 11, "prossima_giornata_lega": 8}"#,
        #"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "ultimo_aggiornamento": null}"#,
        #"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "ultimo_aggiornamento": "boh"}"#,
    ])
    func maiAggiornati(json: String) throws {
        let riga = try #require(RigaStato(info: try info(json), nonRaggiungibile: false))
        #expect(riga.testo == "Giornata 8 · 11ª di Serie A · dati mai aggiornati")
        #expect(riga.pezzi.last.map { " · " + $0 } == Catalogo.Testata.mai)
    }

    @Test("Senza la mia squadra, o con il nome vuoto, il pezzo non c'è e nemmeno lo stemma", arguments: [
        #"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "ultimo_aggiornamento": "2026-10-26T23:55:13"}"#,
        #"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "", "ultimo_aggiornamento": "2026-10-26T23:55:13"}"#,
    ])
    func senzaSquadra(json: String) throws {
        let riga = try #require(RigaStato(info: try info(json), nonRaggiungibile: false))
        #expect(riga.testo == "Giornata 8 · 11ª di Serie A · dati del 26 ott 23:55")
        #expect(riga.squadra == nil)
    }

    @Test("Senza la prossima giornata (o con 0) la riga comincia dalla squadra", arguments: [
        #"{"prossima_giornata": null, "mia_squadra": "Nuvola Ovest", "ultimo_aggiornamento": "2026-10-26T23:55:13"}"#,
        #"{"prossima_giornata": 0, "mia_squadra": "Nuvola Ovest", "ultimo_aggiornamento": "2026-10-26T23:55:13"}"#,
    ])
    func senzaGiornata(json: String) throws {
        let riga = try #require(RigaStato(info: try info(json), nonRaggiungibile: false))
        #expect(riga.testo == "Nuvola Ovest · dati del 26 ott 23:55")
    }

    @Test("Server che non risponde e nessuna risposta di prima: solo «Server non raggiungibile», senza stemma")
    func nonRaggiungibile() throws {
        let riga = try #require(RigaStato(info: nil, nonRaggiungibile: true))
        #expect(riga.pezzi == [Catalogo.Testata.offline])
        #expect(riga.voce == Catalogo.Testata.offline)
        #expect(riga.squadra == nil)
    }

    @Test("Server che non risponde con la risposta di prima (o la copia salvata): «Server non raggiungibile» e poi giornata, squadra e ora, come la web (collaudo del 26/11)")
    func nonRaggiungibileConLaCopia() throws {
        let i = try info(#"""
            {"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest",
             "ultimo_aggiornamento": "2026-10-26T23:55:13"}
            """#)
        let riga = try #require(RigaStato(info: i, nonRaggiungibile: true))
        #expect(riga.pezzi == [Catalogo.Testata.offline, "Giornata 8 · 11ª di Serie A", "Nuvola Ovest", "dati del 26 ott 23:55"])
        #expect(riga.voce == "\(Catalogo.Testata.offline), Giornata 8, 11ª di Serie A, Nuvola Ovest, dati del 26 ott 23:55")
        #expect(riga.squadra == nil, "senza server niente stemma, come la web dopo una ricarica")
    }

    @Test("Con la striscia con «Riprova» o l'errore al posto delle giornate la riga non ripete «Server non raggiungibile», come la web (#864, #980)")
    func guastoGiaDettoDallaPagina() throws {
        let i = try info(#"""
            {"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest",
             "ultimo_aggiornamento": "2026-10-26T23:55:13"}
            """#)
        let riga = try #require(RigaStato(info: i, nonRaggiungibile: true, guastoInPagina: true))
        #expect(riga.pezzi == ["Giornata 8 · 11ª di Serie A", "Nuvola Ovest", "dati del 26 ott 23:55"])
        #expect(riga.voce == "Giornata 8, 11ª di Serie A, Nuvola Ovest, dati del 26 ott 23:55")
        #expect(riga.squadra == nil, "senza server niente stemma, come prima")
        #expect(RigaStato(info: nil, nonRaggiungibile: true, guastoInPagina: true) == nil,
                "se restava solo «Server non raggiungibile» la riga non c'è, come la web")
    }

    @Test("Prima della prima risposta di /api/stato non c'è riga")
    func primaDellaRisposta() {
        #expect(RigaStato(info: nil, nonRaggiungibile: false) == nil)
    }

    // MARK: la pagina

    /// Un server con il diario e, se `stato` non è nil, `/api/stato`; senza, `/api/stato` risponde con un errore del server.
    private static func server(stato: String?) -> ServerDiProva {
        ServerDiProva { _, percorso, _ in
            if percorso == "/api/stato" {
                guard let stato else { throw ErroreApi.server("guasto") }
                return Data(stato.utf8)
            }
            if percorso.hasPrefix("/api/diario") { return Data(#"{"giornate": []}"#.utf8) }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    @Test("La pagina Giornate legge /api/stato con le giornate e mostra la riga")
    func paginaConLaRiga() async throws {
        let vm = GiornateViewModel(server: Self.server(stato: #"""
            {"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest",
             "ultimo_aggiornamento": "2026-10-26T23:55:13"}
            """#))
        #expect(vm.rigaStato == nil, "prima di leggere niente riga")
        await vm.carica()
        #expect(vm.rigaStato?.testo == "Giornata 8 · 11ª di Serie A · Nuvola Ovest · dati del 26 ott 23:55")
        #expect(vm.pagina != nil, "le giornate si leggono come prima")
    }

    @Test("Se /api/stato non risponde la pagina dice «Server non raggiungibile», come la web")
    func paginaSenzaStato() async throws {
        let vm = GiornateViewModel(server: Self.server(stato: nil))
        await vm.carica()
        #expect(vm.rigaStato?.pezzi == [Catalogo.Testata.offline])
        #expect(vm.pagina != nil, "le giornate si vedono lo stesso")
        #expect(vm.paginaDaMostrare != nil, "le giornate non aspettano una riga che non arriverà")
    }

    /// Un server che risponde con le giornate e, se `stato` non è nil, con `/api/stato` (senza, un errore del server); da quando
    /// in `giu` c'è true, niente rete.
    private static func server(stato: String?, giu: Scatola<Bool>) -> ServerDiProva {
        ServerDiProva { _, percorso, _ in
            if giu.valore == true { throw ErroreApi.rete("spento") }
            if percorso == "/api/stato" {
                guard let stato else { throw ErroreApi.server("guasto") }
                return Data(stato.utf8)
            }
            if percorso.hasPrefix("/api/diario") { return Data(#"{"giornate": []}"#.utf8) }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    @Test("Senza rete con le giornate già lette: la striscia con «Riprova» lo dice, e la riga sotto il titolo non ripete «Server non raggiungibile» (#980)")
    func copiaSenzaRete() async throws {
        let giu = Scatola<Bool>()
        let vm = GiornateViewModel(server: Self.server(stato: #"""
            {"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest",
             "ultimo_aggiornamento": "2026-10-26T23:55:13"}
            """#, giu: giu))
        await vm.carica()
        giu.valore = true
        await vm.carica()
        try #require(vm.caricatore.datiSalvati != nil && vm.info.errore != nil, "la striscia dei dati salvati, con «Riprova»")
        #expect(vm.rigaStato?.pezzi == ["Giornata 8 · 11ª di Serie A", "Nuvola Ovest", "dati del 26 ott 23:55"])
        #expect(vm.paginaDaMostrare != nil)
    }

    @Test("Senza rete e senza una risposta di /api/stato da mostrare: niente riga sotto il titolo, ma le giornate salvate si vedono (#980)")
    func copiaSenzaReteNeStato() async throws {
        let giu = Scatola<Bool>()
        let vm = GiornateViewModel(server: Self.server(stato: nil, giu: giu))
        await vm.carica()
        giu.valore = true
        await vm.carica()
        try #require(vm.caricatore.datiSalvati != nil && vm.info.dato == nil, "la striscia dei dati salvati, e /api/stato mai arrivato")
        #expect(vm.rigaStato == nil, "restava solo «Server non raggiungibile», che la striscia dice già")
        #expect(vm.paginaDaMostrare != nil, "le giornate non aspettano la riga")
    }

    @Test("Senza rete e senza copie: l'errore al posto delle giornate lo dice già, e la riga sotto il titolo non c'è (#980)")
    func erroreSenzaCopie() async {
        let giu = Scatola<Bool>()
        giu.valore = true
        let vm = GiornateViewModel(server: Self.server(stato: nil, giu: giu))
        await vm.carica()
        #expect(vm.caricatore.dato == nil && vm.caricatore.errore != nil, "l'errore con «Riprova» al posto delle giornate")
        #expect(vm.rigaStato == nil)
    }

    // MARK: la lista non torna in cima (#913)

    /// Un server con le giornate e `/api/stato`; ognuno dei due, se nella sua scatola c'è un cancello, risponde solo quando il test
    /// lo apre (il cancello si può mettere anche dopo, per la lettura seguente).
    private static func serverLento(diario: Scatola<Cancello> = Scatola(), stato: Scatola<Cancello> = Scatola()) -> ServerDiProva {
        let info = #"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest"}"#
        return ServerDiProva { _, percorso, _ in
            if percorso == "/api/stato" {
                await stato.valore?.passa()
                return Data(info.utf8)
            }
            if percorso.hasPrefix("/api/diario") {
                await diario.valore?.passa()
                return Data(#"{"giornate": []}"#.utf8)
            }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    /// Una scatola con dentro il cancello `c`.
    private static func con(_ c: Cancello) -> Scatola<Cancello> {
        let s = Scatola<Cancello>()
        s.valore = c
        return s
    }

    /// Aspetta (al massimo 5 secondi) che una condizione diventi vera.
    private func aspetta(_ condizione: () -> Bool) async {
        var tentativi = 0
        while !condizione() && tentativi < 250 {
            try? await Task.sleep(for: .milliseconds(20))
            tentativi += 1
        }
    }

    @Test("Le giornate e la riga sotto il titolo si chiedono insieme: /api/stato non aspetta la risposta delle giornate (#913)")
    func letteInsieme() async {
        let diario = Cancello()
        let server = Self.serverLento(diario: Self.con(diario))
        let vm = GiornateViewModel(server: server)
        let lettura = Task { await vm.carica() }
        await diario.richiestaArrivata()
        await aspetta { server.quante("/api/stato") == 1 }
        #expect(server.quante("/api/stato") == 1, "/api/stato si chiede mentre le giornate sono ancora in arrivo")
        #expect(vm.pagina == nil, "le giornate non sono ancora arrivate")
        await diario.apri()
        await lettura.value
        #expect(vm.rigaStato != nil && vm.paginaDaMostrare != nil)
    }

    @Test("Arrivate le giornate prima della riga, la pagina le mostra solo insieme alla riga: la riga non compare sopra una lista già in vista e non la riporta in cima (#913)")
    func giornateInsiemeAllaRiga() async {
        let stato = Cancello()
        let vm = GiornateViewModel(server: Self.serverLento(stato: Self.con(stato)))
        let lettura = Task { await vm.carica() }
        await aspetta { vm.pagina != nil }
        #expect(vm.pagina != nil, "le giornate sono arrivate")
        #expect(vm.rigaStato == nil, "la riga no: /api/stato non ha ancora risposto")
        #expect(vm.paginaDaMostrare == nil, "le giornate aspettano la riga sotto il titolo")
        await stato.apri()
        await lettura.value
        #expect(vm.rigaStato?.testo == "Giornata 8 · 11ª di Serie A · Nuvola Ovest · dati mai aggiornati")
        #expect(vm.paginaDaMostrare != nil, "arrivata la riga, si vedono anche le giornate")
    }

    @Test("Riaprendo la pagina con le giornate e la riga già in memoria, le giornate restano a video mentre si rileggono")
    func riaperturaSenzaAttesa() async {
        let porta = Scatola<Cancello>()
        let vm = GiornateViewModel(server: Self.serverLento(stato: porta))
        await vm.carica()
        let stato = Cancello()
        porta.valore = stato                         // la seconda lettura di /api/stato resta ferma
        let lettura = Task { await vm.carica() }
        await stato.richiestaArrivata()
        await aspetta { vm.caricatore.risposte == 2 }
        #expect(vm.caricatore.risposte == 2, "le giornate sono state rilette")
        #expect(vm.info.inCorso, "/api/stato è ancora in arrivo")
        #expect(vm.paginaDaMostrare != nil, "niente scheletro al posto delle giornate già lette")
        await stato.apri()
        await lettura.value
        #expect(vm.paginaDaMostrare != nil)
    }

    @Test("Letto una volta, se poi /api/stato non risponde la riga tiene giornata, squadra e ora dopo «Server non raggiungibile»")
    func paginaConLoStatoDiPrima() async throws {
        let rotto = Rotto()
        let srv = ServerDiProva { _, percorso, _ in
            if percorso == "/api/stato" {
                if await rotto.si { throw ErroreApi.server("guasto") }
                return Data(#"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "mia_squadra": "Nuvola Ovest", "ultimo_aggiornamento": "2026-10-26T23:55:13"}"#.utf8)
            }
            if percorso.hasPrefix("/api/diario") { return Data(#"{"giornate": []}"#.utf8) }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
        let vm = GiornateViewModel(server: srv)
        await vm.carica()
        await rotto.rompi()
        await vm.carica()
        #expect(vm.rigaStato?.testo == "\(Catalogo.Testata.offline) · Giornata 8 · 11ª di Serie A · Nuvola Ovest · dati del 26 ott 23:55")
    }

    /// Il server che da un certo momento non risponde più a /api/stato.
    private actor Rotto {
        private(set) var si = false
        func rompi() { si = true }
    }
}
