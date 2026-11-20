import Foundation
import Testing
@testable import Schieraxi

/// Widget «Prossima giornata» a giornata in corso come la testa della Formazione dell'app e la web (#774): i punti a fine giornata
/// senza decimali («circa 75 a fine giornata», `Formato.decimali(p, cifre: 0)` come `TestaFormazione` e `num(…, 0)` della web),
/// «punti finora» e chi deve ancora giocare con le frasi del catalogo comune (`formazione.punti_finora`, `formazione.circa_fine`,
/// `oggi.ancora_da_giocare`, `oggi.tutti_giocato`). Prima il widget scriveva «circa 74,6 a fine giornata», «1 deve ancora giocare»
/// e «Hanno giocato tutti» a mano. Dati inventati.
@Suite("Widget «Prossima giornata» in corso: numeri e frasi come l'app (#774)")
struct WidgetInCorsoComeLAppTests {
    /// Oggi a giornata in corso: 41,5 punti fatti, `previsti` a fine giornata, `ancora` giocatori che devono ancora giocare.
    static func oggi(previsti: Double = 74.6, ancora: Int = 4) throws -> Oggi {
        try Decodifica.decodifica(Data(#"""
        {"giornata": 11, "giornata_lega": 8, "iniziata": true, "fase": "in_corso", "scadenza": "2026-10-31 14:50",
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 73.7},
         "in_corso": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 41.5, "punti_previsti": \#(previsti),
                      "ancora_da_giocare": \#(ancora)}}
        """#.utf8))
    }

    /// La formazione della giornata 8 della lega (11ª di Serie A), come la mostra la Formazione dell'app.
    static func formazione() throws -> Formazione {
        try Decodifica.decodifica(Data(#"""
        {"giornata": 11, "giornata_lega": 8, "modulo": "3-4-3", "punteggio_atteso": 73.7, "titolari": [], "panchina": [], "iniziata": true}
        """#.utf8))
    }

    /// La testa della Formazione dell'app per la stessa risposta.
    static func testa(_ o: Oggi) throws -> TestaFormazione {
        TestaFormazione.per(oggi: o, formazione: try formazione(), adesso: try #require(Quando.data("2026-10-31 18:00")))
    }

    @Test("I punti a fine giornata senza decimali: «circa 75 a fine giornata», la stessa frase della testa della Formazione",
          arguments: [(74.6, "75"), (72.4, "72")])
    func puntiAFineGiornataSenzaDecimali(previsti: Double, atteso: String) throws {
        let o = try Self.oggi(previsti: previsti)
        let r = RiassuntoOggi(oggi: o)
        let fine = try #require(r.puntiFineTesto)
        #expect(fine == "circa \(atteso) a fine giornata")
        #expect(fine == Catalogo.Formazione.circaFine(n: Formato.decimali(previsti, cifre: 0)))
        // l'app: «punti finora · circa 75 a fine giornata»
        let testa = try Self.testa(o)
        let app = try #require(testa.testoPunti)
        #expect(app == "\(Catalogo.Formazione.puntiFinora) · \(fine)")
    }

    @Test("Chi deve ancora giocare con le frasi del catalogo, plurale compreso, uguale alla riga sotto i punti dell'app",
          arguments: [0, 1, 4])
    func ancoraDaGiocareComeLApp(ancora: Int) throws {
        let o = try Self.oggi(ancora: ancora)
        let r = RiassuntoOggi(oggi: o)
        let frase = try #require(r.ancoraDaGiocareTesto)
        #expect(frase == (ancora == 0 ? Catalogo.Oggi.tuttiGiocato : Catalogo.Oggi.ancoraDaGiocare(ancora)))
        #expect(frase == TestiFase.ancora(ancora))
        let testa = try Self.testa(o)
        #expect(frase == testa.sotto)
    }

    @Test("Le frasi intere: «Hanno giocato tutti: mancano solo i voti ufficiali.», «1 giocatore deve ancora giocare»",
          arguments: [(0, "Hanno giocato tutti: mancano solo i voti ufficiali."), (1, "1 giocatore deve ancora giocare"),
                      (4, "4 giocatori devono ancora giocare")])
    func frasiIntere(ancora: Int, frase: String) throws {
        let r = RiassuntoOggi(oggi: try Self.oggi(ancora: ancora))
        #expect(r.ancoraDaGiocareTesto == frase)
    }

    @Test("VoiceOver: «punti finora», il numero a fine giornata senza decimali e la frase intera di chi deve ancora giocare")
    func voceOverComeLApp() throws {
        let r = RiassuntoOggi(oggi: try Self.oggi())
        #expect(r.descrizioneFase == "Giornata 8, 11ª di Serie A: formazione chiusa, 41,5 punti finora, circa 75 a fine giornata. "
                + "4 giocatori devono ancora giocare.")
    }

    @Test("VoiceOver con tutti che hanno giocato: la frase del catalogo finisce già con il punto, niente «..»")
    func voceOverSenzaDoppioPunto() throws {
        let r = RiassuntoOggi(oggi: try Self.oggi(ancora: 0))
        let voce = try #require(r.descrizioneFase)
        #expect(voce.hasSuffix("circa 75 a fine giornata. Hanno giocato tutti: mancano solo i voti ufficiali."))
        #expect(!voce.contains(".."))
    }

    @Test("La riga in linea della schermata di blocco: «punti finora» come l'app, poi solo il numero")
    func rigaInLinea() throws {
        let r = RiassuntoOggi(oggi: try Self.oggi())
        #expect(r.formeRigaInLineaFase == ["Giornata 8: 41,5 \(Catalogo.Formazione.puntiFinora)", "Giornata 8: 41,5"])
    }

    /// Nessun numero «circa …» scritto con un decimale nei file del widget (prima `Condiviso.swift` e `WidgetOggi.swift` usavano
    /// `Formato.punti`, una cifra decimale, per i punti a fine giornata).
    @Test("Nei file del widget nessun «circa» con il numero a un decimale", arguments: [
        "Sources/Support/Condiviso.swift", "WidgetSources/WidgetOggi.swift",
    ])
    func maiCircaConUnDecimale(file: String) throws {
        var cartella = URL(fileURLWithPath: #filePath)
        for _ in 0..<3 { cartella.deleteLastPathComponent() }          // questo file, SchieraxiTests, Tests
        let testo = try #require(try? String(contentsOf: cartella.appendingPathComponent(file), encoding: .utf8),
                                 "non riesco a leggere ios/\(file)")
        // il testo «circa \(Formato.punti(…))» di prima; i «66,0 attesi» a giornata finita restano con il decimale
        let righe = RestiDalCatalogoTests.soloCodice(testo).components(separatedBy: .newlines)
        let sbagliate = righe.filter { $0.contains(#"circa \(Formato.punti("#) }
        #expect(sbagliate.isEmpty, "\(file): «circa» con Formato.punti (un decimale): \(sbagliate)")
    }
}
