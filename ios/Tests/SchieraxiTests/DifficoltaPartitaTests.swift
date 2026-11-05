import Foundation
import Testing
@testable import Schieraxi

/// La difficoltà della partita nella scheda del giocatore (issue #322, sotto la #167): lo schermo, VoiceOver e la web dicono le
/// stesse parole, quelle di `diff.1`…`diff.5` di `fanta/web/testi.js`. Prima lo schermo scriveva «Partita normale» e VoiceOver
/// leggeva «Partita: difficoltà media»; per i livelli 1 e 2 le due scale non coincidevano nemmeno («molto facile» e «facile»
/// contro «Facile» e «Abbordabile»). Una scala sola, dati inventati.
@Suite("Difficoltà della partita: le stesse parole su schermo, VoiceOver e web")
struct DifficoltaPartitaTests {
    /// Il livello del server e la chiave di testi.js con la sua parola.
    static let livelli: [(Double, String)] = [(1, "diff.1"), (2, "diff.2"), (3, "diff.3"), (4, "diff.4"), (5, "diff.5")]

    /// Valori che il server di solito non manda ma che l'app deve reggere, con la parola che prendono (si arrotonda come la web).
    static let valoriFuoriScala: [(Double?, String)] = [
        (nil, "diff.3"), (0, "diff.1"), (-2, "diff.1"), (1.4, "diff.1"), (1.5, "diff.2"), (2.6, "diff.3"), (4.5, "diff.5"), (9, "diff.5"),
    ]

    // MARK: la scala di parole è una sola, quella della web

    @Test("Ogni livello ha la parola della web, anche dentro una frase (in minuscolo)", arguments: DifficoltaPartitaTests.livelli)
    @MainActor
    func scalaDellaWeb(livello: Double, chiave: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(PillDifficolta.nome(livello) == web)
        #expect(Formato.difficolta(livello) == web.lowercased())
    }

    @Test("Senza il dato o fuori scala: la parola del livello vicino, come la web", arguments: DifficoltaPartitaTests.valoriFuoriScala)
    @MainActor
    func fuoriScala(valore: Double?, chiave: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(PillDifficolta.nome(valore) == web)
        #expect(Formato.difficolta(valore) == web.lowercased())
    }

    // MARK: la pillola della scheda del giocatore

    @Test("Lo schermo scrive «Partita normale»: «Partita» e la parola della web in minuscolo", arguments: DifficoltaPartitaTests.livelli)
    @MainActor
    func loSchermo(livello: Double, chiave: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(PillDifficolta.testo(livello, conPartita: true) == "Partita " + web.lowercased())
        #expect(PillDifficolta.testo(livello, conPartita: false) == web)
    }

    @Test("VoiceOver legge le parole dello schermo, non un'altra scala: «Partita normale», mai «difficoltà media»",
          arguments: DifficoltaPartitaTests.livelli)
    @MainActor
    func voiceOver(livello: Double, chiave: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(PillDifficolta.etichettaVoceOver(livello, conPartita: true) == "Partita " + web.lowercased())
        #expect(PillDifficolta.etichettaVoceOver(livello, conPartita: true) == PillDifficolta.testo(livello, conPartita: true))
        #expect(PillDifficolta.etichettaVoceOver(livello, conPartita: false) == PillDifficolta.testo(livello, conPartita: false))
    }

    @Test("Senza il dato VoiceOver dice quello che si vede: «Partita normale»")
    @MainActor
    func voiceOverSenzaDato() throws {
        let web = try TestiWeb().italiano("diff.3")
        #expect(PillDifficolta.etichettaVoceOver(nil, conPartita: true) == "Partita " + web.lowercased())
        #expect(PillDifficolta.testo(nil, conPartita: true) == "Partita " + web.lowercased())
    }
}
