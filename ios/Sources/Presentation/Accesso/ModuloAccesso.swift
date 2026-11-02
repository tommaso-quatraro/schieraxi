import Foundation

// La schermata di accesso senza interfaccia: passi, testi e controlli, uguali alla web (`campiAccesso`, `testoInvio` e
// `mostraAccesso` in `fanta/web/app.js`, testi `accesso.*` in `fanta/web/testi.js`). Logica pura: la provano i test.

/// I testi della schermata di accesso, presi dalla web.
enum TestiAccesso {
    /// L'età minima per iscriversi, come `ETA_MINIMA` della web (e `fanta/testi_legali.py`).
    static let etaMinima = 14
    /// La casella della registrazione (anche dopo Google): Privacy, Termini d'uso ed età in una sola conferma.
    static let letto = "Ho letto Privacy e Termini d'uso e ho almeno \(etaMinima) anni"
    static let spuntaLetto = "Per registrarti spunta la casella: hai letto Privacy e Termini d'uso"
    static let leggiPrivacy = "Leggi la Privacy"
    static let leggiTermini = "Leggi i Termini d'uso"
    static let passwordDimenticata = "Password dimenticata"
    static let tornaAllAccesso = "Torna all'accesso"
    static let codiceInviato = "Se l'indirizzo è registrato, il codice sta arrivando (vale 15 minuti)."
    static let passwordCambiata = "Password cambiata"
    static let passwordCambiataAccedi = "Password cambiata: accedi con quella nuova."
    static let vaiAllAccesso = "Vai all'accesso"
    static let rispostaIncompleta = "Qualcosa non ha funzionato: riprova"
}

/// Come si recupera la password: con l'email dell'account o con il codice di recupero.
enum MetodoRecupero: String, CaseIterable, Identifiable {
    case email, codice
    var id: String { rawValue }

    var titolo: String {
        switch self {
        case .email: return "Con l'email"
        case .codice: return "Con il codice di recupero"
        }
    }

    /// Come la web: con la registrazione a invito si parte dal codice di recupero, altrimenti dall'email.
    static func iniziale(_ modo: ModalitaRegistrazione) -> MetodoRecupero { modo == .invito ? .codice : .email }
}

/// Quello che si è scritto nella schermata di accesso e a che punto si è.
struct ModuloAccesso: Equatable {
    typealias Scheda = SchermataAccesso.Scheda

    /// Il passo che si vede: una scheda può averne più di uno (registrazione con il codice per posta, recupero con l'email).
    enum Passo: Equatable {
        case accedi, registra, verificaIscrizione, recuperoCodice, recuperoEmail, recuperoEmailCodice
    }

    var scheda: Scheda = .accedi
    var metodo: MetodoRecupero = .codice
    var nome = ""
    var password = ""
    var invito = ""
    var codice = ""
    var email = ""
    var codiceEmail = ""
    var accetto = false
    /// Registrazione con email a metà: manca il codice arrivato per posta.
    var iscrizione: IscrizioneInAttesa?
    /// Recupero con l'email, secondo passo: l'indirizzo a cui è partito il codice.
    var emailRecupero: String?

    var passo: Passo {
        switch scheda {
        case .accedi: return .accedi
        case .registrati: return iscrizione == nil ? .registra : .verificaIscrizione
        case .recupera:
            switch metodo {
            case .codice: return .recuperoCodice
            case .email: return emailRecupero == nil ? .recuperoEmail : .recuperoEmailCodice
            }
        }
    }

    /// Passa a un'altra scheda: la password scritta non resta, il recupero riparte dal primo passo.
    mutating func vai(_ nuova: Scheda, modo: ModalitaRegistrazione) {
        scheda = nuova
        password = ""
        if nuova == .recupera {
            metodo = MetodoRecupero.iniziale(modo)
            emailRecupero = nil
            codiceEmail = ""
            codice = ""
        }
    }

    // MARK: cosa si vede

    /// I campi del modulo, nell'ordine della web (l'invio dalla tastiera passa al campo dopo; dall'ultimo manda il modulo).
    enum Campo: Hashable { case invito, nome, email, password, codice, codiceEmail }

    func campi(_ modo: ModalitaRegistrazione) -> [Campo] {
        switch passo {
        case .accedi: return [.nome, .password]
        case .registra:
            let base: [Campo] = [.nome, .email, .password]
            return modo.chiedeInvito ? [Campo.invito] + base : base
        case .verificaIscrizione: return [.codiceEmail]
        case .recuperoCodice: return [.nome, .codice, .password]
        case .recuperoEmail: return [.email]
        case .recuperoEmailCodice: return [.codiceEmail, .password]
        }
    }

    /// La password da scegliere (registrazione e recupero): si controlla mentre si scrive.
    var passwordNuova: Bool { ([.registra, .recuperoCodice, .recuperoEmailCodice] as [Passo]).contains(passo) }
    /// La scelta «Con l'email» / «Con il codice di recupero»: solo al primo passo del recupero, come la web.
    var mostraMetodi: Bool { passo == .recuperoCodice || passo == .recuperoEmail }

    var etichettaPassword: String {
        switch passo {
        case .accedi: return "Password"
        case .registra: return "Password (almeno \(RegoleAccount.passwordMinima) caratteri)"
        default: return "Nuova password (almeno \(RegoleAccount.passwordMinima) caratteri)"
        }
    }

    func etichettaEmail(_ modo: ModalitaRegistrazione) -> String {
        passo == .registra && !modo.chiedeEmail ? "Email (facoltativa: serve a recuperare la password)" : "Email"
    }

