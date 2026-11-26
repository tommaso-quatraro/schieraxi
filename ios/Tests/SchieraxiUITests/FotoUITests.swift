import XCTest

/// Le condizioni delle fotografie automatiche (`scripts/screenshot.sh`), con l'app in modalità demo: l'orizzontale chiesto con
/// `-DEMO_ORIENTAMENTO` vale anche per l'accesso (prima la foto usciva girata), la Formazione in orizzontale finisce di caricare,
/// la foto `accesso-account-fondo` mostra «Esci».
final class FotoUITests: XCTestCase {
    private var app: XCUIApplication!

    private func avvia(_ argomenti: [String]) {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments += ["-DEMO"] + argomenti + ["-AppleLanguages", "(it)", "-AppleLocale", "it_IT"]
        app.launch()
    }

    /// Ripete `condizione` ogni mezzo secondo finché è vera, al massimo per `secondi`.
    private func aspetta(_ secondi: TimeInterval, finché condizione: () -> Bool) -> Bool {
        let fine = Date().addingTimeInterval(secondi)
        repeat {
            if condizione() { return true }
            Thread.sleep(forTimeInterval: 0.5)
        } while Date() < fine
        return condizione()
    }

    /// L'app è disegnata in orizzontale: altezza «compatta» del telefono girato, o finestra più larga che alta.
    private var inOrizzontale: Bool {
        let finestra = app.windows.firstMatch
        guard finestra.exists else { return false }
        return finestra.verticalSizeClass == .compact || finestra.frame.width > finestra.frame.height
    }

    func testLAccessoSiGiraInOrizzontaleQuandoLaFotoLoChiede() {
        avvia(["-DEMO_ACCESSO", "accedi", "-DEMO_ORIENTAMENTO", "orizzontale"])
        XCTAssertTrue(app.textFields["Nome utente"].waitForExistence(timeout: 30), "la schermata di accesso deve comparire")
        XCTAssertTrue(aspetta(15) { inOrizzontale }, "con -DEMO_ORIENTAMENTO orizzontale anche l'accesso va in orizzontale")
    }

    func testLaFormazioneInOrizzontaleFinisceDiCaricare() {
        avvia(["-DEMO_SCHERMATA", "formazione", "-DEMO_ORIENTAMENTO", "orizzontale"])
        // la riga dello stato c'è quando formazione e scelta sono arrivate (la demo non ha una scelta salvata)
        let pronta = app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", "È la consigliata.")).firstMatch
        // Il tempo delle foto: 3 secondi dopo l'avvio più al massimo 8 di attesa dello schermo fermo (scripts/screenshot.sh).
        let inTempo = pronta.waitForExistence(timeout: 10)
        var perché = ""
        if !inTempo {
            // Per capire la causa: arriva più tardi? Cambiando scheda e tornando, carica?
            let tardi = pronta.waitForExistence(timeout: 20)
            var cambiandoScheda = tardi
            if !tardi {
                let barra = app.tabBars.firstMatch
                barra.buttons["Giornate"].firstMatch.tap()
                barra.buttons["Formazione"].firstMatch.tap()
                cambiandoScheda = pronta.waitForExistence(timeout: 15)
            }
            perché = " (dopo altri 20 s: \(tardi ? "sì" : "no"); cambiando scheda: \(cambiandoScheda ? "sì" : "no"); orizzontale: \(inOrizzontale ? "sì" : "no"))"
        }
        XCTAssertTrue(inTempo, "in orizzontale la Formazione resta in caricamento oltre il tempo delle foto" + perché)
        XCTAssertTrue(aspetta(5) { inOrizzontale }, "la Formazione deve essere in orizzontale")
    }

    func testIlFondoDellAccountMostraEsci() {
        avvia(["-DEMO_ACCESSO", "account", "-DEMO_FONDO", "1"])
        let esci = app.buttons["account-esci"]
        XCTAssertTrue(aspetta(20) { esci.exists && esci.isHittable }, "nella foto accesso-account-fondo «Esci» deve essere a video")
        XCTAssertEqual(esci.label, "Esci")
    }

    /// Un elemento qualunque (testo, riga, pulsante) con l'etichetta che comincia così.
    private func elemento(cheComincia testo: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH %@", testo)).firstMatch
    }

