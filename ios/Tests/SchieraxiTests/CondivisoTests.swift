import XCTest
@testable import Schieraxi

/// Dati condivisi tra app e widget (App Group): indirizzo, token e ultimo riassunto in un file del contenitore condiviso.
final class CondivisoTests: XCTestCase {
    private var cartella: URL!

    override func setUp() {
        super.setUp()
        cartella = FileManager.default.temporaryDirectory.appendingPathComponent("condiviso-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        Condiviso.cartellaDiProva = cartella
        PortachiaviCondiviso.archivio = MemoriaCollegamento()
    }

    override func tearDown() {
        Condiviso.cartellaDiProva = nil
        PortachiaviCondiviso.archivio = KeychainCollegamento()
        try? FileManager.default.removeItem(at: cartella)
        super.tearDown()
    }

    /// Un profilo come quello che SideStore mette nel pacchetto: un plist dentro una busta firmata (qui byte a caso intorno).
    private func profiloGrezzo(squadra: String = "ABCDE12345", gruppi: [String] = ["group.it.schieraxi.app.ABCDE12345"]) throws -> Data {
        let plist: [String: Any] = [
            "TeamIdentifier": [squadra],
            "Entitlements": [
                "application-identifier": squadra + ".it.schieraxi.app." + squadra,
                "com.apple.developer.team-identifier": squadra,
                "com.apple.security.application-groups": gruppi,
                "keychain-access-groups": [squadra + ".*"],
            ],
        ]
        let xml = try PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0)
        return Data([0x30, 0x82, 0x0F, 0x00, 0x06, 0x09]) + xml + Data([0xA0, 0x82, 0x00, 0x01, 0xFF])
    }

    func testIlProfiloDellaFirmaSiLegge() throws {
        let p = try XCTUnwrap(ProfiloFirma.leggi(try profiloGrezzo()))
        XCTAssertEqual(p.squadra, "ABCDE12345")
        XCTAssertEqual(p.gruppi, ["group.it.schieraxi.app.ABCDE12345"])
        XCTAssertEqual(p.gruppiPortachiavi, ["ABCDE12345.*"])
        XCTAssertEqual(p.identificativoApp, "ABCDE12345.it.schieraxi.app.ABCDE12345")
        XCTAssertNil(ProfiloFirma.leggi(Data("niente di utile".utf8)))
        XCTAssertNil(ProfiloFirma.leggi(Data()))
        // una squadra strana non si usa per costruire nomi
        XCTAssertNil(try XCTUnwrap(ProfiloFirma.leggi(try profiloGrezzo(squadra: "../../x"))).squadra)
    }

    func testLaSquadraDalBundleId() {
        XCTAssertEqual(ProfiloFirma.squadraDalBundle("it.schieraxi.app.ABCDE12345"), "ABCDE12345")
        XCTAssertEqual(ProfiloFirma.squadraDalBundle("it.schieraxi.app.ABCDE12345.widget"), "ABCDE12345")
        XCTAssertNil(ProfiloFirma.squadraDalBundle("it.schieraxi.app.widget"))
        XCTAssertNil(ProfiloFirma.squadraDalBundle("it.schieraxi.app"))
        XCTAssertNil(ProfiloFirma.squadraDalBundle(nil))
    }

    func testSenzaALTAppGroupsIlGruppoVieneDalProfilo() throws {
        // SideStore da settembre 2026 non scrive più ALTAppGroups: il nome vero si legge dal profilo, poi si ricostruisce con la squadra
        let p = try XCTUnwrap(ProfiloFirma.leggi(try profiloGrezzo(gruppi: ["group.it.schieraxi.app.ABCDE12345", "group.altro.invalid"])))
        XCTAssertEqual(Condiviso.identificativi(info: [:], profilo: p, bundle: "it.schieraxi.app.ABCDE12345.widget"),
                       ["group.it.schieraxi.app.ABCDE12345", "group.it.schieraxi.app"])
        // senza profilo basta il bundle id con la squadra
        XCTAssertEqual(Condiviso.identificativi(info: nil, profilo: nil, bundle: "it.schieraxi.app.ZZZZZ99999"),
                       ["group.it.schieraxi.app.ZZZZZ99999", "group.it.schieraxi.app"])
        // un gruppo che comincia solo per il nome base non è nostro
        XCTAssertEqual(Condiviso.identificativi(info: ["ALTAppGroups": ["group.it.schieraxi.appaltro"]], profilo: nil, bundle: nil),
                       ["group.it.schieraxi.app"])
    }

