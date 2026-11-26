// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/frase.json, chiavi elencate in ios/testi/frase.txt.

extension Catalogo {
    enum Frase {
        /// `frase.rose.portieri.one`, `frase.rose.portieri.other`
        static func rosePortieri(_ n: Int) -> String {
            n == 1 ? "\(n) portiere" : "\(n) portieri"
        }

        /// `frase.rose.difensori.one`, `frase.rose.difensori.other`
        static func roseDifensori(_ n: Int) -> String {
            n == 1 ? "\(n) difensore" : "\(n) difensori"
        }

        /// `frase.rose.centrocampisti.one`, `frase.rose.centrocampisti.other`
        static func roseCentrocampisti(_ n: Int) -> String {
            n == 1 ? "\(n) centrocampista" : "\(n) centrocampisti"
        }

        /// `frase.rose.attaccanti.one`, `frase.rose.attaccanti.other`
        static func roseAttaccanti(_ n: Int) -> String {
            n == 1 ? "\(n) attaccante" : "\(n) attaccanti"
        }
    }
}
