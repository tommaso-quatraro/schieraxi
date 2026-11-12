import Foundation
import Testing
@testable import Schieraxi

/// Novità come la web (issue #441, parte di #167). `vistaNovita` di `fanta/web/app.js`: la carta ha per titolo il titolo della
/// versione e sotto «Versione 1.432 · 6 nov 2026, 10:12:00»; le versioni non ancora viste hanno «Nuovo»; si vedono le prime 10
/// (almeno tutte le nuove) e un solo pulsante «Mostra le 42 versioni precedenti» apre tutte le altre.
@Suite("Novità come la web: titolo, «Nuovo», prime 10 e «Mostra le … precedenti» (#441)")
struct NovitaComeLaWebTests {

    private static func versioni(_ n: Int) -> [String] { (0..<n).map { "1.\(500 - $0)" } }

    // MARK: parole

    @Test("«Nuovo» e «Versione N» sono quelli del catalogo")
    func parole() {
        #expect(ParoleNovita.nuovo == Catalogo.Regole.nuovo)
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

    // MARK: quante versioni e quali sono nuove

    @Test("Le versioni subito visibili sono 10, come NOVITA_VISIBILI della web del 12/11/2026")
    func visibiliComeLaWeb() {
        #expect(ParoleNovita.visibili == 10)
    }

    @Test("Prima visita (nessuna versione vista): è «Nuovo» solo l'ultima")
    func primaVisita() {
        #expect(ParoleNovita.nuoveDa(versioni: Self.versioni(50), ultimaVista: nil) == 1)
        #expect(ParoleNovita.nuoveDa(versioni: Self.versioni(50), ultimaVista: "") == 1)
        #expect(ParoleNovita.nuoveDa(versioni: [], ultimaVista: nil) == 0)
    }

    @Test("Versione vista trovata: sono nuove le versioni sopra di lei")
    func vistaTrovata() {
        let elenco = Self.versioni(50)
        #expect(ParoleNovita.nuoveDa(versioni: elenco, ultimaVista: elenco[0]) == 0)
        #expect(ParoleNovita.nuoveDa(versioni: elenco, ultimaVista: elenco[3]) == 3)
        #expect(ParoleNovita.nuoveDa(versioni: elenco, ultimaVista: elenco[14]) == 14)
    }

    @Test("Versione vista che non c'è più nell'elenco: nuove le prime 10 (al massimo quante sono)")
    func vistaPersa() {
        #expect(ParoleNovita.nuoveDa(versioni: Self.versioni(50), ultimaVista: "0.1") == 10)
        #expect(ParoleNovita.nuoveDa(versioni: Self.versioni(4), ultimaVista: "0.1") == 4)
    }

    @Test("Si vedono almeno 10 versioni e tutte le nuove; mai più di quelle che ci sono")
    func quanteVisibili() {
        #expect(ParoleNovita.quanteVisibili(totale: 52, nuoveDa: 0) == 10)
        #expect(ParoleNovita.quanteVisibili(totale: 52, nuoveDa: 1) == 10)
        #expect(ParoleNovita.quanteVisibili(totale: 52, nuoveDa: 14) == 14)
        #expect(ParoleNovita.quanteVisibili(totale: 3, nuoveDa: 3) == 3)
        #expect(ParoleNovita.quanteVisibili(totale: 0, nuoveDa: 0) == 0)
    }

    @Test("Con 52 versioni e niente di nuovo restano da aprire le 42 del pulsante (l'esempio dell'issue)")
    func esempioDellIssue() {
        let elenco = Self.versioni(52)
        let visibili = ParoleNovita.quanteVisibili(totale: elenco.count, nuoveDa: ParoleNovita.nuoveDa(versioni: elenco, ultimaVista: elenco[0]))
        #expect(elenco.count - visibili == 42)
    }
}
