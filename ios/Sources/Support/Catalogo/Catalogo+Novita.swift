// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/novita.json, chiavi elencate in ios/testi/novita.txt.

extension Catalogo {
    enum Novita {
        /// `novita.versione`
        static func versione(v: String) -> String {
            "Versione \(v)"
        }

        /// `novita.precedenti.one`, `novita.precedenti.other`
        static func precedenti(_ n: Int) -> String {
            n == 1 ? "Mostra \(n) versione precedente" : "Mostra le \(n) versioni precedenti"
        }
    }
}
