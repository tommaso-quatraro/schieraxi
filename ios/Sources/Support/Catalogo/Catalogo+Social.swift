// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/social.json, chiavi elencate in ios/testi/social.txt.

extension Catalogo {
    enum Social {
        /// `social.continua`
        static let continua = "Continua con Google"

        /// `social.oppure`
        static let oppure = "oppure"

        /// `social.scegli_nome`
        static let scegliNome = "Scegli il tuo nome utente"

        /// `social.crea`
        static let crea = "Crea l'account"

        /// `social.accessi`
        static let accessi = "Accessi"

        /// `social.password_si`
        static let passwordSi = "Password: impostata"

        /// `social.password_no`
        static let passwordNo = "Password: non impostata"

        /// `social.google_collegato`
        static func googleCollegato(email: String) -> String {
            "Account Google collegato: \(email)"
        }

        /// `social.google_account`
        static let googleAccount = "account collegato"

        /// `social.google_non_collegato`
        static let googleNonCollegato = "Google: non collegato"

        /// `social.collega`
        static let collega = "Collega Google"

        /// `social.scollega`
        static let scollega = "Scollega Google"

        /// `social.scollega_conferma`
        static let scollegaConferma = "Scollegare Google? Potrai entrare solo con la tua password."

        /// `social.scollegato_ok`
        static let scollegatoOk = "Google scollegato."

        /// `social.collegato_ok`
        static let collegatoOk = "Google collegato: ora puoi entrare anche con Google."

        /// `social.serve_password`
        static let servePassword = "Scrivi la tua password per collegare Google."

        /// `social.conferma`
        static let conferma = "Conferma con Google"

        /// `social.conferma_spiega`
        static let confermaSpiega = "Entri solo con Google. Per aggiungere una password, cambiare l'email o eliminare l'account, conferma prima con Google: vale 5 minuti."

        /// `social.riconfermato_ok`
        static let riconfermatoOk = "Confermato. Per 5 minuti puoi aggiungere una password, cambiare l'email o eliminare l'account."

        /// `social.aggiungi_password`
        static let aggiungiPassword = "Aggiungi una password"
    }
}
