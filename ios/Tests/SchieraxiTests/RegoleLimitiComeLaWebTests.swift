import Foundation
import Testing
@testable import Schieraxi

// I limiti dei numeri delle regole come la web (#889, dopo la #886): l'editor li legge da `/limiti-regole.json`, lo stesso file con
// cui il server controlla le regole e da cui la web prende i limiti di − e +. Con un server di prima, che non ha il file, valgono
// quelli di riserva, uguali al file (lo controlla `tests/test_limiti_regole_iphone.py`). Prima di salvare, come la web
// (`problemaCampo` in `vistaRegole`), un campo senza numero, un decimale in un campo di numeri interi o un numero fuori dai limiti
// fermano «Salva le regole» con il nome del campo, e al server non parte niente. Regole della fixture `regole.json`; dove serve,
// limiti inventati.

/// Le chiavi dei limiti dei campi con − e + dell'editor dell'iPhone.
private let chiaviDellEditor = [
    "bonus.gol.P", "bonus.gol.D", "bonus.gol.C", "bonus.gol.A", "bonus.assist", "bonus.rigore_segnato", "bonus.rigore_parato",
    "bonus.portiere_imbattuto", "bonus.mvp", "bonus.ammonizione", "bonus.espulsione", "bonus.autogol", "bonus.rigore_sbagliato",
    "bonus.gol_subito_portiere", "rosa.P", "rosa.D", "rosa.C", "rosa.A", "crediti_iniziali", "panchina.numero",
    "panchina.max_sostituzioni", "panchina.posti.P", "panchina.posti.D", "panchina.posti.C", "panchina.posti.A",
    "voto_senza_sostituto", "voto_ufficio_rinviate", "modificatore_difesa.min_difensori", "modificatore_difesa.soglie.media",
    "modificatore_difesa.soglie.bonus",
]

/// Le regole della fixture, lette come le legge l'editor.
private func regole() throws -> JSONValue {
    try JSONDecoder().decode(JSONValue.self, from: Fixture.dati("regole"))
}

/// Un campo con un numero che la web non lascia salvare, e la frase che la web mostra.
struct CampoFuoriPosto: Sendable, CustomTestStringConvertible {
    let percorso: String
    let numero: Double
    let frase: String

    var testDescription: String { "\(percorso) = \(numero)" }
}

private let campiFuoriPosto: [CampoFuoriPosto] = [
    CampoFuoriPosto(percorso: "bonus.assist", numero: 99, frase: "«Assist» deve essere tra 0 e 20"),
    CampoFuoriPosto(percorso: "bonus.autogol", numero: 3, frase: "«Autogol» deve essere tra −20 e 0"),
    CampoFuoriPosto(percorso: "bonus.gol.A", numero: -4, frase: "«Gol di un attaccante» deve essere tra 0 e 20"),
    CampoFuoriPosto(percorso: "rosa.P", numero: 0, frase: "«Portieri» deve essere tra 1 e 30"),
    CampoFuoriPosto(percorso: "panchina.max_sostituzioni", numero: 11, frase: "«Cambi massimi» deve essere tra 0 e 10"),
    CampoFuoriPosto(percorso: "panchina.posti.D", numero: 11, frase: "«Difensori» deve essere tra 0 e 10"),
    CampoFuoriPosto(percorso: "crediti_iniziali", numero: 200_000, frase: "«Crediti iniziali» deve essere tra 0 e 100000"),
    CampoFuoriPosto(percorso: "modificatore_difesa.min_difensori", numero: 6, frase: "«Difensori minimi in campo» deve essere tra 3 e 5"),
    CampoFuoriPosto(percorso: "rosa.D", numero: 8.5, frase: "«Difensori» deve essere un numero intero"),
    CampoFuoriPosto(percorso: "panchina.posti.P", numero: 1.5, frase: "«Portieri» deve essere un numero intero"),
]

@Suite("Regole: i limiti dei numeri dal server e i campi controllati prima di salvare, come la web (#889)")
struct RegoleLimitiComeLaWebTests {
    // MARK: limiti

