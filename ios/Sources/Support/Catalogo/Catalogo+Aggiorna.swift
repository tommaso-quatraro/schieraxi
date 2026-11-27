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

        /// `aggiorna.nessun_dato`
        static func nessunDato(errori: String) -> String {
            "Nessun dato nuovo: \(errori)"
        }

        /// `aggiorna.nessun_dato_niente`
        static let nessunDatoNiente = "Nessun dato nuovo: non c'era niente di più recente da scaricare."

        /// `aggiorna.non_so`
        static let nonSo = "Non riesco a sapere come è andato l'aggiornamento: riapri l'app tra poco"

        /// `aggiorna.in_corso`
        static let inCorso = "Il server è occupato con un aggiornamento: il pulsante torna attivo appena finisce."
    }
}