    func testIGruppiDelKeychainCondiviso() throws {
        let p = try XCTUnwrap(ProfiloFirma.leggi(try profiloGrezzo()))
        XCTAssertEqual(PortachiaviCondiviso.gruppiCandidati(profilo: p, bundle: "it.schieraxi.app.ABCDE12345"),
                       ["ABCDE12345.it.schieraxi.app.condiviso", "group.it.schieraxi.app.ABCDE12345"])
        XCTAssertEqual(PortachiaviCondiviso.gruppiCandidati(profilo: nil, bundle: "it.schieraxi.app"), [], "senza squadra non si scrive niente")
    }

    func testIlKeychainCondivisoPassaIndirizzoETokenDelWidget() {
        let archivio = MemoriaCollegamento(ammessi: ["ABCDE12345.it.schieraxi.app.condiviso"])
        PortachiaviCondiviso.archivio = archivio
        XCTAssertTrue(PortachiaviCondiviso.salva(indirizzo: "https://uno.invalid", token: "fw_tokenDiProva123456",
                                                 gruppi: ["group.non.concesso", "ABCDE12345.it.schieraxi.app.condiviso"]))
        XCTAssertEqual(PortachiaviCondiviso.leggi(), CodiceWidget.Contenuto(i: "https://uno.invalid", t: "fw_tokenDiProva123456"))
        // nessun gruppo concesso: niente collegamento automatico (e niente copia nel gruppo privato)
        XCTAssertFalse(PortachiaviCondiviso.salva(indirizzo: "https://uno.invalid", token: "fw_altroToken12345678", gruppi: ["group.non.concesso"]))
        XCTAssertNil(PortachiaviCondiviso.leggi())
        PortachiaviCondiviso.salva(indirizzo: "https://uno.invalid", token: nil, gruppi: ["ABCDE12345.it.schieraxi.app.condiviso"])
        XCTAssertEqual(PortachiaviCondiviso.leggi()?.i, "https://uno.invalid")
        XCTAssertNil(PortachiaviCondiviso.leggi()?.t, "server senza account: solo l'indirizzo")
        Condiviso.dimentica()
        XCTAssertNil(PortachiaviCondiviso.leggi(), "uscendo dall'account il widget perde anche il Keychain condiviso")
    }

    func testCollegamentoAutomatico() {
        XCTAssertTrue(CollegamentoWidget.automatico(canale: true, conAccount: true, haToken: true))
        XCTAssertTrue(CollegamentoWidget.automatico(canale: true, conAccount: false, haToken: false), "server senza account: basta l'indirizzo")
        XCTAssertFalse(CollegamentoWidget.automatico(canale: true, conAccount: true, haToken: false))
        XCTAssertFalse(CollegamentoWidget.automatico(canale: false, conAccount: true, haToken: true))
    }

    func testIdentificativiDaSideStore() {
        // SideStore riscrive il gruppo con un suffisso e lo mette in Info.plist (ALTAppGroups): si prova prima quello
        let info: [String: Any] = ["ALTAppGroups": ["group.it.schieraxi.app.ABCDE12345", "group.altro.invalid", "group.it.schieraxi.app.ABCDE12345"]]
        XCTAssertEqual(Condiviso.identificativi(info: info), ["group.it.schieraxi.app.ABCDE12345", "group.it.schieraxi.app"])
        XCTAssertEqual(Condiviso.identificativi(info: [:]), ["group.it.schieraxi.app"])
        XCTAssertEqual(Condiviso.identificativi(info: ["ALTAppGroups": "non una lista"]), ["group.it.schieraxi.app"])
        XCTAssertEqual(Condiviso.identificativi(info: nil), ["group.it.schieraxi.app"])
    }

