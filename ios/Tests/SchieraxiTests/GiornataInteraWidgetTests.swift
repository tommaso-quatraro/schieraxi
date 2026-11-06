import Foundation
import Testing
@testable import Schieraxi

/// Issue #299, l'ultimo pezzo: nei widget la giornata si scrive «Giornata 8 · 11ª di Serie A» o «Giornata 8», mai «G8» né «G11»
/// (`docs/COERENZA-WEB-IPHONE.md`, «Giornata: le forme»: la sigla solo nelle colonne strette, sotto un titolo). La stessa funzione
/// del widget Formazione (`ParoleWidget.formeGiornata`) per Cruscotto, Prossima giornata, Attesi e fatti, Da controllare, Chi gioca
/// e Dati; dove la giornata non entra accanto al titolo si perde il titolo (resta il simbolo), non la giornata. VoiceOver legge
/// sempre la forma intera. Numeri inventati.
@Suite("Widget: la giornata intera, mai «G8» (#299)")
struct GiornataInteraWidgetTests {
    private let lega = NomeGiornata(serieA: 11, lega: 8)
    private let soloSerieA = NomeGiornata(serieA: 11, lega: nil)

    /// true se il testo contiene una sigla di giornata («G8», «G11»), la forma che nei widget non si usa più.
    private func haSigla(_ testo: String) -> Bool { testo.range(of: #"\bG\d+\b"#, options: .regularExpression) != nil }

    /// Il riassunto di un `/api/widget` inventato nella fase data (`prima`, `in_corso`, `finita`). `conLega` false: senza
    /// `giornata_lega`, come prima che la lega parta o con un server che non lo manda («11ª di Serie A»).
    private func riassunto(_ fase: String, conLega: Bool = true) throws -> RiassuntoOggi {
        var corpo: String
        switch fase {
        case "in_corso":
            corpo = #"""
            {"giornata": 11, "giornata_lega": 8, "fase": "in_corso", "scadenza": "2026-10-31 14:50",
             "in_corso": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 41.5, "punti_previsti": 72.4, "ancora_da_giocare": 4,
                          "giocatori": [], "sostituzioni": []}}
            """#
        case "finita":
            corpo = #"""
            {"giornata": 12, "giornata_lega": 9, "fase": "finita", "scadenza": "2026-11-07 14:50",
             "riepilogo": {"giornata": 11, "giornata_lega": 8, "nel_diario": true, "punti_fatti": 69.5, "punti_attesi": 73.7}}
            """#
        default:
            corpo = #"{"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 14:50"}"#
        }
        if !conLega {
            corpo = corpo.replacingOccurrences(of: #""giornata_lega": \d+"#, with: #""giornata_lega": null"#, options: .regularExpression)
        }
        let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
        return try #require(w.comeRiassuntoOggi())
    }

    /// Le giornate di «Attesi e fatti» da provare: con il numero della lega, senza (stagione in corso, server che non lo manda)
    /// e di una stagione passata (agosto: l'ultima giornata è la 38 dell'anno prima).
    private let giornatePunti = [
        PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66, fatti: 63.5),
        PuntiGiornata(giornata: 10, attesi: 66, fatti: 63.5),
        PuntiGiornata(giornata: 38, stagione: "2025-26", attesi: 70, fatti: 71),
    ]

    @Test("Nei cerchi della schermata di blocco «Giornata 8» (rimpicciolita se serve), mai «G8»")
    func cerchio() {
        #expect(ParoleWidget.giornataNelCerchio(lega) == "Giornata 8")
        #expect(ParoleWidget.giornataNelCerchio(soloSerieA) == "11ª di Serie A")
        #expect(ParoleWidget.giornataNelCerchio(nil) == "Giornata –", "senza giornata il trattino del dato che manca")
    }

    @Test("Testata con titolo: prima il titolo con ogni forma della giornata, poi il solo simbolo; la forma più corta è «Giornata 8»")
    func testata() {
        typealias F = FormaTestataWidget
        #expect(ParoleWidget.testata(lega, soloCorta: false) == [
            F(conTitolo: true, giornata: "Giornata 8 · 11ª di Serie A"), F(conTitolo: true, giornata: "Giornata 8"),
            F(conTitolo: false, giornata: "Giornata 8 · 11ª di Serie A"), F(conTitolo: false, giornata: "Giornata 8"),
        ])
        #expect(ParoleWidget.testata(lega, soloCorta: true) == [F(conTitolo: true, giornata: "Giornata 8"), F(conTitolo: false, giornata: "Giornata 8")])
        #expect(ParoleWidget.testata(soloSerieA, soloCorta: true).map(\.giornata) == ["11ª di Serie A", "11ª di Serie A"])
    }

    @Test("Prossima giornata e Da controllare: le righe delle fasi con «Giornata 8», e la riga in linea che si accorcia di parole")
    func fasi() throws {
        let inCorso = try riassunto("in_corso")
        #expect(inCorso.testaRettangoloFase == "Giornata 8 · Chiusa")
        #expect(inCorso.formeRigaInLineaFase == ["Giornata 8: 41,5 punti fatti finora", "Giornata 8: 41,5 punti fatti", "Giornata 8: 41,5"])
        let finita = try riassunto("finita")
        #expect(finita.testaRettangoloFase == "Giornata 8 finita")
        #expect(finita.formeRigaInLineaFase == ["Giornata 8: 69,5 punti fatti", "Giornata 8: 69,5"])
        #expect(finita.formeTitoloFase == ["Giornata 8 · 11ª di Serie A: finita", "Giornata 8: finita"])
        #expect(finita.formeGiornataChiusa == ["Giornata 8 · 11ª di Serie A", "Giornata 8"])
        #expect(finita.formeSottotitoloRettangolo == ["Prossima: Giornata 9 · 12ª di Serie A", "Prossima: Giornata 9"])
        #expect(try riassunto("prima").formeGiornata == ["Giornata 8 · 11ª di Serie A", "Giornata 8"])
    }

    @Test("Attesi e fatti: testata, tabella, rettangolo e riga in linea con «Giornata 7», mai «G7»")
    func attesiEFatti() {
        let g = PuntiGiornata(giornata: 10, giornataLega: 7, attesi: 66.0, fatti: 63.5)
        #expect(g.formeTestata.map(\.giornata) == ["Giornata 7", "Giornata 7"])
        #expect(PuntiGiornata.FormaRiga.allCases.map { g.riga($0).titolo } == ["Giornata 7 · 10ª di Serie A", "Giornata 7", "Giornata 7", "Giornata 7"])
        #expect(g.formeTitolo == ["Giornata 7 · 10ª di Serie A: 63,5 punti", "Giornata 7: 63,5 punti", "Giornata 7: 63,5"])
        #expect(g.formeSottoTitolo == ["attesi 66,0 · −2,5"])
        #expect(g.formeInLinea == ["Giornata 7: 63,5 fatti, 66,0 attesi", "Giornata 7: 63,5 su 66,0", "Giornata 7: 63,5 fatti", "Giornata 7: 63,5"])
    }

    @Test("Stagione passata (agosto): la stagione scende sulla seconda riga del rettangolo, e la riga in linea la perde per ultima")
    func stagionePassata() {
        let g = PuntiGiornata(giornata: 38, stagione: "2025-26", attesi: 70, fatti: 71)
        #expect(g.formeTitolo == ["38ª giornata di Serie A: 71,0 punti", "38ª di Serie A: 71,0 punti", "38ª di Serie A: 71,0"])
        #expect(g.formeSottoTitolo == ["2025-26 · attesi 70,0 · +1,0", "2025-26 · +1,0"], "la stagione non si perde mai")
        #expect(g.formeInLinea == ["38ª di Serie A · 2025-26: 71,0 su 70,0", "38ª di Serie A · 2025-26: 71,0 fatti",
                                   "38ª di Serie A: 71,0 fatti", "38ª di Serie A: 71,0"])
        #expect(g.descrizione.contains("2025-26"), "VoiceOver dice la stagione anche quando la riga in linea non c'è")
    }

    /// Quanti caratteri entrano, al più, nell'ultima forma: titolo del rettangolo in `.headline` (circa 160 punti), seconda riga
    /// in `.caption`, riga in linea della schermata di blocco (circa 25). Con o senza lega, stagione in corso o passata.
    @Test("L'ultima forma del rettangolo e della riga in linea è abbastanza corta da entrare, anche senza il numero della lega")
    func ultimeFormeCorte() throws {
        for g in giornatePunti {
            let titolo = try #require(g.formeTitolo.last), sotto = try #require(g.formeSottoTitolo.last)
            let inLinea = try #require(g.formeInLinea.last)
            #expect(titolo.count <= 20, "titolo del rettangolo troppo lungo: «\(titolo)»")
            #expect(sotto.count <= 24, "seconda riga troppo lunga: «\(sotto)»")
            #expect(inLinea.count <= 25, "riga in linea troppo lunga: «\(inLinea)»")
        }
        for conLega in [true, false] {
            for fase in ["in_corso", "finita"] {
                let r = try riassunto(fase, conLega: conLega)
                let inLinea = try #require(r.formeRigaInLineaFase.last)
                #expect(inLinea.count <= 25, "riga in linea della fase troppo lunga: «\(inLinea)»")
                #expect(r.testaRettangoloFase.count <= 26, "prima riga del rettangolo troppo lunga: «\(r.testaRettangoloFase)»")
            }
        }
    }

    @Test("Nessuna forma dei widget ha la sigla della giornata, con e senza il numero della lega, in nessuna fase")
    func maiLaSigla() throws {
        var forme: [String] = []
        for nome in [lega, soloSerieA] {
            forme += ParoleWidget.formeGiornata(nome) + [ParoleWidget.giornataNelCerchio(nome)]
            forme += (ParoleWidget.testata(nome, soloCorta: false) + ParoleWidget.testata(nome, soloCorta: true)).map(\.giornata)
        }
        for conLega in [true, false] {
            for fase in ["prima", "in_corso", "finita"] {
                let r = try riassunto(fase, conLega: conLega)
                forme += r.formeGiornata + r.formeGiornataChiusa + (r.formeTitoloFase ?? []) + r.formeSottotitoloRettangolo
                forme += [r.testaRettangoloFase] + r.formeRigaInLineaFase
            }
        }
        for g in giornatePunti {
            forme += g.formeTestata.map(\.giornata) + PuntiGiornata.FormaRiga.allCases.map { g.riga($0).titolo }
            forme += g.formeTitolo + g.formeSottoTitolo + g.formeInLinea
        }
        #expect(forme.count > 40, "troppe poche forme: il test non proverebbe niente")
        let conSigla = forme.filter { haSigla($0) }
        #expect(conSigla.isEmpty, "forme con la sigla: \(conSigla)")
    }
}
