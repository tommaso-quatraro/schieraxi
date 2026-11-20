import Foundation
import Testing
@testable import Schieraxi

/// La riga della copia salvata nei widget (#834). Il giorno conta: una copia di venerdì sera vista la domenica non può dire solo
/// «dati delle 18:30», sembrerebbe di oggi. Di oggi resta la sola ora; degli altri giorni il giorno scritto come `Quando.relativa`
/// («dati di ieri 18:30», «dati di mar 17 21:05»), sempre in ora italiana e contato dall'istante della voce della timeline.
/// Nei widget Formazione piccolo e medio la riga c'è anche con giocatori da controllare: prima «2 da controllare» la toglieva e
/// una copia vecchia sembrava attuale. Dati inventati.
@Suite("Widget: l'ora della copia salvata")
struct WidgetOraCopiaTests {
    /// Venerdì 20 novembre 2026 alle 10:00, ora italiana.
    private static let adesso = "2026-11-20 10:00"

    private func data(_ testo: String) throws -> Date { try #require(Quando.data(testo)) }

    // MARK: il testo della copia

    @Test("Di oggi la sola ora; degli altri giorni anche il giorno, e dove non entra il giorno senza l'ora", arguments: [
        ("2026-11-20 08:15", ["dati delle 08:15"]),
        ("2026-11-19 18:30", ["dati di ieri 18:30", "dati di ieri"]),
        ("2026-11-17 21:05", ["dati di mar 17 21:05", "dati di mar 17"]),            // entro la settimana il giorno e il numero
        ("2026-11-08 18:30", ["dati di dom 8 nov 18:30", "dati di dom 8 nov"]),      // oltre, anche il mese
    ])
    func formeDellaCopia(scaricata: String, attese: [String]) throws {
        let copia = try data(scaricata), ora = try data(Self.adesso)
        #expect(ParoleWidget.datiSalvati(copia, adesso: ora) == attese)
    }

    @Test("A mezzanotte, in ora italiana, la copia delle 23:30 diventa di ieri; quella delle 00:05 resta di oggi fino a sera")
    func mezzanotte() throws {
        let tardi = try data("2026-11-19 23:30"), dopoMezzanotte = try data("2026-11-20 00:30")
        #expect(ParoleWidget.datiSalvati(tardi, adesso: dopoMezzanotte) == ["dati di ieri 23:30", "dati di ieri"])
        let presto = try data("2026-11-20 00:05"), sera = try data("2026-11-20 23:55")
        #expect(ParoleWidget.datiSalvati(presto, adesso: sera) == ["dati delle 00:05"])
    }

    @Test("Le forme della copia non sono mai vuote e non finiscono con i puntini")
    func senzaPuntini() throws {
        let ora = try data(Self.adesso)
        let tutte = try ["2026-11-20 08:15", "2026-11-19 18:30", "2026-11-17 21:05", "2026-11-08 18:30"]
            .flatMap { ParoleWidget.datiSalvati(try data($0), adesso: ora) }
        #expect(tutte.allSatisfy { !$0.isEmpty && !$0.hasSuffix("…") && !$0.hasSuffix("...") })
    }

    @Test("Nessun widget scrive l'ora della copia a mano: tutti passano da `ParoleWidget.datiSalvati` (`RigaCopia`)")
    func nessunaOraAMano() throws {
        // i sorgenti stanno accanto ai test sul Mac di GitHub (come in TestiCortiWidgetTests): ios/WidgetSources
        let ios = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let elenco = try #require(FileManager.default.enumerator(at: ios.appendingPathComponent("WidgetSources", isDirectory: true),
                                                                 includingPropertiesForKeys: nil))
        var aMano: [String] = [], letti = 0
        for case let url as URL in elenco where url.pathExtension == "swift" {
            let testo = try String(contentsOf: url, encoding: .utf8)
            letti += 1
            if testo.contains("dati delle \\(") { aMano.append(url.lastPathComponent) }
        }
        #expect(letti > 5, "i sorgenti non si leggono: il test non proverebbe niente")
        #expect(aMano.isEmpty, "l'ora della copia scritta a mano (senza il giorno) in: \(aMano)")
    }

    // MARK: Formazione piccolo e medio: la riga della copia c'è sempre

    private typealias Prova = DisposizioneWidget.ProvaFormazione

    @Test("Piccolo con la copia e giocatori da controllare: la copia in ogni prova, sopra «da controllare», che cede per primo")
    func piccoloConCopiaEDubbi() {
        let prove = DisposizioneWidget.proveFormazione(conGiornata: true, datiSalvati: true, daControllare: 2)
        // con una chiusura, non con un percorso: dentro #expect il percorso come funzione fa credere che la chiamata lanci errori
        #expect(prove.allSatisfy { $0.piede.first == .copia })
        #expect(prove == [
            Prova(conTitolo: true, piede: [.copia, .daControllare]),
            Prova(conTitolo: false, piede: [.copia, .daControllare]),
            Prova(conTitolo: false, piede: [.copia]),
        ])
    }

    @Test("Medio (testata senza giornata): prima la copia e «da controllare», poi la sola copia")
    func medioConCopiaEDubbi() {
        #expect(DisposizioneWidget.proveFormazione(conGiornata: false, datiSalvati: true, daControllare: 1) == [
            Prova(conTitolo: true, piede: [.copia, .daControllare]),
            Prova(conTitolo: true, piede: [.copia]),
        ])
    }

    @Test("Senza copia «da controllare» resta com'era; senza giocatori da controllare la sola copia; senza niente nessuna riga")
    func altriCasi() {
        #expect(DisposizioneWidget.proveFormazione(conGiornata: true, datiSalvati: false, daControllare: 3) == [
            Prova(conTitolo: true, piede: [.daControllare]),
            Prova(conTitolo: false, piede: [.daControllare]),
        ])
        #expect(DisposizioneWidget.proveFormazione(conGiornata: true, datiSalvati: true, daControllare: 0) == [
            Prova(conTitolo: true, piede: [.copia]),
            Prova(conTitolo: false, piede: [.copia]),
        ])
        #expect(DisposizioneWidget.proveFormazione(conGiornata: false, datiSalvati: false, daControllare: 0) == [
            Prova(conTitolo: true, piede: []),
        ])
    }
}