    func testIndirizzoETokenSiScambiano() {
        XCTAssertNil(Condiviso.leggi().indirizzo)
        Condiviso.sincronizza(indirizzo: "https://uno.invalid", token: "abc123")
        let d = Condiviso.leggi()
        XCTAssertEqual(d.indirizzo, "https://uno.invalid")
        XCTAssertEqual(d.token(per: "https://uno.invalid"), "abc123")
        XCTAssertNil(d.token(per: "https://due.invalid"), "il token non va a un altro indirizzo")
    }

    func testCambiandoServerIlVecchioTokenSiTogliePoi() {
        Condiviso.sincronizza(indirizzo: "https://uno.invalid", token: "abc123")
        Condiviso.sincronizza(indirizzo: "https://due.invalid", token: nil)
        let d = Condiviso.leggi()
        XCTAssertEqual(d.indirizzo, "https://due.invalid")
        XCTAssertNil(d.token, "il token del server di prima non resta")
        XCTAssertNil(d.token(per: "https://due.invalid"))
    }

    func testDimenticaTogliTokenERiassunto() {
        Condiviso.sincronizza(indirizzo: "https://uno.invalid", token: "abc123")
        Condiviso.salvaRiassunto(RiassuntoOggi(giornata: 11, inizio: nil, modulo: "3-4-3", punti: 64.5, daControllare: 1, probabili: true, scaricatoIl: Date()))
        XCTAssertNotNil(Condiviso.leggi().riassunto)
        Condiviso.dimentica()
        let d = Condiviso.leggi()
        XCTAssertNil(d.token)
        XCTAssertNil(d.riassunto)
        XCTAssertEqual(d.indirizzo, "https://uno.invalid", "l'indirizzo è del telefono, non di un utente")
    }

    func testIlRiassuntoVieneDaOggi() throws {
        let oggi: Oggi = try Decodifica.decodifica(try Fixture.dati("oggi"))
        let r = RiassuntoOggi(oggi: oggi)
        XCTAssertEqual(r.giornata, oggi.giornata)
        XCTAssertEqual(r.modulo, oggi.formazione?.modulo)
        Condiviso.salvaRiassunto(r)
        XCTAssertEqual(Condiviso.leggi().riassunto?.giornata, oggi.giornata)
    }

    func testSenzaGruppoNonSuccedeNiente() {
        Condiviso.cartellaDiProva = nil
        // nel simulatore il gruppo può esistere o no: l'importante è che nessuna chiamata si rompa
        _ = Condiviso.disponibile
        _ = Condiviso.leggi()
        Condiviso.sincronizza(indirizzo: "https://x.invalid", token: nil)
        Condiviso.dimentica()
    }

    func testUnFileRovinatoSiIgnora() throws {
        try Data("non json".utf8).write(to: cartella.appendingPathComponent("condiviso.json"))
        XCTAssertEqual(Condiviso.leggi(), DatiCondivisi())
        Condiviso.sincronizza(indirizzo: "https://uno.invalid", token: nil)
        XCTAssertEqual(Condiviso.leggi().indirizzo, "https://uno.invalid", "si riscrive pulito")
    }
}

/// Il codice di collegamento del widget e la diagnostica della condivisione.
final class CodiceWidgetTests: XCTestCase {
    func testIlCodiceFaIlGiroCompleto() {
        let codice = CodiceWidget.crea(indirizzo: "https://uno.invalid:8443", token: "tok_abc-123")
        XCTAssertTrue(codice.hasPrefix("schieraxi1."))
        XCTAssertFalse(codice.contains("="), "senza il riempimento: si copia e si incolla meglio")
        XCTAssertFalse(codice.contains("+") || codice.contains("/"))
        let c = CodiceWidget.leggi(codice)
        XCTAssertEqual(c, CodiceWidget.Contenuto(i: "https://uno.invalid:8443", t: "tok_abc-123"))
    }

