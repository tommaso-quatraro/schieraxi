import Foundation
import Testing
@testable import Schieraxi

/// I testi dei widget che si accorciano quando non c'è spazio (testo grande, iPad, schermata di blocco): dalla forma più lunga
/// alla più corta, sempre di parole intere («4 da controllare» → «4»), mai «4 da contr…». La vista mostra la prima che entra;
/// VoiceOver legge sempre la prima, intera. Dati inventati.
@Suite("Widget: testi che si accorciano senza tagli")
struct TestiCortiWidgetTests {
    // MARK: forme semplici

    @Test("«4 da controllare» diventa «4»; senza dubbi «titolari a posto» diventa «a posto»")
    func daControllare() {
        #expect(ParoleWidget.daControllare(4) == ["4 da controllare", "4"])
        #expect(ParoleWidget.daControllare(1) == ["1 da controllare", "1"])
        #expect(ParoleWidget.daControllare(0) == ["titolari a posto", "a posto"])
    }

    @Test("Lo stato di un giocatore si accorcia come la pillola del campo: «gioca 70%»")
    func stato() {
        #expect(ParoleWidget.stato("In dubbio · gioca 70%") == ["In dubbio · gioca 70%", "gioca 70%"])
        #expect(ParoleWidget.stato("Infortunato") == ["Infortunato"])
        #expect(ParoleWidget.stato("") == [""])
    }

