import Foundation
import Testing
@testable import Schieraxi

/// Squadre e rose come la web (issue #441, parte di #167). Le parole vengono dal catalogo comune (chiavi `lega.*` e `scambio.*`,
/// #496): «maglia» e mai «divisa», «Cambia il nome» e «Crediti residui» nella rosa, «Senza ruolo (da controllare)»,
/// «Rose aggiornate il 6 novembre 2026». Le parole che l'iPhone non prende ancora dal catalogo (`shell.chiudi`, i plurali di
/// `Formato`) si confrontano con `testi.js`. Qui si prova il testo; le schermate le fotografa il fotografo su `main`.
@MainActor
@Suite("Squadre e rose come la web: parole, maglia, Cambia il nome e crediti (#441)")
struct SquadreComeLaWebTests {

    /// Il testo italiano di `testi.js` con i segnaposto riempiti: solo per le chiavi che l'iPhone non prende dal catalogo.
    private static func pezzo(_ chiave: String, _ valori: [String: String] = [:]) throws -> String {
        try valori.reduce(try TestiWeb().italiano(chiave)) { $0.replacingOccurrences(of: "{\($1.key)}", with: $1.value) }
    }

    // MARK: parole della pagina

    @Test("Titolo della pagina: «Squadre e rose»; senza le rose degli altri «La mia squadra e rosa», come il menu")
    func titolo() throws {
        #expect(ParoleSquadre.titolo(squadreAltrui: true) == Catalogo.Lega.voceSquadre)
        #expect(ParoleSquadre.titolo(squadreAltrui: false) == Catalogo.Lega.voceMiasquadra)
    }

