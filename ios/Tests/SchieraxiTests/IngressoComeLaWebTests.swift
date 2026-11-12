import Foundation
import Testing
@testable import Schieraxi

// Ingresso di un amico nuovo come la web (#580, riga 66 di docs/COERENZA-WEB-IPHONE.md):
// - #594: in Importa le rose il pulsante del file dice «Scegli il file (Excel o CSV)», come il passo «Le rose» del primo avvio
//   della web (`pav.scegli_file`), perché il selettore accetta anche CSV e testo;
// - #595: la configurazione guidata cominciata prima di caricare le rose (anche sulla web o su un altro dispositivo) si riprende
//   da sola all'apertura dell'app, con la regola della web (`paDaRiprendere` e `primoAvvioSeServe` in `fanta/web/primoavvio.js`):
//   cominciata e non chiusa, nessuna rosa, passo «Le rose» né fatto né saltato; mai se l'app è stata aperta da Condividi.
//   Chiusa trascinandola giù vale come «Più tardi» (la ✕ della web): i passi rimasti diventano saltati.
// Server finto e nomi inventati; ogni test usa oggetti suoi, quindi i test girano in parallelo senza toccarsi.

@Suite("Importa le rose: il pulsante del file come il primo avvio della web (#594)")
struct PulsanteFileRoseTests {
    // che la vista usi proprio questa costante lo controlla `RestiDalCatalogoTests`; i tipi del selettore `FileRoseTests`
    @Test("Dice cosa accetta, con il testo del catalogo comune (`pav.scegli_file`)")
    func diceExcelOCSV() {
        #expect(Catalogo.Pav.scegliFile == "Scegli il file (Excel o CSV)")
    }
}

/// Quello che il server ricorda della guida, scritto come nella risposta di `GET /api/primo-avvio` (o `nil` = mai iniziata).
struct StatoGuida: Sendable, CustomTestStringConvertible {
    let nome: String
    let json: String?
    let siRiprende: Bool
    var testDescription: String { nome }

    var avanzamento: AvanzamentoPrimoAvvio? {
        guard let json else { return nil }
        return try? Decodifica.decodifica(Data(json.utf8))
    }

