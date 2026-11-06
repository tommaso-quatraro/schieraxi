import Foundation
import Testing
@testable import Schieraxi

/// Squadre e rose come la web (issue #441, parte di #167). Le parole sono quelle di `fanta/web/testi.js` (chiavi `lega.*` e
/// `scambio.*`): «maglia» e mai «divisa», «Cambia il nome» e «Crediti residui» nella rosa, «Senza ruolo (da controllare)»,
/// «Rose aggiornate il 6 novembre 2026». Qui si prova il testo; le schermate le fotografa il fotografo su `main`.
@MainActor
@Suite("Squadre e rose come la web: parole, maglia, Cambia il nome e crediti (#441)")
struct SquadreComeLaWebTests {

    private static func pezzo(_ chiave: String, _ valori: [String: String] = [:]) throws -> String {
        try valori.reduce(try TestiWeb().italiano(chiave)) { $0.replacingOccurrences(of: "{\($1.key)}", with: $1.value) }
    }

    // MARK: parole della pagina

    @Test("Titolo della pagina: «Squadre e rose»; senza le rose degli altri «La mia squadra e rosa», come il menu")
    func titolo() throws {
        #expect(ParoleSquadre.titolo(squadreAltrui: true) == (try Self.pezzo("lega.voce_squadre")))
        #expect(ParoleSquadre.titolo(squadreAltrui: false) == (try Self.pezzo("lega.voce_miasquadra")))
    }

    @Test("La carta «La mia squadra» e l'elenco: stesse frasi della web")
    func carta() throws {
        #expect(ParoleSquadre.miaSquadra == (try Self.pezzo("lega.mia_squadra")))
        #expect(ParoleSquadre.stemmaEMaglia == (try Self.pezzo("lega.stemma_maglia")))
        #expect(ParoleSquadre.vediLaRosa == (try Self.pezzo("lega.vedi_rosa")))
        #expect(ParoleSquadre.nonLaTua == (try Self.pezzo("lega.non_tua_squadra")))
        #expect(ParoleSquadre.scegliLaTua == (try Self.pezzo("lega.scegli_quale_delle")))
        #expect(ParoleSquadre.tuaSquadra == (try Self.pezzo("lega.tua_squadra")))
        #expect(ParoleSquadre.toccaUnaSquadra == (try Self.pezzo("lega.tocca_una_squadra")))
        #expect(ParoleSquadre.importaPrima == (try Self.pezzo("lega.importa_prima_rose")))
        #expect(ParoleSquadre.chiudi == (try Self.pezzo("shell.chiudi")))
    }

    @Test("«24 giocatori · 12 crediti», con il singolare e senza i crediti se il server non li dà")
    func riepilogo() throws {
        let giocatori = try Self.pezzo("sd.n_giocatori.other", ["n": "24"])
        let crediti = try Self.pezzo("lega.n_crediti.other", ["n": "12"])
        #expect(ParoleSquadre.riepilogo(giocatori: 24, crediti: 12) == "\(giocatori) · \(crediti)")
        let uno = try Self.pezzo("sd.n_giocatori.one", ["n": "1"])
        let unCredito = try Self.pezzo("lega.n_crediti.one", ["n": "1"])
        #expect(ParoleSquadre.riepilogo(giocatori: 1, crediti: 1) == "\(uno) · \(unCredito)")
        #expect(ParoleSquadre.riepilogo(giocatori: 24, crediti: nil) == giocatori)
        let zeroGiocatori = try Self.pezzo("sd.n_giocatori.other", ["n": "0"])
        let zeroCrediti = try Self.pezzo("lega.n_crediti.other", ["n": "0"])
        #expect(ParoleSquadre.riepilogo(giocatori: nil, crediti: 0) == "\(zeroGiocatori) · \(zeroCrediti)")
    }

    // MARK: maglia, mai divisa

    @Test("Stemma e maglia: i nomi, i messaggi e i pulsanti sono quelli della web")
    func stemmaEMaglia() throws {
        #expect(ParoleSquadre.nome(tipo: "stemma") == (try Self.pezzo("scambio.stemma")))
        #expect(ParoleSquadre.nome(tipo: "maglia") == (try Self.pezzo("scambio.maglia")))
        #expect(ParoleSquadre.aggiornata(tipo: "stemma") == (try Self.pezzo("scambio.stemma_aggiornato")))
        #expect(ParoleSquadre.aggiornata(tipo: "maglia") == (try Self.pezzo("scambio.maglia_aggiornata")))
        #expect(ParoleSquadre.usaCome(tipo: "stemma") == (try Self.pezzo("lega.usa_come_stemma")))
        #expect(ParoleSquadre.usaCome(tipo: "maglia") == (try Self.pezzo("lega.usa_come_maglia")))
        #expect(ParoleSquadre.cambia(tipo: "maglia") == (try Self.pezzo("scambio.cambia_tipo", ["tipo": "maglia"])))
        #expect(ParoleSquadre.carica(tipo: "stemma") == (try Self.pezzo("scambio.carica_tipo", ["tipo": "stemma"])))
    }