    @Test("I limiti di riserva hanno ogni campo dell'editor, con i numeri del file del server")
    func riserva() {
        let r = LimitiRegole.riserva
        for chiave in chiaviDellEditor {
            #expect(r.valori[chiave] != nil, "manca il limite di \(chiave)")
        }
        #expect(r.intervallo("bonus.assist") == 0...20)
        #expect(r.intervallo("bonus.autogol") == -20...0)
        #expect(r.intervallo("rosa.P") == 1...30)
        #expect(r.intervallo("crediti_iniziali") == 0...100_000)
        #expect(r.intervallo("panchina.numero") == 1...30)
        #expect(r.intervallo("panchina.max_sostituzioni") == 0...10)
        #expect(r.intervallo("panchina.posti.A") == 0...10)
        #expect(r.intervallo("modificatore_difesa.min_difensori") == 3...5)
        #expect(r.intervallo("modificatore_difesa.soglie.media") == 0...10)
    }

    @Test("Il file del server vince su quelli di riserva; una chiave che non ha, o scritta male, resta quella di riserva")
    func fileDelServer() throws {
        let json = """
            {"bonus.assist": {"min": 0, "max": 15}, "rosa.P": {"min": 2, "max": 4.5},
             "bonus.mvp": {"min": 5, "max": 1}, "bonus.gol.P": {"min": "0", "max": 20}}
            """
        let limiti = try #require(LimitiRegole(dati: Data(json.utf8)))
        #expect(limiti.intervallo("bonus.assist") == 0...15)
        #expect(limiti.intervallo("rosa.P") == 2...4.5)
        #expect(limiti.intervallo("bonus.mvp") == 0...20, "il minimo sopra il massimo non vale: resta quello di riserva")
        #expect(limiti.intervallo("bonus.gol.P") == 0...20, "senza due numeri non vale: resta quello di riserva")
        #expect(limiti.intervallo("crediti_iniziali") == 0...100_000, "una chiave che il file non ha: quella di riserva")
    }

