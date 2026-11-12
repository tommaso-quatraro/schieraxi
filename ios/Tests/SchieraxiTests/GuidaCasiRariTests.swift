import Foundation
import Testing
@testable import Schieraxi

// Quattro casi rari della configurazione guidata (#600, dalla revisione di #599):
// 1. l'arrivo da un'altra app (Condividi, «Apri con») blocca la partenza da sola della guida solo finché serve: uscendo
//    dall'account, o finita l'importazione (o la scelta dello stemma) aperta da fuori, la guida può di nuovo partire da sola;
// 2. il foglio chiuso dall'app (sessione finita, altro server, un file arrivato) non segna saltati i passi: lo fa solo l'utente;
// 3. senza avanzamento salvato si guarda prima la vecchia procedura degli account (`GET /api/onboarding`), come
//    `paControllaAvvio` della web (`fanta/web/primoavvio.js`): completata o saltata, la guida non parte da sola;
// 4. un file o un'immagine arrivati con la guida aperta: la guida si chiude (senza segnare saltati) e si apre l'importazione
//    o la scelta dello stemma, un foglio alla volta.
// Server finti e nomi inventati; ogni test usa oggetti suoi, quindi i test girano in parallelo senza toccarsi.

/// Un server finto per la guida: senza rose (o con), che ricorda la guida come `avanzamento` e risponde a `/api/onboarding`
/// con `onboarding` (nil = rotta che non risponde, come un server senza account).
private func serverGuida(avanzamento: String = "null", roseImportate: Bool = false, onboarding: String? = nil) -> ServerDiProva {
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
        if percorso.hasPrefix("/api/onboarding"), let onboarding { return Data(onboarding.utf8) }
        throw ErroreApi.server("nessuna risposta per \(percorso)")
    }
}

/// La risposta di `GET /api/onboarding` del server (`onboarding._come_dict`), con lo stato dato.
private func onboarding(_ stato: String) -> String {
    #"{"tipo": "classic", "stato": "\#(stato)", "passo": "benvenuto", "demo": false, "aggiornato": "2026-09-01T10:00:00+00:00", "passi": ["benvenuto", "tipo", "regole", "rose", "squadra", "controlli", "formazione", "avvisi"]}"#
}

private let appenaRegistrato = #"{"fatti": ["server", "accesso"], "saltati": [], "chiuso": false}"#
private let fileRose = URL(fileURLWithPath: "/tmp/rose-di-prova.xlsx")
private let stemma = URL(fileURLWithPath: "/tmp/stemma-di-prova.png")

// MARK: 1. l'arrivo da fuori non blocca la guida per sempre

@Suite("Configurazione guidata: l'arrivo da un'altra app vale finché serve (#600)")
@MainActor
struct ArrivoDaFuoriFinitoTests {
    @Test("Uscendo dall'account dopo un file già aperto, al nuovo accesso la guida torna a partire da sola")
    func uscitaDallAccount() async {
        let nav = Navigazione()
        nav.apriFile(fileRose)
        nav.fileDaImportare = nil          // preso dalla pagina «Aggiorna le rose»
        nav.uscitoDallAccount()
        #expect(!nav.apertaDaFuori)
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: serverGuida(), apertaDaFuori: { nav.apertaDaFuori })
        #expect(parte)
    }

    @Test("Uscendo dall'account con un file o un'immagine ancora da aprire, resta un arrivo da fuori: dopo l'accesso si apre quello",
          arguments: [fileRose, stemma])
    func uscitaConArrivoDaAprire(url: URL) {
        let nav = Navigazione()
        nav.apriFile(url)
        nav.uscitoDallAccount()
        #expect(nav.apertaDaFuori)
    }

    @Test("Il file aperto da fuori: finché la pagina «Aggiorna le rose» è aperta conta ancora, lasciata (salvato o no) non più")
    func importazioneFinita() {
        let nav = Navigazione()
        nav.apriFile(fileRose)
        nav.controllaFineArrivo(importaAperta: true)
        #expect(nav.apertaDaFuori, "il file non è ancora stato preso")
        nav.fileDaImportare = nil
        nav.controllaFineArrivo(importaAperta: true)
        #expect(nav.apertaDaFuori, "l'importazione è ancora sullo schermo")
        nav.controllaFineArrivo(importaAperta: false)
        #expect(!nav.apertaDaFuori)
    }

    @Test("L'immagine aperta da fuori: conta finché il foglio «Stemma o maglia?» è aperto")
    func immagineFinita() {
        let nav = Navigazione()
        nav.apriFile(stemma)
        nav.controllaFineArrivo(importaAperta: false)
        #expect(nav.apertaDaFuori, "il foglio dello stemma è ancora aperto")
        nav.immagineRicevuta = nil         // scelta fatta o annullata: il foglio si chiude
        nav.controllaFineArrivo(importaAperta: false)
        #expect(!nav.apertaDaFuori)
    }
}

