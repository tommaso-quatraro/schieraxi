import XCTest

/// Test di fumo dell'interfaccia: l'app parte in modalità demo (dati finti, senza rete, tutte le funzioni accese), le tre voci si raggiungono
/// e le schermate principali mostrano il testo atteso. Si cerca per testo (etichetta di accessibilità), non per posizione.
/// Ogni tocco che apre qualcosa passa da `tocca(_:finchéCompare:_:)` (Tocchi.swift): se il tocco si perde, si ritocca (#212).
final class FumoUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments += ["-DEMO", "-AppleLanguages", "(it)", "-AppleLocale", "it_IT"]
        app.launch()
    }

    /// Un elemento qualsiasi (testo, pulsante, riga) con quell'etichetta, anche solo contenuta.
    private func elemento(_ testo: String, contiene: Bool = false) -> XCUIElement {
        let predicato = NSPredicate(format: contiene ? "label CONTAINS[c] %@" : "label ==[c] %@", testo)
        return app.descendants(matching: .any).matching(predicato).firstMatch
    }

    private func attendi(_ testo: String, contiene: Bool = false, secondi: TimeInterval = 20, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(elemento(testo, contiene: contiene).waitForExistence(timeout: secondi), "non compare «\(testo)»", file: file, line: line)
    }

    /// Per le liste: le righe fuori dallo schermo non esistono ancora, quindi si scorre finché compare l'elemento.
    private func attendiScorrendo(_ testo: String, contiene: Bool = false, file: StaticString = #filePath, line: UInt = #line) {
        for _ in 0..<12 {
            if elemento(testo, contiene: contiene).waitForExistence(timeout: 2) { return }
            app.swipeUp()
        }
        XCTFail("non compare «\(testo)» nemmeno scorrendo", file: file, line: line)
    }

    /// Apre una sezione dalla barra in basso: è aperta quando c'è la sua barra del titolo.
    private func vaiA(_ sezione: String, file: StaticString = #filePath, line: UInt = #line) {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire", file: file, line: line)
        // con iOS 26 la barra a volte espone due elementi per la stessa scheda
        tocca(barra.buttons[sezione].firstMatch, finchéCompare: app.navigationBars[sezione], "la sezione «\(sezione)» non si apre",
              file: file, line: line)
    }

    func testLeSezioniSonoRaggiungibili() {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire")
        for nome in ["Formazione", "Giornate", "Impostazioni"] {
            XCTAssertTrue(barra.buttons[nome].exists, "manca la sezione \(nome)")
        }
        // la barra a tre voci come la web (#673 passo 3): Squadra e Altro stanno in Impostazioni > La mia lega
        for tolta in ["Oggi", "Squadra", "Altro"] {
            XCTAssertFalse(barra.buttons[tolta].exists, "«\(tolta)» non è più una voce della barra")
        }
    }

    /// La pagina Giornate (#673 passo 2): in cima la riga sulla precisione e «Dettagli», poi una riga per giornata finita.
    func testGiornateConLaPrecisioneELeRighe() {
        vaiA("Giornate")
        attendi("Finora il fantavoto atteso sbaglia", contiene: true)
        attendi("Dettagli")
        attendi("Giornata 7", contiene: true)
    }

    func testLaFormazioneSiApreConLaGiornataEIlCampo() {
        // la Formazione unica (#673) si apre per prima, come la web: quando si chiude, i punti attesi, la riga dello stato (la demo
        // non ha una scelta salvata), «Copia per l'app della lega», la panchina. Niente più modifica a mano né «Salva»
        attendi("Si chiude", contiene: true)
        attendi("punti attesi", contiene: true)
        attendi("È la consigliata.")
        XCTAssertTrue(app.navigationBars["Formazione"].exists)
        attendiScorrendo("Copia per l'app della lega", contiene: true)
        attendiScorrendo("Panchina")
        // gli stili non ci sono più (#634): niente frase dello stile («Equilibrata: propone il 3-4-3.»)
        XCTAssertFalse(elemento("propone il", contiene: true).exists, "in Formazione non c'è più la frase dello stile")
        XCTAssertFalse(elemento("Modifica a mano").exists, "il salvataggio è automatico: niente «Modifica a mano»")
        XCTAssertFalse(elemento("Salva come mia scelta").exists)
    }

    func testUnAltroModuloSiSalvaETornaAllaConsigliata() {
        // il modulo è un menu: un altro modulo si salva da solo e la riga dello stato lo dice, con «Torna alla consigliata»
        let menu = app.buttons["Modulo"].firstMatch
        XCTAssertTrue(menu.waitForExistence(timeout: 30), "il menu del modulo deve esserci")
        attendi("È la consigliata.")
        // le voci del menu: «4-3-3 · 73,7 punti · consigliato», le altre senza «consigliato»
        let altro = app.buttons.matching(NSPredicate(format: "label MATCHES %@", "^[0-9]-[0-9]-[0-9](-[0-9])? · .* punti$")).firstMatch
        tocca(menu, finchéCompare: altro, "il menu del modulo si apre")
        tocca(altro, finchéCompare: elemento("L'hai cambiata tu", contiene: true), "un altro modulo si salva da solo")
        let torna = app.buttons["Torna alla consigliata"].firstMatch
        XCTAssertTrue(torna.waitForExistence(timeout: 10))
        tocca(torna, finchéCompare: elemento("È la consigliata."), "«Torna alla consigliata» rimette la consigliata")
    }

    /// La mia lega nelle Impostazioni (#673 passo 3, come la web): Aggiorna le rose, La mia squadra, Regole e scadenza, Le altre squadre.
    func testLaMiaLegaNelleImpostazioni() {
        vaiA("Impostazioni")
        attendiScorrendo("La mia lega")
        for voce in ["Aggiorna le rose", "La mia squadra", "Regole e scadenza", "Le altre squadre"] {
            attendiScorrendo(voce, contiene: true)
        }
        // le pagine tolte non hanno più una voce
        for tolta in ["Cambi consigliati", "Seguiti", "Elenco dei giocatori", "Diario delle giornate", "Movimenti e storico"] {
            XCTAssertFalse(elemento(tolta, contiene: true).exists, "«\(tolta)» non deve stare nelle Impostazioni")
        }
    }

    /// Il rimedio di #212 funziona davvero: il primo tocco su «Regole e scadenza» si perde (non lo si manda all'app) e `tocca` deve
    /// accorgersene e ritoccare finché si apre la pagina. Senza il nuovo tocco questo test fallisce.
    func testUnToccoPersoSiRitocca() {
        vaiA("Impostazioni")
        attendiScorrendo("Regole e scadenza", contiene: true)
        var tocchi = 0
        tocca(elemento("Regole e scadenza", contiene: true), finchéCompare: app.navigationBars["Regole e scadenza"],
              "dopo un tocco perso si ritocca", entro: 5, tap: { riga in
                  tocchi += 1
                  if tocchi > 1 { riga.tap() }   // il primo tocco «si perde»
              })
        XCTAssertGreaterThanOrEqual(tocchi, 2, "un tocco perso e almeno uno arrivato")
    }

    /// Le Impostazioni in una pagina sola (#673 passo 3): un interruttore unico per gli avvisi e le ore tranquille, poi Aspetto.
    func testImpostazioniInUnaPagina() {
        vaiA("Impostazioni")
        attendi("Avvisi su questo dispositivo", contiene: true)
        attendi("Ore tranquille", contiene: true)
        // gli interruttori per singolo avviso e le voci tolte non ci sono più
        for tolta in ["Promemoria un'ora prima", "Avviso se il consiglio cambia", "Riepilogo della giornata", "Icona dell'app",
                      "Sotto il cofano", "Copia di sicurezza", "Configurazione guidata", "Mostra tutte le funzioni"] {
            XCTAssertFalse(elemento(tolta, contiene: true).exists, "«\(tolta)» non deve stare nelle Impostazioni")
        }
        attendiScorrendo("Automatico")
        attendiScorrendo("Animazioni ridotte", contiene: true)
        XCTAssertFalse(elemento("Colore principale").exists, "l'aspetto ha solo tema e animazioni")
    }

    /// Le novità si leggono in Impostazioni > Informazioni (#634, come la web).
    func testLeNovitaSiLeggonoNelleImpostazioni() {
        vaiA("Impostazioni")
        attendiScorrendo("Informazioni", contiene: true)
        tocca(elemento("Informazioni", contiene: true), finchéCompare: elemento("Novità"), "«Informazioni» apre la sua pagina")
    }

    func testSchedaDiUnGiocatoreSiApreEDiChiude() {
        // un tocco su una pedina della Formazione apre la scheda (foglio) unica, come la web (#616): gli ultimi voti e, chiusi,
        // «Tutti i numeri»
        let riga = app.buttons.matching(NSPredicate(format: "label CONTAINS 'fantavoto atteso'")).firstMatch
        XCTAssertTrue(riga.waitForExistence(timeout: 30), "serve almeno una pedina o una riga di giocatore nella Formazione")
        tocca(riga, finchéCompare: elemento("Ultimi voti"), "un tocco sulla riga apre la scheda del giocatore")
        attendiScorrendo("Tutti i numeri")
        let chiudi = app.buttons["Chiudi"]
        XCTAssertTrue(chiudi.waitForExistence(timeout: 10))
        chiudi.tap()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 10))
    }

    /// Riapre la demo direttamente su una schermata (`-DEMO_SCHERMATA`).
    private func apriDemo(_ schermata: String) {
        app.terminate()
        app.launchArguments += ["-DEMO_SCHERMATA", schermata]
        app.launch()
    }

    func testUnCsvDelleRoseSiImportaDaUnAltraApp() {
        // la demo scrive un CSV vero (separatore «;») e lo importa come se arrivasse da «Apri con SchieraXI»
        apriDemo("lega-importa-csv")
        // prima l'anteprima (niente si salva), poi «Conferma e salva»
        attendi("Controlla prima di salvare")
        XCTAssertFalse(elemento("Usa un Excel (.xlsx), un CSV o un file di testo.").exists, "il CSV non deve essere rifiutato")
        let conferma = app.buttons["Conferma e salva"]
        for _ in 0..<8 where !conferma.isHittable { app.swipeUp() }
        // l'esito come la web: «Cosa è cambiato», le squadre importate, poi «Da controllare:» con gli avvisi del server
        tocca(conferma, finchéCompare: elemento("Rose salvate", contiene: true), "«Conferma e salva» salva le rose", entro: 20)
        attendi("Cosa è cambiato")
        attendiScorrendo("Importate:", contiene: true)
        attendiScorrendo("Da controllare:")
        attendiScorrendo("24 giocatori invece di 25", contiene: true)
    }

    func testLEsitoConAvvisiDiceCosaControllare() {
        apriDemo("lega-importa-salvate")
        attendi("Rose salvate", contiene: true)
        XCTAssertFalse(elemento("La tua squadra:", contiene: true).exists, "come la web: l'esito non ripete la propria squadra")
        attendiScorrendo("Da controllare:")
        attendiScorrendo("«Bastrini» non è nel listone", contiene: true)
        XCTAssertFalse(elemento("tutto in ordine", contiene: true).exists, "con degli avvisi non si dice «tutto in ordine»")
    }

    func testLEsitoSenzaAvvisiDiceTuttoInOrdine() {
        apriDemo("lega-importa-salvate-ok")
        attendi("Rose salvate", contiene: true)
        attendiScorrendo("Rose controllate: tutto in ordine.", contiene: true)
        XCTAssertFalse(elemento("Da controllare", contiene: true).exists, "senza avvisi non c'è niente da controllare")
    }

    func testIlCollegamentoDelWidgetAspettaUnTocco() {
        // `schieraxi://widget/collega` lo può aprire qualsiasi app o pagina e apre questa schermata (`Navigazione.vai`, lo stesso
        // `collegaWidgetAperto` della demo): si apre solo la schermata, il collegamento e la copia del codice negli appunti partono
        // dal tocco su «Collega» (#482). La demo apre la schermata dall'argomento di lancio, senza `XCUIApplication.open`, che sul
        // simulatore a volte non consegna l'indirizzo all'app.
        apriDemo("collega-widget")
        attendi("Collega il widget")
        XCTAssertFalse(elemento("Codice copiato").exists, "senza un tocco il codice non si copia")
        // in demo il tocco dice «Codice copiato» senza toccare gli appunti veri
        tocca(app.buttons["Collega"].firstMatch, finchéCompare: elemento("Codice copiato"), "il tocco su «Collega» collega il widget")
    }

    /// La ricerca è una voce della barra (#673 passo 3, come la lente della web): il nome lo dà iOS.
    func testLaRicercaEUnaVoceDellaBarra() {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire")
        let cerca = barra.buttons.matching(NSPredicate(format: "label IN %@", ["Cerca", "Search"])).firstMatch
        XCTAssertTrue(cerca.waitForExistence(timeout: 10), "la voce della ricerca deve esserci nella barra")
        tocca(cerca, finchéCompare: elemento("Scrivi almeno due lettere."), "la voce apre la ricerca")
    }
}
