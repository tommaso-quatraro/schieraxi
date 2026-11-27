import Foundation

/// Le parole e i numeri della pagina Novità, uguali alla web (issue #441): `mostraNovita` di `fanta/web/impostazioni.js` e le chiavi
/// `novita.*` del catalogo comune (`Catalogo+Novita.swift`). `NovitaComeLaWebTests` le prova. Come la web dalla #615, nessuna
/// etichetta «Nuovo»: si vedono sempre le ultime `visibili` versioni.
enum ParoleNovita {
    /// Quante versioni si vedono subito (`NOVITA_VISIBILI` della web): le altre, sono centinaia, dietro «Mostra le … precedenti».
    static let visibili = 10

    /// «Versione 1.432» (`novita.versione`).
    static func versione(_ numero: String) -> String { Catalogo.Novita.versione(v: numero) }

    /// La riga sotto il titolo: «Versione 1.432 · 6 nov 2026, 10:12:00»; senza data solo la versione.
    static func sotto(versione numero: String, data: String?) -> String {
        let quando = Quando.dataVersione(data)
        return quando.isEmpty ? versione(numero) : "\(versione(numero)) · \(quando)"
    }

    /// Quante versioni si vedono subito: le ultime `visibili`, come la web, mai più di quelle che ci sono.
    static func quanteVisibili(totale: Int) -> Int {
        min(totale, visibili)
    }

    /// Il pulsante che apre tutte le altre: «Mostra le 42 versioni precedenti» o «Mostra 1 versione precedente»
    /// (`novita.precedenti`).
    static func precedenti(_ n: Int) -> String { Catalogo.Novita.precedenti(n) }
}