    @Test("La carta «La mia squadra» e l'elenco: stesse frasi della web")
    func carta() throws {
        #expect(ParoleSquadre.miaSquadra == Catalogo.Lega.miaSquadra)
        #expect(ParoleSquadre.stemmaEMaglia == Catalogo.Lega.stemmaMaglia)
        #expect(ParoleSquadre.vediLaRosa == Catalogo.Lega.vediRosa)
        #expect(ParoleSquadre.nonLaTua == Catalogo.Lega.nonTuaSquadra)
        #expect(ParoleSquadre.scegliLaTua == Catalogo.Lega.scegliQualeDelle)
        #expect(ParoleSquadre.tuaSquadra == Catalogo.Lega.tuaSquadra)
        #expect(ParoleSquadre.toccaUnaSquadra == Catalogo.Lega.toccaUnaSquadra)
        #expect(ParoleSquadre.importaPrima == Catalogo.Lega.importaPrimaRose)
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
    func stemmaEMaglia() {
        #expect(ParoleSquadre.nome(tipo: "stemma") == Catalogo.Scambio.stemma)
        #expect(ParoleSquadre.nome(tipo: "maglia") == Catalogo.Scambio.maglia)
        #expect(ParoleSquadre.aggiornata(tipo: "stemma") == Catalogo.Scambio.stemmaAggiornato)
        #expect(ParoleSquadre.aggiornata(tipo: "maglia") == Catalogo.Scambio.magliaAggiornata)
        #expect(ParoleSquadre.usaCome(tipo: "stemma") == Catalogo.Lega.usaComeStemma)
        #expect(ParoleSquadre.usaCome(tipo: "maglia") == Catalogo.Lega.usaComeMaglia)
        #expect(ParoleSquadre.cambia(tipo: "maglia") == Catalogo.Scambio.cambiaTipo(tipo: "maglia"))
        #expect(ParoleSquadre.cambia(tipo: "maglia") == "Cambia maglia")
        #expect(ParoleSquadre.carica(tipo: "stemma") == Catalogo.Scambio.caricaTipo(tipo: "stemma"))
        #expect(ParoleSquadre.carica(tipo: "stemma") == "Carica stemma")
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
    func rosa() {
        #expect(ParoleSquadre.cambiaIlNome == Catalogo.Scambio.cambiaNome)
        #expect(ParoleSquadre.nuovoNome == Catalogo.Scambio.nuovoNome)
        #expect(ParoleSquadre.aiutoNome == Catalogo.Scambio.nomeAiuto)
        #expect(ParoleSquadre.nomeNonValido == Catalogo.Scambio.nomeNonValido)
        #expect(ParoleSquadre.nomeSalvato == Catalogo.Scambio.nomeSalvato)
        #expect(ParoleSquadre.creditiResidui == Catalogo.Scambio.creditiResidui)
        #expect(ParoleSquadre.salva == Catalogo.Scambio.salva)
        #expect(ParoleSquadre.creditiSalvati == Catalogo.Scambio.creditiSalvati)
        #expect(ParoleSquadre.scriviCrediti == Catalogo.Scambio.scriviCreditiCome)
        #expect(ParoleSquadre.senzaRuolo == Catalogo.Scambio.senzaRuolo)
    }

    @Test("«Rose aggiornate il 6 novembre 2026»: il mese per intero, ora italiana; senza data «–»")
    func roseAggiornate() {
        func web(_ data: String) -> String { Catalogo.Scambio.roseAggiornate(data: data) }
        #expect(ParoleSquadre.roseAggiornate("2026-11-06T10:12:00") == "Rose aggiornate il 6 novembre 2026")
        #expect(ParoleSquadre.roseAggiornate("2026-11-06T10:12:00") == web("6 novembre 2026"))
        #expect(ParoleSquadre.roseAggiornate("2026-03-01 08:00") == web("1 marzo 2026"))
        #expect(ParoleSquadre.roseAggiornate("2026-12-31") == web("31 dicembre 2026"))
        #expect(ParoleSquadre.roseAggiornate(nil) == web("–"))
        #expect(ParoleSquadre.roseAggiornate("") == web("–"))
        #expect(ParoleSquadre.roseAggiornate("ieri") == web("–"))
    }

    // MARK: Cambia il nome

    /// Un server che risponde come quello vero: la rosa (fixture), e `PUT /api/squadre/nome` con il nome nuovo.
    /// `ritardo` (nanosecondi) fa durare le scritture: serve a provare cosa succede se si preme di nuovo durante il salvataggio.
    private static func serverRosa(ritardo: UInt64 = 0, rispostaNome: @escaping @Sendable () throws -> Data = {
        Data(#"{"nome":"Nuvola Est","prima":"Nuvola Ovest","mia_squadra":"Nuvola Est"}"#.utf8)
    }) -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", ritardo > 0 { try await Task.sleep(nanoseconds: ritardo) }
            if metodo == "PUT", percorso == "/api/squadre/nome" { return try rispostaNome() }
            if metodo == "GET", percorso.hasPrefix("/api/rosa") { return try Fixture.dati("rosa") }
            return Data("{}".utf8)
        }
    }

    /// Ogni prova ha il suo centro delle notifiche: l'avviso «aggiornaTutto» non sveglia le schermate delle altre prove.
    private static func vm(_ server: ServerDiProva, centro: NotificationCenter = NotificationCenter()) -> RosaViewModel {
        RosaViewModel(nome: "Nuvola Ovest", server: server, immagini: Immagini(server: server), centro: centro)
    }

    /// Conta gli avvisi «aggiornaTutto» arrivati su un centro.
    private static func contaAvvisi(su centro: NotificationCenter) -> (conteggio: Scatola<Int>, osservatore: NSObjectProtocol) {
        let conteggio = Scatola<Int>()
        conteggio.valore = 0
        let osservatore = centro.addObserver(forName: .aggiornaTutto, object: nil, queue: nil) { _ in
            conteggio.valore = (conteggio.valore ?? 0) + 1
        }
        return (conteggio, osservatore)
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
        #expect(vm.messaggio == Catalogo.Scambio.nomeSalvato)
        #expect(server.quante("GET /api/rosa?squadra=" + IndirizzoServer.codifica("Nuvola Est")) == 1, "la rosa si rilegge con il nome nuovo")
    }

    @Test("Invio sulla tastiera mentre il salvataggio è in corso: una richiesta sola, niente 412 finto")
    func rinominaDueVolteDiSeguito() async throws {
        let server = Self.serverRosa(ritardo: 300_000_000)
        let vm = Self.vm(server)
        await vm.carica()
        vm.nuovoNome = "Nuvola Est"
        async let primo: Void = vm.rinomina()
        async let secondo: Void = vm.rinomina()
        _ = await (primo, secondo)
        #expect(server.quante("PUT /api/squadre/nome") == 1, "il secondo invio, a salvataggio in corso, non parte")
        #expect(vm.messaggio == Catalogo.Scambio.nomeSalvato)
        #expect(!vm.inCorso)
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
            #expect(vm.messaggio == Catalogo.Scambio.nomeNonValido, "«\(scritto)»")
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

    @Test("Dopo «Cambia il nome» tutta l'app si ricarica (aggiornaTutto): Squadre e Oggi non restano con il nome vecchio")
    func rinominaAvvisaTutta() async throws {
        let centro = NotificationCenter()
        let (arrivi, osservatore) = Self.contaAvvisi(su: centro)
        defer { centro.removeObserver(osservatore) }
        let server = Self.serverRosa()
        let vm = Self.vm(server, centro: centro)
        await vm.carica()
        vm.nuovoNome = "Nuvola Est"
        await vm.rinomina()
        #expect(vm.nome == "Nuvola Est")
        #expect(arrivi.valore == 1, "un solo avviso, a nome salvato")
    }

    @Test("Nessun avviso se il nome non cambia davvero: vuoto, uguale, o rifiutato dal server")
    func nessunAvvisoSenzaCambio() async throws {
        let centro = NotificationCenter()
        let (arrivi, osservatore) = Self.contaAvvisi(su: centro)
        defer { centro.removeObserver(osservatore) }
        let rifiuta = Self.serverRosa(rispostaNome: { throw ErroreApi.server("C'è già una squadra con questo nome: scegline un altro.") })
        let vm = Self.vm(rifiuta, centro: centro)
        await vm.carica()
        vm.nuovoNome = ""
        await vm.rinomina()
        vm.nuovoNome = "Nuvola Ovest"
        await vm.rinomina()
        vm.nuovoNome = "Borgo Alto"
        await vm.rinomina()
        #expect(arrivi.valore == 0)
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
        #expect(vm.messaggio == Catalogo.Scambio.creditiSalvati)
    }

    @Test("Crediti scritti male (lettere, negativi, decimali, più di 5 cifre, vuoto): la frase della web e niente richiesta",
          arguments: ["abc", "-3", "2,5", "123456", "", "  "])
    func creditiNonValidi(scritto: String) async throws {
        let server = Self.serverRosa()
        let vm = Self.vm(server)
        await vm.carica()
        vm.crediti = scritto
        await vm.salvaCrediti()
        #expect(vm.messaggio == Catalogo.Scambio.scriviCreditiCome)
        #expect(server.quante("PUT /api/crediti") == 0)
    }

    @Test("Salva premuto due volte di seguito sui crediti: una richiesta sola")
    func creditiDueVolteDiSeguito() async throws {
        let server = Self.serverRosa(ritardo: 300_000_000)
        let vm = Self.vm(server)
        await vm.carica()
        vm.crediti = "40"
        async let primo: Void = vm.salvaCrediti()
        async let secondo: Void = vm.salvaCrediti()
        _ = await (primo, secondo)
        #expect(server.quante("PUT /api/crediti") == 1, "il secondo «Salva», a salvataggio in corso, non parte")
        #expect(vm.messaggio == Catalogo.Scambio.creditiSalvati)
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