    @Test("Una risposta che non è il file dei limiti non vale",
          arguments: ["<html><body>Pagina</body></html>", "[]", "{}", #"{"detail": "Not Found"}"#])
    func rispostaSbagliata(testo: String) {
        #expect(LimitiRegole(dati: Data(testo.utf8)) == nil)
    }

    // MARK: l'editor

    /// Le regole della fixture e, a `/limiti-regole.json`, `limiti` (nil: un server di prima, che risponde 404). I PUT rimandano il
    /// corpo ricevuto.
    private func server(limiti: String?) -> ServerDiProva {
        ServerDiProva { metodo, percorso, corpo in
            if percorso == "/limiti-regole.json" {
                guard let limiti else { throw ErroreApi.risposta(404) }
                return Data(limiti.utf8)
            }
            if metodo == "PUT" { return corpo ?? Data("{}".utf8) }
            return try Fixture.dati("regole")
        }
    }

    @MainActor
    @Test("L'editor usa i limiti del server, chiesti una volta sola e dopo le regole")
    func editorConIlFileDelServer() async {
        let s = server(limiti: #"{"bonus.assist": {"min": 0, "max": 15}}"#)
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        #expect(vm.limiti.intervallo("bonus.assist") == 0...15)
        #expect(vm.limiti.intervallo("rosa.P") == 1...30)
        #expect(Array(s.richieste.prefix(2)) == ["GET /api/regole", "GET /limiti-regole.json"])
        await vm.carica()
        #expect(s.quante("GET /limiti-regole.json") == 1)
    }

    @MainActor
    @Test("Un server di prima, senza il file: la pagina si apre con i limiti di riserva")
    func serverDiPrima() async {
        let vm = RegoleEditorViewModel(server: server(limiti: nil))
        await vm.carica()
        #expect(vm.caricato)
        #expect(vm.caricatore.errore == nil)
        #expect(vm.limiti == LimitiRegole.riserva)
    }

    @MainActor
    @Test("Un numero fuori dai limiti del server ferma «Salva» con il nome del campo, e al server non parte niente")
    func salvaFermato() async {
        let s = server(limiti: #"{"bonus.assist": {"min": 0, "max": 15}}"#)
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 16
        #expect(await vm.salva() == false)
        #expect(vm.esito == "«Assist» deve essere tra 0 e 15")
        #expect(!vm.esitoRiuscito)
        #expect(vm.modificato, "la modifica resta da correggere")
        #expect(s.quante("PUT") == 0)
        vm.numero("bonus.assist").wrappedValue = 15
        #expect(await vm.salva())
        #expect(s.quante("PUT /api/regole") == 1)
    }

    @MainActor
    @Test("Una fascia nuova non va oltre i limiti del server: mezzo punto sopra l'ultima, al massimo il limite")
    func fasciaNuovaDentroILimite() async {
        let vm = RegoleEditorViewModel(server: server(limiti: nil))
        await vm.carica()
        vm.fasce = [RegoleLogica.Fascia(media: 9.75, bonus: 19.5)]
        vm.aggiungiFascia()
        #expect(vm.fasce.last?.media == 10, "la media arriva a 10, il limite del server (prima si fermava a 9)")
        #expect(vm.fasce.last?.bonus == 20)
    }

    // MARK: i campi controllati prima di salvare

    @Test("Le regole della fixture vanno bene")
    func regoleBuone() throws {
        #expect(CampiRegole.problema(try regole(), limiti: .riserva) == nil)
    }

    @Test("Un numero che la web non lascia salvare: la frase della web, con il nome della riga", arguments: campiFuoriPosto)
    func fuoriPosto(caso: CampoFuoriPosto) throws {
        var r = try regole()
        r.imposta(caso.percorso, JSONValue.numero(caso.numero))
        #expect(CampiRegole.problema(r, limiti: .riserva) == caso.frase)
    }

    @Test("Un campo senza numero: «è vuoto: scrivi un numero»")
    func campoVuoto() throws {
        var r = try regole()
        r.imposta("bonus.mvp", .nullo)
        #expect(CampiRegole.problema(r, limiti: .riserva) == "«Migliore in campo» è vuoto: scrivi un numero")
        var senza = try regole()
        senza.imposta("crediti_iniziali", .testo(""))
        #expect(CampiRegole.problema(senza, limiti: .riserva) == Catalogo.Regole.campoVuoto(campo: "Crediti iniziali"))
    }

    @Test("Il primo campo che non va, nell'ordine della pagina")
    func primoCampo() throws {
        var r = try regole()
        r.imposta("crediti_iniziali", JSONValue.numero(-1))
        r.imposta("bonus.assist", JSONValue.numero(30))
        #expect(CampiRegole.problema(r, limiti: .riserva) == "«Assist» deve essere tra 0 e 20")
    }

    @Test("Le fasce del modificatore acceso si controllano con il loro nome, «Fascia N, media almeno»")
    func fasce() throws {
        let r = try regole()
        let fasce = [RegoleLogica.Fascia(media: 6, bonus: 1), RegoleLogica.Fascia(media: 10.5, bonus: 2)]
        #expect(CampiRegole.problema(r, fasce: fasce, limiti: .riserva) == "«Fascia 2, media almeno» deve essere tra 0 e 10")
        let bonus = [RegoleLogica.Fascia(media: 6, bonus: 21)]
        #expect(CampiRegole.problema(r, fasce: bonus, limiti: .riserva) == "«Fascia 1, bonus» deve essere tra 0 e 20")
    }

    @Test("Non si controllano i campi che non si salvano: modificatore spento, posti senza i posti fissi, voto d'ufficio spento")
    func campiNonSalvati() throws {
        var spento = try regole()
        spento.imposta("modificatore_difesa.attivo", .booleano(false))
        spento.imposta("modificatore_difesa.min_difensori", JSONValue.numero(9))
        let fasce = [RegoleLogica.Fascia(media: 12, bonus: 1)]
        #expect(CampiRegole.problema(spento, fasce: fasce, limiti: .riserva) == nil, "il modificatore spento non si controlla")

        var postiFissi = try regole()
        postiFissi.imposta("panchina.numero", JSONValue.numero(0))
        #expect(CampiRegole.problema(postiFissi, limiti: .riserva) == nil, "con i posti fissi la panchina è la loro somma")

        var senzaPosti = try regole()
        senzaPosti.imposta("panchina.posti", .nullo)
        senzaPosti.imposta("panchina.numero", JSONValue.numero(40))
        #expect(CampiRegole.problema(senzaPosti, limiti: .riserva) == "«Giocatori in panchina» deve essere tra 1 e 30")

        var votoAcceso = try regole()
        votoAcceso.imposta("voto_senza_sostituto", JSONValue.numero(12))
        #expect(CampiRegole.problema(votoAcceso, limiti: .riserva) == "«Voto d'ufficio» deve essere tra 0 e 10")
    }

    @Test("I limiti del server valgono anche nel controllo")
    func limitiDelServerNelControllo() throws {
        let limiti = try #require(LimitiRegole(dati: Data(#"{"panchina.max_sostituzioni": {"min": 0, "max": 5}}"#.utf8)))
        var r = try regole()
        r.imposta("panchina.max_sostituzioni", JSONValue.numero(6))
        #expect(CampiRegole.problema(r, limiti: limiti) == "«Cambi massimi» deve essere tra 0 e 5")
        #expect(CampiRegole.problema(r, limiti: .riserva) == nil)
    }
}
