// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/aggiorna.json, chiavi elencate in ios/testi/aggiorna.txt.

extension Catalogo {
    enum Aggiorna {
        /// `aggiorna.avviato`
        static let avviato = "Aggiornamento dei dati avviato: ci vuole circa un minuto"

        /// `aggiorna.ok`
        static let ok = "Dati aggiornati"

        /// `aggiorna.problemi`
        static func problemi(errori: String) -> String {
            "Aggiornato, ma con problemi: \(errori)"
        }

        /// `aggiorna.non_so`
        static let nonSo = "Non riesco a sapere come è andato l'aggiornamento: riapri l'app tra poco"
    }
}