    @Test("In nessuna parola della pagina e della rosa c'è «divisa»", arguments: ["stemma", "maglia"])
    func niente_divisa(tipo: String) {
        let testi = [ParoleSquadre.nome(tipo: tipo), ParoleSquadre.aggiornata(tipo: tipo), ParoleSquadre.usaCome(tipo: tipo),
                     ParoleSquadre.cambia(tipo: tipo), ParoleSquadre.carica(tipo: tipo), ParoleSquadre.daUnFile(tipo: tipo),
                     ParoleSquadre.stemmaEMaglia, ParoleSquadre.indirizzoImmagine,
                     ParoleSquadre.aiutoIndirizzo, ParoleSquadre.senzaIndirizzoWeb]
        for testo in testi { #expect(!testo.localizedCaseInsensitiveContains("divisa"), "«\(testo)»") }
        #expect(ParoleSquadre.aiutoIndirizzo.contains("maglia"))
        #expect(ParoleSquadre.senzaIndirizzoWeb.contains("maglia"))
        #expect(ParoleSquadre.indirizzoImmagine.contains("maglia"))
    }

    @Test("«Maglia da un file» al posto di «Divisa da un file»")
    func daUnFile() {
        #expect(ParoleSquadre.daUnFile(tipo: "stemma") == "Stemma da un file")
        #expect(ParoleSquadre.daUnFile(tipo: "maglia") == "Maglia da un file")
    }

    // MARK: la rosa

    @Test("La rosa: Cambia il nome, Crediti residui, Salva e Senza ruolo con le parole della web")
    func rosa() throws {
        #expect(ParoleSquadre.cambiaIlNome == (try Self.pezzo("scambio.cambia_nome")))
        #expect(ParoleSquadre.nuovoNome == (try Self.pezzo("scambio.nuovo_nome")))
        #expect(ParoleSquadre.aiutoNome == (try Self.pezzo("scambio.nome_aiuto")))
        #expect(ParoleSquadre.nomeNonValido == (try Self.pezzo("scambio.nome_non_valido")))
        #expect(ParoleSquadre.nomeSalvato == (try Self.pezzo("scambio.nome_salvato")))
        #expect(ParoleSquadre.creditiResidui == (try Self.pezzo("scambio.crediti_residui")))
        #expect(ParoleSquadre.salva == (try Self.pezzo("scambio.salva")))
        #expect(ParoleSquadre.creditiSalvati == (try Self.pezzo("scambio.crediti_salvati")))
        #expect(ParoleSquadre.scriviCrediti == (try Self.pezzo("scambio.scrivi_crediti_come")))
        #expect(ParoleSquadre.senzaRuolo == (try Self.pezzo("scambio.senza_ruolo")))
    }

    @Test("«Rose aggiornate il 6 novembre 2026»: il mese per intero, ora italiana; senza data «–»")
    func roseAggiornate() throws {
        let modello = try Self.pezzo("scambio.rose_aggiornate")
        func web(_ data: String) -> String { modello.replacingOccurrences(of: "{data}", with: data) }
        #expect(ParoleSquadre.roseAggiornate("2026-11-06T10:12:00") == web("6 novembre 2026"))
        #expect(ParoleSquadre.roseAggiornate("2026-03-01 08:00") == web("1 marzo 2026"))
        #expect(ParoleSquadre.roseAggiornate("2026-12-31") == web("31 dicembre 2026"))
        #expect(ParoleSquadre.roseAggiornate(nil) == web("–"))
        #expect(ParoleSquadre.roseAggiornate("") == web("–"))
        #expect(ParoleSquadre.roseAggiornate("ieri") == web("–"))
    }

    // MARK: Cambia il nome

    /// Un server che risponde come quello vero: la rosa (fixture), e `PUT /api/squadre/nome` con il nome nuovo.
    private static func serverRosa(rispostaNome: @escaping @Sendable () throws -> Data = {
        Data(#"{"nome":"Nuvola Est","prima":"Nuvola Ovest","mia_squadra":"Nuvola Est"}"#.utf8)
    }) -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", percorso == "/api/squadre/nome" { return try rispostaNome() }
            if metodo == "GET", percorso.hasPrefix("/api/rosa") { return try Fixture.dati("rosa") }
            return Data("{}".utf8)
        }
    }

    private static func vm(_ server: ServerDiProva) -> RosaViewModel {
        RosaViewModel(nome: "Nuvola Ovest", server: server, immagini: Immagini(server: server))
    }

