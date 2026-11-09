// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/accesso.json, chiavi elencate in ios/testi/accesso.txt.

extension Catalogo {
    enum Accesso {
        /// `accesso.scheda_accedi`
        static let schedaAccedi = "Accedi"

        /// `accesso.scheda_registra`
        static let schedaRegistra = "Registrati"

        /// `accesso.scheda_recupero`
        static let schedaRecupero = "Password dimenticata"

        /// `accesso.nome_utente`
        static let nomeUtente = "Nome utente"

        /// `accesso.password`
        static let password = "Password"

        /// `accesso.password_10`
        static let password10 = "Password (almeno 10 caratteri)"

        /// `accesso.password_nuova_10`
        static let passwordNuova10 = "Nuova password (almeno 10 caratteri)"

        /// `accesso.codice_invito`
        static let codiceInvito = "Codice d'invito"

        /// `accesso.codice`
        static let codice = "Codice"

        /// `accesso.codice_email`
        static let codiceEmail = "Codice a 6 cifre ricevuto per email"

        /// `accesso.email`
        static let email = "Email"

        /// `accesso.email_facoltativa`
        static let emailFacoltativa = "Email (facoltativa)"

        /// `accesso.email_facoltativa_aiuto`
        static let emailFacoltativaAiuto = "Serve a recuperare la password."

        /// `accesso.invio_accedi`
        static let invioAccedi = "Accedi"

        /// `accesso.invio_registra`
        static let invioRegistra = "Crea l'account"

        /// `accesso.invio_verifica`
        static let invioVerifica = "Conferma e crea l'account"

        /// `accesso.invio_recupero`
        static let invioRecupero = "Scegli la nuova password"

        /// `accesso.invio_recupero_email`
        static let invioRecuperoEmail = "Mandami il codice"

        /// `accesso.serve_invito`
        static let serveInvito = "Ti serve un codice d'invito: chiedilo a chi ti ha invitato."

        /// `accesso.serve_invito_email`
        static let serveInvitoEmail = "Serve un codice d'invito e un indirizzo email: ti mandiamo un codice per confermarlo."

        /// `accesso.serve_email`
        static let serveEmail = "Scrivi la tua email: ti mandiamo un codice per confermarla e creare l'account."

        /// `accesso.verifica_spiega`
        static func verificaSpiega(email: String) -> String {
            "Ti abbiamo scritto a \(email). Inserisci il codice a 6 cifre (vale 15 minuti). Se non arriva, controlla la posta indesiderata."
        }

        /// `accesso.recupero_spiega`
        static let recuperoSpiega = "Usa il codice di recupero che hai ricevuto quando ti sei registrato, oppure il codice che ti ha dato chi ti ha invitato."

        /// `accesso.recupero_email_spiega`
        static let recuperoEmailSpiega = "Scrivi l'email del tuo account: se è registrata, ti mandiamo un codice per scegliere una nuova password. Per sicurezza la risposta è sempre la stessa."

        /// `accesso.recupero_codice_email_spiega`
        static func recuperoCodiceEmailSpiega(email: String) -> String {
            "Scrivi il codice arrivato a \(email) e scegli la nuova password."
        }

        /// `accesso.recupero_con_email`
        static let recuperoConEmail = "Con l'email"

        /// `accesso.recupero_con_codice`
        static let recuperoConCodice = "Con il codice di recupero"

        /// `accesso.letto`
        static func letto(eta: String, privacy: String, termini: String) -> String {
            "Ho letto \(privacy) e \(termini) e ho almeno \(eta) anni"
        }

        /// `accesso.spunta_letto`
        static func spuntaLetto(eta: String) -> String {
            "Per registrarti spunta la casella: hai letto Privacy e Termini d'uso e hai almeno \(eta) anni"
        }

        /// `accesso.torna`
        static let torna = "Torna all'accesso"

        /// `accesso.codice_inviato`
        static let codiceInviato = "Se l'indirizzo è registrato, il codice sta arrivando (vale 15 minuti)."

        /// `accesso.password_cambiata`
        static let passwordCambiata = "Password cambiata"

        /// `accesso.password_cambiata_accedi`
        static let passwordCambiataAccedi = "Password cambiata: accedi con quella nuova."

        /// `accesso.vai_accesso`
        static let vaiAccesso = "Vai all'accesso"

        /// `accesso.risposta_incompleta`
        static let rispostaIncompleta = "Qualcosa non ha funzionato: riprova"
    }
}
