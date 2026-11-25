// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/testata.json, chiavi elencate in ios/testi/testata.txt.

extension Catalogo {
    enum Testata {
        /// `testata.dati_del`
        static func datiDel(data: String, ora: String) -> String {
            " · dati del \(data) \(ora)"
        }

        /// `testata.mai`
        static let mai = " · dati mai aggiornati"

        /// `testata.offline`
        static let offline = "Server non raggiungibile"
    }
}
