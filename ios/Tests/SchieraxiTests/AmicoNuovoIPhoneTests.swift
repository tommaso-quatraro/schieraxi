import Foundation
import Testing
@testable import Schieraxi

// Un amico nuovo sull'iPhone come sulla web dopo la #878 (#880):
// 1. «Importa le rose» della guida non segna saltati i passi rimasti: lasciata la pagina delle rose (salvate o «indietro»), la
//    guida si riapre e continua con i passi che restano, fino a «Tutto pronto»; lo stesso dopo le pagine di squadra e stemma e
//    il foglio del widget, ripartendo dal passo da cui era uscita (revisione della #887);
// 4. la pagina delle rose al primo caricamento parla a chi le carica la prima volta (la frase del passo «Le rose» della web),
//    subito se arriva dalla guida, e non mostra frasi forse sbagliate finché non sa se le rose ci sono;
// 5. dopo «Esci» si rientra dove si apre l'app (Formazione o Giornate), non sulle Impostazioni;
// 6. nel campo «Codice d'invito» va bene anche il link d'invito incollato: il codice si legge come `invitoDaIndirizzo` della web.
// Server finti; nomi, indirizzi e codici INVENTATI.

/// Quello che un server finto ricorda della guida e della lega: la guida salvata (`PUT /api/primo-avvio`) e le rose.
private final class MemoriaGuida: @unchecked Sendable {
    private let blocco = NSLock()
    private var guida: String
    private var rose = false
    private var mia: String?

    init(guida: String) { self.guida = guida }

    var avanzamento: String {
        blocco.lock(); defer { blocco.unlock() }
        return guida
    }

    var stato: String {
        blocco.lock(); defer { blocco.unlock() }
        let squadra = mia.map { "\"\($0)\"" } ?? "null"
        return #"{"rose_importate": \#(rose), "mia_squadra": \#(squadra)}"#
    }

    func salva(_ corpo: Data?) {
        guard let corpo, let testo = String(data: corpo, encoding: .utf8) else { return }
        blocco.lock(); defer { blocco.unlock() }
        guida = testo
    }

    /// Le rose salvate dalla pagina delle rose (con la squadra scelta nell'anteprima, o senza).
    func importaRose(mia: String?) {
        blocco.lock(); defer { blocco.unlock() }
        rose = true
        self.mia = mia
    }
}

