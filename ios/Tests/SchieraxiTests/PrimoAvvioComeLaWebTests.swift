import Foundation
import Testing
@testable import Schieraxi

// Il primo avvio dell'iPhone come quello della web (#931, punto 1): i tre passi della web («Le rose», «La tua squadra», «I tempi
// della lega», `PA_PASSI` e `PA_NOMI` di primoavvio.js) con i loro testi del catalogo, poi i due dell'iPhone («Il widget», «Gli
// avvisi», differenza ammessa). Lo stemma non è più un passo: «Tutto pronto» dice dov'è, come la web (`pav.il_resto`).
// I tempi si chiedono e si salvano come `paTempiSalva`: si rileggono le regole e si cambiano solo i due valori. Dati inventati.

@Suite("Primo avvio: i passi e le frasi della web (#931)")
struct PassiComeLaWebTests {
    @Test("I passi sono quelli della web, nello stesso ordine, più widget e avvisi; niente stemma")
    func passi() {
        #expect(PassoGuidato.allCases == [.rose, .squadra, .tempi, .widget, .avvisi])
        #expect(PassoGuidato.allCases.map(\.nomeServer) == ["rose", "squadra", "tempi", "widget", "avvisi"],
                "i nomi del server, gli stessi della web")
    }

    @Test("I nomi dei passi sono quelli della web (`PA_NOMI`): «Le rose», «La tua squadra», «I tempi della lega»")
    func nomi() {
        #expect(PassoGuidato.rose.titolo == Catalogo.Pav.nRose)
        #expect(PassoGuidato.squadra.titolo == Catalogo.Pav.nSquadra)
        #expect(PassoGuidato.tempi.titolo == Catalogo.Pav.nTempi)
        #expect(PassoGuidato.widget.titolo == Catalogo.Pav.nWidget)
        #expect(PassoGuidato.avvisi.titolo == Catalogo.Pav.nAvvisi)
        #expect(Catalogo.Pav.nRose == "Le rose" && Catalogo.Pav.nTempi == "I tempi della lega")
    }

    @Test("Le frasi e i pulsanti dei passi vengono dal catalogo")
    func frasiEPulsanti() {
        #expect(PassoGuidato.rose.spiegazione == Catalogo.Pav.roseSpiega)
        #expect(PassoGuidato.squadra.spiegazione == Catalogo.Pav.qualeSquadraTua)
        #expect(PassoGuidato.tempi.spiegazione == Catalogo.Pav.tempiSpiega)
        #expect(PassoGuidato.widget.spiegazione == Catalogo.Pav.widgetSpiega)
        #expect(PassoGuidato.avvisi.spiegazione == Catalogo.Pav.avvisiSpiega)
        #expect(PassoGuidato.rose.azione == Catalogo.Comune.importaRose)
        #expect(PassoGuidato.squadra.azione == Catalogo.Pav.scegliSquadra)
        #expect(PassoGuidato.tempi.azione == Catalogo.Pav.tempiSalva)
        #expect(PassoGuidato.widget.azione == Catalogo.Pav.collegaWidget)
        #expect(PassoGuidato.avvisi.azione == Catalogo.Onb.attivaGliAvvisiB, "lo stesso pulsante di «Tutto pronto» della web")
    }

    @Test("«L'ho già fatto» solo per widget e avvisi, che l'app non vede dai dati della lega")
    func giaFatto() {
        #expect(PassoGuidato.allCases.filter(\.siSegnaAMano) == [.widget, .avvisi])
    }

    @Test("Nel riepilogo «(fatto)» e «(saltato)» accanto al nome, come l'indicatore dei passi della web")
    func esiti() {
        #expect(EsitoPasso.fatto.suffisso == Catalogo.Pav.fattoPar)
        #expect(EsitoPasso.saltato.suffisso == Catalogo.Pav.saltatoPar)
        #expect(EsitoPasso.daFare.suffisso.isEmpty)
        #expect(PassoGuidato.tempi.titolo + EsitoPasso.saltato.suffisso == "I tempi della lega (saltato)")
    }

    @Test("«Tutto pronto»: «Hai finito la configurazione.» o i passi rimasti per nome, come `paFine` della web")
    func frasePronto() {
        #expect(PrimoAvvioLogica.frasePronto(nonFatti: [], roseImportate: true) == Catalogo.Pav.haiFinito)
        #expect(PrimoAvvioLogica.frasePronto(nonFatti: [.tempi, .widget], roseImportate: true)
                == "Hai saltato I tempi della lega, Il widget: puoi riprenderli quando vuoi dalla Formazione.")
        #expect(PrimoAvvioLogica.frasePronto(nonFatti: [.rose, .squadra], roseImportate: false)
                == Catalogo.Pav.haiSaltatoSenzaRose(nomi: "Le rose, La tua squadra"),
                "senza rose si ritrovano con «Importa le rose» della Formazione")
    }

    @Test("Passo 2 di 5, dal catalogo")
    func avanzamento() {
        #expect(Catalogo.Pav.passoDi(n: "2", tot: "5") == "Passo 2 di 5")
    }
}

