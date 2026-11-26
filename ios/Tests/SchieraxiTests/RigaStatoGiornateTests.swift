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
