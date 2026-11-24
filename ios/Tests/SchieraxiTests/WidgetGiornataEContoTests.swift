import Foundation
import Testing
@testable import Schieraxi

/// Collaudo dei widget del 25/11 (#871). La giornata non si perde mai (Formazione extra large e rettangolo della schermata di
/// blocco con «2 da controllare»); il widget Prossima giornata sulla schermata di blocco mostra il conto alla rovescia, che è il
/// suo motivo, e non la stessa riga della Formazione; data e ora non si spezzano su due righe («lun / 23 20:35»); «Prossima:» e
/// il conto alla rovescia stanno in un testo solo, della stessa grandezza. Le viste dei widget non entrano nei test: qui le
/// parole e le scelte di disposizione (`ParoleWidget`, `DisposizioneWidget`, `RiassuntoOggi`). Dati inventati.
@Suite("Widget: giornata e avvisi dove mancavano, conto alla rovescia, data e ora unite (#871)")
struct WidgetGiornataEContoTests {
    /// Lo spazio che non va a capo: tiene uniti giorno, numero e ora («lun 23 20:35») e i pezzi del conto alla rovescia.
    private static let unito = "\u{00A0}"
    /// Venerdì 20 novembre 2026 alle 10:00, ora italiana.
    private static let adesso = "2026-11-20 10:00"

