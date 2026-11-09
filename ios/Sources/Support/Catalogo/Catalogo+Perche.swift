// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/perche.json, chiavi elencate in ios/testi/perche.txt.

extension Catalogo {
    enum Perche {
        /// `perche.titolo`
        static let titolo = "Perché questo numero"

        /// `perche.definizione`
        static let definizione = "Il fantavoto atteso è quello che SchieraXI si aspetta da questo giocatore in questa partita, se gioca, con le regole della tua lega."

        /// `perche.rispetto`
        static func rispetto(n: String) -> String {
            "Un giocatore medio del suo ruolo ha \(n). Il resto sono differenze piccole."
        }

        /// `perche.nessuno`
        static func nessuno(n: String) -> String {
            "Nessun motivo spicca: il numero è vicino a quello di un giocatore medio del suo ruolo, che ha \(n)."
        }

        /// `perche.apri_scheda`
        static let apriScheda = "Apri la scheda"
    }
}