    /// `lega-stato-fondo` (#425): in fondo a Stato dei dati ci sono i gol attesi nostri (#404) e, per ultimi, gli indicatori del
    /// consiglio di formazione (#371). L'ultimo indicatore deve essere a video, la cima della pagina no.
    func testIlFondoDelloStatoMostraGliIndicatoriDelConsiglio() {
        avvia(["-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "1"])
        let ultimo = elemento(cheComincia: "Scelte strane senza un motivo detto")
        XCTAssertTrue(aspetta(30) { ultimo.exists && ultimo.isHittable },
                      "nella foto lega-stato-fondo l'ultimo indicatore del consiglio di formazione deve essere a video")
        XCTAssertFalse(elemento(cheComincia: "Coppe europee fino al").isHittable,
                       "nella foto lega-stato-fondo la cima di Stato dei dati non deve più essere a video")
    }

    /// `lega-stato-nostri` (#430): i gol attesi nostri (#404) non stanno nella foto del fondo (c'è il consiglio di formazione, lungo
    /// quasi quanto lo schermo). Con `-DEMO_FONDO nostri` la lista si ferma sul riquadro: le prime misure sono a video, il fondo no.
    func testLaFotoDelleNostriMostraIGolAttesiNostri() {
        avvia(["-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "nostri"])
        let insieme = elemento(cheComincia: "Le tre misure insieme")
        XCTAssertTrue(aspetta(30) { insieme.exists && insieme.isHittable },
                      "nella foto lega-stato-nostri il riquadro dei gol attesi nostri deve essere a video")
        let errore = elemento(cheComincia: "Errore del fantavoto atteso contro i numeri mostrati")
        XCTAssertTrue(aspetta(5) { errore.exists && errore.isHittable }, "nella foto lega-stato-nostri deve esserci la prima misura")
        XCTAssertFalse(elemento(cheComincia: "Scelte strane senza un motivo detto").isHittable,
                       "nella foto lega-stato-nostri l'ultimo indicatore del consiglio non deve essere a video")
    }

    /// `lega-stato-taratura` (#527): la riga della taratura di «gioca N%» sta sotto i gruppi di «Quanto sono giuste le previsioni»,
    /// fra la cima della pagina e le nostri. Con `-DEMO_FONDO taratura` la lista si ferma sull'ultimo gruppo: il gruppo e la riga
    /// sono a video, la cima e il fondo no (se la lista non scorresse resterebbe in fondo, sugli indicatori del consiglio).
    func testLaFotoDellaTaraturaMostraLaRiga() {
        avvia(["-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "taratura"])
        let riga = app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", "Taratura con le probabili")).firstMatch
        XCTAssertTrue(aspetta(30) { riga.exists && riga.isHittable }, "nella foto lega-stato-taratura la riga della taratura deve essere a video")
        let gruppo = elemento(cheComincia: "Panchina 20-49%")
        XCTAssertTrue(aspetta(5) { gruppo.exists && gruppo.isHittable }, "nella foto lega-stato-taratura l'ultimo gruppo deve essere a video")
        XCTAssertFalse(elemento(cheComincia: "Scelte strane senza un motivo detto").isHittable,
                       "nella foto lega-stato-taratura l'ultimo indicatore del consiglio non deve essere a video")
        XCTAssertFalse(elemento(cheComincia: "Coppe europee fino al").isHittable,
                       "nella foto lega-stato-taratura la cima di Stato dei dati non deve più essere a video")
    }

    /// Dove sta un elemento rispetto alla finestra, per capire di quanto manca quando una foto non lo mostra.
    private func posizione(_ e: XCUIElement) -> String {
        "elemento \(e.exists ? String(describing: e.frame) : "assente"), finestra \(String(describing: app.windows.firstMatch.frame))"
    }

    /// `lega-stato-prova` (#842): la frase della prova delle previsioni su «da fantamedia» (#840) sta a metà di Stato dei dati, sotto
    /// la riga della taratura, in nessuna delle altre foto. Con `-DEMO_FONDO prova` la lista si ferma lì: la frase è a video, la cima no.
    func testLaFotoDellaProvaMostraLaFraseDaFantamedia() {
        avvia(["-DEMO_SCHERMATA", "lega-stato", "-DEMO_FONDO", "prova"])
        let frase = elemento(cheComincia: "Prova sulle ultime 8 giornate giocate")
        XCTAssertTrue(aspetta(30) { frase.exists && frase.isHittable },
                      "nella foto lega-stato-prova la frase della prova deve essere a video (\(posizione(frase)))")
        XCTAssertTrue(frase.label.contains("«Da fantamedia» è la formazione scelta con la fantamedia dei giocatori"), frase.label)
        XCTAssertFalse(elemento(cheComincia: "Coppe europee fino al").isHittable,
                       "nella foto lega-stato-prova la cima di Stato dei dati non deve più essere a video")
    }

    /// `giornate-confronto` (#842): Giornate › Dettagli nella demo in cui la consigliata ha fatto 1,0 punti in più, con a video la fine
    /// della voce del confronto, «…avresti fatto 1,0 punti in più.» (il plurale scelto sul numero scritto; prima «1,0 punto»).
    func testLaFotoDelConfrontoMostraUnoVirgolaZeroPunti() {
        fineDelConfrontoAVideo(testo: nil)
    }

    /// La stessa foto col testo più grande: la voce è più alta dello schermo e la prima versione della scena la spingeva sopra il bordo
    /// alto (foto della corsa 44826938210, `iphone_chiaro_testomassimo_giornate-confronto.png`).
    func testLaFotoDelConfrontoColTestoMassimoMostraUnoVirgolaZeroPunti() {
        fineDelConfrontoAVideo(testo: "UICTContentSizeCategoryAccessibilityXXXL")
    }

    /// Si guarda il bordo basso della voce, dove sta la frase, e non il centro: con il testo grande la voce è più alta dello schermo e
    /// il centro può essere a video con la frase fuori. La fine della voce deve stare sopra la barra in basso e sotto le barre in alto.
    private func fineDelConfrontoAVideo(testo: String?) {
        avvia(["-DEMO_SCHERMATA", "giornate-confronto"] + (testo.map { ["-UIPreferredContentSizeCategoryName", $0] } ?? []))
        let voce = app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", "avresti fatto 1,0 punti in più")).firstMatch
        XCTAssertTrue(voce.waitForExistence(timeout: 30), "nella foto giornate-confronto manca la voce del confronto")
        let finestra = app.windows.firstMatch.frame
        let barra = app.tabBars.firstMatch
        let squadra = elemento(cheComincia: "Punti di scarto medio sulla squadra")
        func dove() -> String {
            "voce \(voce.frame), squadra \(squadra.exists ? String(describing: squadra.frame) : "assente"), "
                + "barra \(barra.exists ? String(describing: barra.frame) : "assente"), finestra \(finestra)"
        }
        // la barra in basso, se c'è e sta davvero in basso; se no il fondo della finestra
        let sotto = barra.exists && barra.frame.minY > finestra.midY ? barra.frame.minY + 8 : finestra.maxY
        // lo scorrimento arriva dopo i dati: si aspetta che la fine della voce sia fra le barre (in alto: stato e titolo, circa 110 punti)
        XCTAssertTrue(aspetta(20) { voce.frame.maxY <= sotto && voce.frame.maxY >= finestra.minY + 160 },
                      "nella foto giornate-confronto la fine della voce del confronto deve essere a video (\(dove()))")
        // e ci resta: il difetto di prima era la lista che scorreva e poi tornava in cima quando arrivava la riga sotto il titolo
        Thread.sleep(forTimeInterval: 2)
        XCTAssertTrue(voce.frame.maxY <= sotto && voce.frame.maxY >= finestra.minY + 160,
                      "nella foto giornate-confronto la voce del confronto è uscita dallo schermo dopo lo scorrimento (\(dove()))")
        if testo != nil {
            XCTAssertGreaterThan(voce.frame.height, finestra.height / 2,
                                 "il testo grande non è arrivato all'app: la prova non dice niente (\(dove()))")
        }
    }

    /// `formazione-metti-in-campo` (#778): la scena apre da sola l'elenco «Chi esce per …» del panchinaro della demo, con in cima
    /// il cambio che rende di più, che cambia modulo («Si passa al …»).
    func testLaFotoDiMettiInCampoMostraLElenco() {
        avvia(["-DEMO_SCHERMATA", "formazione-metti-in-campo"])
        XCTAssertTrue(elemento(cheComincia: "Chi esce per Fabio Dimarzi").waitForExistence(timeout: 30),
                      "nella foto formazione-metti-in-campo l'elenco deve aprirsi da solo")
        let riga = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Si passa al")).firstMatch
        XCTAssertTrue(riga.waitForExistence(timeout: 10), "in cima all'elenco c'è un cambio di modulo, con «Si passa al …»")
    }

    /// `lega-rosa-fondo` (#425): la rosa di un'altra squadra (#375) arriva fino a «Rose aggiornate il…», in fondo alla lista.
    func testIlFondoDellaRosaMostraLUltimaRiga() {
        avvia(["-DEMO_SCHERMATA", "lega-rosa", "-DEMO_FONDO", "1"])
        let ultima = elemento(cheComincia: "Rose aggiornate il")
        XCTAssertTrue(aspetta(30) { ultima.exists && ultima.isHittable },
                      "nella foto lega-rosa-fondo l'ultima riga della rosa deve essere a video")
        XCTAssertFalse(elemento(cheComincia: "Crediti residui").isHittable,
                       "nella foto lega-rosa-fondo la cima della rosa non deve più essere a video")
    }
}
