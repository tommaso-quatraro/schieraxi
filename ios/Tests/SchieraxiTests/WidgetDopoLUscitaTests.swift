import Foundation
import Testing
@testable import Schieraxi

// Issue #482. Dopo l'uscita dall'account il widget non mostra più niente dell'account di prima, anche quando la cartella condivisa
// (App Group) manca e la copia del widget sta nelle UserDefaults del widget, che l'app non raggiunge. Ogni copia porta l'impronta
// del collegamento con cui è stata scaricata (indirizzo e token): con un collegamento diverso non si mostra.
// Indirizzi e token finti (.invalid); ogni test ha la sua cartella e le sue UserDefaults, niente stato in comune.

private let indirizzoProva = "https://esempio.invalid"
private let pubblicoProva = "https://pubblico.invalid"
private let tokenUno = "fw_tokenAccountUno123456"
private let tokenDue = "fw_tokenAccountDue123456"
private let riassuntoProva = RiassuntoOggi(giornata: 11, inizio: nil, modulo: "3-4-3", punti: 64.5, daControllare: 1, probabili: true,
                                           scaricatoIl: Date(timeIntervalSince1970: 1_800_000_000))

private func impronta(_ token: String?, indirizzo: String = indirizzoProva) -> String {
    MemoriaWidget.impronta(indirizzo: indirizzo, token: token)
}

private func copiaProva(_ chi: String?) -> CopiaWidget {
    CopiaWidget(dati: Data(WidgetRiassuntoTests.corpo.utf8), etag: "\"e1\"", scaricatoIl: Date(timeIntervalSince1970: 1_800_000_000), chi: chi)
}

/// La cartella del gruppo, le UserDefaults dell'app e quelle del widget, e il Keychain condiviso: solo per un test.
private struct PostiWidgetDiProva {
    let cartella: URL
    let app: UserDefaults
    let widget: UserDefaults
    let portachiavi = MemoriaCollegamento()
    private let nomeApp: String
    private let nomeWidget: String

    init() throws {
        cartella = FileManager.default.temporaryDirectory.appendingPathComponent("widget-482-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        nomeApp = "prova-482-app-\(UUID().uuidString)"
        nomeWidget = "prova-482-widget-\(UUID().uuidString)"
        app = try #require(UserDefaults(suiteName: nomeApp))
        widget = try #require(UserDefaults(suiteName: nomeWidget))
    }

    func togli() {
        try? FileManager.default.removeItem(at: cartella)
        app.removePersistentDomain(forName: nomeApp)
        widget.removePersistentDomain(forName: nomeWidget)
    }

    /// Dove scarica il widget senza cartella condivisa e senza codice incollato (come `ScaricaOggi.destinazione`).
    func destinazioneSenzaGruppo() -> (indirizzo: String, token: String?)? {
        let collegamento = portachiavi.leggi().flatMap { try? JSONDecoder().decode(CodiceWidget.Contenuto.self, from: $0) }
        return CodiceWidget.destinazione(condiviso: Condiviso.leggi(cartella: nil), portachiavi: collegamento, codice: "",
                                         predefinito: pubblicoProva, pulisci: { $0 })
    }
}

@Suite("Widget dopo l'uscita dall'account (#482)")
@MainActor
struct WidgetDopoLUscitaTests {
    @Test("La copia del widget si ricorda, si mostra solo con lo stesso collegamento e poi si dimentica")
    func copiaSoloDelCollegamento() throws {
        let p = try PostiWidgetDiProva()
        defer { p.togli() }
        #expect(MemoriaWidget.leggi(per: impronta(tokenUno), cartella: p.cartella, memoria: p.widget) == nil)
        MemoriaWidget.salva(copiaProva(impronta(tokenUno)), cartella: p.cartella, memoria: p.widget)
        let letta = try #require(MemoriaWidget.leggi(per: impronta(tokenUno), cartella: p.cartella, memoria: p.widget))
        #expect(letta.etag == "\"e1\"")
        #expect(letta.riassunto?.giornata == 11)
        #expect(MemoriaWidget.leggi(per: impronta(tokenDue), cartella: p.cartella, memoria: p.widget) == nil, "un altro account")
        #expect(MemoriaWidget.leggi(per: impronta(nil), cartella: p.cartella, memoria: p.widget) == nil, "dopo l'uscita: senza token")
        #expect(MemoriaWidget.leggi(per: impronta(tokenUno, indirizzo: pubblicoProva), cartella: p.cartella, memoria: p.widget) == nil,
                "un altro server")
        MemoriaWidget.dimentica(cartella: p.cartella, memoria: p.widget)
        #expect(MemoriaWidget.leggi(per: impronta(tokenUno), cartella: p.cartella, memoria: p.widget) == nil)
    }

    @Test("Una copia di prima delle impronte non si mostra")
    func copiaSenzaImpronta() throws {
        let p = try PostiWidgetDiProva()
        defer { p.togli() }
        MemoriaWidget.salva(copiaProva(nil), cartella: nil, memoria: p.widget)
        #expect(MemoriaWidget.leggi(per: impronta(tokenUno), cartella: nil, memoria: p.widget) == nil)
        #expect(MemoriaWidget.leggi(per: impronta(nil), cartella: nil, memoria: p.widget) == nil)
    }

    @Test("L'impronta: uguale per lo stesso collegamento, diversa per un altro; il token non si legge")
    func improntaDelCollegamento() {
        let uno = impronta(tokenUno)
        #expect(uno == impronta(tokenUno, indirizzo: " " + indirizzoProva + "/ "), "spazi e «/» finali non contano")
        #expect(uno != impronta(tokenDue))
        #expect(uno != impronta(nil))
        #expect(uno != impronta(tokenUno, indirizzo: pubblicoProva))
        #expect(!uno.contains(tokenUno))
        #expect(!uno.contains("fw_"))
    }

