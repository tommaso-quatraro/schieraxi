import Foundation
import Testing
@testable import Schieraxi

/// Novità come la web (issue #441, parte di #167; `mostraNovita` di `fanta/web/impostazioni.js`): la carta ha per titolo il titolo
/// della versione e sotto «Versione 1.432 · 6 nov 2026, 10:12:00»; si vedono sempre le ultime 10 e un solo pulsante «Mostra le 42
/// versioni precedenti» apre tutte le altre. Dalla #615 la web non ha più l'etichetta «Nuovo»: nemmeno l'iPhone (27/11/2026).
@Suite("Novità come la web: titolo, ultime 10 e «Mostra le … precedenti» (#441)")
struct NovitaComeLaWebTests {

    private static func versioni(_ n: Int) -> [String] { (0..<n).map { "1.\(500 - $0)" } }

    // MARK: parole

    @Test("«Versione N» è quella del catalogo")
    func parole() {
        #expect(ParoleNovita.versione("1.432") == Catalogo.Novita.versione(v: "1.432"))
        #expect(ParoleNovita.versione("1.432") == "Versione 1.432")
    }

    @Test("Sotto il titolo: «Versione 1.432 · 6 nov 2026, 10:12:00»; senza data solo la versione")
    func sottoIlTitolo() {
        #expect(ParoleNovita.sotto(versione: "1.432", data: "2026-11-06T10:12:00") == "Versione 1.432 · 6 nov 2026, 10:12:00")
        #expect(ParoleNovita.sotto(versione: "1.432", data: "2026-11-06") == "Versione 1.432 · 6 nov 2026")
        #expect(ParoleNovita.sotto(versione: "1.432", data: nil) == "Versione 1.432")
        #expect(ParoleNovita.sotto(versione: "1.432", data: "") == "Versione 1.432")
    }

    @Test("Il pulsante delle precedenti: «Mostra le 42 versioni precedenti» e, per una sola, «Mostra 1 versione precedente»")
    func precedenti() {
        #expect(ParoleNovita.precedenti(42) == "Mostra le 42 versioni precedenti")
        #expect(ParoleNovita.precedenti(1) == "Mostra 1 versione precedente")
        #expect(ParoleNovita.precedenti(2) == Catalogo.Novita.precedenti(2))
    }

    // MARK: quante versioni

    @Test("Le versioni subito visibili sono 10, come NOVITA_VISIBILI della web")
    func visibiliComeLaWeb() {
        #expect(ParoleNovita.visibili == 10)
    }

    @Test("Si vedono sempre le ultime 10, mai più di quelle che ci sono", arguments: [(52, 10), (11, 10), (10, 10), (3, 3), (0, 0)])
    func quanteVisibili(totale: Int, attese: Int) {
        #expect(ParoleNovita.quanteVisibili(totale: totale) == attese)
    }

    @Test("Con 52 versioni restano da aprire le 42 del pulsante (l'esempio dell'issue)")
    func esempioDellIssue() {
        let elenco = Self.versioni(52)
        #expect(elenco.count - ParoleNovita.quanteVisibili(totale: elenco.count) == 42)
    }
}
