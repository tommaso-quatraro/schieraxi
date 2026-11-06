import Foundation

/// Le parole e i numeri della pagina Novità, uguali alla web (issue #441): `vistaNovita` di `fanta/web/app.js` e le chiavi
/// `novita.*` e `regole.nuovo` di `fanta/web/testi.js`. `NovitaComeLaWebTests` li confronta. Quali versioni sono nuove e quante se
/// ne vedono subito si decide qui, con la stessa regola della web.
enum ParoleNovita {
    /// Quante versioni si vedono subito (`NOVITA_VISIBILI` della web): le altre, sono centinaia, dietro «Mostra le … precedenti».
    static let visibili = 10

    /// L'etichetta delle versioni non ancora viste (`regole.nuovo`).
    static let nuovo = "Nuovo"

    /// «Versione 1.432» (`novita.versione`).
    static func versione(_ numero: String) -> String { "Versione \(numero)" }

    /// La riga sotto il titolo: «Versione 1.432 · 6 nov 2026, 10:12:00»; senza data solo la versione.
    static func sotto(versione numero: String, data: String?) -> String {
        let quando = Quando.dataVersione(data)
        return quando.isEmpty ? versione(numero) : "\(versione(numero)) · \(quando)"
    }

    /// Quante delle versioni in cima sono «Nuovo». Alla prima visita (nessuna versione vista) solo l'ultima, non tutto lo storico;
    /// se la versione vista non c'è più nell'elenco, le prime `visibili`; altrimenti tutte quelle sopra la versione vista.
    static func nuoveDa(versioni: [String], ultimaVista: String?) -> Int {
        guard let ultima = ultimaVista, !ultima.isEmpty else { return min(1, versioni.count) }
        guard let trovata = versioni.firstIndex(of: ultima) else { return min(visibili, versioni.count) }
        return trovata
    }

    /// Quante versioni si vedono subito: almeno `visibili` e tutte le nuove, mai più di quelle che ci sono.
    static func quanteVisibili(totale: Int, nuoveDa: Int) -> Int {
        min(totale, max(visibili, nuoveDa))
    }

    /// Il pulsante che apre tutte le altre: «Mostra le 42 versioni precedenti» o «Mostra 1 versione precedente»
    /// (`novita.precedenti`).
    static func precedenti(_ n: Int) -> String {
        n == 1 ? "Mostra 1 versione precedente" : "Mostra le \(n) versioni precedenti"
    }
}