    @Test("Rinomina: PUT con il nome di adesso e il nuovo senza spazi in più, poi la rosa si rilegge con il nome nuovo")
    func rinomina() async throws {
        let server = Self.serverRosa()
        let vm = Self.vm(server)
        await vm.carica()
        #expect(vm.nuovoNome == "Nuvola Ovest", "il campo parte dal nome di adesso, come la web")
        vm.nuovoNome = "  Nuvola   Est "
        await vm.rinomina()
        let corpo = try #require(server.corpiInviati(a: "PUT /api/squadre/nome").last)
        let json = try #require(try JSONSerialization.jsonObject(with: corpo) as? [String: String])
        #expect(json == ["nome": "Nuvola Ovest", "nuovo": "Nuvola Est"])
        #expect(vm.nome == "Nuvola Est")
        #expect(vm.messaggio == (try Self.pezzo("scambio.nome_salvato")))
        #expect(server.quante("GET /api/rosa?squadra=" + IndirizzoServer.codifica("Nuvola Est")) == 1, "la rosa si rilegge con il nome nuovo")
    }

    @Test("Nome vuoto o più lungo di 60 caratteri: la frase della web e niente richiesta")
    func nomeNonValido() async throws {
        let server = Self.serverRosa()
        let vm = Self.vm(server)
        await vm.carica()
        for scritto in ["", "   ", String(repeating: "a", count: 61)] {
            vm.messaggio = nil
            vm.nuovoNome = scritto
            await vm.rinomina()
            #expect(vm.messaggio == (try Self.pezzo("scambio.nome_non_valido")), "«\(scritto)»")
        }
        #expect(server.quante("PUT /api/squadre/nome") == 0)
        vm.nuovoNome = String(repeating: "a", count: 60)
        await vm.rinomina()
        #expect(server.quante("PUT /api/squadre/nome") == 1, "60 caratteri vanno bene")
    }

    @Test("Lo stesso nome (anche con spazi in più): niente richiesta")
    func stessoNome() async throws {
        let server = Self.serverRosa()
        let vm = Self.vm(server)
        await vm.carica()
        vm.nuovoNome = " Nuvola  Ovest "
        await vm.rinomina()
        #expect(server.quante("PUT /api/squadre/nome") == 0)
        #expect(vm.nome == "Nuvola Ovest")
    }

    @Test("Il server rifiuta (nome già preso): si vede la sua frase e il nome resta quello di prima")
    func rifiutato() async throws {
        let frase = "C'è già una squadra con questo nome: scegline un altro."
        let server = Self.serverRosa(rispostaNome: { throw ErroreApi.server("C'è già una squadra con questo nome: scegline un altro.") })
        let vm = Self.vm(server)
        await vm.carica()
        vm.nuovoNome = "Borgo Alto"
        await vm.rinomina()
        #expect(vm.messaggio == frase)
        #expect(vm.nome == "Nuvola Ovest")
        #expect(server.quante("GET /api/rosa?squadra=" + IndirizzoServer.codifica("Borgo Alto")) == 0)
    }

    // MARK: crediti residui

    @Test("Crediti: parte dal valore della rosa, «Salva» manda PUT /api/crediti con la squadra e il numero")
    func creditiSalvati() async throws {
        let server = Self.serverRosa()
        let vm = Self.vm(server)
        await vm.carica()
        #expect(vm.crediti == "", "nella fixture i crediti non ci sono: campo vuoto, come la web")
        vm.crediti = "125"
        await vm.salvaCrediti()
        let corpo = try #require(server.corpiInviati(a: "PUT /api/crediti").last)
        let json = try #require(try JSONSerialization.jsonObject(with: corpo) as? [String: [String: Int]])
        #expect(json == ["crediti": ["Nuvola Ovest": 125]])
        #expect(vm.messaggio == (try Self.pezzo("scambio.crediti_salvati")))
    }

    @Test("Crediti scritti male (lettere, negativi, decimali, più di 5 cifre, vuoto): la frase della web e niente richiesta",
          arguments: ["abc", "-3", "2,5", "123456", "", "  "])
    func creditiNonValidi(scritto: String) async throws {
        let server = Self.serverRosa()
        let vm = Self.vm(server)
        await vm.carica()
        vm.crediti = scritto
        await vm.salvaCrediti()
        #expect(vm.messaggio == (try Self.pezzo("scambio.scrivi_crediti_come")))
        #expect(server.quante("PUT /api/crediti") == 0)
    }

    @Test("Zero è un numero buono (la web dice «anche 0»)")
    func creditiZero() async throws {
        let server = Self.serverRosa()
        let vm = Self.vm(server)
        await vm.carica()
        vm.crediti = "0"
        await vm.salvaCrediti()
        #expect(server.quante("PUT /api/crediti") == 1)
    }
}
