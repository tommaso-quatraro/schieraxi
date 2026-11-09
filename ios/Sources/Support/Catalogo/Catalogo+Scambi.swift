// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/scambi.json, chiavi elencate in ios/testi/scambi.txt.

extension Catalogo {
    enum Scambi {
        /// `scambi.analizza_titolo`
        static let analizzaTitolo = "Costruisci uno scambio"

        /// `scambi.analizza_spiega`
        static let analizzaSpiega = "Scegli da 1 a 4 giocatori per parte, anche in numero diverso (2 contro 1, 3 contro 2…). Se vuoi, aggiungi un conguaglio in crediti."

        /// `scambi.con`
        static let con = "Scambio con"

        /// `scambi.dai`
        static let dai = "Dai"

        /// `scambi.ricevi`
        static let ricevi = "Ricevi"

        /// `scambi.scelti`
        static func scelti(max: String, n: String) -> String {
            "\(n) su \(max)"
        }

        /// `scambi.massimo`
        static func massimo(max: String) -> String {
            "Al massimo \(max) giocatori per parte"
        }

        /// `scambi.conguaglio`
        static let conguaglio = "Conguaglio in crediti (+/−)"

        /// `scambi.conguaglio_aiuto`
        static let conguaglioAiuto = "Facoltativo. «Ricevo» = ti danno i crediti, «Pago» = li dai tu."

        /// `scambi.ricevo_crediti`
        static let ricevoCrediti = "Ricevo"

        /// `scambi.pago_crediti`
        static let pagoCrediti = "Pago"

        /// `scambi.crediti_quanti`
        static let creditiQuanti = "Quanti crediti"

        /// `scambi.conguaglio_numero`
        static let conguaglioNumero = "Scrivi i crediti con un numero intero, per esempio 30"

        /// `scambi.analizza`
        static let analizza = "Valuta lo scambio"

        /// `scambi.calcolo`
        static let calcolo = "Calcolo…"

        /// `scambi.formato`
        static func formato(m: String, n: String) -> String {
            "\(n) contro \(m)"
        }

        /// `scambi.chi_non_valido`
        static let chiNonValido = "Così non si può fare"

        /// `scambi.rose_dopo`
        static let roseDopo = "Giocatori in rosa dopo lo scambio"

        /// `scambi.formazione_migliore`
        static func formazioneMigliore(n: String) -> String {
            "Formazione migliore (prossime \(n) giornate)"
        }

        /// `scambi.formazione_migliore_una`
        static let formazioneMiglioreUna = "Formazione migliore (prossima giornata)"

        /// `scambi.panchina`
        static let panchina = "Panchina"

        /// `scambi.in_stagione`
        static let inStagione = "Punti attesi in stagione"

        /// `scambi.tu`
        static let tu = "Tu"

        /// `scambi.crediti_titolo`
        static let creditiTitolo = "Crediti"
    }
}