// MARK: 2. chiusa dall'app: niente passi saltati

/// Un server il cui indirizzo cambia a metà (Impostazioni > Server, o lo spostamento automatico a un altro server).
private final class ServerCheCambia: ServerClient, @unchecked Sendable {
    private let dentro: ServerDiProva
    private let blocco = NSLock()
    private var attuale: String

    init(_ dentro: ServerDiProva) {
        self.dentro = dentro
        attuale = dentro.indirizzo
    }

    var indirizzo: String {
        blocco.lock(); defer { blocco.unlock() }
        return attuale
    }

    func cambia(in nuovo: String) {
        blocco.lock(); defer { blocco.unlock() }
        attuale = nuovo
    }

    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data {
        try await dentro.richiesta(metodo, percorso, corpo: corpo)
    }

    func carica(_ percorso: String, nome: String, dati: Data, tipo: String) async throws -> Data {
        try await dentro.carica(percorso, nome: nome, dati: dati, tipo: tipo)
    }
}

@Suite("Configurazione guidata: chiusa dall'app non segna saltati i passi (#600)")
@MainActor
struct ChiusaDallAppTests {
    @Test("Chiusa dall'app (sessione finita, file arrivato da fuori): nessun salvataggio, la guida resta da riprendere")
    func chiusaDallApp() async {
        let s = serverGuida(avanzamento: appenaRegistrato)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.chiusa(dallApp: true)
        #expect(s.quante("PUT /api/primo-avvio") == 0)
        #expect(PrimoAvvioLogica.daRiprendere(vm.avanzamento))
    }

    @Test("Cambiato il server con la guida aperta: la chiusura non scrive niente, né sul vecchio né sul nuovo")
    func altroServer() async {
        let dentro = serverGuida(avanzamento: appenaRegistrato)
        let s = ServerCheCambia(dentro)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        s.cambia(in: "https://altro-server-di-prova.invalid")
        await vm.chiusa()
        #expect(dentro.quante("PUT") == 0)
    }

    @Test("Chiusa dall'utente (trascinata giù) resta come «Più tardi»: i passi rimasti diventano saltati")
    func chiusaDallUtente() async throws {
        let s = serverGuida(avanzamento: appenaRegistrato)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.chiusa(dallApp: false)
        let corpo = try JSONDecoder().decode(CorpoPrimoAvvio.self, from: try #require(s.corpiInviati(a: "/api/primo-avvio").last))
        #expect(corpo.saltati.contains("rose"))
    }

    @Test("La navigazione ricorda che la guida l'ha chiusa l'app, finché non si riapre")
    func navigazioneRicorda() {
        let nav = Navigazione()
        nav.chiudiGuidaDallApp()
        #expect(!nav.guidaChiusaDallApp, "una guida già chiusa non si chiude di nuovo")
        nav.guidaAperta = true
        nav.chiudiGuidaDallApp()
        #expect(!nav.guidaAperta)
        #expect(nav.guidaChiusaDallApp)
        nav.guidaAperta = true             // riaperta (da Oggi): la prossima chiusura è di nuovo dell'utente
        #expect(!nav.guidaChiusaDallApp)
    }
}

// MARK: 3. la vecchia procedura degli account, come la web

@Suite("Configurazione guidata: senza avanzamento salvato si guarda la vecchia procedura, come la web (#600)")
@MainActor
struct VecchiaProceduraTests {
    @Test("La risposta di /api/onboarding: completata o saltata vuol dire finita",
          arguments: [("completato", true), ("saltato", true), ("da_fare", false), ("in_corso", false)])
    func finita(stato: String, finita: Bool) throws {
        let p: ProceduraVecchia = try Decodifica.decodifica(Data(onboarding(stato).utf8))
        #expect(p.finita == finita)
    }

