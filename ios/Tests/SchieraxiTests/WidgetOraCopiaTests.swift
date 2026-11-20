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

    // L'ultima forma, la sola data, sta su una riga anche con il testo molto grande nella colonna di 120 punti del medio (#834:
    // «dati di mer 18» non entrava e finiva con «…»); il simbolo della nuvola sbarrata accanto dice che è la copia, VoiceOver
    // legge sempre la prima forma.
    @Test("Di oggi la sola ora; degli altri giorni anche il giorno; dove non entra via l'ora, poi via «dati di»", arguments: [
        ("2026-11-20 08:15", ["dati delle 08:15", "08:15"]),
        ("2026-11-19 18:30", ["dati di ieri 18:30", "dati di ieri", "ieri"]),
        ("2026-11-17 21:05", ["dati di mar 17 21:05", "dati di mar 17", "mar 17"]),            // entro la settimana il giorno e il numero
        ("2026-11-08 18:30", ["dati di dom 8 nov 18:30", "dati di dom 8 nov", "dom 8 nov"]),   // oltre, anche il mese
    ])
    func formeDellaCopia(scaricata: String, attese: [String]) throws {
        let copia = try data(scaricata), ora = try data(Self.adesso)
        #expect(ParoleWidget.datiSalvati(copia, adesso: ora) == attese)
    }

    @Test("A mezzanotte, in ora italiana, la copia delle 23:30 diventa di ieri; quella delle 00:05 resta di oggi fino a sera")
    func mezzanotte() throws {
        let tardi = try data("2026-11-19 23:30"), dopoMezzanotte = try data("2026-11-20 00:30")
        #expect(ParoleWidget.datiSalvati(tardi, adesso: dopoMezzanotte) == ["dati di ieri 23:30", "dati di ieri", "ieri"])
        let presto = try data("2026-11-20 00:05"), sera = try data("2026-11-20 23:55")
        #expect(ParoleWidget.datiSalvati(presto, adesso: sera) == ["dati delle 00:05", "00:05"])
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

    private static func piccolo(salvati: Bool, dubbi: Int, fascia: Bool = true) -> [Prova] {
        DisposizioneWidget.proveFormazione(medio: false, conGiornata: true, conFascia: fascia, datiSalvati: salvati, daControllare: dubbi)
    }

    private static func medio(salvati: Bool, dubbi: Int, fascia: Bool = true) -> [Prova] {
        DisposizioneWidget.proveFormazione(medio: true, conGiornata: false, conFascia: fascia, datiSalvati: salvati, daControllare: dubbi)
    }

    // Le foto della corsa 44731480155: con il testo normale il medio dell'iPhone, e piccolo e medio dell'iPad, perdevano
    // «2 da controllare» per far posto alla copia. Prima si libera un'altra riga; «da controllare» cede per ultimo.
    @Test("Copia e giocatori da controllare: la copia in ogni prova, sopra; «da controllare» in tutte tranne l'ultima",
          arguments: [(false, true), (false, false), (true, true), (true, false)])
    func daControllareCedePerUltimo(medio: Bool, fascia: Bool) throws {
        let prove = medio ? Self.medio(salvati: true, dubbi: 2, fascia: fascia) : Self.piccolo(salvati: true, dubbi: 2, fascia: fascia)
        let ultima = try #require(prove.last)
        #expect(ultima.piede == [DisposizioneWidget.RigaPiedeFormazione.copia])
        // con una chiusura, non con un percorso: dentro #expect il percorso come funzione fa credere che la chiamata lanci errori
        #expect(prove.dropLast().allSatisfy { $0.piede == [.copia, .daControllare] })
        #expect(prove.count >= 3, "prima di «da controllare» deve cedere almeno un'altra riga")
    }

    @Test("Piccolo: prima via il titolo (resta il simbolo con la giornata), poi la fascia («72,7 attesi»), per ultimo «da controllare»")
    func piccoloConCopiaEDubbi() {
        #expect(Self.piccolo(salvati: true, dubbi: 2) == [
            Prova(conTitolo: true, punti: .unaRiga, piede: [.copia, .daControllare]),
            Prova(conTitolo: false, punti: .unaRiga, piede: [.copia, .daControllare]),
            Prova(conTitolo: false, punti: .accanto, piede: [.copia, .daControllare]),
            Prova(conTitolo: false, punti: .accanto, piede: [.copia]),
        ])
    }

    @Test("Medio: prima «attesi · tra 65 e 81» su una riga, poi «72,7 attesi», per ultimo «da controllare»")
    func medioConCopiaEDubbi() {
        #expect(Self.medio(salvati: true, dubbi: 1) == [
            Prova(conTitolo: true, punti: .dueRighe, piede: [.copia, .daControllare]),
            Prova(conTitolo: true, punti: .unaRiga, piede: [.copia, .daControllare]),
            Prova(conTitolo: true, punti: .accanto, piede: [.copia, .daControllare]),
            Prova(conTitolo: true, punti: .accanto, piede: [.copia]),
        ])
        // senza fascia «punti attesi» sta già su una riga: si passa subito a «72,7 attesi»
        #expect(Self.medio(salvati: true, dubbi: 1, fascia: false) == [
            Prova(conTitolo: true, punti: .unaRiga, piede: [.copia, .daControllare]),
            Prova(conTitolo: true, punti: .accanto, piede: [.copia, .daControllare]),
            Prova(conTitolo: true, punti: .accanto, piede: [.copia]),
        ])
    }

    @Test("Senza copia, o senza giocatori da controllare, le righe in basso restano in ogni prova; la prima è quella di sempre")
    func altriCasi() {
        #expect(Self.piccolo(salvati: false, dubbi: 3) == [
            Prova(conTitolo: true, punti: .unaRiga, piede: [.daControllare]),
            Prova(conTitolo: false, punti: .unaRiga, piede: [.daControllare]),
            Prova(conTitolo: false, punti: .accanto, piede: [.daControllare]),
        ])
        #expect(Self.medio(salvati: true, dubbi: 0) == [
            Prova(conTitolo: true, punti: .dueRighe, piede: [.copia]),
            Prova(conTitolo: true, punti: .unaRiga, piede: [.copia]),
            Prova(conTitolo: true, punti: .accanto, piede: [.copia]),
        ])
        #expect(Self.medio(salvati: false, dubbi: 0, fascia: false) == [
            Prova(conTitolo: true, punti: .unaRiga, piede: []),
            Prova(conTitolo: true, punti: .accanto, piede: []),
        ])
    }
}
