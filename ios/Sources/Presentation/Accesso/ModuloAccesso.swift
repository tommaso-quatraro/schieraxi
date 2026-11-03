import Foundation

// La schermata di accesso senza interfaccia: passi, testi e controlli, uguali alla web (`campiAccesso`, `testoInvio` e
// `mostraAccesso` in `fanta/web/app.js`, testi `accesso.*` in `fanta/web/testi.js`). Logica pura: la provano i test.

/// I testi della schermata di accesso, presi dalla web.
enum TestiAccesso {
    /// L'età minima per iscriversi, come `ETA_MINIMA` della web (e `fanta/testi_legali.py`).
    static let etaMinima = 14
    /// La casella della registrazione (anche dopo Google): Privacy, Termini d'uso ed età in una sola conferma.
    static let letto = "Ho letto Privacy e Termini d'uso e ho almeno \(etaMinima) anni"
    static let spuntaLetto = "Per registrarti spunta la casella: hai letto Privacy e Termini d'uso e hai almeno \(etaMinima) anni"
    static let leggiPrivacy = "Leggi la Privacy"
    static let leggiTermini = "Leggi i Termini d'uso"
    static let passwordDimenticata = "Password dimenticata"
    static let tornaAllAccesso = "Torna all'accesso"
    static let codiceInviato = "Se l'indirizzo è registrato, il codice sta arrivando (vale 15 minuti)."
    static let passwordCambiata = "Password cambiata"
    static let passwordCambiataAccedi = "Password cambiata: accedi con quella nuova."
    static let vaiAllAccesso = "Vai all'accesso"
    /// Il recupero è andato a metà (nessun nuovo codice leggibile): come `accesso.risposta_incompleta` della web.
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

    /// Come la web: con la registrazione a invito, o con la posta spenta sul server, si parte dal codice di recupero;
    /// altrimenti dall'email.
    static func iniziale(_ modo: ModalitaRegistrazione, postaAccesa: Bool = true) -> MetodoRecupero {
        modo == .invito || !postaAccesa ? .codice : .email
    }
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

    /// Passa a un'altra scheda, come la web che riapre il modulo da capo: la password scritta non resta, i codici e i passi
    /// a metà (recupero, registrazione con il codice per posta) si dimenticano.
    mutating func vai(_ nuova: Scheda, modo: ModalitaRegistrazione, postaAccesa: Bool = true) {
        scheda = nuova
        password = ""
        codiceEmail = ""
        switch nuova {
        case .accedi:
            codice = ""
            emailRecupero = nil
        case .registrati:
            iscrizione = nil
        case .recupera:
            metodo = MetodoRecupero.iniziale(modo, postaAccesa: postaAccesa)
            emailRecupero = nil
            codice = ""
        }
    }

    /// Il codice per posta è partito (recupero con l'email, primo passo): si passa al secondo passo, ma solo se si è ancora
    /// dove lo si è chiesto (`daPasso`). Restituisce false se nel frattempo si è andati altrove: allora non cambia niente.
    mutating func codiceInviato(a indirizzo: String, daPasso: Passo) -> Bool {
        guard daPasso == .recuperoEmail, passo == daPasso else { return false }
        emailRecupero = indirizzo
        codiceEmail = ""
        password = ""
        return true
    }

    // MARK: cosa si vede

    /// I campi del modulo, nell'ordine della web (l'invio dalla tastiera passa al campo dopo; dall'ultimo manda il modulo).
    enum Campo: Hashable { case invito, nome, email, password, codice, codiceEmail }

    /// `postaAccesa` falso (il server non manda email): con l'invito l'email non si chiede, come la web.
    func campi(_ modo: ModalitaRegistrazione, postaAccesa: Bool = true) -> [Campo] {
        switch passo {
        case .accedi: return [.nome, .password]
        case .registra:
            let conEmail = postaAccesa || modo != .invito
            let base: [Campo] = conEmail ? [.nome, .email, .password] : [.nome, .password]
            return modo.chiedeInvito ? [Campo.invito] + base : base
        case .verificaIscrizione: return [.codiceEmail]
        case .recuperoCodice: return [.nome, .codice, .password]
        case .recuperoEmail: return [.email]
        case .recuperoEmailCodice: return [.codiceEmail, .password]
        }
    }

    /// La password da scegliere (registrazione e recupero): si controlla mentre si scrive.
    var passwordNuova: Bool { ([.registra, .recuperoCodice, .recuperoEmailCodice] as [Passo]).contains(passo) }
    /// La scelta «Con l'email» / «Con il codice di recupero»: solo al primo passo del recupero e con la posta accesa, come la web.
    func mostraMetodi(postaAccesa: Bool = true) -> Bool {
        postaAccesa && (passo == .recuperoCodice || passo == .recuperoEmail)
    }