@Suite("Primo avvio, «I tempi della lega»: le due domande della web (#931)")
struct TempiGuidaTests {
    @Test("Le scadenze più comuni, con i nomi della web (`paScadenzaNome`)")
    func scadenze() {
        #expect(TempiGuida.scadenze == [0, 5, 10, 15, 30, 60])
        #expect(TempiGuida.nomeScadenza(0) == "All'inizio della prima partita")
        #expect(TempiGuida.nomeScadenza(1) == "1 minuto prima della prima partita")
        #expect(TempiGuida.nomeScadenza(10) == "10 minuti prima della prima partita")
    }

    @Test("Una scadenza salvata diversa dalle solite si aggiunge in fondo al menu, come la web")
    func scadenzaSalvata() {
        #expect(TempiGuida.sceltaScadenze(salvata: 20) == [0, 5, 10, 15, 30, 60, 20])
        #expect(TempiGuida.sceltaScadenze(salvata: 10) == TempiGuida.scadenze)
        #expect(TempiGuida.sceltaScadenze(salvata: nil) == TempiGuida.scadenze)
    }

    @Test("Le giornate di partenza con i nomi della web (`vocePrimaGiornata`), l'apostrofo davanti all'8ª e all'11ª",
          arguments: [(1, "Dalla 1ª, con il campionato"), (2, "Dalla 2ª"), (8, "Dall'8ª"), (11, "Dall'11ª"), (18, "Dalla 18ª")])
    func giornate(_ giornata: Int, _ atteso: String) {
        #expect(TempiGuida.nomePrima(giornata) == atteso)
    }

    @Test("Le giornate vanno dalla 1ª alla 38ª")
    func tutteLeGiornate() {
        #expect(TempiGuida.giornate.first == 1 && TempiGuida.giornate.last == 38 && TempiGuida.giornate.count == 38)
    }