    func testSenzaTokenSoloIndirizzo() {
        let c = CodiceWidget.leggi(CodiceWidget.crea(indirizzo: "https://uno.invalid", token: nil))
        XCTAssertEqual(c?.i, "https://uno.invalid")
        XCTAssertNil(c?.t)
        XCTAssertNil(CodiceWidget.leggi(CodiceWidget.crea(indirizzo: "https://uno.invalid", token: ""))?.t)
    }

    func testSpaziEACapoIntornoSiIgnorano() {
        let codice = CodiceWidget.crea(indirizzo: "https://uno.invalid", token: "t")
        XCTAssertNotNil(CodiceWidget.leggi("  \n" + codice + "\n "))
    }

    func testUnIndirizzoSempliceVaBene() {
        XCTAssertEqual(CodiceWidget.leggi("https://uno.invalid")?.i, "https://uno.invalid")
    }

    func testCodiciSbagliatiONemiciNonRompono() {
        for cattivo in ["", "ciao", "schieraxi1.", "schieraxi1.!!!", "schieraxi1.e30", String(repeating: "a", count: 5000), "schieraxi1." + String(repeating: "A", count: 100)] {
            XCTAssertNil(CodiceWidget.leggi(cattivo), cattivo)
        }
    }

    // MARK: da dove il widget prende indirizzo e token

    /// Come `ScaricaOggi.indirizzoBase` del widget: solo https, senza «/» finale.
    private func pulisci(_ t: String) -> String? {
        var s = t.trimmingCharacters(in: .whitespacesAndNewlines)
        while s.hasSuffix("/") { s.removeLast() }
        return s.hasPrefix("https://") && s.count > 8 ? s : nil
    }

    private func dove(_ condiviso: DatiCondivisi = DatiCondivisi(), portachiavi: CodiceWidget.Contenuto? = nil, codice: String = "",
                      predefinito: String = "https://pubblico.invalid") -> (indirizzo: String, token: String?)? {
        CodiceWidget.destinazione(condiviso: condiviso, portachiavi: portachiavi, codice: codice, predefinito: predefinito, pulisci: pulisci)
    }

    func testSenzaAppGroupVinceIlCodiceIncollato() {
        let codice = CodiceWidget.crea(indirizzo: "https://uno.invalid", token: "fw_codiceIncollato123")
        let d = dove(codice: codice)
        XCTAssertEqual(d?.indirizzo, "https://uno.invalid")
        XCTAssertEqual(d?.token, "fw_codiceIncollato123")
    }

    func testIlKeychainCondivisoVinceSulCodiceMaNonSulGruppo() {
        let chiave = CodiceWidget.Contenuto(i: "https://chiave.invalid", t: "fw_dalKeychain1234567")
        let codice = CodiceWidget.crea(indirizzo: "https://uno.invalid", token: "fw_codiceIncollato123")
        XCTAssertEqual(dove(portachiavi: chiave, codice: codice)?.token, "fw_dalKeychain1234567", "automatico prima del manuale")
        let gruppo = DatiCondivisi(indirizzo: "https://app.invalid", token: "fw_dalGruppo12345678", tokenPerIndirizzo: "https://app.invalid")
        XCTAssertEqual(dove(gruppo, portachiavi: chiave)?.token, "fw_dalGruppo12345678")
        // Keychain senza token: vale il codice incollato; senza codice l'indirizzo del Keychain
        let soloIndirizzo = CodiceWidget.Contenuto(i: "https://chiave.invalid", t: nil)
        XCTAssertEqual(dove(portachiavi: soloIndirizzo, codice: codice)?.token, "fw_codiceIncollato123")
        XCTAssertEqual(dove(portachiavi: soloIndirizzo)?.indirizzo, "https://chiave.invalid")
        XCTAssertNil(dove(portachiavi: soloIndirizzo)?.token)
        // un indirizzo non ammesso nel Keychain non si usa
        XCTAssertEqual(dove(portachiavi: CodiceWidget.Contenuto(i: "http://chiaro.invalid", t: "fw_dalKeychain1234567"))?.indirizzo,
                       "https://pubblico.invalid")
    }