    /// L'email da mandare con la registrazione: solo se il campo c'è (con la posta spenta un'email scritta prima non parte).
    func emailDaMandare(_ modo: ModalitaRegistrazione, postaAccesa: Bool = true) -> String {
        campi(modo, postaAccesa: postaAccesa).contains(.email) ? email : ""
    }

    var etichettaPassword: String {
        switch passo {
        case .accedi: return "Password"
        case .registra: return "Password (almeno \(RegoleAccount.passwordMinima) caratteri)"
        default: return "Nuova password (almeno \(RegoleAccount.passwordMinima) caratteri)"
        }
    }

    /// Breve, perché sta sopra il campo: il perché dell'email facoltativa va sotto (`aiuto`). La web ha la frase intera
    /// nell'etichetta (`accesso.email_facoltativa`): sull'iPhone era tagliata o rimpicciolita (issue #191).
    func etichettaEmail(_ modo: ModalitaRegistrazione) -> String {
        emailFacoltativa(modo) ? "Email (facoltativa)" : "Email"
    }

    private func emailFacoltativa(_ modo: ModalitaRegistrazione) -> Bool { passo == .registra && !modo.chiedeEmail }

    static let etichettaNome = "Nome utente"
    static let etichettaInvito = "Codice d'invito"
    static let etichettaCodice = "Codice"
    static let etichettaCodiceEmail = "Codice a 6 cifre ricevuto per email"
    static let aiutoEmailFacoltativa = "Serve a recuperare la password."

    /// L'etichetta sopra il campo, che resta mentre si scrive (come `campoAccesso` della web). Il campo non ha testo d'esempio.
    func etichetta(_ campo: Campo, _ modo: ModalitaRegistrazione) -> String {
        switch campo {
        case .nome: Self.etichettaNome
        case .invito: Self.etichettaInvito
        case .email: etichettaEmail(modo)
        case .password: etichettaPassword
        case .codice: Self.etichettaCodice
        case .codiceEmail: Self.etichettaCodiceEmail
        }
    }

    /// La spiegazione sotto il campo, se serve: oggi solo per l'email facoltativa della registrazione.
    func aiuto(_ campo: Campo, _ modo: ModalitaRegistrazione) -> String? {
        campo == .email && emailFacoltativa(modo) ? Self.aiutoEmailFacoltativa : nil
    }

    /// Il problema che si vede sotto il campo mentre si scrive (l'ultima parola resta del server).
    func problema(_ campo: Campo) -> String? {
        switch campo {
        case .nome: problemaNome
        case .email: problemaEmail
        case .password: problemaPassword
        case .invito, .codice, .codiceEmail: nil
        }
    }

    /// Cosa legge VoiceOver dopo l'etichetta del campo: il problema, se c'è, altrimenti la spiegazione.
    func suggerimento(_ campo: Campo, _ modo: ModalitaRegistrazione) -> String? {
        problema(campo) ?? aiuto(campo, modo)
    }

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
    func pronto(_ modo: ModalitaRegistrazione, postaAccesa: Bool = true) -> Bool {
        switch passo {
        case .accedi:
            return !RegoleAccount.pulisciNome(nome).isEmpty && !password.isEmpty
        case .registra:
            let emailOk: Bool
            if !campi(modo, postaAccesa: postaAccesa).contains(.email) {
                emailOk = true   // il campo non c'è: un'email scritta prima non conta (e non parte, vedi `emailDaMandare`)
            } else {
                emailOk = modo.chiedeEmail ? RegoleAccount.problemaEmail(email) == nil : problemaEmail == nil
            }
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

    /// Cosa fa l'invio (pulsante, o tasto Invio dall'ultimo campo).
    enum PrimaDellInvio: Equatable {
        /// Si scrive al server.
        case manda
        /// Si mostra questo messaggio e non si manda niente.
        case avvisa(String)
        /// Il modulo è a metà: i problemi sono già sotto i campi e il pulsante è spento.
        case aspetta
    }

    /// Come la web: la casella si controlla per prima, anche con il modulo a metà. Il resto la web lo fa dire al server; qui
    /// un modulo a metà non parte (pulsante spento, problemi sotto i campi).
    func primaDellInvio(_ modo: ModalitaRegistrazione, postaAccesa: Bool = true) -> PrimaDellInvio {
        if let problema = problemaPrimaDellInvio { return .avvisa(problema) }
        return pronto(modo, postaAccesa: postaAccesa) ? .manda : .aspetta
    }
}