    static let etichettaNome = "Nome utente"
    static let etichettaInvito = "Codice d'invito"
    static let etichettaCodice = "Codice"
    static let etichettaCodiceEmail = "Codice a 6 cifre ricevuto per email"

    /// La frase in cima al modulo (la web la mette come prima riga); nessuna per accedere.
    func spiegazione(_ modo: ModalitaRegistrazione) -> String? {
        switch passo {
        case .accedi: return nil
        case .registra:
            switch modo {
            case .invito: return "Ti serve un codice d'invito: chiedilo a chi ti ha invitato."
            case .email: return "Serve un codice d'invito e un indirizzo email: ti mandiamo un codice per confermarlo."
            case .aperta: return "Scrivi la tua email: ti mandiamo un codice per confermarla e creare l'account."
            }
        case .verificaIscrizione:
            let a = iscrizione?.email ?? ""
            return "Ti abbiamo scritto a \(a). Inserisci il codice a 6 cifre (vale 15 minuti). Se non arriva, controlla la posta indesiderata."
        case .recuperoCodice:
            return "Usa il codice di recupero che hai ricevuto quando ti sei registrato, oppure il codice che ti ha dato chi ti ha invitato."
        case .recuperoEmail:
            return "Scrivi l'email del tuo account: se è registrata, ti mandiamo un codice per scegliere una nuova password. Per sicurezza la risposta è sempre la stessa."
        case .recuperoEmailCodice:
            return "Scrivi il codice arrivato a \(emailRecupero ?? "") e scegli la nuova password."
        }
    }

    var titoloPulsante: String {
        switch passo {
        case .accedi: return "Accedi"
        case .registra: return "Crea l'account"
        case .verificaIscrizione: return "Conferma e crea l'account"
        case .recuperoEmail: return "Mandami il codice"
        case .recuperoCodice, .recuperoEmailCodice: return "Scegli la nuova password"
        }
    }

    // MARK: controlli (l'ultima parola è del server)

    var problemaNome: String? {
        guard !nome.isEmpty, passo != .accedi else { return nil }
        return RegoleAccount.problemaSpaziNome(nome) ?? RegoleAccount.problemaNome(nome)
    }

    var problemaPassword: String? {
        guard passwordNuova, !password.isEmpty else { return nil }
        return RegoleAccount.problemaPassword(password, nome: nome)
    }

    /// L'email si controlla solo quando c'è scritto qualcosa (quella facoltativa vuota va bene).
    var problemaEmail: String? {
        email.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : RegoleAccount.problemaEmail(email)
    }

    private var nomeOk: Bool { !nome.isEmpty && problemaNome == nil }
    private var passwordOk: Bool { RegoleAccount.problemaPassword(password, nome: nome) == nil }
    private func pieno(_ testo: String) -> Bool { !testo.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

    /// Si può premere il pulsante. La casella di Privacy, Termini ed età NON conta qui: come sulla web, se manca lo dice
    /// il messaggio `TestiAccesso.spuntaLetto` al tocco (vedi `problemaPrimaDellInvio`).
    func pronto(_ modo: ModalitaRegistrazione) -> Bool {
        switch passo {
        case .accedi:
            return !RegoleAccount.pulisciNome(nome).isEmpty && !password.isEmpty
        case .registra:
            let emailOk = modo.chiedeEmail ? RegoleAccount.problemaEmail(email) == nil : problemaEmail == nil
            return nomeOk && passwordOk && emailOk && (!modo.invitoObbligatorio || pieno(invito))
        case .verificaIscrizione:
            return pieno(codiceEmail)
        case .recuperoCodice:
            return nomeOk && pieno(codice) && passwordOk
        case .recuperoEmail:
            return RegoleAccount.problemaEmail(email) == nil
        case .recuperoEmailCodice:
            return pieno(codiceEmail) && passwordOk
        }
    }

    /// Un controllo che si fa al tocco, senza scrivere al server: la casella non spuntata (la password scritta resta).
    var problemaPrimaDellInvio: String? {
        passo == .registra && !accetto ? TestiAccesso.spuntaLetto : nil
    }
}

/// «Password dimenticata» con l'email: le due rotte senza sessione della web (`/api/account/recupero-email` e `/conferma`).
@MainActor
enum RecuperoConEmail {
    private struct Richiesta: Encodable { let email: String }
    private struct Conferma: Encodable {
        let email: String
        let codice: String
        let nuova: String
    }

    /// Chiede il codice per posta. La risposta del server è la stessa che l'indirizzo esista o no: non c'è niente da leggere.
    static func chiediCodice(email: String, server: any ServerClient) async throws {
        let pulita = email.trimmingCharacters(in: .whitespacesAndNewlines)
        _ = try await server.corpoJSON("POST", "/api/account/recupero-email", Richiesta(email: pulita))
    }

    /// Nuova password con il codice arrivato per posta. Restituisce il NUOVO codice di recupero, da far salvare.
    static func conferma(email: String, codice: String, nuova: String, server: any ServerClient) async throws -> String {
        let corpo = Conferma(email: email.trimmingCharacters(in: .whitespacesAndNewlines),
                             codice: codice.trimmingCharacters(in: .whitespacesAndNewlines), nuova: nuova)
        let r: RispostaAccount
        do {
            r = try await server.posta("POST", "/api/account/recupero-email/conferma", corpo)
        } catch ErroreApi.dati {
            throw SessioneAccount.Errore.serverNonValido
        }
        guard let nuovo = r.codiceRecupero, Accesso.codiceRecuperoValido(nuovo) else { throw SessioneAccount.Errore.rispostaNonValida }
        return nuovo
    }
}