    func testAppGroupConTokenVinceSulCodice() {
        let gruppo = DatiCondivisi(indirizzo: "https://app.invalid", token: "fw_dalGruppo12345678", tokenPerIndirizzo: "https://app.invalid")
        let codice = CodiceWidget.crea(indirizzo: "https://uno.invalid", token: "fw_codiceIncollato123")
        let d = dove(gruppo, codice: codice)
        XCTAssertEqual(d?.indirizzo, "https://app.invalid")
        XCTAssertEqual(d?.token, "fw_dalGruppo12345678")
    }

    func testAppGroupSenzaTokenLasciaPassareIlCodice() {
        // il gruppo passa l'indirizzo ma non il token: il codice incollato deve valere, altrimenti il widget resta «da collegare»
        let gruppo = DatiCondivisi(indirizzo: "https://app.invalid")
        let codice = CodiceWidget.crea(indirizzo: "https://app.invalid", token: "fw_codiceIncollato123")
        XCTAssertEqual(dove(gruppo, codice: codice)?.token, "fw_codiceIncollato123")
        // senza codice resta l'indirizzo del gruppo, senza token
        let soloGruppo = dove(gruppo)
        XCTAssertEqual(soloGruppo?.indirizzo, "https://app.invalid")
        XCTAssertNil(soloGruppo?.token)
    }

    func testIlTokenDiUnAltroServerNonSiUsa() {
        let gruppo = DatiCondivisi(indirizzo: "https://app.invalid", token: "fw_altroServer123456", tokenPerIndirizzo: "https://altro.invalid")
        XCTAssertNil(dove(gruppo)?.token)
    }

    func testSenzaNienteValeIlServerPubblico() {
        // il widget non chiede più l'indirizzo: senza dati dell'app né codice usa il server pubblico (senza token)
        XCTAssertEqual(dove()?.indirizzo, "https://pubblico.invalid")
        XCTAssertNil(dove()?.token)
        XCTAssertEqual(dove(codice: "schieraxi1.!!!")?.indirizzo, "https://pubblico.invalid", "un codice rovinato si ignora")
        XCTAssertNil(dove(predefinito: "http://chiaro.invalid"), "solo https")
        XCTAssertEqual(ServerPubblico.indirizzo, Config.indirizzoPredefinito)
    }

    // MARK: «Tocca per collegare»

    func testQuandoIlWidgetVaCollegato() {
        XCTAssertTrue(CollegamentoWidget.daCollegare(haDati: false, indirizzoMancante: true, accessoRichiesto: false))
        XCTAssertTrue(CollegamentoWidget.daCollegare(haDati: false, indirizzoMancante: false, accessoRichiesto: true))
        XCTAssertTrue(CollegamentoWidget.daCollegare(haDati: true, indirizzoMancante: false, accessoRichiesto: true),
                      "codice non più valido: si ricollega anche se c'è una copia vecchia")
        XCTAssertFalse(CollegamentoWidget.daCollegare(haDati: false, indirizzoMancante: false, accessoRichiesto: false), "solo rete: si aspetta")
        XCTAssertFalse(CollegamentoWidget.daCollegare(haDati: true, indirizzoMancante: false, accessoRichiesto: false))
    }

    func testIlToccoDelWidgetApreCollegaIlWidget() throws {
        let url = try XCTUnwrap(CollegamentoWidget.url)
        XCTAssertEqual(Collegamenti.interpreta(url), .collegaWidget)
        XCTAssertEqual(Collegamenti.interpreta(try XCTUnwrap(URL(string: "schieraxi://widget"))), .collegaWidget)
        XCTAssertNil(Collegamenti.interpreta(try XCTUnwrap(URL(string: "schieraxi://widget/boh"))))
        XCTAssertLessThanOrEqual(CollegamentoWidget.durataAppunti, 10 * 60, "il codice negli appunti dura poco")
    }