    @Test("I valori letti dalle regole; mancanti, strani o fuori dai limiti valgono come sulla web (0 minuti, dalla 1ª)")
    func valori() throws {
        let regole: JSONValue = try Decodifica.decodifica(Data(#"{"scadenza_minuti": 20, "prima_giornata_lega": 4}"#.utf8), snake: false)
        #expect(TempiGuida.valori(regole) == TempiGuida.Valori(scadenza: 20, prima: 4))
        #expect(TempiGuida.valori(.oggetto([:])) == TempiGuida.Valori(scadenza: 0, prima: 1))
        let strane: JSONValue = try Decodifica.decodifica(Data(#"{"scadenza_minuti": "venti", "prima_giornata_lega": 1e300}"#.utf8), snake: false)
        #expect(TempiGuida.valori(strane) == TempiGuida.Valori(scadenza: 0, prima: 1))
        let fuori: JSONValue = try Decodifica.decodifica(Data(#"{"scadenza_minuti": -5, "prima_giornata_lega": 40}"#.utf8), snake: false)
        #expect(TempiGuida.valori(fuori) == TempiGuida.Valori(scadenza: 0, prima: 38))
    }

    @Test("Si salvano le regole lette con solo i due valori cambiati: le altre restano come sono")
    func regoleDaSalvare() throws {
        let lette: JSONValue = try Decodifica.decodifica(Data(
            #"{"scadenza_minuti": 0, "prima_giornata_lega": 1, "moduli": ["3-4-3"], "bonus": {"gol": {"A": 3}}}"#.utf8), snake: false)
        let nuove = TempiGuida.regole(lette, scadenza: 15, prima: 8)
        #expect(nuove.valore("scadenza_minuti") == .intero(15))
        #expect(nuove.valore("prima_giornata_lega") == .intero(8))
        #expect(nuove.valore("moduli") == lette.valore("moduli"))
        #expect(nuove.valore("bonus.gol.A") == .intero(3))
    }
}

/// Un server finto per il passo dei tempi: la guida, lo stato della lega e le regole (con il loro ultimo PUT). `fallite`: quante
/// letture delle regole non riescono prima di riuscire; `ferma`: le letture aspettano `sblocca()`, per toccare «Salva» mentre la
/// lettura è in corso.
private final class ServerTempi: @unchecked Sendable {
    private let blocco = NSLock()
    private var regole: String
    let regoleLeggibili: Bool
    private var fallite: Int
    private var ferma: Bool

    init(regole: String = #"{"scadenza_minuti": 10, "prima_giornata_lega": 4, "moduli": ["3-4-3", "4-4-2"]}"#, leggibili: Bool = true,
         fallite: Int = 0, ferma: Bool = false) {
        self.regole = regole
        regoleLeggibili = leggibili
        self.fallite = fallite
        self.ferma = ferma
    }

    var regoleSalvate: String {
        blocco.lock(); defer { blocco.unlock() }
        return regole
    }

    func sblocca() {
        blocco.lock(); defer { blocco.unlock() }
        ferma = false
    }

    private var fermo: Bool {
        blocco.lock(); defer { blocco.unlock() }
        return ferma
    }

    /// Vero se questa lettura deve fallire (e ne toglie una dal conto).
    private func falliscePerFinta() -> Bool {
        blocco.lock(); defer { blocco.unlock() }
        guard fallite > 0 else { return false }
        fallite -= 1
        return true
    }

    private func salva(_ testo: String) {
        blocco.lock(); defer { blocco.unlock() }
        regole = testo
    }

    var server: ServerDiProva {
        ServerDiProva { [self] metodo, percorso, corpo in
            if percorso.hasPrefix("/api/primo-avvio") {
                if metodo == "PUT" { return Data("{}".utf8) }
                return Data(#"{"primo_avvio": {"fatti": ["server", "accesso", "rose", "squadra"], "saltati": [], "chiuso": false}, "passi": ["server", "accesso", "rose", "stemma", "squadra", "tempi", "pwa", "widget", "avvisi"]}"#.utf8)
            }
            if percorso.hasPrefix("/api/stato") { return Data(#"{"rose_importate": true, "mia_squadra": "Squadra di prova"}"#.utf8) }
            if percorso.hasPrefix("/api/regole") {
                if metodo == "PUT" {
                    let testo = String(decoding: corpo ?? Data(), as: UTF8.self)
                    salva(testo)
                    return Data(testo.utf8)
                }
                while fermo { try await Task.sleep(nanoseconds: 5_000_000) }
                guard regoleLeggibili, !falliscePerFinta() else { throw ErroreApi.rete("giù") }
                return Data(regoleSalvate.utf8)
            }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }
}

/// Aspetta (al massimo 5 secondi) che `condizione` sia vera; chi chiama la controlla dopo con `#expect`.
@MainActor
private func aspetta(_ condizione: @MainActor () -> Bool) async {
    for _ in 0..<250 where !condizione() {
        try? await Task.sleep(nanoseconds: 20_000_000)
    }
}

@MainActor
@Suite("Primo avvio, «I tempi della lega»: si leggono e si salvano come la web (#931)")
struct TempiNellaGuidaTests {
    @Test("Nella demo il server conosce il passo «tempi», come quello vero (foto `guida`)")
    func demoConITempi() async throws {
        let risposta: PrimoAvvioRisposta = try await FinteServer.demo.get("/api/primo-avvio")
        #expect(risposta.passi.contains("tempi"))
        let corpo = PrimoAvvioLogica.corpo(precedente: nil, passiAmmessi: risposta.passi, fatti: [.tempi], saltati: [], chiuso: false)
        #expect(corpo.fatti == ["tempi"], "il passo fatto nella demo si manda, non si scarta")
    }

    @Test("Con rose e squadra già fatte la guida parte dai tempi")
    func parteDaiTempi() async {
        let vm = ConfigurazioneGuidataViewModel(server: ServerTempi().server)
        await vm.carica()
        #expect(vm.passi == [.tempi, .widget, .avvisi])
        #expect(vm.passoCorrente == .tempi)
    }

    @Test("All'apertura del passo i due menu prendono i valori salvati della lega")
    func leggeITempi() async {
        let vm = ConfigurazioneGuidataViewModel(server: ServerTempi(regole: #"{"scadenza_minuti": 20, "prima_giornata_lega": 4}"#).server)
        await vm.carica()
        #expect(vm.scadenza == 0 && vm.prima == 1, "prima di leggere, i valori più comuni come la web")
        await vm.caricaTempi()
        #expect(vm.scadenza == 20)
        #expect(vm.prima == 4)
        #expect(vm.scadenzeScelte == [0, 5, 10, 15, 30, 60, 20], "la scadenza salvata si aggiunge al menu")
    }

    @Test("«Salva» rilegge le regole, cambia solo i due valori, le salva e segna fatto il passo")
    func salva() async throws {
        let finto = ServerTempi()
        let s = finto.server
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.caricaTempi()
        vm.scadenza = 30
        vm.prima = 8
        await vm.salvaTempi()
        let salvate: JSONValue = try Decodifica.decodifica(Data(finto.regoleSalvate.utf8), snake: false)
        #expect(salvate.valore("scadenza_minuti") == .intero(30))
        #expect(salvate.valore("prima_giornata_lega") == .intero(8))
        #expect(salvate.valore("moduli") == .lista([.testo("3-4-3"), .testo("4-4-2")]), "le altre regole restano come sono")
        #expect(s.quante("GET /api/regole") == 2, "una lettura all'apertura del passo e una prima di salvare, come la web")
        #expect(vm.esito(.tempi) == .fatto)
        #expect(vm.passoCorrente == .widget)
        let corpo = try JSONDecoder().decode(CorpoPrimoAvvio.self, from: try #require(s.corpiInviati(a: "PUT /api/primo-avvio").last))
        #expect(corpo.fatti.contains("tempi"), "il server ricorda il passo, anche per la web")
    }

    @Test("Regole non lette: «Salva» non scrive niente, lo dice con la frase della web e il passo resta da fare")
    func regoleNonLette() async {
        let finto = ServerTempi(leggibili: false)
        let s = finto.server
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.caricaTempi()
        await vm.salvaTempi()
        #expect(s.quante("PUT /api/regole") == 0, "i valori di partenza non vanno sopra quelli veri")
        #expect(vm.avviso == Catalogo.Pav.tempiNonLetti)
        #expect(vm.passoCorrente == .tempi)
        #expect(vm.esito(.tempi) == .daFare)
    }

    @Test("Un menu scelto a mano prima che le regole arrivino non torna al valore salvato, come `data-scelto` della web")
    func sceltaNonSovrascritta() async {
        let vm = ConfigurazioneGuidataViewModel(server: ServerTempi().server)
        await vm.carica()
        vm.scadenza = 60
        await vm.caricaTempi()
        #expect(vm.scadenza == 60, "scelto a mano: resta la scelta")
        #expect(vm.prima == 4, "non toccato: prende il valore salvato")
    }

    @Test("«Salva» toccato mentre si leggono le regole aspetta la lettura e poi salva i menu, come la web (#801)")
    func salvaAspettaLaLettura() async throws {
        let finto = ServerTempi(ferma: true)
        let s = finto.server
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        let lettura = Task { await vm.caricaTempi() }
        await aspetta { s.quante("GET /api/regole") == 1 }
        vm.prima = 8                                         // scelto a mano mentre la lettura è in corso
        let salva = Task { await vm.salvaTempi() }
        await aspetta { vm.inCorso }
        #expect(vm.inCorso, "«Salva» è partito e aspetta la lettura")
        finto.sblocca()
        _ = await lettura.value
        await salva.value
        #expect(vm.avviso == nil, "niente «Non riesco a leggere i tempi salvati»: la lettura c'era, bastava aspettarla")
        #expect(s.quante("GET /api/regole") == 2, "una lettura sola all'apertura, più quella prima di salvare")
        let salvate: JSONValue = try Decodifica.decodifica(Data(finto.regoleSalvate.utf8), snake: false)
        #expect(salvate.valore("scadenza_minuti") == .intero(10), "il menu non toccato ha il valore salvato")
        #expect(salvate.valore("prima_giornata_lega") == .intero(8), "il menu scelto a mano resta")
        #expect(vm.esito(.tempi) == .fatto)
    }

    @Test("Dopo una lettura non riuscita, «Salva» rilegge e salva i menu scelti a mano: non li riporta ai valori salvati")
    func sceltaDopoUnaLetturaNonRiuscita() async throws {
        let finto = ServerTempi(fallite: 1)
        let vm = ConfigurazioneGuidataViewModel(server: finto.server)
        await vm.carica()
        await vm.caricaTempi()
        #expect(!vm.tempiLetti)
        vm.scadenza = 30
        await vm.salvaTempi()
        let salvate: JSONValue = try Decodifica.decodifica(Data(finto.regoleSalvate.utf8), snake: false)
        #expect(vm.scadenza == 30)
        #expect(salvate.valore("scadenza_minuti") == .intero(30), "la scelta a mano, non quella salvata prima (10)")
        #expect(salvate.valore("prima_giornata_lega") == .intero(4))
        #expect(vm.passoCorrente == .widget)
    }

    @Test("Mentre «Salva» è in corso «Salta» e «L'ho già fatto» non fanno niente: il passo avanza una volta sola")
    func comandiFermiMentreSalva() async {
        let finto = ServerTempi(ferma: true)
        let vm = ConfigurazioneGuidataViewModel(server: finto.server)
        await vm.carica()
        let salva = Task { await vm.salvaTempi() }
        await aspetta { vm.inCorso }
        await vm.salta(.tempi)
        await vm.giaFatto(.tempi)
        #expect(vm.passoCorrente == .tempi, "il tocco su «Salta» durante il salvataggio non vale")
        #expect(vm.esito(.tempi) == .daFare)
        finto.sblocca()
        await salva.value
        #expect(vm.esito(.tempi) == .fatto)
        #expect(vm.passoCorrente == .widget, "un passo solo: prima saltava anche il widget")
    }

    @Test("«Tutto pronto» dice i passi saltati per nome")
    func riepilogo() async {
        let vm = ConfigurazioneGuidataViewModel(server: ServerTempi().server)
        await vm.carica()
        await vm.salta(.tempi)
        await vm.segnaFatto(.widget)
        await vm.salta(.avvisi)
        #expect(vm.eRiepilogo)
        #expect(vm.frasePronto == "Hai saltato I tempi della lega, Gli avvisi: puoi riprenderli quando vuoi dalla Formazione.")
    }
}