    @Test("Una risposta strana non fa cadere niente: non è finita")
    func rispostaStrana() throws {
        let p: ProceduraVecchia = try Decodifica.decodifica(Data(#"{"stato": 3}"#.utf8))
        #expect(!p.finita)
    }

    @Test("Mai iniziata e senza rose: con la vecchia procedura completata o saltata non parte, altrimenti sì",
          arguments: [("completato", false), ("saltato", false), ("da_fare", true), ("in_corso", true)])
    func conAccount(stato: String, parte: Bool) async {
        let s = serverGuida(onboarding: onboarding(stato))
        let risultato = await ConfigurazioneGuidataViewModel.devePartire(server: s, conAccount: true)
        #expect(risultato == parte)
        #expect(s.quante("GET /api/onboarding") == 1)
    }

    @Test("Con gli account, se la vecchia procedura non risponde non parte (come la web: si riprova alla prossima apertura)")
    func conAccountSenzaRisposta() async {
        let s = serverGuida(onboarding: nil)
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s, conAccount: true)
        #expect(!parte)
    }

    @Test("Senza account la vecchia procedura non c'è: non si chiede e la guida parte")
    func senzaAccount() async {
        let s = serverGuida(onboarding: nil)
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s, conAccount: false)
        #expect(parte)
        #expect(s.quante("/api/onboarding") == 0)
    }

    @Test("Con un avanzamento salvato conta quello: la vecchia procedura non si chiede")
    func avanzamentoSalvato() async {
        let s = serverGuida(avanzamento: appenaRegistrato, onboarding: onboarding("completato"))
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s, conAccount: true)
        #expect(parte, "cominciata e lasciata prima delle rose: si riprende")
        #expect(s.quante("/api/onboarding") == 0)
    }

    @Test("Con le rose non si chiede niente alla vecchia procedura")
    func conRose() async {
        let s = serverGuida(roseImportate: true, onboarding: onboarding("da_fare"))
        let parte = await ConfigurazioneGuidataViewModel.devePartire(server: s, conAccount: true)
        #expect(!parte)
        #expect(s.quante("/api/onboarding") == 0)
    }

    @Test("La regola, senza rete: mai iniziata, la vecchia procedura finita la ferma")
    func regola() {
        let maiIniziata = PrimoAvvioRisposta(primoAvvio: nil)
        #expect(!PrimoAvvioLogica.daAvviare(maiIniziata, roseImportate: false, procedura: ProceduraVecchia(stato: "completato")))
        #expect(!PrimoAvvioLogica.daAvviare(maiIniziata, roseImportate: false, procedura: ProceduraVecchia(stato: "saltato")))
        #expect(PrimoAvvioLogica.daAvviare(maiIniziata, roseImportate: false, procedura: ProceduraVecchia(stato: "da_fare")))
        #expect(PrimoAvvioLogica.daAvviare(maiIniziata, roseImportate: false, procedura: nil), "senza account")
    }
}

// MARK: 4. un file o un'immagine con la guida aperta

@Suite("Configurazione guidata: un file o un'immagine con la guida aperta, un foglio alla volta (#600)")
@MainActor
struct ArrivoConGuidaApertaTests {
    @Test("Arriva un file: la guida si chiude dall'app (senza segnare saltati) e si apre l'importazione")
    func file() {
        let nav = Navigazione()
        nav.guidaAperta = true
        nav.guidaComparsa()
        nav.apriFile(fileRose)
        #expect(!nav.guidaAperta)
        #expect(nav.guidaChiusaDallApp)
        #expect(nav.fileDaImportare == fileRose)
    }

