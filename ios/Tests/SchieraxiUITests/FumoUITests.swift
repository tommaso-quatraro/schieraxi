import XCTest

/// Test di fumo dell'interfaccia: l'app parte in modalità demo (dati finti, senza rete, tutte le funzioni accese), le quattro sezioni si raggiungono
/// e le schermate principali mostrano il testo atteso. Si cerca per testo (etichetta di accessibilità), non per posizione.
final class FumoUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        // DIAGNOSI TEMPORANEA (#212): in questa corsa girano solo le diagnosi di questo file
        if !name.contains("Diagnosi") { throw XCTSkip("diagnosi temporanea #212") }
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

    private func vaiA(_ sezione: String) {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire")
        barra.buttons[sezione].firstMatch.tap()   // con iOS 26 la barra a volte espone due elementi per la stessa scheda
    }

    func testLeQuattroSezioniSonoRaggiungibili() {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire")
        for nome in ["Oggi", "Formazione", "Squadra", "Altro"] {
            XCTAssertTrue(barra.buttons[nome].exists, "manca la sezione \(nome)")
        }
    }

    func testOggiMostraLaGiornataELaFormazione() {
        attendi("La tua scelta")
        attendi("Da controllare")
        attendi("Apri la formazione")
        attendi("punti attesi", contiene: true)
        XCTAssertTrue(app.navigationBars["Oggi"].exists)
    }

    func testFormazioneConCampoEModificaAMano() {
        vaiA("Formazione")
        attendi("Campo")
        attendi("Modulo proposto", contiene: true)
        attendi("Panchina")
        let modifica = app.buttons["Modifica a mano"]
        XCTAssertTrue(modifica.waitForExistence(timeout: 20), "il pulsante «Modifica a mano» deve esserci")
        modifica.tap()
        attendi("Salva come mia scelta")
        attendi("Torna alla consigliata")
        app.buttons["Torna alla consigliata"].tap()
        XCTAssertTrue(app.buttons["Modifica a mano"].waitForExistence(timeout: 20), "tornando alla consigliata ricompare «Modifica a mano»")
    }

    func testSquadraConLeSuePagine() {
        vaiA("Squadra")
        attendi("Aggiorna le rose")
        for voce in ["Aggiorna le rose", "Squadre e rose", "Cambi consigliati", "Seguiti", "Elenco dei giocatori", "Calendario"] {
            attendiScorrendo(voce, contiene: true)
        }
        elemento("Cambi consigliati", contiene: true).tap()
        attendi("Svincolati che migliorano la squadra")
    }

    func testElencoDeiGiocatoriDentroSquadra() {
        vaiA("Squadra")
        attendiScorrendo("Elenco dei giocatori", contiene: true)
        elemento("Elenco dei giocatori", contiene: true).tap()
        attendi("Solo svincolati")
    }

    func testScambiConOffertaEAnalisi() {
        vaiA("Altro")
        attendi("Scambi", contiene: true)
        elemento("Scambi", contiene: true).tap()
        XCTAssertTrue(app.buttons["Cerca scambi"].waitForExistence(timeout: 20), "le proposte si cercano con il pulsante")
        for modo in ["Trova per me", "Costruisci", "Valuta un'offerta"] {
            XCTAssertTrue(app.buttons[modo].waitForExistence(timeout: 10), "manca il modo «\(modo)»")
        }
        attendi("Chi accetta più volentieri")
        app.buttons["Valuta un'offerta"].tap()
        attendi("Ho ricevuto un'offerta")
        app.buttons["Costruisci"].tap()
        attendi("Squadra")
    }

    func testAltroConLeSuePagine() {
        vaiA("Altro")
        attendi("Scambi", contiene: true)
        for voce in ["Scambi", "Movimenti e storico", "Regole", "Diario delle giornate", "Novità"] {
            attendiScorrendo(voce, contiene: true)
        }
        // ogni voce in un posto solo: niente copia di sicurezza, niente rimando alle Impostazioni (c'è l'ingranaggio)
        XCTAssertFalse(elemento("Copia di sicurezza", contiene: true).exists)
        XCTAssertFalse(elemento("Impostazioni dell'app e dell'account").exists)
    }

    func testImpostazioniDallIngranaggio() {
        vaiA("Altro")
        let ingranaggio = app.buttons["Impostazioni"]
        XCTAssertTrue(ingranaggio.waitForExistence(timeout: 20), "l'ingranaggio sta accanto alla lente")
        ingranaggio.tap()
        attendi("Aspetto")
        attendi("Avvisi e promemoria")
        // le voci tolte non ci sono più
        for tolta in ["Icona dell'app", "Sotto il cofano", "Copia di sicurezza", "Configurazione guidata", "Copia il codice per il widget"] {
            XCTAssertFalse(elemento(tolta, contiene: true).exists, "«\(tolta)» non deve stare nelle Impostazioni")
        }
        elemento("Aspetto").tap()
        attendi("Automatico")
        attendiScorrendo("Animazioni ridotte", contiene: true)
        XCTAssertFalse(elemento("Colore principale").exists, "l'aspetto ha solo tema e animazioni")
    }

    func testSchedaDiUnGiocatoreSiApreEDiChiude() {
        // un tocco su una riga di Oggi apre la scheda (foglio) con la previsione, la forma e il grafico dei voti
        let riga = app.buttons.matching(NSPredicate(format: "label CONTAINS 'fantavoto atteso'")).firstMatch
        XCTAssertTrue(riga.waitForExistence(timeout: 30), "serve almeno una riga di giocatore in Oggi")
        riga.tap()
        attendi("Prossima partita")
        attendi("Forma")
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
        conferma.tap()
        // l'esito come la web: «Cosa è cambiato», le squadre importate, poi «Da controllare:» con gli avvisi del server
        attendi("Rose salvate", contiene: true)
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
        attendiScorrendo("«Bastrani» non è nel listone", contiene: true)
        XCTAssertFalse(elemento("tutto in ordine", contiene: true).exists, "con degli avvisi non si dice «tutto in ordine»")
    }

    func testLEsitoSenzaAvvisiDiceTuttoInOrdine() {
        apriDemo("lega-importa-salvate-ok")
        attendi("Rose salvate", contiene: true)
        attendiScorrendo("Rose controllate: tutto in ordine.", contiene: true)
        XCTAssertFalse(elemento("Da controllare", contiene: true).exists, "senza avvisi non c'è niente da controllare")
    }

    func testLaLenteApreLaRicerca() {
        let lente = app.buttons["Cerca un giocatore"]
        XCTAssertTrue(lente.waitForExistence(timeout: 30), "la lente della ricerca deve esserci in Oggi")
        lente.tap()
        attendi("Scrivi almeno due lettere del nome.")
    }

    // MARK: - DIAGNOSI TEMPORANEA (#212), da togliere prima della PR

    private func adesso() -> TimeInterval { Date().timeIntervalSinceReferenceDate }
    private func f(_ t: TimeInterval) -> String { String(format: "%.2f", t) }

    /// Fili che tengono occupata la CPU del Mac (come nella diagnosi di #177).
    private final class Carico: @unchecked Sendable {
        private let lucchetto = NSLock()
        private var acceso = true
        var attivo: Bool { lucchetto.lock(); defer { lucchetto.unlock() }; return acceso }
        func ferma() { lucchetto.lock(); acceso = false; lucchetto.unlock() }
        init(fili: Int) {
            for _ in 0..<fili {
                Thread.detachNewThread { [self] in
                    var x = 0.0
                    while self.attivo { for i in 0..<200_000 { x += sin(Double(i)) } }
                    if x == 42 { print(x) }
                }
            }
        }
    }

    /// Cosa c'è a schermo: barre di navigazione, scheda scelta, la riga «Scambi», i pezzi della pagina Scambi.
    private func statoSchermo() -> String {
        let barre = app.navigationBars.allElementsBoundByIndex.map { $0.identifier }.joined(separator: "/")
        let schede = app.tabBars.firstMatch.buttons.allElementsBoundByIndex.filter { $0.isSelected }.map { $0.label }.joined(separator: "/")
        let riga = elemento("Scambi", contiene: true)
        let rigaStato = riga.exists ? "c'è(tipo \(riga.elementType.rawValue) tocc \(riga.isHittable) y \(Int(riga.frame.minY)))" : "no"
        let quante = app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS[c] %@", "Scambi")).count
        return "barre=[\(barre)] scheda=[\(schede)] riga=\(rigaStato) etichScambi=\(quante) segm=\(app.segmentedControls.count) "
            + "cerco=\(app.buttons["Cerco…"].exists) cerca=\(app.buttons["Cerca scambi"].exists) valuta=\(app.buttons["Valuta un'offerta"].exists) "
            + "guardo=\(elemento("Guardo gli scambi", contiene: true).exists) conChi=\(elemento("Con chi").exists) "
            + "fogli=\(app.sheets.count) avvisi=\(app.alerts.count)"
    }

    /// Il percorso del test, molte volte: avvio, scheda Altro, tocco sulla riga «Scambi», attesa di «Cerca scambi» (20 s come il
    /// test). Avvii dispari: tocco subito appena la riga c'è (come il test); pari: tocco dopo 1,5 s. Poi, nello stesso avvio,
    /// altri 3 giri indietro e avanti. Se «Cerca scambi» non compare: cosa c'è a schermo, se compare più tardi senza toccare,
    /// e se compare con un secondo tocco.
    private func diagnosiScambi(fili: Int, secondi: TimeInterval) {
        continueAfterFailure = true
        let carico = fili > 0 ? Carico(fili: fili) : nil
        defer { carico?.ferma() }
        var avvii = 0
        var primi = 0
        var altri = 0
        var lenti = 0
        var mancati: [String] = []
        var tempi: [String] = []
        let inizio = adesso()
        while adesso() - inizio < secondi {
            avvii += 1
            if avvii > 1 { app.terminate(); app.launch() }
            let subito = !avvii.isMultiple(of: 2)
            let t0 = adesso()
            let barra = app.tabBars.firstMatch
            guard barra.waitForExistence(timeout: 30) else { mancati.append("avvio \(avvii): niente barra"); continue }
            let t1 = adesso()
            barra.buttons["Altro"].firstMatch.tap()
            for prova in 0..<4 {
                let riga = elemento("Scambi", contiene: true)
                guard riga.waitForExistence(timeout: 20) else {
                    mancati.append("avvio \(avvii) prova \(prova): niente riga Scambi | \(statoSchermo())")
                    break
                }
                if prova == 0 && !subito { usleep(1_500_000) }
                let t2 = adesso()
                let yPrima = riga.exists ? Int(riga.frame.minY) : -1
                riga.tap()
                let t3 = adesso()
                let cerca = app.buttons["Cerca scambi"]
                let ok = cerca.waitForExistence(timeout: 20)
                let t4 = adesso()
                if prova == 0 {
                    primi += 1
                    tempi.append("\(subito ? "s" : "a")\(f(t1 - t0))/\(f(t2 - t1))/\(f(t3 - t2))/\(f(t4 - t3))")
                } else {
                    altri += 1
                }
                if t4 - t3 > 5 { lenti += 1 }
                if !ok {
                    let stato = statoSchermo()
                    let tardi = cerca.waitForExistence(timeout: 30)
                    var dopo = "più tardi=\(tardi)"
                    if !tardi {
                        dopo += " | \(statoSchermo())"
                        let r = elemento("Scambi", contiene: true)
                        if r.exists && r.isHittable {
                            r.tap()
                            dopo += " | ritocco=\(cerca.waitForExistence(timeout: 20))"
                        }
                    }
                    mancati.append("avvio \(avvii) prova \(prova) \(subito ? "subito" : "dopo 1,5 s"): y \(yPrima) tap \(f(t3 - t2))s | \(stato) | \(dopo)")
                    break
                }
                guard prova < 3 else { break }
                // indietro alla lista di Altro, per un altro tocco nello stesso avvio
                let indietro = app.navigationBars.buttons.element(boundBy: 0)
                guard indietro.exists else { mancati.append("avvio \(avvii) prova \(prova): niente indietro"); break }
                indietro.tap()
                if !cerca.waitForNonExistence(timeout: 10) { mancati.append("avvio \(avvii) prova \(prova): indietro non torna"); break }
            }
        }
        let riassunto = "DIAGNOSI Scambi, carico \(fili) fili: senza «Cerca scambi» \(mancati.count) su \(primi + altri) tocchi "
            + "(primi dopo l'avvio \(primi), successivi \(altri), avvii \(avvii), arrivo oltre 5 s \(lenti)) || "
            + mancati.joined(separator: " || ") + " || tempi barra/riga/tap/arrivo: " + tempi.joined(separator: " ")
        print(riassunto)
        XCTFail(riassunto)
    }

    func testDiagnosiScambiSenzaCarico() { diagnosiScambi(fili: 0, secondi: 360) }
    func testDiagnosiScambiSottoCarico() { diagnosiScambi(fili: 6, secondi: 900) }
}