private func serverGuida(_ memoria: MemoriaGuida) -> ServerDiProva {
    let passi = #"["server","accesso","rose","squadra","stemma","pwa","widget","avvisi"]"#
    return ServerDiProva { metodo, percorso, corpo in
        if percorso.hasPrefix("/api/primo-avvio") {
            if metodo == "PUT" {
                memoria.salva(corpo)
                return Data("{}".utf8)
            }
            return Data(#"{"primo_avvio": \#(memoria.avanzamento), "passi": \#(passi)}"#.utf8)
        }
        if percorso.hasPrefix("/api/stato") { return Data(memoria.stato.utf8) }
        if percorso.hasPrefix("/api/squadre") { return Data("[]".utf8) }
        throw ErroreApi.server("nessuna risposta per \(percorso)")
    }
}

private let appenaRegistrato = #"{"fatti": ["server", "accesso"], "saltati": [], "chiuso": false}"#

// MARK: 1. la guida continua dopo le rose

@MainActor
@Suite("Configurazione guidata: dopo «Importa le rose» continua con i passi che restano (#880)")
struct GuidaDopoLeRoseTests {
    @Test("Andando alle rose niente diventa saltato: se l'app si chiude prima, la guida si riprende dalle rose")
    func versoLeRoseNonSaltaNiente() async {
        let memoria = MemoriaGuida(guida: appenaRegistrato)
        let s = serverGuida(memoria)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        #expect(vm.passoCorrente == .rose)
        await vm.versoLeRose()
        await vm.chiusa()                    // il foglio sparisce per lasciare il posto alla pagina delle rose
        #expect(s.quante("PUT /api/primo-avvio") == 0)
        #expect(PrimoAvvioLogica.daRiprendere(vm.avanzamento))
    }

    @Test("Salvate le rose, la guida riaperta propone squadra, stemma, widget e avvisi, nessuno già saltato")
    func riapertaDopoLeRose() async {
        let memoria = MemoriaGuida(guida: appenaRegistrato)
        let s = serverGuida(memoria)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.versoLeRose()
        await vm.chiusa()
        memoria.importaRose(mia: nil)        // nell'anteprima la squadra non è stata scelta
        let riaperta = ConfigurazioneGuidataViewModel(server: s)
        await riaperta.carica()
        #expect(riaperta.passi == [.squadra, .stemma, .widget, .avvisi])
        #expect(riaperta.passoCorrente == .squadra)
        for passo in riaperta.passi {
            #expect(riaperta.esito(passo) == .daFare, "\(passo.rawValue) non è stato saltato: si era solo andati alle rose")
        }
    }

    @Test("Con la squadra scelta nell'anteprima la guida riaperta comincia dallo stemma")
    func riapertaConLaSquadra() async {
        let memoria = MemoriaGuida(guida: appenaRegistrato)
        let s = serverGuida(memoria)
        let vm = ConfigurazioneGuidataViewModel(server: s)
        await vm.carica()
        await vm.versoLeRose()
        await vm.chiusa()
        memoria.importaRose(mia: "Squadra di prova")
        let riaperta = ConfigurazioneGuidataViewModel(server: s)
        await riaperta.carica()
        #expect(riaperta.passi == [.stemma, .widget, .avvisi])
        #expect(riaperta.esito(.squadra) == .fatto)
    }

    @Test("Tornata dalla pagina dello stemma, la guida riparte dallo stemma: la squadra saltata prima non si ripropone")
    func riapertaDalloStemma() async {
        // squadra saltata con «Salta», poi «Scegli stemma e maglia»: uscendo i passi rimasti sono stati segnati saltati (si
        // ritrovano in «Da fare» se l'app si chiude prima di tornare)
        let memoria = MemoriaGuida(guida: #"{"fatti": ["server", "accesso", "rose"], "saltati": ["squadra", "stemma", "widget", "avvisi"], "chiuso": false}"#)
        memoria.importaRose(mia: nil)
        let riaperta = ConfigurazioneGuidataViewModel(server: serverGuida(memoria), riprendiDa: .stemma)
        await riaperta.carica()
        #expect(riaperta.passi == [.squadra, .stemma, .widget, .avvisi])
        #expect(riaperta.passoCorrente == .stemma)
    }

    @Test("Tornata dalla pagina della squadra con la squadra scelta, la guida riparte dallo stemma")
    func riapertaDopoLaSquadra() async {
        let memoria = MemoriaGuida(guida: #"{"fatti": ["server", "accesso", "rose"], "saltati": ["squadra", "stemma", "widget", "avvisi"], "chiuso": false}"#)
        memoria.importaRose(mia: "Squadra di prova")
        let riaperta = ConfigurazioneGuidataViewModel(server: serverGuida(memoria), riprendiDa: .squadra)
        await riaperta.carica()
        #expect(riaperta.passoCorrente == .stemma)
        #expect(riaperta.esito(.squadra) == .fatto)
    }

    @Test("Tornata dall'ultimo passo che resta, la guida mostra «Tutto pronto»")
    func riapertaSulRiepilogo() async {
        let memoria = MemoriaGuida(guida: #"{"fatti": ["server", "accesso", "rose", "widget", "avvisi"], "saltati": ["stemma"], "chiuso": false}"#)
        memoria.importaRose(mia: "Squadra di prova")
        let riaperta = ConfigurazioneGuidataViewModel(server: serverGuida(memoria), riprendiDa: .widget)
        await riaperta.carica()
        #expect(riaperta.passi == [.stemma])
        #expect(riaperta.eRiepilogo)
    }
}

@Suite("Da dove riparte la guida tornando da una pagina in cui l'aveva portata un passo (#880)")
struct InizioGuidaTests {
    /// I passi da fare, il passo da cui era uscita (nil = aperta da sola o da «Da fare») e il passo da cui riparte.
    static let casi: [([PassoGuidato], PassoGuidato?, Int)] = [
        ([.squadra, .stemma, .widget, .avvisi], .rose, 0),
        ([.stemma, .widget, .avvisi], .squadra, 0),
        ([.squadra, .stemma, .widget, .avvisi], .stemma, 1),
        ([.squadra, .widget, .avvisi], .stemma, 1),
        ([.widget, .avvisi], .widget, 0),
        ([.squadra], .widget, 1),
        ([.squadra, .stemma], nil, 0),
    ]

    @Test("Dal passo da cui era uscita, se è ancora da fare; altrimenti dal primo dopo; nessuno dopo: «Tutto pronto»",
          arguments: InizioGuidaTests.casi)
    func inizio(passi: [PassoGuidato], riprendiDa: PassoGuidato?, atteso: Int) {
        #expect(PrimoAvvioLogica.inizio(passi, riprendiDa: riprendiDa) == atteso)
    }
}

@Suite("Le pagine aperte dalla guida: lasciate, la guida si riapre dal loro passo (#880)")
struct RitornoAllaGuidaTests {
    /// Le pile delle Impostazioni una dopo l'altra: per ognuna, il passo da cui riaprire la guida (nil = non si riapre).
    /// `#expect` non chiama metodi `mutating`: i risultati si raccolgono prima.
    private func segui(_ r: inout RitornoAllaGuida, _ pile: [[PaginaImpostazioni]]) -> [PassoGuidato?] {
        pile.map { r.pilaCambiata($0) }
    }

    private func foglio(_ r: inout RitornoAllaGuida, _ stati: [Bool]) -> [PassoGuidato?] {
        stati.map { r.foglioWidget(aperto: $0) }
    }

    @Test("Lasciata la pagina delle rose (salvate o «indietro») la guida si riapre dalle rose, una volta sola")
    func siRiapreUnaVolta() {
        var r = RitornoAllaGuida()
        r.chiesta(.pagina(.importa), dalPasso: .rose)
        #expect(r.attivo(per: .importa))
        let aperta = segui(&r, [[.importa]])
        #expect(aperta == [nil], "la pagina delle rose è aperta: la guida aspetta")
        #expect(r.attivo(per: .importa))
        let lasciata = segui(&r, [[]])
        #expect(lasciata == [.rose], "pagina lasciata: la guida si riapre")
        #expect(!r.attivo(per: .importa))
        let dopo = segui(&r, [[.importa], []])
        #expect(dopo == [nil, nil], "la volta dopo la pagina è aperta dalle Impostazioni: niente guida")
    }

    @Test("Aperta dalle Impostazioni o dalla Formazione, senza la guida, lasciarla non apre niente")
    func senzaGuida() {
        var r = RitornoAllaGuida()
        #expect(!r.attivo(per: .importa))
        let risposte = segui(&r, [[.importa], []])
        #expect(risposte == [nil, nil])
        let widget = foglio(&r, [true, false])
        #expect(widget == [nil, nil])
    }

    @Test("La pagina non si è aperta (Regole con modifiche da salvare) e si torna indietro: niente guida a sorpresa dopo")
    func paginaMaiAperta() {
        var r = RitornoAllaGuida()
        r.chiesta(.pagina(.importa), dalPasso: .rose)
        let indietro = segui(&r, [[]])
        #expect(indietro == [nil])
        #expect(!r.attivo(per: .importa))
        let dopo = segui(&r, [[.importa], []])
        #expect(dopo == [nil, nil])
    }

    @Test("La scelta della squadra: anche aprendo una rosa dall'elenco, la guida torna quando si lascia l'elenco")
    func squadra() {
        var r = RitornoAllaGuida()
        r.chiesta(.pagina(.squadre), dalPasso: .squadra)
        #expect(!r.attivo(per: .importa), "solo la pagina delle rose si chiude da sola dopo il salvataggio")
        let pile = segui(&r, [[.squadre], [.squadre, .rosa("Squadra di prova")], [.squadre], []])
        #expect(pile == [nil, nil, nil, .squadra])
    }

    @Test("Stemma e maglia nella rosa della tua squadra: lasciata la rosa, la guida torna dallo stemma")
    func stemma() {
        var r = RitornoAllaGuida()
        r.chiesta(.pagina(.rosa("Squadra di prova")), dalPasso: .stemma)
        let pile = segui(&r, [[.rosa("Squadra di prova")], []])
        #expect(pile == [nil, .stemma])
    }

    @Test("«Collega il widget»: chiuso il foglio la guida torna dal widget; la pila delle Impostazioni non c'entra")
    func widget() {
        var r = RitornoAllaGuida()
        r.chiesta(.widget, dalPasso: .widget)
        let pile = segui(&r, [[.importa], []])
        #expect(pile == [nil, nil])
        let stati = foglio(&r, [true, false, false])
        #expect(stati == [nil, .widget, nil])
    }
}

@MainActor
@Suite("La guida riaperta dopo una pagina sa da quale passo ripartire (#880)", .serialized)
struct RiapriGuidaTests {
    @Test("Riaperta sulla Formazione con il passo da cui ripartire; chiusa, il passo si dimentica")
    func riapri() {
        let prima = UserDefaults.standard.string(forKey: "ultimaSezione")
        defer { UserDefaults.standard.set(prima, forKey: "ultimaSezione") }
        let nav = Navigazione()
        nav.sezione = .impostazioni
        nav.riapriGuida(da: .stemma)
        #expect(nav.guidaAperta)
        #expect(nav.sezione == .formazione)
        #expect(nav.guidaRiprendeDa == .stemma)
        nav.guidaAperta = false
        #expect(nav.guidaRiprendeDa == nil, "aperta dopo da «Da fare» o da sola, la guida riparte dall'inizio")
    }
}

// MARK: 4. la pagina delle rose al primo caricamento

@MainActor
@Suite("Importa le rose al primo caricamento: i testi del primo avvio della web (#880)")
struct RoseAlPrimoCaricamentoTests {
    private func server(stato: String?) -> ServerDiProva {
        ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/stato"), let stato { return Data(stato.utf8) }
            if percorso.hasPrefix("/api/rose/anteprima") { return Data(AnteprimaRoseTests.risposta.utf8) }
            if percorso.hasPrefix("/api/rose/testo") {
                return Data(#"{"squadre_importate": ["Squadra di prova"], "totale_squadre": 1, "riepilogo": "Fatto"}"#.utf8)
            }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    @Test("Senza rose salvate: «Importa le rose», la frase del passo «Le rose» della web, niente «Togli le squadre…»")
    func primoCaricamento() async {
        let vm = ImportaExcelViewModel(server: server(stato: #"{"rose_importate": false, "mia_squadra": null}"#))
        await vm.leggiRoseSalvate()
        #expect(vm.primoCaricamento)
        #expect(vm.titolo == Catalogo.Comune.importaRose)
        #expect(vm.spiegazione == Catalogo.Pav.incollaTestoDelle)
    }

    @Test("Con le rose salvate, o se il server non lo dice, la pagina di sempre",
          arguments: [#"{"rose_importate": true}"#, #"{"stagione": "2026-27"}"#, nil])
    func paginaDiSempre(stato: String?) async {
        let vm = ImportaExcelViewModel(server: server(stato: stato))
        await vm.leggiRoseSalvate()
        #expect(!vm.primoCaricamento)
        #expect(vm.titolo == Catalogo.Lega.voceImporta)
        #expect(vm.spiegazione == Catalogo.Lega.esportaRoseExcel)
    }

    @Test("Salvate le prime rose, la pagina torna quella di sempre (con «Togli le squadre…»)")
    func dopoLePrimeRose() async {
        let s = server(stato: #"{"rose_importate": false}"#)
        let vm = ImportaExcelViewModel(server: s)
        await vm.leggiRoseSalvate()
        #expect(vm.primoCaricamento)
        vm.testoRose = "Squadra di prova\nOddone"
        await vm.importaTesto()
        await vm.conferma()
        #expect(vm.esito != nil)
        #expect(!vm.primoCaricamento)
        #expect(vm.titolo == Catalogo.Lega.voceImporta)
    }

    @Test("Arrivando dalla guida si sa già che le rose mancano: i testi del primo caricamento subito, senza aspettare il server")
    func dallaGuidaSubito() {
        let vm = ImportaExcelViewModel(server: server(stato: nil), roseSalvate: false)
        #expect(vm.primoCaricamento)
        #expect(vm.titolo == Catalogo.Comune.importaRose)
        #expect(vm.spiegazione == Catalogo.Pav.incollaTestoDelle)
        #expect(!vm.mostraPerChiHaLeRose)
    }

    @Test("Finché non si sa se le rose ci sono, niente titolo né frasi che potrebbero essere sbagliate; poi la pagina giusta")
    func finoAQuandoNonSiSa() async {
        let vm = ImportaExcelViewModel(server: server(stato: nil))
        #expect(vm.titolo.isEmpty)
        #expect(vm.spiegazione == nil)
        #expect(!vm.mostraPerChiHaLeRose)
        await vm.leggiRoseSalvate()                 // il server non risponde: la pagina di sempre
        #expect(vm.titolo == Catalogo.Lega.voceImporta)
        #expect(vm.spiegazione == Catalogo.Lega.esportaRoseExcel)
        #expect(vm.mostraPerChiHaLeRose)
    }

    /// Le squadre già lette dalle Impostazioni (`/api/squadre`), scritte come le manda il server.
    private func squadre(_ json: String) throws -> [SquadraLega] {
        try Decodifica.decodifica(Data(json.utf8))
    }

    @Test("Cosa si sa delle rose aprendo la pagina: dalle squadre già lette, altrimenti dalla guida, altrimenti niente")
    func roseNote() throws {
        let una = try squadre(#"[{"nome": "Squadra di prova", "mia": true, "giocatori": 25}]"#)
        #expect(ImportaExcelViewModel.roseNote(dallaGuida: false, squadre: una) == true)
        #expect(ImportaExcelViewModel.roseNote(dallaGuida: false, squadre: []) == false)
        #expect(ImportaExcelViewModel.roseNote(dallaGuida: true, squadre: nil) == false)
        #expect(ImportaExcelViewModel.roseNote(dallaGuida: false, squadre: nil) == nil)
        #expect(ImportaExcelViewModel.roseNote(dallaGuida: true, squadre: una) == true, "le squadre lette vincono")
    }
}

// MARK: 5. rientro dopo «Esci»

@MainActor
@Suite("«Esci» e nuovo accesso: si rientra dove si apre l'app, non sulle Impostazioni (#880)", .serialized)
struct UscitaTornaAllAvvioTests {
    @Test("Usciti dalle Impostazioni si rientra sulla Formazione, o su Giornate se era l'ultima delle due")
    func tornaAllAvvio() throws {
        let prima = UserDefaults.standard.string(forKey: "ultimaSezione")
        defer { UserDefaults.standard.set(prima, forKey: "ultimaSezione") }
        let nomeSuite = "prova-uscita-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nomeSuite))
        defer { memoria.removePersistentDomain(forName: nomeSuite) }
        let nav = Navigazione()
        nav.sezione = .impostazioni
        nav.uscitoDallAccount(memoria: memoria)
        #expect(nav.sezione == .formazione)
        memoria.set("giornate", forKey: "ultimaSezione")
        nav.sezione = .impostazioni
        nav.uscitoDallAccount(memoria: memoria)
        #expect(nav.sezione == .giornate)
    }
}

// MARK: 6. il link d'invito incollato

@Suite("Codice d'invito: va bene anche il link incollato, letto come la web (#880)")
struct CodiceInvitoDalLinkTests {
    @Test("Il codice scritto a mano parte come prima: senza spazi ai lati e in maiuscolo",
          arguments: [(" inv-123 ", "INV-123"), ("abcd-efgh-2345", "ABCD-EFGH-2345"), ("", ""), ("X", "X")])
    func scritto(scritto: String, atteso: String) {
        #expect(CodiceInvito.daCampo(scritto) == atteso)
    }

    @Test("Dal link d'invito (`https://<indirizzo>/?invito=CODICE`) si prende il codice, come `invitoDaIndirizzo` della web",
          arguments: [
              ("https://esempio.invalid/?invito=AbCd-2345-EfGh", "ABCD-2345-EFGH"),
              ("  https://esempio.invalid/?invito=abcd-2345 \n", "ABCD-2345"),
              ("https://esempio.invalid/?vista=formazione&invito=ABCD-2345", "ABCD-2345"),
              ("https://esempio.invalid/?invito=ABCD%2D2345", "ABCD-2345"),
              ("https://esempio.invalid/?invito=ABCD-2345.", "ABCD-2345"),
              ("esempio.invalid/?invito=abcd-2345", "ABCD-2345"),
          ])
    func dalLink(incollato: String, atteso: String) {
        #expect(CodiceInvito.daCampo(incollato) == atteso)
    }

    @Test("Incollato tutto il messaggio d'invito, si prende il codice del link che c'è dentro")
    func dalMessaggio() {
        let messaggio = "Ti invito su SchieraXI, l'app che ti consiglia la formazione del fantacalcio. Apri questo link e crea il tuo "
            + "account (il codice d'invito è già dentro, vale 7 giorni): https://esempio.invalid/?invito=abcd-2345"
        #expect(CodiceInvito.daCampo(messaggio) == "ABCD-2345")
    }

    @Test("Registrandosi con il link incollato al server parte solo il codice")
    @MainActor
    func registrazioneConIlLink() async throws {
        let nomeSuite = "prova-invito-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nomeSuite))
        defer { memoria.removePersistentDomain(forName: nomeSuite) }
        memoria.set(true, forKey: "account.multiutente")
        let utente = #"{"id": 7, "nome_utente": "mister.rossi", "ruolo": "utente", "creato": "2026-10-29"}"#
        let server = ServerDiProva { _, percorso, _ in
            if percorso == "/api/account/registra" {
                return Data(#"{"multiutente": true, "utente": \#(utente), "token": "tok-2", "codice_recupero": "AAAAA-BBBBB-CCCCC"}"#.utf8)
            }
            return Data(#"{"ok": true}"#.utf8)
        }
        let sessione = SessioneAccount(server: server, archivio: MemoriaToken(), memoria: memoria, pulisci: {})
        try await sessione.registra(nomeUtente: "mister.rossi", password: "Prova-Finta-Zero",
                                    invito: "https://esempio.invalid/?invito=abcd-2345")
        let dati = try #require(server.corpiInviati(a: "/registra").first)
        let corpo = try #require(try JSONSerialization.jsonObject(with: dati) as? [String: Any])
        #expect(corpo["invito"] as? String == "ABCD-2345")
    }
}
