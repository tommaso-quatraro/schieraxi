import Foundation

/// I testi di «Il tuo account» e di «Accessi» (Impostazioni), uguali alla web (`schedaAccount` e `htmlAccessi` in
/// `fanta/web/app.js`): vengono dal catalogo comune (`Catalogo.Account`, `Catalogo.Social`). Logica pura: la provano i test.
enum TestiAccount {
    static let cambiaPassword = Catalogo.Account.cambiaPassword
    static let passwordAttuale = Catalogo.Account.passwordAttuale
    /// Come la web anche per «Aggiungi una password» (chi entra solo con Google): il minimo dei caratteri sta nella frase.
    static let nuovaPassword = Catalogo.Accesso.passwordNuova10
    /// La nuova password scritta due volte, come la web (`account.ripeti_password` e `account.password_diverse`).
    static let ripetiPassword = Catalogo.Account.ripetiPassword
    static let passwordDiverse = Catalogo.Account.passwordDiverse
    static let altriScollegati = Catalogo.Account.altriScollegati
    static let passwordCambiataOk = Catalogo.Account.passwordCambiataOk
    static let laTuaPassword = Catalogo.Account.laTuaPassword

    /// L'esito sotto «Il tuo account» dopo il cambio della password, come l'avviso della web: con il codice nuovo dice di
    /// salvarlo (`account.password_cambiata_codice`), senza (server più vecchio) solo `account.password_cambiata_ok`.
    static func esitoCambioPassword(codiceNuovo: Bool) -> String {
        codiceNuovo ? Catalogo.Account.passwordCambiataCodice : Catalogo.Account.passwordCambiataOk
    }

    static let recupero = Catalogo.Account.recupero
    static let recuperoSpiega = Catalogo.Account.recuperoSpiega
    static let nuovoCodice = Catalogo.Account.nuovoCodice

    static let email = Catalogo.Account.email
    static let emailSpiega = Catalogo.Account.emailSpiega
    static let emailNuova = Catalogo.Account.emailNuova
    static let emailInvia = Catalogo.Account.emailInvia
    static let emailInviato = Catalogo.Account.emailInviato
    static let emailCodice = Catalogo.Account.emailCodice
    static let emailConferma = Catalogo.Account.emailConferma
    static let emailConfermataOk = Catalogo.Account.emailConfermataOk
    static let emailTogli = Catalogo.Account.emailTogli
    static let emailToltaOk = Catalogo.Account.emailToltaOk
    static let emailServePassword = Catalogo.Account.emailServePassword
    /// Posta spenta sul server e nessuna email: al posto della riga e della voce dell'email, come la web (`account.email_spenta`).
    static let emailSpenta = Catalogo.Account.emailSpenta

    static let datiTitolo = Catalogo.Account.datiTitolo
    static let datiSpiega = Catalogo.Account.datiSpiega
    static let datiScarica = Catalogo.Account.datiScarica

    static let eliminaTitolo = Catalogo.Account.eliminaTitolo
    /// «tutti» in grassetto come sulla web: il `<b>` della web diventa il Markdown di `Text`.
    static let eliminaAvviso = Catalogo.Account.eliminaAvviso
        .replacingOccurrences(of: "<b>", with: "**")
        .replacingOccurrences(of: "</b>", with: "**")
    static let elimina = Catalogo.Account.elimina
    static let eliminaConferma = Catalogo.Account.eliminaConferma

    /// La riga sotto il nome: «Utente · dal 1 settembre 2026» (o «Amministratore · …»). Senza una data leggibile resta il ruolo.
    static func ruoloEData(ruolo: String, creato: String?) -> String {
        let chi = ruolo == "amministratore" ? Catalogo.Account.ruoloAdmin : Catalogo.Account.ruoloUtente
        guard let giorno = dataIscrizione(creato) else { return chi }
        return Catalogo.Account.dal(data: giorno, ruolo: chi)
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

    /// La riga dell'email in «Il tuo account», con le frasi della web. Con un codice in attesa la riga dice solo «In attesa di
    /// conferma: …», l'inizio di `account.email_attesa`: sulla web la frase intera sta accanto al campo del codice, sull'iPhone
    /// il campo (e la frase intera, `emailAttesa`) sta nel foglio dell'email.
    static func rigaEmail(account: String?, google: String?, inAttesa: String?) -> String {
        if let a = pulita(account) { return Catalogo.Account.emailVerificata(email: a) }
        if let g = pulita(google) { return Catalogo.Account.emailGoogle(email: g) }
        if let i = pulita(inAttesa) { return "In attesa di conferma: \(i)" }
        return Catalogo.Account.emailNessuna
    }

    /// Nel foglio dell'email, quando il codice è partito.
    static func emailAttesa(_ indirizzo: String) -> String {
        Catalogo.Account.emailAttesa(email: indirizzo)
    }

    /// «Accessi», come la web: «Password: impostata» o «Password: non impostata». Se il server non lo dice, niente riga.
    static func rigaPassword(_ accessi: AccessiAccount) -> String? {
        accessi.password.map { $0 ? Catalogo.Social.passwordSi : Catalogo.Social.passwordNo }
    }

    /// «Accessi», come la web: «Account Google collegato: <email>» («account collegato» senza email) o «Google: non collegato».
    static func rigaGoogle(_ accessi: AccessiAccount) -> String {
        guard let google = accessi.google else { return Catalogo.Social.googleNonCollegato }
        return Catalogo.Social.googleCollegato(email: pulita(google.email) ?? Catalogo.Social.googleAccount)
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