    func testLaDiagnosticaDiceCosaManca() {
        let cartella = FileManager.default.temporaryDirectory.appendingPathComponent("diag-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        Condiviso.cartellaDiProva = cartella
        defer { Condiviso.cartellaDiProva = nil; try? FileManager.default.removeItem(at: cartella) }
        var d = Condiviso.diagnostica(info: ["ALTAppGroups": ["group.it.schieraxi.app.XYZ"]])
        XCTAssertEqual(d.scrittiDaSideStore, ["group.it.schieraxi.app.XYZ"])
        XCTAssertEqual(d.provati.first, "group.it.schieraxi.app.XYZ")
        XCTAssertFalse(d.filePresente)
        XCTAssertFalse(d.haIndirizzo)
        XCTAssertTrue(d.breve.contains("file no"), d.breve)
        Condiviso.sincronizza(indirizzo: "https://uno.invalid", token: "tok")
        d = Condiviso.diagnostica(info: [:])
        XCTAssertTrue(d.filePresente)
        XCTAssertTrue(d.haIndirizzo)
        XCTAssertTrue(d.haToken)
        XCTAssertNotNil(d.ultimaScrittura)
        XCTAssertTrue(d.breve.contains("token sì"), d.breve)
        XCTAssertTrue(d.lungo.contains("Gruppi provati"))
    }
}

/// Il riassunto per il widget «Da controllare».
final class DubbiWidgetTests: XCTestCase {
    func testDalleAvvisiDiOggiVengonoIDubbiDellaFormazione() throws {
        let corpo = #"""
        {"giornata": 11, "inizio": "2026-10-31 18:30", "con_probabili": false,
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 73.7},
         "avvisi": [
           {"id": 5, "nome": "Leonel Marteni", "ruolo": "A", "squadra": "inter", "tipo": "dubbio", "in_formazione": true, "p_voto": 0.55},
           {"id": 6, "nome": "Bastrani", "ruolo": "D", "tipo": "diffidato", "in_formazione": true},
           {"id": 7, "nome": "Riserva", "ruolo": "C", "tipo": "infortunato", "in_formazione": false}
         ]}
        """#
        let oggi: Oggi = try Decodifica.decodifica(Data(corpo.utf8))
        let r = RiassuntoOggi(oggi: oggi)
        XCTAssertEqual(r.daControllare, 2)
        XCTAssertEqual(r.dubbi?.map(\.id), [5, 6])
        XCTAssertEqual(r.dubbi?.first?.descrizione, "Dubbio 55%")
        XCTAssertEqual(r.dubbi?.last?.descrizione, "Diffidato")
    }

    func testAlMassimoSeiDubbi() throws {
        let avvisi = (1...9).map { #"{"id": \#($0), "nome": "G\#($0)", "tipo": "dubbio", "in_formazione": true}"# }.joined(separator: ",")
        let corpo = #"{"giornata": 1, "avvisi": [\#(avvisi)]}"#
        let oggi: Oggi = try Decodifica.decodifica(Data(corpo.utf8))
        let r = RiassuntoOggi(oggi: oggi)
        XCTAssertEqual(r.daControllare, 9)
        XCTAssertEqual(r.dubbi?.count, 6)
    }

    func testUnRiassuntoVecchioSenzaDubbiSiLegge() throws {
        let vecchio = #"{"giornata": 9, "daControllare": 2, "scaricatoIl": 783000000}"#
        let r = try JSONDecoder().decode(RiassuntoOggi.self, from: Data(vecchio.utf8))
        XCTAssertNil(r.dubbi)
        XCTAssertEqual(r.daControllare, 2)
    }

    func testDescrizioneSenzaTipo() {
        XCTAssertEqual(DubbioRiassunto(id: 1, nome: "A", ruolo: nil, tipo: nil, pVoto: nil).descrizione, "Da controllare")
    }
}

/// Il token del widget (fw_): l'unica credenziale che esce dall'app; quello della sessione resta nel Keychain.
final class TokenWidgetTests: XCTestCase {
    private let indirizzo = "https://prova-token-widget.invalid"
    private var cartella: URL!
    private var memoria: UserDefaults!
    private var nomeSuite = ""

    override func setUp() {
        super.setUp()
        cartella = FileManager.default.temporaryDirectory.appendingPathComponent("tw-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        Condiviso.cartellaDiProva = cartella
        nomeSuite = "prova-tw-\(UUID().uuidString)"
        memoria = UserDefaults(suiteName: nomeSuite)
        TokenWidget.archivio = MemoriaToken()
        PortachiaviCondiviso.archivio = MemoriaCollegamento()
    }

    override func tearDown() {
        Condiviso.cartellaDiProva = nil
        PortachiaviCondiviso.archivio = KeychainCollegamento()
        try? FileManager.default.removeItem(at: cartella)
        memoria.removePersistentDomain(forName: nomeSuite)
        TokenWidget.archivio = KeychainToken(servizio: TokenWidget.servizio)
        super.tearDown()
    }

    private func server(_ gestore: @escaping @Sendable (String, String) throws -> Data) -> ServerDiProva {
        ServerDiProva(indirizzo: indirizzo) { metodo, percorso, _ in try gestore(metodo, percorso) }
    }

    func testIlTokenDelWidgetSiRiconosce() {
        XCTAssertTrue(TokenWidget.valido("fw_abcdefghijklmnop"))
        XCTAssertFalse(TokenWidget.valido("abcdefghijklmnop"), "un token di sessione non e' un token del widget")
        XCTAssertFalse(TokenWidget.valido("fw_"))
        XCTAssertFalse(TokenWidget.valido("fw_con spazio e altro"))
        XCTAssertFalse(TokenWidget.valido("fw_" + String(repeating: "a", count: 600)))
    }

    func testDopoLAccessoSiChiedeIlTokenDelWidgetEVaNelFileCondiviso() async {
        let s = server { metodo, percorso in
            if metodo == "POST", percorso == "/api/account/token-widget" { return Data(#"{"token": "fw_tokenDiProva123456", "scade": "2027-01-28T12:00:00", "etichetta": "widget"}"#.utf8) }
            throw ErroreApi.server("niente")
        }
        await TokenWidget.assicura(server: s, memoria: memoria)
        XCTAssertEqual(s.quante("POST /api/account/token-widget"), 1)
        XCTAssertEqual(TokenWidget.leggi(server: indirizzo), "fw_tokenDiProva123456")
    }

    func testNelFileCondivisoNonVaMaiIlTokenDiSessione() async {
        // la sessione sta nel Keychain dell'app; il file condiviso riceve solo il token del widget
        let sessione = MemoriaToken()
        sessione.salva("token-di-sessione-segreto", server: indirizzo)
        let s = server { _, _ in Data(#"{"token": "fw_tokenDiProva123456", "scade": "2027-01-28T12:00:00"}"#.utf8) }
        await TokenWidget.assicura(server: s, memoria: memoria)
        Condiviso.sincronizza(indirizzo: indirizzo, token: TokenWidget.leggi(server: indirizzo))
        let file = (try? String(contentsOf: cartella.appendingPathComponent("condiviso.json"), encoding: .utf8)) ?? ""
        XCTAssertFalse(file.contains("token-di-sessione-segreto"))
        XCTAssertTrue(file.contains("fw_tokenDiProva123456"))
        XCTAssertFalse(Condiviso.diagnostica().lungo.contains("fw_"), "la diagnostica non stampa mai un token")
        XCTAssertFalse(Condiviso.diagnostica().breve.contains("fw_"))
    }

    func testUnTokenChePuoServireNonSiChiedeDiNuovo() async {
        TokenWidget.archivio.salva("fw_esistenteDiProva1234", server: indirizzo)
        memoria.set("2099-01-01T00:00:00", forKey: "tokenWidgetScade|" + indirizzo)
        let s = server { _, _ in throw ErroreApi.server("non doveva chiamare") }
        await TokenWidget.assicura(server: s, memoria: memoria)
        XCTAssertEqual(s.quante("token-widget"), 0)
        XCTAssertEqual(TokenWidget.leggi(server: indirizzo), "fw_esistenteDiProva1234")
    }

    func testRinnovoQuandoStaPerScadere() {
        let adesso = ISO8601DateFormatter().date(from: "2027-01-01T12:00:00+01:00") ?? Date()
        XCTAssertTrue(TokenWidget.daRinnovare(token: nil, scade: "2099-01-01T00:00:00", adesso: adesso))
        XCTAssertTrue(TokenWidget.daRinnovare(token: "fw_x", scade: nil, adesso: adesso))
        XCTAssertTrue(TokenWidget.daRinnovare(token: "fw_x", scade: "non una data", adesso: adesso))
        XCTAssertTrue(TokenWidget.daRinnovare(token: "fw_x", scade: "2027-01-05T12:00:00", adesso: adesso), "meno di 7 giorni")
        XCTAssertFalse(TokenWidget.daRinnovare(token: "fw_x", scade: "2027-02-01T12:00:00", adesso: adesso))
    }

    func testLaScadenzaConFusoNonEOraItaliana() {
        // 12:00 UTC = 13:00 italiane: con il fuso vale quello, senza fuso e' ora italiana
        let utc = TokenWidget.leggiScadenza("2027-01-20T12:00:00+00:00")
        let italiana = TokenWidget.leggiScadenza("2027-01-20T13:00:00")
        XCTAssertNotNil(utc)
        XCTAssertEqual(utc, italiana)
        XCTAssertEqual(TokenWidget.leggiScadenza("2027-01-20T12:00:00.123456+00:00"), utc)
        XCTAssertEqual(TokenWidget.leggiScadenza("2027-01-20T12:00:00Z"), utc)
        let adesso = ISO8601DateFormatter().date(from: "2027-01-13T12:30:00Z") ?? Date()
        // mancano 6 giorni e 23 ore e mezza: si rinnova; con la lettura sbagliata (UTC come ora italiana) sarebbe 7 giorni e 30 minuti
        XCTAssertTrue(TokenWidget.daRinnovare(token: "fw_x", scade: "2027-01-20T12:00:00+00:00", adesso: adesso))
        XCTAssertFalse(TokenWidget.daRinnovare(token: "fw_x", scade: "2027-01-20T13:00:00+00:00", adesso: adesso))
    }

    func testUnTokenStranoDelServerNonSiSalva() async {
        let s = server { _, _ in Data(#"{"token": "sessione-finta", "scade": "2027-01-28T12:00:00"}"#.utf8) }
        await TokenWidget.assicura(server: s, memoria: memoria)
        XCTAssertNil(TokenWidget.leggi(server: indirizzo))
    }

    func testUnServerSenzaAccountNonFaDanni() async {
        let s = server { _, _ in throw ErroreApi.risposta(404) }
        await TokenWidget.assicura(server: s, memoria: memoria)
        XCTAssertNil(TokenWidget.leggi(server: indirizzo))
    }

    func testUscendoIlServerTogliIlTokenEIlTelefonoLoDimentica() async {
        TokenWidget.archivio.salva("fw_daRevocare1234567", server: indirizzo)
        Condiviso.sincronizza(indirizzo: indirizzo, token: "fw_daRevocare1234567")
        let s = server { metodo, percorso in
            if metodo == "DELETE", percorso == "/api/account/token-widget" { return Data(#"{"revocato": true}"#.utf8) }
            throw ErroreApi.server("niente")
        }
        await TokenWidget.revoca(server: s, memoria: memoria)
        XCTAssertEqual(s.quante("DELETE /api/account/token-widget"), 1)
        XCTAssertNil(TokenWidget.leggi(server: indirizzo))
        XCTAssertNil(Condiviso.leggi().token)
    }

    func testAncheSeIlServerNonRispondeIlTelefonoDimentica() async {
        TokenWidget.archivio.salva("fw_daRevocare1234567", server: indirizzo)
        Condiviso.sincronizza(indirizzo: indirizzo, token: "fw_daRevocare1234567")
        await TokenWidget.revoca(server: server { _, _ in throw ErroreApi.rete("spento") }, memoria: memoria)
        XCTAssertNil(TokenWidget.leggi(server: indirizzo))
        XCTAssertNil(Condiviso.leggi().token)
    }
}
