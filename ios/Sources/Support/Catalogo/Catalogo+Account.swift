// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/account.json, chiavi elencate in ios/testi/account.txt.

extension Catalogo {
    enum Account {
        /// `account.ruolo_admin`
        static let ruoloAdmin = "Amministratore"

        /// `account.ruolo_utente`
        static let ruoloUtente = "Utente"

        /// `account.dal`
        static func dal(data: String, ruolo: String) -> String {
            "\(ruolo) · dal \(data)"
        }

        /// `account.esci`
        static let esci = "Esci"

        /// `account.cambia_password`
        static let cambiaPassword = "Cambia la password"

        /// `account.password_attuale`
        static let passwordAttuale = "Password attuale"

        /// `account.ripeti_password`
        static let ripetiPassword = "Ripeti la nuova password"

        /// `account.password_diverse`
        static let passwordDiverse = "Le due password non coincidono."

        /// `account.altri_scollegati`
        static let altriScollegati = "Gli altri dispositivi vengono scollegati."

        /// `account.password_cambiata_ok`
        static let passwordCambiataOk = "Password cambiata. Gli altri dispositivi sono stati scollegati."

        /// `account.password_cambiata_codice`
        static let passwordCambiataCodice = "Password cambiata. Gli altri dispositivi sono stati scollegati e il codice di recupero è nuovo: salvalo."

        /// `account.la_tua_password`
        static let laTuaPassword = "La tua password"

        /// `account.recupero`
        static let recupero = "Codice di recupero"

        /// `account.recupero_spiega`
        static let recuperoSpiega = "Serve se dimentichi la password. Il vecchio codice smette di valere appena ne generi uno nuovo."

        /// `account.nuovo_codice`
        static let nuovoCodice = "Genera un nuovo codice"

        /// `account.email`
        static let email = "Email"

        /// `account.email_spiega`
        static let emailSpiega = "Facoltativa. Serve a recuperare la password senza il codice di recupero e a ricevere un avviso se qualcuno entra da un dispositivo nuovo. Non la usiamo per altro."

        /// `account.email_verificata`
        static func emailVerificata(email: String) -> String {
            "Email confermata: \(email)"
        }

        /// `account.email_google`
        static func emailGoogle(email: String) -> String {
            "Email da Google: \(email)"
        }

        /// `account.email_nessuna`
        static let emailNessuna = "Nessuna email collegata."

        /// `account.email_attesa`
        static func emailAttesa(email: String) -> String {
            "In attesa di conferma: \(email). Scrivi qui sotto il codice a 6 cifre che ti abbiamo mandato."
        }

        /// `account.email_nuova`
        static let emailNuova = "Nuovo indirizzo email"

        /// `account.email_invia`
        static let emailInvia = "Mandami il codice"

        /// `account.email_inviato`
        static let emailInviato = "Se l'indirizzo è valido, il codice sta arrivando."

        /// `account.email_codice`
        static let emailCodice = "Codice a 6 cifre"

        /// `account.email_conferma`
        static let emailConferma = "Conferma l'email"

        /// `account.email_confermata_ok`
        static let emailConfermataOk = "Email confermata"

        /// `account.email_togli`
        static let emailTogli = "Togli l'email"

        /// `account.email_tolta_ok`
        static let emailToltaOk = "Email tolta"

        /// `account.email_serve_password`
        static let emailServePassword = "Scrivi la tua password per confermare"

        /// `account.email_spenta`
        static let emailSpenta = "Su questo server l'invio delle email è spento: per ora non puoi collegare un'email. Se dimentichi la password ti serve il codice di recupero."

        /// `account.dati_titolo`
        static let datiTitolo = "Scarica i tuoi dati"

        /// `account.dati_spiega`
        static let datiSpiega = "Un file con i dati del tuo account (nome, email, accessi collegati, termini accettati) e della tua lega: regole, rose, scelte, giocatori seguiti e notifiche. Contiene solo i tuoi dati, mai la password."

        /// `account.dati_scarica`
        static let datiScarica = "Scarica il file"

        /// `account.elimina_titolo`
        static let eliminaTitolo = "Elimina l'account"

        /// `account.elimina_avviso`
        static let eliminaAvviso = "Cancella l'account e <b>tutti</b> i tuoi dati dal server. Non si può annullare: prima scarica i tuoi dati se ti servono."

        /// `account.elimina`
        static let elimina = "Elimina il mio account"

        /// `account.elimina_conferma`
        static let eliminaConferma = "Elimino il tuo account e TUTTI i tuoi dati? Non si può annullare."
    }
}
