import Foundation

/// I testi di «Il tuo account» (Impostazioni), uguali alla web (`schedaAccount` in `fanta/web/app.js`, testi `account.*`).
/// Logica pura: la provano i test.
enum TestiAccount {
    static let cambiaPassword = "Cambia la password"
    static let passwordAttuale = "Password attuale"
    static let nuovaPassword = "Nuova password (almeno \(RegoleAccount.passwordMinima) caratteri)"
    /// La nuova password scritta due volte, come la web (`account.ripeti_password` e `account.password_diverse`).
    static let ripetiPassword = "Ripeti la nuova password"
    static let passwordDiverse = "Le due password non coincidono."
    static let altriScollegati = "Gli altri dispositivi vengono scollegati."
    static let passwordCambiataOk = "Password cambiata. Gli altri dispositivi sono stati scollegati."
    static let laTuaPassword = "La tua password"

    static let recupero = "Codice di recupero"
    static let recuperoSpiega = "Serve se dimentichi la password. Il vecchio codice smette di valere appena ne generi uno nuovo."
    static let nuovoCodice = "Genera un nuovo codice"

    static let email = "Email"
    static let emailSpiega = "Facoltativa. Serve a recuperare la password senza il codice di recupero e a ricevere un avviso se qualcuno entra da un dispositivo nuovo. Non la usiamo per altro."
    static let emailNuova = "Nuovo indirizzo email"
    static let emailInvia = "Mandami il codice"
    static let emailInviato = "Se l'indirizzo è valido, il codice sta arrivando."
    static let emailCodice = "Codice a 6 cifre"
    static let emailConferma = "Conferma l'email"
    static let emailConfermataOk = "Email confermata"
    static let emailTogli = "Togli l'email"
    static let emailToltaOk = "Email tolta"
    static let emailServePassword = "Scrivi la tua password per confermare"
    /// Posta spenta sul server e nessuna email: al posto della riga e della voce dell'email, come la web (`account.email_spenta`).
    static let emailSpenta = "Su questo server l'invio delle email è spento: per ora non puoi collegare un'email. Se dimentichi la password ti serve il codice di recupero."

    static let datiTitolo = "Scarica i tuoi dati"
    static let datiSpiega = "Un file con i dati del tuo account (nome, email, accessi collegati, termini accettati) e della tua lega: regole, rose, scelte, giocatori seguiti e notifiche. Contiene solo i tuoi dati, mai la password."
    static let datiScarica = "Scarica il file"

    static let eliminaTitolo = "Elimina l'account"
    /// «tutti» in grassetto come sulla web (Markdown di `Text`).
    static let eliminaAvviso = "Cancella l'account e **tutti** i tuoi dati dal server. Non si può annullare: prima scarica i tuoi dati se ti servono."
    static let elimina = "Elimina il mio account"
    static let eliminaConferma = "Elimino il tuo account e TUTTI i tuoi dati? Non si può annullare."

    /// La riga sotto il nome: «Utente · dal 1 settembre 2026» (o «Amministratore · …»). Senza una data leggibile resta il ruolo.
    static func ruoloEData(ruolo: String, creato: String?) -> String {
        let chi = ruolo == "amministratore" ? "Amministratore" : "Utente"
        guard let giorno = dataIscrizione(creato) else { return chi }
        return "\(chi) · dal \(giorno)"
    }

    /// «1 settembre 2026» (ora italiana) dalla data del server: ISO 8601 con il fuso («2026-09-01T08:30:00+00:00»), senza fuso
    /// (ora italiana, come le altre date del server) o solo il giorno. nil se non si capisce.
    static func dataIscrizione(_ testo: String?) -> String? {
        guard let t = testo?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else { return nil }
        let iso = ISO8601DateFormatter()
        let data = iso.date(from: t)
            ?? Quando.data(t)
            ?? (t.count == 10 ? soloGiorno.date(from: t) : nil)
        guard let data else { return nil }
        return scrittura.string(from: data)
    }

    /// La riga dell'email in «Il tuo account», con le frasi della web.
    static func rigaEmail(account: String?, google: String?, inAttesa: String?) -> String {
        if let a = pulita(account) { return "Email confermata: \(a)" }
        if let g = pulita(google) { return "Email da Google: \(g)" }
        if let i = pulita(inAttesa) { return "In attesa di conferma: \(i)" }
        return "Nessuna email collegata."
    }

    /// Nel foglio dell'email, quando il codice è partito.
    static func emailAttesa(_ indirizzo: String) -> String {
        "In attesa di conferma: \(indirizzo). Scrivi qui sotto il codice a 6 cifre che ti abbiamo mandato."
    }

    private static func pulita(_ testo: String?) -> String? {
        guard let t = testo?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else { return nil }
        return t
    }

    private static let roma = TimeZone(identifier: "Europe/Rome") ?? .current

    private static let soloGiorno: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = roma
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static let scrittura: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.timeZone = roma
        f.dateFormat = "d MMMM yyyy"
        return f
    }()
}