    /// Gli stessi casi del test della web (`test_quando_si_riprende_da_solo` in `tests/test_ingresso_amico_web.py`).
    static let casi: [StatoGuida] = [
        StatoGuida(nome: "mai iniziata (la apre l'altra regola)", json: nil, siRiprende: false),
        StatoGuida(nome: "appena registrato", json: #"{"fatti": ["server", "accesso"], "saltati": [], "chiuso": false}"#, siRiprende: true),
        StatoGuida(nome: "rose fatte, resta altro", json: #"{"fatti": ["server", "accesso", "rose"], "saltati": [], "chiuso": false}"#, siRiprende: false),
        StatoGuida(nome: "rose saltate", json: #"{"fatti": ["server", "accesso"], "saltati": ["rose"], "chiuso": false}"#, siRiprende: false),
        StatoGuida(nome: "chiusa con la ✕ della web", json: #"{"fatti": ["server", "accesso"], "saltati": ["rose", "squadra", "tempi"], "chiuso": false}"#, siRiprende: false),
        StatoGuida(nome: "chiusa con «Vai a Oggi» o «Fine»", json: #"{"fatti": ["server", "accesso"], "saltati": [], "chiuso": true}"#, siRiprende: false),
        StatoGuida(nome: "cominciata sull'iPhone, un altro passo saltato", json: #"{"fatti": [], "saltati": ["widget"], "chiuso": false}"#, siRiprende: true),
    ]
}

@Suite("Configurazione guidata: si riprende come la web (#595)")
struct RipresaGuidaTests {
    @Test("Da riprendere solo se cominciata, non chiusa, con «Le rose» né fatto né saltato", arguments: StatoGuida.casi)
    func daRiprendere(stato: StatoGuida) {
        #expect(PrimoAvvioLogica.daRiprendere(stato.avanzamento) == stato.siRiprende)
    }

    @Test("Senza rose si apre da sola: mai iniziata, o cominciata e lasciata prima delle rose", arguments: StatoGuida.casi)
    func senzaRose(stato: StatoGuida) {
        let risposta = PrimoAvvioRisposta(primoAvvio: stato.avanzamento)
        #expect(PrimoAvvioLogica.daAvviare(risposta, roseImportate: false) == (stato.json == nil || stato.siRiprende))
    }

    @Test("Con le rose, o se non si sa, non si apre mai da sola", arguments: StatoGuida.casi)
    func conRoseONonSiSa(stato: StatoGuida) {
        let risposta = PrimoAvvioRisposta(primoAvvio: stato.avanzamento)
        #expect(!PrimoAvvioLogica.daAvviare(risposta, roseImportate: true))
        #expect(!PrimoAvvioLogica.daAvviare(risposta, roseImportate: nil))
        #expect(!PrimoAvvioLogica.daAvviare(nil, roseImportate: false), "il server non ha risposto")
    }
}

@Suite("Configurazione guidata: all'apertura dell'app e alla chiusura (#595)")
@MainActor
struct AperturaGuidaTests {
    /// Un server senza rose (o con) che ricorda la guida com'è scritta in `avanzamento`.
    private func server(avanzamento: String, roseImportate: Bool = false) -> ServerDiProva {
        let squadra = roseImportate ? #""Squadra di prova""# : "null"
        let passi = #"["server","accesso","rose","squadra","stemma","pwa","widget","avvisi"]"#
        return ServerDiProva { metodo, percorso, _ in
            if percorso.hasPrefix("/api/primo-avvio") {
                if metodo == "PUT" { return Data("{}".utf8) }
                return Data(#"{"primo_avvio": \#(avanzamento), "passi": \#(passi)}"#.utf8)
            }
            if percorso.hasPrefix("/api/stato") {
                return Data(#"{"rose_importate": \#(roseImportate), "mia_squadra": \#(squadra)}"#.utf8)
            }
            if percorso.hasPrefix("/api/squadre") { return Data("[]".utf8) }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    private let appenaRegistrato = #"{"fatti": ["server", "accesso"], "saltati": [], "chiuso": false}"#

    private func ultimoCorpo(_ s: ServerDiProva) throws -> CorpoPrimoAvvio {
        try JSONDecoder().decode(CorpoPrimoAvvio.self, from: try #require(s.corpiInviati(a: "/api/primo-avvio").last))
    }

    @Test("Cominciata sulla web prima delle rose: all'apertura parte da sola, dal passo «Carica le rose», senza riscrivere lo stato")
    func riprendeDalleRose() async throws {
        let s = server(avanzamento: appenaRegistrato)
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s)
        #expect(parte)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        #expect(vm.passoCorrente == .rose)
        #expect(s.quante("PUT /api/primo-avvio") == 0, "si riprende, non si riparte")
    }

    @Test("Rose saltate, guida chiusa o rose già caricate: all'apertura non parte")
    func nonRiparte() async {
        let casi = [
            server(avanzamento: #"{"fatti": ["server", "accesso"], "saltati": ["rose"], "chiuso": false}"#),
            server(avanzamento: #"{"fatti": ["server", "accesso"], "saltati": [], "chiuso": true}"#),
            server(avanzamento: appenaRegistrato, roseImportate: true),
        ]
        for s in casi {
            let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s)
            #expect(!parte)
        }
    }

    @Test("Aperta con un file o un'immagine da un'altra app (Condividi, «Apri con»): la guida non parte, né mai iniziata né da riprendere",
          arguments: ["/tmp/rose.xlsx", "/tmp/stemma.png"])
    func apertaDaFuori(percorso: String) async {
        let nav = Navigazione()
        #expect(!nav.apertaDaFuori)
        nav.apriFile(URL(fileURLWithPath: percorso))
        #expect(nav.apertaDaFuori)
        for avanzamento in ["null", appenaRegistrato] {
            let s = server(avanzamento: avanzamento)
            let senzaFile = await ConfigurazioneGuidataViewModel.devePartire(server: s)
            #expect(senzaFile, "senza il file la guida partirebbe")
            let conFile = await ConfigurazioneGuidataViewModel.devePartire(server: s, apertaDaFuori: { nav.apertaDaFuori })
            #expect(!conFile)
        }
    }

    @Test("Un indirizzo web non è un arrivo da Condividi")
    func indirizzoWebNonConta() throws {
        let nav = Navigazione()
        nav.apriFile(try #require(URL(string: "https://esempio.invalid/rose.xlsx")))
        #expect(!nav.apertaDaFuori)
    }

    @Test("Chiusa trascinandola giù vale come «Più tardi»: i passi rimasti diventano saltati e non si riprende più da sola")
    func chiusaComePiuTardi() async throws {
        let s = server(avanzamento: appenaRegistrato)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.chiusa()
        let corpo = try ultimoCorpo(s)
        #expect(corpo.saltati.contains("rose"))
        #expect(!corpo.chiuso)
        #expect(!PrimoAvvioLogica.daRiprendere(vm.avanzamento))
    }

    @Test("Dopo «Più tardi» o «Fine» la chiusura del foglio non salva una seconda volta")
    func chiusaDopoPiuTardiOFine() async {
        let s = server(avanzamento: appenaRegistrato)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.piuTardi()
        await vm.chiusa()
        #expect(s.quante("PUT /api/primo-avvio") == 1)

        let s2 = server(avanzamento: appenaRegistrato)
        let vm2 = ConfigurazioneGuidataViewModel(server: s2)
        await vm2.carica()
        await vm2.termina()
        await vm2.chiusa()
        #expect(s2.quante("PUT /api/primo-avvio") == 1)
    }

    @Test("Chiusa a guida finita, o prima che fosse pronta, non salva niente (come la web)")
    func chiusaSenzaNienteDaSalvare() async {
        let s = server(avanzamento: appenaRegistrato)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        for passo in vm.passi { await vm.salta(passo) }
        #expect(vm.eRiepilogo)
        let prima = s.quante("PUT /api/primo-avvio")
        await vm.chiusa()
        #expect(s.quante("PUT /api/primo-avvio") == prima)

        let spento = ServerDiProva { _, _, _ in throw ErroreApi.server("non trovato") }
        let vm2 = ConfigurazioneGuidataViewModel(server: spento)
        await vm2.carica()
        await vm2.chiusa()
        #expect(spento.quante("PUT") == 0, "senza sapere cosa ricorda il server non si scrive niente")
    }
}