    private func data(_ testo: String) throws -> Date { try #require(Quando.data(testo)) }

    /// La giornata 11 di Serie A, 8 della lega, con la scadenza data (o nessuna).
    private func prima(scadenza: String?, lega: Int? = 8) throws -> RiassuntoOggi {
        RiassuntoOggi(giornata: 11, inizio: try scadenza.map { try data($0) }, modulo: "3-4-3", punti: 72.7, daControllare: 2,
                      probabili: true, scaricatoIl: try data(Self.adesso), giornataLega: lega)
    }

    // MARK: data e ora unite

    @Test("«alla scadenza, lun 23 20:35»: giorno, numero e ora restano uniti, si va a capo solo dopo la virgola", arguments: [
        ("2026-11-23 20:35", "alla scadenza, lun\u{00A0}23\u{00A0}20:35"),
        ("2026-11-20 12:20", "alla scadenza, oggi\u{00A0}12:20"),
        ("2026-12-08 18:30", "alla scadenza, mar\u{00A0}8\u{00A0}dic\u{00A0}18:30"),   // oltre la settimana anche il mese
    ])
    func allaScadenza(scadenza: String, attesa: String) throws {
        let testo = ParoleWidget.allaScadenza(try data(scadenza), adesso: try data(Self.adesso))
        #expect(testo == attesa)
        // l'unico punto dove si può andare a capo è dopo la virgola
        #expect(testo.filter { $0 == " " }.count == 2, "«\(testo)»")
    }

    @Test("Nessun widget scrive «alla scadenza, …» a mano: tutti passano da `ParoleWidget.allaScadenza`, con data e ora unite")
    func nessunaScadenzaAMano() throws {
        let aMano = try sorgentiWidget().filter { $0.testo.contains("alla scadenza, \\(") }.map(\.nome)
        #expect(aMano.isEmpty, "«alla scadenza, …» scritto a mano (data e ora si spezzano) in: \(aMano)")
    }

    // MARK: «Prossima:» e il conto alla rovescia, un testo solo

    @Test("«Prossima: 4 giorni 1 h» in un testo solo: il conto non si spezza e va a capo intero dopo «Prossima:»")
    func prossima() throws {
        let scadenza = try data("2026-11-24 11:00"), ora = try data(Self.adesso)
        #expect(ParoleWidget.prossima(fino: scadenza, adesso: ora) == "Prossima: 4\(Self.unito)giorni\(Self.unito)1\(Self.unito)h")
        #expect(ParoleWidget.voceProssima(fino: scadenza, adesso: ora) == "Prossima: 4 giorni e 1 ora", "VoiceOver legge le parole intere")
        let vicina = try data("2026-11-20 16:44")
        #expect(ParoleWidget.prossima(fino: vicina, adesso: ora) == "Prossima: 6\(Self.unito)h\(Self.unito)44\(Self.unito)min")
    }

    // Prima «Prossima:» e il conto erano due testi con `minimumScaleFactor` ciascuno: con il testo molto grande «4 giorni 1 h»
    // usciva più piccolo di «Prossima:» (foto dei piccoli e dei rettangoli).
    @Test("Nessun widget mette «Prossima:» in un testo a parte dal conto alla rovescia")
    func prossimaNonSiSpezza() throws {
        let aParte = try sorgentiWidget().filter { $0.testo.contains("Text(\"Prossima:\")") }.map(\.nome)
        #expect(aParte.isEmpty, "«Prossima:» in un testo a parte in: \(aParte)")
    }

    // MARK: Prossima giornata sulla schermata di blocco: il conto alla rovescia

    @Test("Rettangolo a giornata finita: «Giornata 8: finita», come il widget Da controllare e il documento")
    func rettangoloFinita() throws {
        let corpo = #"""
        {"giornata": 12, "giornata_lega": 9, "fase": "finita", "scadenza": "2026-11-28 14:50",
         "riepilogo": {"giornata": 11, "giornata_lega": 8, "nel_diario": true, "punti_fatti": 69.5, "punti_attesi": 73.7}}
        """#
        let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
        let r = try #require(w.comeRiassuntoOggi())
        #expect(r.testaRettangoloFase == "Giornata 8: finita")
        #expect(r.testaRettangoloFase == r.formeTitoloFase?.last, "la stessa forma corta della testata di Da controllare")
    }

    @Test("Riga della schermata di blocco: la giornata con il conto alla rovescia, che resta anche quando la giornata non entra")
    func rigaConConto() throws {
        let r = try prima(scadenza: "2026-11-21 14:50"), ora = try data("2026-11-20 21:00")
        #expect(r.formeRigaInLineaConto(adesso: ora) == ["Giornata 8: 17 h 50 min", "17 h 50 min"])
        #expect(r.voceRigaInLineaConto(adesso: ora) == "Giornata 8, 11ª di Serie A: 17 ore e 50 minuti")
        #expect(r.formeRigaInLineaConto(adesso: ora) != ParoleWidget.moduloEPunti(r.modulo, punti: r.punti, fascia: nil),
                "prima era la stessa riga della Formazione consigliata")
        // dopo la scadenza «Chiusa», come il conto alla rovescia di tutti i widget
        let dopo = try data("2026-11-21 15:00")
        #expect(r.formeRigaInLineaConto(adesso: dopo) == ["Giornata 8: Chiusa", "Chiusa"])
        #expect(r.voceRigaInLineaConto(adesso: dopo) == "Giornata 8, 11ª di Serie A: Chiusa")
    }

    @Test("Riga senza il numero della lega o senza scadenza: forme corte e mai vuote")
    func rigaCasiRari() throws {
        let ora = try data("2026-11-20 21:00")
        let senzaLega = try prima(scadenza: "2026-11-24 23:00", lega: nil)
        let forme = senzaLega.formeRigaInLineaConto(adesso: ora)
        #expect(forme == ["11ª di Serie A: 4 giorni 2 h", "4 giorni 2 h"])
        // la riga in linea tiene circa 25 caratteri (GiornataInteraWidgetTests)
        #expect((forme.last ?? "").count <= 25)
        // senza scadenza non c'è un conto: resta la formazione, come prima
        let senzaScadenza = try prima(scadenza: nil)
        #expect(senzaScadenza.formeRigaInLineaConto(adesso: ora) == ParoleWidget.moduloEPunti("3-4-3", punti: 72.7, fascia: nil))
    }

    // MARK: Formazione sulla schermata di blocco: la giornata anche con «2 da controllare»

    private typealias ProvaRettangolo = DisposizioneWidget.ProvaRettangoloFormazione

    @Test("Rettangolo della Formazione: la giornata sopra il titolo; dove non entra accanto al modulo; «da controllare» resta")
    func rettangoloFormazione() {
        #expect(DisposizioneWidget.proveRettangoloFormazione(conGiornata: true, daControllare: 2) == [
            ProvaRettangolo(giornata: .sopra, daControllare: true),
            ProvaRettangolo(giornata: .accanto, daControllare: true),
        ])
        #expect(DisposizioneWidget.proveRettangoloFormazione(conGiornata: true, daControllare: 0) == [
            ProvaRettangolo(giornata: .sopra, daControllare: false),
            ProvaRettangolo(giornata: .accanto, daControllare: false),
        ])
        // senza giornata dal server non c'è niente da spostare
        #expect(DisposizioneWidget.proveRettangoloFormazione(conGiornata: false, daControllare: 1) == [
            ProvaRettangolo(giornata: nil, daControllare: true),
        ])
    }

    // MARK: Formazione extra large: giornata, «2 da controllare» e «7 in panchina» come il grande

    @Test("Extra large: la prima prova è il campo di prima; poi volti più piccoli, per ultimi via i cognomi (li ha l'elenco accanto)")
    func proveExtraLarge() throws {
        let prove = DisposizioneWidget.proveCampoExtraLarge
        #expect(prove.first == DisposizioneWidget.ProvaCampoExtraLarge(lato: 48, conNomi: true))
        #expect((3...6).contains(prove.count), "PrimaCheEntra prova al più sei forme; servono almeno tre prove")
        #expect(zip(prove, prove.dropFirst()).allSatisfy { $0.lato > $1.lato || ($0.lato == $1.lato && $0.conNomi && !$1.conNomi) },
                "ogni prova deve essere più bassa della precedente")
        // con una chiusura, non con un percorso (come in WidgetOraCopiaTests)
        #expect(prove.dropLast().allSatisfy { $0.conNomi })
        #expect(prove.last?.conNomi == false)
    }

    // MARK: sorgenti

    /// I sorgenti dei widget (ios/WidgetSources), che stanno accanto ai test sul Mac di GitHub (come in WidgetOraCopiaTests).
    private func sorgentiWidget() throws -> [(nome: String, testo: String)] {
        let ios = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let elenco = try #require(FileManager.default.enumerator(at: ios.appendingPathComponent("WidgetSources", isDirectory: true),
                                                                 includingPropertiesForKeys: nil))
        var sorgenti: [(nome: String, testo: String)] = []
        for case let url as URL in elenco where url.pathExtension == "swift" {
            sorgenti.append((url.lastPathComponent, try String(contentsOf: url, encoding: .utf8)))
        }
        #expect(sorgenti.count > 5, "i sorgenti non si leggono: il test non proverebbe niente")
        return sorgenti
    }
}
