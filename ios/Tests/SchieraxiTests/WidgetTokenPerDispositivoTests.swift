import Foundation
import Testing
@testable import Schieraxi

// 26/11/2026. Lo stesso account su iPhone e iPad: ogni dispositivo ha il suo token del widget. Quando il server rifiuta il token del
// widget (401: revocato, scaduto, sostituito), il widget lascia un segnale nella cartella del gruppo (`SegnaleWidget`) e l'app,
// all'apertura o nell'aggiornamento in background, dimentica quel token e ne chiede uno nuovo; «Collega» ne chiede sempre uno nuovo.
// Una lettura della giornata partita prima di «Esci» non riscrive il riassunto dell'account uscito (`Aggiornamento.elabora`).
// Indirizzi e token finti (.invalid); ogni test ha la sua cartella, le sue UserDefaults e i suoi archivi, niente stato in comune.

private let indirizzoProva = "https://token-dispositivo.invalid"
private let tokenVecchio = "fw_vecchioDiProva123456"
private let tokenNuovo = "fw_nuovoDiProva1234567"
private let tokenAltro = "fw_altroDiProva12345678"

private func impronta(_ token: String?) -> String {
    MemoriaWidget.impronta(indirizzo: indirizzoProva, token: token)
}

/// Un server finto che dà `token` a `POST /api/account/token-widget`; senza token non risponde (rete giù).
private func serverDiProva(token: String? = tokenNuovo) -> ServerDiProva {
    ServerDiProva(indirizzo: indirizzoProva) { metodo, percorso, _ in
        guard metodo == "POST", percorso == "/api/account/token-widget", let token else { throw ErroreApi.rete("spento") }
        return Data(#"{"token": "\#(token)", "scade": "2027-02-24T12:00:00+00:00", "etichetta": "widget"}"#.utf8)
    }
}

/// La cartella del gruppo, le UserDefaults, il token del widget e quello della sessione di un solo test.
private struct PostiDiProva {
    let cartella: URL
    let memoria: UserDefaults
    let widget = MemoriaToken()
    let sessione = MemoriaToken()
    private let nome: String

    init() throws {
        cartella = FileManager.default.temporaryDirectory.appendingPathComponent("token-dispositivo-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        nome = "prova-token-dispositivo-\(UUID().uuidString)"
        memoria = try #require(UserDefaults(suiteName: nome))
        sessione.salva("sessione-di-prova", server: indirizzoProva)
    }

    /// L'app ha questo token del widget e scade fra molto: senza un motivo non ne chiederebbe un altro.
    func conToken(_ token: String) {
        widget.salva(token, server: indirizzoProva)
        memoria.set("2099-01-01T00:00:00", forKey: "tokenWidgetScade|" + indirizzoProva)
    }

    var luoghi: TokenWidget.Luoghi {
        let c = cartella
        return TokenWidget.Luoghi(archivio: widget, memoria: memoria, cartella: { c }, portachiavi: MemoriaCollegamento(), sincronizza: {})
    }

    func togli() {
        try? FileManager.default.removeItem(at: cartella)
        memoria.removePersistentDomain(forName: nome)
    }
}

@Suite("Un token del widget per dispositivo e il segnale del 401")
struct WidgetTokenPerDispositivoTests {
    @Test("Il 401 con un token lascia il segnale per l'app, con l'impronta e mai il token; senza token niente")
    func segnaleDelWidget() throws {
        let p = try PostiDiProva()
        defer { p.togli() }
        let senza = MemoriaWidget.applica(.accessoRichiesto, copia: nil, chi: impronta(nil), conToken: false, cartella: p.cartella, memoria: p.memoria)
        #expect(senza.accessoRichiesto)
        #expect(SegnaleWidget.leggi(cartella: p.cartella) == nil, "senza token non c'è niente da rinnovare")

        let con = MemoriaWidget.applica(.accessoRichiesto, copia: nil, chi: impronta(tokenVecchio), conToken: true, cartella: p.cartella,
                                        memoria: p.memoria)
        #expect(con.accessoRichiesto)
        #expect(con.copia == nil, "con un 401 niente dati vecchi, come prima")
        let segnale = try #require(SegnaleWidget.leggi(cartella: p.cartella))
        #expect(segnale.chi == impronta(tokenVecchio))
        let file = try String(contentsOf: p.cartella.appendingPathComponent("widget-rifiutato.json"), encoding: .utf8)
        #expect(!file.contains("fw_"), "nel segnale c'è l'impronta, mai il token")

        // il ripiego del widget su /api/oggi passa da qui
        SegnaleWidget.cancella(cartella: p.cartella)
        MemoriaWidget.accessoNegato(segnala: impronta(tokenVecchio), cartella: p.cartella, memoria: p.memoria)
        #expect(SegnaleWidget.leggi(cartella: p.cartella)?.chi == impronta(tokenVecchio))
    }

    @Test("Al segnale l'app dimentica il token rifiutato e ne chiede uno nuovo; il segnale se ne va")
    func segnaleENuovoToken() async throws {
        let p = try PostiDiProva()
        defer { p.togli() }
        p.conToken(tokenVecchio)
        Condiviso.aggiorna(cartella: p.cartella) {
            $0.indirizzo = indirizzoProva
            $0.token = tokenVecchio
            $0.tokenPerIndirizzo = indirizzoProva
        }
        SegnaleWidget.scrivi(chi: impronta(tokenVecchio), cartella: p.cartella)
        #expect(TokenWidget.rifiutato(tokenVecchio, indirizzo: indirizzoProva, cartella: p.cartella))

        let server = serverDiProva()
        await TokenWidget.assicura(server: server, luoghi: p.luoghi, sessione: p.sessione)

        #expect(server.quante("POST /api/account/token-widget") == 1)
        #expect(p.widget.leggi(server: indirizzoProva) == tokenNuovo)
        #expect(Condiviso.leggi(cartella: p.cartella).token == nil, "il token rifiutato non resta nel file condiviso")
        #expect(SegnaleWidget.leggi(cartella: p.cartella) == nil, "il segnale letto se ne va")
        #expect(!TokenWidget.rifiutato(tokenNuovo, indirizzo: indirizzoProva, cartella: p.cartella))
    }

    @Test("Senza segnale un token buono non si chiede di nuovo; un segnale per un altro token si toglie e basta")
    func segnaleDiUnAltroToken() async throws {
        let p = try PostiDiProva()
        defer { p.togli() }
        p.conToken(tokenVecchio)
        let server = serverDiProva()
        await TokenWidget.assicura(server: server, luoghi: p.luoghi, sessione: p.sessione)
        #expect(server.quante("token-widget") == 0)

        // un codice incollato di un altro account, o un token che l'app ha già sostituito
        SegnaleWidget.scrivi(chi: impronta(tokenAltro), cartella: p.cartella)
        #expect(!TokenWidget.rifiutato(tokenVecchio, indirizzo: indirizzoProva, cartella: p.cartella))
        await TokenWidget.assicura(server: server, luoghi: p.luoghi, sessione: p.sessione)
        #expect(server.quante("token-widget") == 0)
        #expect(p.widget.leggi(server: indirizzoProva) == tokenVecchio)
        #expect(SegnaleWidget.leggi(cartella: p.cartella) == nil)
    }

    @Test("Se il token nuovo non arriva, quello rifiutato non resta e si chiede di nuovo alla volta dopo")
    func segnaleSenzaRete() async throws {
        let p = try PostiDiProva()
        defer { p.togli() }
        p.conToken(tokenVecchio)
        SegnaleWidget.scrivi(chi: impronta(tokenVecchio), cartella: p.cartella)

        let giu = serverDiProva(token: nil)
        await TokenWidget.assicura(server: giu, luoghi: p.luoghi, sessione: p.sessione)
        #expect(giu.quante("POST /api/account/token-widget") == 1)
        #expect(p.widget.leggi(server: indirizzoProva) == nil, "il token rifiutato non resta sul telefono")

        let su = serverDiProva()
        await TokenWidget.assicura(server: su, luoghi: p.luoghi, sessione: p.sessione)
        #expect(su.quante("POST /api/account/token-widget") == 1)
        #expect(p.widget.leggi(server: indirizzoProva) == tokenNuovo)
    }

    @Test("«Collega» chiede sempre un token nuovo, anche con uno che sembra buono")
    func collegaChiedeSempre() async throws {
        let p = try PostiDiProva()
        defer { p.togli() }
        p.conToken(tokenVecchio)
        let server = serverDiProva()
        let dato = await TokenWidget.nuovo(server: server, luoghi: p.luoghi, sessione: p.sessione)
        #expect(dato == tokenNuovo)
        #expect(server.quante("POST /api/account/token-widget") == 1)
        #expect(p.widget.leggi(server: indirizzoProva) == tokenNuovo)
    }

    @Test("«Collega» senza risposta del server: nessun token da dare al widget, sul telefono resta quello di prima")
    func collegaSenzaRete() async throws {
        let p = try PostiDiProva()
        defer { p.togli() }
        p.conToken(tokenVecchio)
        let dato = await TokenWidget.nuovo(server: serverDiProva(token: nil), luoghi: p.luoghi, sessione: p.sessione)
        #expect(dato == nil, "«Collega» non dice «collegato» con il token di prima")
        #expect(p.widget.leggi(server: indirizzoProva) == tokenVecchio)
    }

    @Test("Un token nuovo arrivato dopo un cambio di sessione non si tiene")
    func tokenDopoIlCambioDiSessione() async throws {
        let p = try PostiDiProva()
        defer { p.togli() }
        let sessione = p.sessione
        let server = ServerDiProva(indirizzo: indirizzoProva) { _, _, _ in
            sessione.cancella(server: indirizzoProva)      // «Esci» mentre il server risponde
            return Data(#"{"token": "\#(tokenNuovo)", "scade": "2027-02-24T12:00:00+00:00"}"#.utf8)
        }
        let dato = await TokenWidget.nuovo(server: server, luoghi: p.luoghi, sessione: sessione)
        #expect(dato == nil)
        #expect(p.widget.leggi(server: indirizzoProva) == nil)
    }
}

@Suite("Una lettura della giornata partita prima di «Esci»")
struct LetturaPrimaDellUscitaTests {
    @Test("Chi legge: con la stessa sessione sì; dopo «Esci» o con un altro accesso no")
    func chiLegge() {
        let sessione = MemoriaToken()
        sessione.salva("sessione-a", server: indirizzoProva)
        let chi = ChiLegge.adesso(indirizzo: indirizzoProva, sessione: sessione)
        #expect(chi.ancoraLui(sessione))
        sessione.salva("sessione-b", server: indirizzoProva)
        #expect(!chi.ancoraLui(sessione), "un altro accesso")
        sessione.cancella(server: indirizzoProva)
        #expect(!chi.ancoraLui(sessione), "dopo «Esci»")
        let senzaAccount = ChiLegge.adesso(indirizzo: indirizzoProva, sessione: MemoriaToken())
        #expect(senzaAccount.ancoraLui(MemoriaToken()), "un server senza account: nessuna sessione, prima e dopo")
    }

    /// Solo i casi in cui `elabora` si ferma prima dei promemoria: con la stessa sessione passerebbe dal centro delle notifiche di
    /// iOS, che nei test non si tocca (che la stessa sessione vada avanti lo dice `chiLegge`).
    @Test("Con la sessione cambiata `elabora` non scrive il riassunto nel file condiviso")
    func elaboraConLaSessioneCambiata() async throws {
        let cartella = FileManager.default.temporaryDirectory.appendingPathComponent("elabora-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: cartella) }
        let oggi: Oggi = try Decodifica.decodifica(try Fixture.dati("oggi"))
        let chiesta = Date(timeIntervalSince1970: 1_800_000_000)
        let sessione = MemoriaToken()
        sessione.salva("sessione-a", server: indirizzoProva)
        let chi = ChiLegge.adesso(indirizzo: indirizzoProva, sessione: sessione)

        sessione.cancella(server: indirizzoProva)        // «Esci» mentre la lettura era in viaggio
        await Aggiornamento.elabora(oggi, chiestaIl: chiesta, di: chi, sessione: sessione, cartella: cartella)
        #expect(Condiviso.leggi(cartella: cartella).riassunto == nil, "dopo «Esci» niente riassunto dell'account uscito")

        sessione.salva("sessione-b", server: indirizzoProva)     // un altro accesso
        await Aggiornamento.elabora(oggi, chiestaIl: chiesta, di: chi, sessione: sessione, cartella: cartella)
        #expect(Condiviso.leggi(cartella: cartella).riassunto == nil, "né sopra quello di un altro account")
    }
}