    @Test("Punti attesi: «73,7 punti attesi» → «73,7 attesi»; la scelta tua resta finché entra")
    func puntiAttesi() {
        #expect(ParoleWidget.puntiAttesi(73.7) == ["73,7 punti attesi", "73,7 attesi"])
        #expect(ParoleWidget.puntiAttesi(73.7, tuaScelta: true)
                == ["73,7 punti attesi · la tua scelta", "73,7 attesi · la tua scelta", "73,7 attesi"])
    }

    @Test("Punti attesi con la fascia (rettangolo della Formazione)")
    func puntiConFascia() {
        #expect(ParoleWidget.puntiConFascia(73.7, fascia: "tra 62 e 85") == ["73,7 attesi · tra 62 e 85", "73,7 attesi"])
        #expect(ParoleWidget.puntiConFascia(73.7, fascia: nil) == ["73,7 punti attesi", "73,7 attesi"])
    }

    @Test("Modulo e punti nel rettangolo del Cruscotto: via la fascia, poi la parola «punti»")
    func moduloEPunti() {
        #expect(ParoleWidget.moduloEPunti("3-4-3", punti: 73.7, fascia: "tra 62 e 85")
                == ["3-4-3 · 73,7 punti · tra 62 e 85", "3-4-3 · 73,7 punti", "3-4-3 · 73,7"])
        #expect(ParoleWidget.moduloEPunti("3-4-3", punti: 73.7, fascia: nil) == ["3-4-3 · 73,7 punti", "3-4-3 · 73,7"])
        #expect(ParoleWidget.moduloEPunti(nil, punti: 73.7, fascia: nil).first == "— · 73,7 punti")
    }

    @Test("Titolo del rettangolo della Formazione: resta il modulo")
    func titoloFormazione() {
        #expect(ParoleWidget.titoloFormazione("3-4-3", tuaScelta: false) == ["Formazione 3-4-3", "3-4-3"])
        #expect(ParoleWidget.titoloFormazione("3-4-3", tuaScelta: true) == ["La tua scelta 3-4-3", "3-4-3"])
        #expect(ParoleWidget.titoloFormazione(nil, tuaScelta: false) == ["Formazione —", "—"])
    }

    @Test("Un elenco di nomi perde i nomi in fondo e dice quanti mancano")
    func nomi() {
        #expect(ParoleWidget.nomi(["Sorvani", "Bastrani", "Dimarzi"])
                == ["Sorvani, Bastrani, Dimarzi", "Sorvani, Bastrani e un altro", "Sorvani e altri 2"])
        let otto = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Calvaroglu", "Zelawski", "Marteni", "Thorvan"]
        #expect(ParoleWidget.nomi(otto) == ["Sorvani, Bastrani, Dimarzi e altri 5", "Sorvani, Bastrani e altri 6", "Sorvani e altri 7"])
        #expect(ParoleWidget.nomi(["Sorvani"]) == ["Sorvani"])
        #expect(ParoleWidget.nomi([]).isEmpty)
    }

    @Test("Riga del rettangolo «Da controllare»: prima il cognome, poi lo stato corto")
    func rigaDubbio() {
        let d = DubbioRiassunto(id: 1, nome: "Fabio Dimarzi", ruolo: "D", tipo: "dubbio", pVoto: 0.7)
        #expect(d.formeRiga == ["Fabio Dimarzi · In dubbio · gioca 70%", "Dimarzi · In dubbio · gioca 70%", "Dimarzi · gioca 70%"])
        let corto = DubbioRiassunto(id: 2, nome: "Bastrani", ruolo: "D", tipo: "diffidato", pVoto: nil)
        #expect(corto.formeRiga == ["Bastrani · Diffidato"])
    }

    @Test("Sotto il conto del Cruscotto: quando scade o quando si è chiusa; senza probabili prima l'avviso intero, poi solo l'avviso")
    func sottoScadenza() throws {
        let scadenza = try #require(Quando.data("2026-10-31 20:45"))
        let prima = scadenza.addingTimeInterval(-6 * 3600), dopo = scadenza.addingTimeInterval(3600)
        #expect(ParoleWidget.sottoScadenza(scadenza, adesso: prima, conProbabili: true) == ["alla scadenza, oggi 20:45"])
        #expect(ParoleWidget.sottoScadenza(scadenza, adesso: prima, conProbabili: nil) == ["alla scadenza, oggi 20:45"])
        #expect(ParoleWidget.sottoScadenza(scadenza, adesso: dopo, conProbabili: true) == ["si è chiusa oggi 20:45"])
        // mai «probabili non uscite · oggi 20:45»: sembrerebbe l'ora delle probabili
        #expect(ParoleWidget.sottoScadenza(scadenza, adesso: prima, conProbabili: false)
                == ["probabili non uscite · alla scadenza, oggi 20:45", "probabili non uscite"])
        #expect(ParoleWidget.sottoScadenza(nil, adesso: prima, conProbabili: false) == ["scadenza non nota"])
    }

    @Test("Stato dei dati in linea: senza «Dati delle», poi senza le probabili")
    func statoDati() {
        #expect(ParoleWidget.statoDati(ora: "14:32", probabili: "probabili uscite")
                == ["Dati delle 14:32 · probabili uscite", "14:32 · probabili uscite", "Dati delle 14:32"])
    }

    @Test("Nessuna forma è vuota (tranne lo stato vuoto) e nessuna finisce con i puntini")
    func senzaPuntini() {
        let tutte = ParoleWidget.daControllare(3) + ParoleWidget.stato("In dubbio · gioca 55%") + ParoleWidget.puntiAttesi(70, tuaScelta: true)
            + ParoleWidget.moduloEPunti("4-4-2", punti: 70, fascia: "tra 60 e 80") + ParoleWidget.nomi(["A", "B", "C", "D"])
        #expect(tutte.allSatisfy { !$0.isEmpty && !$0.hasSuffix("…") && !$0.hasSuffix("...") })
    }

    // MARK: parole come la web e come l'app

    @Test("Dopo la scadenza il conto alla rovescia dice «Chiusa», come la web (`oggi.chiusa`)")
    func chiusaComeLaWeb() throws {
        let comeLaWeb = try TestiWeb().italiano("oggi.chiusa")
        #expect(ParoleWidget.chiusa == comeLaWeb)
        let scadenza = try #require(Quando.data("2026-10-31 15:00"))
        #expect(ParoleWidget.conto(fino: scadenza, adesso: scadenza.addingTimeInterval(60)) == "Chiusa")
        #expect(ParoleWidget.conto(fino: scadenza, adesso: scadenza.addingTimeInterval(-24_240)) == "6 h 44 min")
        #expect(ParoleWidget.conto(fino: nil, adesso: scadenza) == "—")
    }

    @Test("App e widget usano lo stesso simbolo dei crediti («C» nel cerchio, `ParoleWidget.simboloCrediti`), mai l'euro")
    func simboloCrediti() throws {
        #expect(ParoleWidget.simboloCrediti == "c.circle")
        // i sorgenti stanno accanto ai test sul Mac di GitHub (come in NomiRealiTests): ios/Sources e ios/WidgetSources
        let ios = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        var conEuro: [String] = [], aMano: [String] = [], letti = 0
        for cartella in ["Sources", "WidgetSources"] {
            let elenco = try #require(FileManager.default.enumerator(at: ios.appendingPathComponent(cartella, isDirectory: true),
                                                                     includingPropertiesForKeys: nil))
            for case let url as URL in elenco where url.pathExtension == "swift" {
                let testo = try String(contentsOf: url, encoding: .utf8)
                letti += 1
                if testo.contains("eurosign") { conEuro.append(url.lastPathComponent) }
                if testo.contains("\"c.circle\""), url.lastPathComponent != "WidgetRiassunto.swift" { aMano.append(url.lastPathComponent) }
            }
        }
        #expect(letti > 10, "i sorgenti non si leggono: il test non proverebbe niente")
        #expect(conEuro.isEmpty, "simbolo dell'euro per i crediti in: \(conEuro)")
        #expect(aMano.isEmpty, "simbolo dei crediti scritto a mano (usa ParoleWidget.simboloCrediti) in: \(aMano)")
    }

    // MARK: tabella e righe del widget «Punti attesi e fatti»

    @Test("Riga della tabella: prima via «10ª di Serie A», poi via la fascia, poi solo i fatti; sempre «Giornata 7», mai «G7» (#299)")
    func rigaTabella() {
        let g = PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66.0, fatti: 63.5, intervallo: IntervalloWidget(basso: 55, alto: 77))
        #expect(PuntiGiornata.FormaRiga.allCases == [.completa, .cortaConFascia, .corta, .soloFatti])
        let completa = g.riga(.completa)
        #expect(completa.titolo == "Giornata 7 · 10ª di Serie A")
        #expect(completa.fascia == "dentro la fascia")
        #expect(completa.punti == "63,5 su 66,0")
        #expect(g.riga(.cortaConFascia).titolo == "Giornata 7")
        #expect(g.riga(.cortaConFascia).fascia == "dentro la fascia")
        #expect(g.riga(.corta).titolo == "Giornata 7")
        #expect(g.riga(.corta).fascia == nil)
        #expect(g.riga(.corta).punti == "63,5 su 66,0")
        #expect(g.riga(.soloFatti).titolo == "Giornata 7")
        #expect(g.riga(.soloFatti).punti == "63,5")
    }

    @Test("Una giornata di un'altra stagione tiene la stagione anche nella forma corta")
    func rigaAltraStagione() {
        let g = PuntiGiornata(giornata: 38, stagione: "2025-26", attesi: 70, fatti: 71)
        #expect(g.riga(.completa).titolo == "38ª giornata di Serie A · 2025-26")
        #expect(g.riga(.cortaConFascia).titolo == "38ª di Serie A · 2025-26")
        #expect(g.riga(.corta).titolo == "38ª di Serie A · 2025-26")
        #expect(g.formeTitolo == ["38ª di Serie A · 2025-26: 71,0 punti", "38ª di Serie A · 2025-26: 71,0"])
    }

    @Test("Rettangolo e riga in linea del widget «Punti»")
    func formeRettangoloERiga() {
        let g = PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66.0, fatti: 63.5)
        #expect(g.formeTitolo == ["Giornata 7 · 10ª di Serie A: 63,5 punti", "Giornata 7: 63,5 punti", "Giornata 7: 63,5"])
        #expect(g.formeInLinea == ["Giornata 7: 63,5 fatti, 66,0 attesi", "Giornata 7: 63,5 su 66,0", "Giornata 7: 63,5 fatti"])
    }

    @Test("Scambio in linea: se i nomi non entrano resta il guadagno")
    func scambioInLinea() {
        let s = ScambioWidget(do: [GiocatoreScambio(nome: "Nico Zanvolo"), GiocatoreScambio(nome: "Marcello Carsetti")],
                              ricevo: [GiocatoreScambio(nome: "Marzio Zaviani")], guadagnoMio: 3.4)
        #expect(s.formeInLinea == ["Scambio +3,4: Zanvolo, Carsetti per Zaviani", "Scambio +3,4 punti"])
    }

    // MARK: quante righe provare (widget «Da controllare»)

    @Test("Righe da provare: dal massimo che c'è fino a una", arguments: [
        (3, 4, [3, 2, 1]), (6, 4, [4, 3, 2, 1]), (3, 2, [2, 1]), (3, 1, [1]),
    ])
    func righeDaProvare(massimo: Int, totale: Int, attese: [Int]) {
        #expect(DisposizioneWidget.righeDaProvare(massimo: massimo, totale: totale) == attese)
    }

    @Test("Punti, misura grande: prima via le frasi di riepilogo, poi le righe più vecchie (mai meno di due)")
    func provePuntiGrande() {
        let prove = DisposizioneWidget.provePuntiGrande(righe: 5, frasi: 2)
        #expect(prove.map(\.righe) == [5, 5, 5, 4, 3, 2])
        #expect(prove.map(\.frasi) == [2, 1, 0, 0, 0, 0])
        #expect(DisposizioneWidget.provePuntiGrande(righe: 2, frasi: 0).map(\.righe) == [2])
        #expect(DisposizioneWidget.provePuntiGrande(righe: 1, frasi: 1).map(\.righe) == [1, 1])
        #expect(DisposizioneWidget.provePuntiGrande(righe: 0, frasi: 0).count == 1)
    }

    @Test("Righe da provare: mai zero forme, mai più di sei")
    func righeDaProvareLimiti() {
        #expect(DisposizioneWidget.righeDaProvare(massimo: 3, totale: 0) == [0])
        #expect(DisposizioneWidget.righeDaProvare(massimo: 10, totale: 9).count == 6)
        #expect(DisposizioneWidget.righeDaProvare(massimo: 10, totale: 9).first == 9)
    }

    // MARK: fasi della giornata (dopo la scadenza e a giornata finita)

    /// Il riassunto di un `/api/widget` inventato con la fase data.
    private func riassunto(_ fase: String) throws -> RiassuntoOggi {
        let corpo: String
        switch fase {
        case "in_corso":
            corpo = #"""
            {"giornata": 11, "giornata_lega": 8, "fase": "in_corso", "scadenza": "2026-10-31 14:50",
             "in_corso": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 41.5, "punti_previsti": 72.4, "ancora_da_giocare": 4,
                          "giocatori": [], "sostituzioni": []}}
            """#
        case "finita":
            // a giornata finita giornata e scadenza sono già quelle della prossima (la 9 della lega)
            corpo = #"""
            {"giornata": 12, "giornata_lega": 9, "fase": "finita", "scadenza": "2026-11-07 14:50",
             "riepilogo": {"giornata": 11, "giornata_lega": 8, "nel_diario": true, "punti_fatti": 69.5, "punti_attesi": 73.7}}
            """#
        default:
            corpo = #"{"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 14:50"}"#
        }
        let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
        return try #require(w.comeRiassuntoOggi())
    }

    @Test("Dopo la scadenza il titolo è «Chiusa», non «Giornata in corso»")
    func titoloInCorso() throws {
        let r = try riassunto("in_corso")
        #expect(r.titoloFase == "Chiusa")
        #expect(r.etichettaTestata == "Giornata 8 · 11ª di Serie A")
        #expect(r.testaRettangoloFase == "Giornata 8 · Chiusa")
        #expect(r.rigaInLineaFase == "Giornata 8: 41,5 punti fatti finora")
    }

    @Test("Dopo la scadenza la frase è quella della web (`oggi.chiusa_dettaglio`), senza ripetere la giornata, e dice dove sono i punti")
    func fraseInCorso() throws {
        let r = try riassunto("in_corso")
        let adesso = try #require(Quando.data("2026-10-31 18:00"))
        // docs/COERENZA-WEB-IPHONE.md, «Giornata: le forme»: la giornata è scritta sopra e non si ripete
        let attesa = "La formazione si è chiusa oggi 14:50"
        #expect(r.fraseFase(adesso: adesso) == attesa + ". I punti fatti sono in Oggi.")
        if let web = try TestiWeb().italianoDopo299("oggi.chiusa_dettaglio", "oggi 14:50") { #expect(web == attesa) }
    }

    @Test("A giornata finita la testata dice la giornata finita (la 8), non la prossima (la 9)")
    func testataFinita() throws {
        let r = try riassunto("finita")
        #expect(r.etichettaGiornata == "Giornata 9 · 12ª di Serie A", "la prossima resta nei campi di sempre")
        #expect(r.etichettaTestata == "Giornata 8 · 11ª di Serie A")
        // come la web (`oggi.giornata_finita`): la forma intera in testa, poi i due punti
        let attesa = "Giornata 8 · 11ª di Serie A: finita"
        #expect(r.titoloFase == attesa)
        if let web = try TestiWeb().italianoDopo299("oggi.giornata_finita", "Giornata 8 · 11ª di Serie A") { #expect(web == attesa) }
        #expect(r.formeTitoloFase == [attesa, "Giornata 8: finita"])
        #expect(r.voceTitoloFase == "Giornata 8, 11ª di Serie A: finita")
        #expect(r.testaRettangoloFase == "Giornata 8 finita")
        #expect(r.rigaInLineaFase == "Giornata 8: 69,5 punti fatti")
        #expect(r.formeSottotitoloRettangolo == ["Prossima: Giornata 9 · 12ª di Serie A", "Prossima: Giornata 9"])
        #expect(r.voceSottotitoloRettangolo == "Prossima: Giornata 9, 12ª di Serie A")
        #expect(r.fraseFase(adesso: Date()) == "Si ricomincia con la prossima giornata.")
    }

    @Test("Prima della scadenza niente titolo di fase; la testata è la giornata da giocare")
    func prima() throws {
        let r = try riassunto("prima")
        #expect(r.titoloFase == nil)
        #expect(r.fraseFase(adesso: Date()) == nil)
        #expect(r.etichettaTestata == "Giornata 8 · 11ª di Serie A")
        #expect(r.sottotitoloRettangolo == "Giornata 8 · 11ª di Serie A")
        #expect(r.formeGiornata == ["Giornata 8 · 11ª di Serie A", "Giornata 8"])
        #expect(r.voceGiornata == "Giornata 8, 11ª di Serie A")
    }

    @Test("A giornata finita senza il numero della giornata chiusa: niente numero sbagliato in testata")
    func finitaSenzaNumero() throws {
        let corpo = #"{"giornata": 12, "giornata_lega": 9, "fase": "finita", "riepilogo": {"nel_diario": true, "punti_fatti": 60}}"#
        let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
        let r = try #require(w.comeRiassuntoOggi())
        #expect(r.etichettaTestata == nil)
        #expect(r.titoloFase == "Giornata finita")
    }
}