    @Test("Uscita con la cartella condivisa: nessun dato del widget leggibile e i widget si ricaricano")
    func uscitaConGruppo() throws {
        let p = try PostiWidgetDiProva()
        defer { p.togli() }
        // prima: l'app ha passato indirizzo, token e riassunto; il Keychain condiviso ha il collegamento; c'è la copia di /api/widget
        // nel gruppo e una vecchia nelle UserDefaults dell'app
        Condiviso.aggiorna(cartella: p.cartella) {
            $0.indirizzo = indirizzoProva
            $0.token = tokenUno
            $0.tokenPerIndirizzo = indirizzoProva
            $0.riassunto = riassuntoProva
        }
        let collegamento = try JSONEncoder().encode(CodiceWidget.Contenuto(i: indirizzoProva, t: tokenUno))
        #expect(p.portachiavi.scrivi(collegamento, gruppi: ["SQUADRA.it.schieraxi.app.condiviso"]) != nil)
        MemoriaWidget.salva(copiaProva(impronta(tokenUno)), cartella: nil, memoria: p.app)
        MemoriaWidget.salva(copiaProva(impronta(tokenUno)), cartella: p.cartella, memoria: p.widget)
        try #require(MemoriaWidget.leggi(per: impronta(tokenUno), cartella: p.cartella, memoria: p.widget) != nil)
        try #require(MemoriaWidget.leggi(per: impronta(tokenUno), cartella: nil, memoria: p.app) != nil)

        var ricariche = 0
        DatiLocali.dimenticaIlWidget(cartella: p.cartella, memoria: p.app, portachiavi: p.portachiavi, ricarica: { ricariche += 1 })

        let condiviso = Condiviso.leggi(cartella: p.cartella)
        #expect(condiviso.token == nil)
        #expect(condiviso.riassunto == nil)
        #expect(p.portachiavi.leggi() == nil, "il Keychain condiviso")
        for chi in [impronta(tokenUno), impronta(nil)] {
            #expect(MemoriaWidget.leggi(per: chi, cartella: p.cartella, memoria: p.app) == nil, "la copia nel gruppo")
            #expect(MemoriaWidget.leggi(per: chi, cartella: nil, memoria: p.app) == nil, "la copia nelle UserDefaults dell'app")
        }
        #expect(ricariche == 1, "i widget si ridisegnano subito, senza i dati di prima")
    }

    @Test("Uscita senza cartella condivisa: la copia nelle UserDefaults del widget non si mostra più")
    func uscitaSenzaGruppo() throws {
        let p = try PostiWidgetDiProva()
        defer { p.togli() }
        // prima: il widget è collegato con il Keychain condiviso (account uno) e ha la sua copia nelle SUE UserDefaults
        let collegamento = try JSONEncoder().encode(CodiceWidget.Contenuto(i: indirizzoProva, t: tokenUno))
        #expect(p.portachiavi.scrivi(collegamento, gruppi: ["SQUADRA.it.schieraxi.app.condiviso"]) != nil)
        let prima = try #require(p.destinazioneSenzaGruppo())
        #expect(prima.token == tokenUno)
        let chiPrima = MemoriaWidget.impronta(indirizzo: prima.indirizzo, token: prima.token)
        MemoriaWidget.salva(copiaProva(chiPrima), cartella: nil, memoria: p.widget)
        try #require(MemoriaWidget.leggi(per: chiPrima, cartella: nil, memoria: p.widget) != nil)

        // l'uscita, dall'app: il gruppo non c'è e le UserDefaults del widget l'app non le raggiunge
        DatiLocali.dimenticaIlWidget(cartella: nil, memoria: p.app, portachiavi: p.portachiavi, ricarica: {})
        #expect(p.portachiavi.leggi() == nil)

        // il widget alla ricarica: il collegamento è cambiato (niente token), la copia dell'account uno non si mostra, nemmeno senza rete
        let dopo = try #require(p.destinazioneSenzaGruppo())
        #expect(dopo.token == nil)
        #expect(MemoriaWidget.leggi(per: MemoriaWidget.impronta(indirizzo: dopo.indirizzo, token: dopo.token), cartella: nil, memoria: p.widget) == nil)
        // al primo 401 il widget la cancella dalle sue UserDefaults
        MemoriaWidget.dimentica(cartella: nil, memoria: p.widget)
        #expect(MemoriaWidget.leggi(per: chiPrima, cartella: nil, memoria: p.widget) == nil)
    }

    @Test("Il riassunto dell'app solo al widget collegato come l'app")
    func riassuntoDellAppSoloAlloStessoCollegamento() {
        let condiviso = DatiCondivisi(indirizzo: indirizzoProva, token: tokenUno, tokenPerIndirizzo: indirizzoProva, riassunto: riassuntoProva)
        #expect(MemoriaWidget.riassuntoDellApp(condiviso, per: impronta(tokenUno)) == riassuntoProva)
        #expect(MemoriaWidget.riassuntoDellApp(condiviso, per: impronta(tokenDue)) == nil, "il widget usa il codice di un altro account")
        #expect(MemoriaWidget.riassuntoDellApp(condiviso, per: impronta(nil)) == nil)
        #expect(MemoriaWidget.riassuntoDellApp(DatiCondivisi(), per: impronta(nil)) == nil, "dopo l'uscita il file condiviso è vuoto")
    }
}
