// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/df.json, chiavi elencate in ios/testi/df.txt.

extension Catalogo {
    enum Df {
        /// `df.da_fare`
        static let daFare = "Da fare"

        /// `df.urgente`
        static let urgente = "Urgente"

        /// `df.altre.one`, `df.altre.other`
        static func altre(_ n: Int) -> String {
            n == 1 ? "Un'altra cosa da fare" : "Altre \(n) cose da fare"
        }

        /// `df.tutto_posto_mister`
        static let tuttoPostoMister = "Tutto a posto, Mister."

        /// `df.non_niente_sbrigare`
        static let nonNienteSbrigare = "Nessuna azione utile oggi."

        /// `df.apri`
        static let apri = "Apri"
    }
}