    @Test("Arriva un'immagine: la guida si chiude e il foglio «Stemma o maglia?» si apre solo quando la guida è sparita")
    func immagine() {
        let nav = Navigazione()
        nav.guidaAperta = true
        nav.guidaComparsa()
        nav.apriFile(stemma)
        #expect(!nav.guidaAperta)
        #expect(nav.guidaChiusaDallApp)
        #expect(nav.immagineRicevuta == nil, "due fogli insieme: la guida si sta ancora chiudendo")
        nav.guidaSparita()
        #expect(nav.immagineRicevuta?.url == stemma)
        #expect(nav.apertaDaFuori)
    }

    @Test("Senza la guida sullo schermo l'immagine si apre subito")
    func immagineSenzaGuida() {
        let nav = Navigazione()
        nav.apriFile(stemma)
        #expect(nav.immagineRicevuta?.url == stemma)
        #expect(!nav.guidaChiusaDallApp)
    }

    @Test("Guida chiusa dall'utente e poi sparita: nessuna immagine da aprire")
    func sparitaSenzaImmagine() {
        let nav = Navigazione()
        nav.guidaAperta = true
        nav.guidaComparsa()
        nav.guidaAperta = false
        nav.guidaSparita()
        #expect(nav.immagineRicevuta == nil)
        #expect(!nav.guidaChiusaDallApp)
    }

    @Test("Un'immagine tra l'apertura della guida e la comparsa del suo foglio aspetta anche lei")
    func immaginePrimaDellaComparsa() {
        let nav = Navigazione()
        nav.guidaAperta = true             // il foglio non è ancora comparso
        nav.apriFile(stemma)
        #expect(!nav.guidaAperta)
        #expect(nav.immagineRicevuta == nil, "il foglio della guida può essere ancora in arrivo")
        nav.guidaSparita()
        #expect(nav.immagineRicevuta?.url == stemma)
    }

    @Test("Chiusa dall'app, la guida non conta più come sullo schermo: senza la scomparsa del foglio, l'immagine dopo si apre subito")
    func chiusaDallAppSenzaScomparsa() {
        let nav = Navigazione()
        nav.guidaAperta = true
        nav.guidaComparsa()
        nav.chiudiGuidaDallApp()           // per esempio la sessione cambiata; `guidaSparita` non arriva
        nav.apriFile(stemma)
        #expect(nav.immagineRicevuta?.url == stemma)
    }

    @Test("Un'immagine in attesa si apre comunque se la scomparsa del foglio della guida non arriva")
    func attesaSenzaScomparsa() async {
        let nav = Navigazione()
        nav.attesaFoglio = .milliseconds(10)
        nav.guidaAperta = true
        nav.guidaComparsa()
        nav.apriFile(stemma)
        #expect(nav.immagineRicevuta == nil)
        let limite = ContinuousClock.now + .seconds(3)
        while nav.immagineRicevuta == nil, ContinuousClock.now < limite {
            try? await Task.sleep(for: .milliseconds(20))
        }
        #expect(nav.immagineRicevuta?.url == stemma)
    }

    @Test("La guida si stava già chiudendo per scelta dell'utente: un'immagine arrivata intanto aspetta, la scelta resta sua")
    func chiusuraDellUtenteInCorso() {
        let nav = Navigazione()
        nav.guidaAperta = true
        nav.guidaComparsa()
        nav.guidaAperta = false            // trascinata giù: il foglio si sta chiudendo
        nav.apriFile(stemma)
        #expect(!nav.guidaChiusaDallApp, "i passi rimasti diventano saltati come per «Più tardi»")
        #expect(nav.immagineRicevuta == nil)
        nav.guidaSparita()
        #expect(nav.immagineRicevuta?.url == stemma)
    }
}
