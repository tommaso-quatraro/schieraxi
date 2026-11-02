import SwiftUI
import UserNotifications
import CoreSpotlight

// Account del server con più utenti (modalità «multiutente»). Con il server di sempre (un solo utente) `/api/account/me`
// dice multiutente=false: l'app non chiede nessun accesso e funziona come prima.

/// L'utente che ha fatto l'accesso.
struct Utente: Codable, Equatable {
    let id: Int
    let nomeUtente: String
    let ruolo: String
    let creato: String?
    /// Il nome come l'ha scritto l'utente («TuttoBene»): il server (1.77+) lo manda accanto al nome utente in minuscolo.
    var nomeVisualizzato: String? = nil

    /// Il nome da mostrare: quello visualizzato se c'è, altrimenti il nome utente.
    var nome: String {
        if let v = nomeVisualizzato?.trimmingCharacters(in: .whitespacesAndNewlines), !v.isEmpty { return v }
        return nomeUtente
    }

    var amministratore: Bool { ruolo == "amministratore" }
    var ruoloLeggibile: String { amministratore ? "Amministratore" : "Utente" }
}

/// Le risposte delle rotte `/api/account/...` (alcuni campi ci sono solo in certi casi).
struct RispostaAccount: Decodable {
    var multiutente: Bool?
    var utente: Utente?
    var token: String?
    var codiceRecupero: String?
    /// Email dell'account e indirizzo ancora da verificare (il server li manda con gli account accesi; facoltativi e letti con tolleranza).
    var email: String?
    var emailInAttesa: String?
    /// Da dove viene `email`: "account" o "google" (facoltativo: un server più vecchio non lo manda).
    var emailOrigine: String?
    /// Registrazione con email: l'account non c'è ancora, serve il codice arrivato per posta e questo segreto dell'iscrizione.
    var verificaEmail: Bool?
    var iscrizione: String?
    /// I servizi di accesso accesi sul server (per ora «google») e i modi di entrare di questo account: facoltativi.
    var social: [String]?
    var accessi: AccessiAccount?

    private enum CodingKeys: String, CodingKey { case multiutente, utente, token, codiceRecupero, email, emailInAttesa, emailOrigine, verificaEmail, iscrizione, social, accessi }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        multiutente = try c.decodeIfPresent(Bool.self, forKey: .multiutente)
        utente = try c.decodeIfPresent(Utente.self, forKey: .utente)
        token = try c.decodeIfPresent(String.self, forKey: .token)
        codiceRecupero = try c.decodeIfPresent(String.self, forKey: .codiceRecupero)
        email = (try? c.decodeIfPresent(String.self, forKey: .email)) ?? nil
        emailInAttesa = (try? c.decodeIfPresent(String.self, forKey: .emailInAttesa)) ?? nil
        emailOrigine = (try? c.decodeIfPresent(String.self, forKey: .emailOrigine)) ?? nil
        verificaEmail = (try? c.decodeIfPresent(Bool.self, forKey: .verificaEmail)) ?? nil
        iscrizione = (try? c.decodeIfPresent(String.self, forKey: .iscrizione)) ?? nil
        social = ((try? c.decodeIfPresent([String].self, forKey: .social)) ?? nil)
        accessi = (try? c.decodeIfPresent(AccessiAccount.self, forKey: .accessi)) ?? nil
    }
}

/// Dove siamo rispetto all'accesso.
enum StatoAccesso: Equatable {
    /// Il server non ha account (un solo utente): nessun accesso, come sempre.
    case nonRichiesto
    /// Il server ha gli account e non c'è una sessione valida: si mostra la schermata di accesso.
    case daAccedere
    case connesso(Utente)
}

/// Regole di nome utente e password, uguali a quelle del server (`fanta/account.py`): l'app le controlla prima di scrivere al server
/// e dice subito cosa non va, ma l'ultima parola resta al server.
enum RegoleAccount {
    static let passwordMinima = 10
    static let passwordMassima = 200

    /// Il nome utente come lo vuole il server: minuscolo, senza spazi ai lati.
    static func pulisciNome(_ testo: String) -> String {
        testo.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    /// Controllo leggero di un indirizzo email (l'ultima parola è del server).
    static func problemaEmail(_ testo: String) -> String? {
        let t = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return "Scrivi l'indirizzo email." }
        let parti = t.split(separator: "@", omittingEmptySubsequences: false)
        guard parti.count == 2, !parti[0].isEmpty, parti[1].contains("."), !parti[1].hasPrefix("."), !parti[1].hasSuffix("."),
              !t.contains(" "), t.count <= 254 else { return "Questo non sembra un indirizzo email." }
        return nil
    }

    /// nil se va bene, altrimenti cosa non va (frase breve, da spogliatoio).
    static func problemaNome(_ testo: String) -> String? {
        let nome = pulisciNome(testo)
        if nome.isEmpty { return "Scrivi il tuo nome utente." }
        if nome.count < 3 || nome.count > 32 { return "Il nome utente è lungo da 3 a 32 caratteri." }
        let ammessi = Set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if !nome.allSatisfy({ ammessi.contains($0) }) { return "Solo lettere, numeri, punto, trattino e trattino basso." }
        if let primo = nome.first, !(primo.isLetter || primo.isNumber) { return "Il nome utente comincia con una lettera o un numero." }
        return nil
    }

    /// Spazi (o a capo) prima o dopo il testo: di solito un errore di copia e incolla. Il nome utente si sistema da solo al login,
    /// ma quando si crea l'account si chiede di toglierli, così si sa con certezza cosa si è scelto.
    static func problemaSpaziNome(_ testo: String) -> String? {
        testo != testo.trimmingCharacters(in: .whitespacesAndNewlines) ? "Togli gli spazi prima e dopo il nome utente." : nil
    }

    static func problemaPassword(_ testo: String, nome: String = "") -> String? {
        if testo.isEmpty { return "Scrivi la password." }
        if testo != testo.trimmingCharacters(in: .whitespacesAndNewlines) { return "La password non può cominciare o finire con uno spazio." }
        if testo.count < passwordMinima { return "Servono almeno \(passwordMinima) caratteri (ora sono \(testo.count))." }
        if testo.count > passwordMassima { return "Massimo \(passwordMassima) caratteri." }
        if testo.allSatisfy(\.isNumber) { return "Solo numeri è troppo facile: aggiungi delle lettere." }
        if Set(testo.lowercased()).count < 4 { return "Troppi caratteri uguali: scegline una più varia." }
        let n = pulisciNome(nome)
        if !n.isEmpty, testo.lowercased().contains(n), testo.count < n.count + 6 { return "Non usare il nome utente come password." }
        return nil
    }
}

private struct CorpoAccesso: Encodable {
    let nomeUtente: String
    let password: String
    let nativo = true
    enum CodingKeys: String, CodingKey { case nomeUtente = "nome_utente", password, nativo }
}

private struct CorpoRegistrazione: Encodable {
    let nomeUtente: String
    let password: String
    let invito: String?
    let email: String?
    let accettoTermini: Bool
    let nativo = true
    enum CodingKeys: String, CodingKey { case nomeUtente = "nome_utente", password, invito, email, accettoTermini = "accetto_termini", nativo }
}

private struct CorpoConfermaIscrizione: Encodable {
    let email: String
    let codice: String
    let iscrizione: String
    let nativo = true
}

private struct CorpoRecupero: Encodable {
    let nomeUtente: String
    let codice: String
    let nuova: String
    enum CodingKeys: String, CodingKey { case nomeUtente = "nome_utente", codice, nuova }
}

private struct CorpoCambioPassword: Encodable {
    let attuale: String
    let nuova: String
}

private struct CorpoSoloPassword: Encodable {
    let password: String
}


private struct CorpoEmail: Encodable {
    let email: String
    let password: String
}

private struct CorpoAvvioSocial: Encodable {
    let scopo: String
    let sfida: String
    let password: String
    let piattaforma = "ios"
}

private struct CorpoScambioSocial: Encodable {
    let codice: String
    let verificatore: String
    let nativo = true
}

private struct CorpoCompletaSocial: Encodable {
    let iscrizione: String
    let nomeUtente: String
    let invito: String?
    let accettoTermini: Bool
    let nativo = true
    enum CodingKeys: String, CodingKey { case iscrizione, nomeUtente = "nome_utente", invito, accettoTermini = "accetto_termini", nativo }
}

private struct CorpoCodiceEmail: Encodable {
    let codice: String
}

/// Il conto alla rovescia dopo un «troppi tentativi» (429): quanti secondi mancano, e si ferma a zero.
enum AttesaRiprova {
    static func secondiRimasti(fino: Date, adesso: Date = Date()) -> Int {
        max(0, Int(fino.timeIntervalSince(adesso).rounded(.up)))
    }
}

/// Cosa si cancella dal telefono quando si esce da un account (o la sessione finisce): copie su disco delle risposte e delle immagini,
/// immagini in memoria, ricordi dell'aggiornamento in background, giocatori osservati in Spotlight, promemoria in attesa.
/// Così chi entra dopo non vede niente di chi c'era prima.
@MainActor
enum DatiLocali {
    static func svuota() {
        Cache.svuotaTutto()
        URLCache.shared.removeAllCachedResponses()   // copie delle risposte tenute da iOS, anche loro dell'account che esce
        Immagini.condivise.azzera()
        VersioniRisorse.condivise.azzera()
        Condiviso.dimentica()
        MemoriaWidget.dimentica()
        let memoria = UserDefaults.standard
        for chiave in ["bg.giornata", "bg.modulo", "bg.probabili", "novitaVista", "ultimoRiassunto"] { memoria.removeObject(forKey: chiave) }
        ArchivioScambi.svuota(memoria)
        if !Demo.attivo {
            CSSearchableIndex.default().deleteAllSearchableItems { _ in }
            let centro = UNUserNotificationCenter.current()
            centro.removeAllPendingNotificationRequests()
            centro.removeAllDeliveredNotifications()
        }
    }
}

/// L'accesso all'account: stato, accedi, registrati, esci, cambia password, ecc. Il token sta nel Keychain (`ArchivioToken`).
@MainActor
final class SessioneAccount: ObservableObject {
    @Published private(set) var stato: StatoAccesso
    /// Il server ha gli account (l'ultima volta che l'abbiamo saputo).
    @Published private(set) var multiutente: Bool
    /// Il codice di recupero appena creato, da far salvare: compare a schermo intero finché non si conferma «l'ho salvato».
    @Published var codiceDaMostrare: String?
    /// Cambia a ogni accesso e a ogni uscita: l'app ricostruisce le schermate (e i loro dati) da zero.
    @Published private(set) var generazione = 0
    @Published private(set) var inCorso = false
    /// Un avviso da far vedere in Lega: per esempio il Keychain che non ha salvato l'accesso.
    @Published private(set) var avviso: String?
    /// Email dell'account (verificata) e indirizzo in attesa di verifica: dal server, solo con gli account accesi.
    @Published private(set) var email: String?
    @Published private(set) var emailInAttesa: String?
    /// "google" se `email` è quella di Google (il server la dà quando l'account non ne ha una sua).
    @Published private(set) var emailOrigine: String?
    /// Come si entra in questo account (password, Google): dal server, solo se Google è acceso.
    @Published private(set) var accessi: AccessiAccount?
    /// true se l'app ha appena lasciato un vecchio server per quello nuovo: la schermata Accedi lo spiega, finché non si rientra.
    @Published private(set) var serverSpostato = false

    /// Errori dell'app (non del server) durante accesso e account.
    enum Errore: LocalizedError, Equatable {
        case occupato
        case serverNonValido
        case rispostaNonValida

        var errorDescription: String? {
            switch self {
            case .occupato: return "Un attimo: sto ancora lavorando alla richiesta di prima."
            case .serverNonValido: return "Questo non sembra un server di SchieraXI. Controlla l'indirizzo del server."
            case .rispostaNonValida: return "Il server ha mandato una risposta strana: per sicurezza non entro. Controlla l'indirizzo del server."
            }
        }
    }

    private let server: any ServerClient
    private let archivio: any ArchivioToken
    private let memoria: UserDefaults
    private let pulisci: @MainActor () -> Void
    private var osservatore: NSObjectProtocol?

    private static let chiaveMultiutente = "account.multiutente"
    private static let chiaveUtente = "account.utente"
    /// L'indirizzo del server a cui si riferisce l'ultimo accesso (non è un segreto): se cambia, il token vecchio si butta.
    private static let chiaveIndirizzo = "account.indirizzo"

    init(server: any ServerClient = ServerCorrente.condiviso,
         archivio: any ArchivioToken = Accesso.archivio,
         memoria: UserDefaults = .standard,
         pulisci: @escaping @MainActor () -> Void = { DatiLocali.svuota() }) {
        self.server = server
        self.archivio = archivio
        self.memoria = memoria
        self.pulisci = pulisci
        // Aggiornando da una versione vecchia può restare l'indirizzo di un server che non c'è più: si passa al predefinito
        // e si butta la sessione di quello vecchio, prima di tutto il resto.
        if let vecchio = MigrazioneServer.migraSubito(memoria) {
            Self.lasciaServerVecchio(vecchio, nuovo: server.indirizzo, archivio: archivio, memoria: memoria, pulisci: pulisci)
        }
        var iniziale = Self.statoIniziale(server: server.indirizzo, archivio: archivio, memoria: memoria)
        let spostato = memoria.bool(forKey: MigrazioneServer.chiaveSpostato)
        if spostato && iniziale == .nonRichiesto { iniziale = .daAccedere }   // dopo lo spostamento si riparte sempre dall'accesso
        serverSpostato = spostato
        stato = iniziale
        multiutente = iniziale != .nonRichiesto
        if memoria.string(forKey: Self.chiaveIndirizzo) == nil { memoria.set(server.indirizzo, forKey: Self.chiaveIndirizzo) }
        osservatore = NotificationCenter.default.addObserver(forName: .accessoRichiesto, object: nil, queue: .main) { [weak self] n in
            let indirizzo = n.userInfo?["server"] as? String
            let impronta = n.userInfo?["impronta"] as? Int
            MainActor.assumeIsolated { self?.sessioneFinita(daServer: indirizzo, impronta: impronta) }
        }
        // Solo per le fotografie (-DEMO_ACCESSO <scenario>): lo stato si decide a mano, senza server.
        if let scenario = Demo.accesso {
            let utenteDemo = Utente(id: 7, nomeUtente: "mister.rossi", ruolo: "utente", creato: nil)
            multiutente = true
            switch scenario {
            case "codice":
                stato = .connesso(utenteDemo)
                codiceDaMostrare = "K7M2P-XQ4NH-W8RTV"
            case "account", "rose":
                stato = .connesso(utenteDemo)
                if Demo.argomento("DEMO_ACCOUNT_CHE_CAMBIA") != nil { simulaRisposteDemo(utenteDemo) }
            default:
                stato = .daAccedere
            }
        }
    }

    /// Solo per i test di interfaccia (`-DEMO_ACCESSO account -DEMO_ACCOUNT_CHE_CAMBIA 1`): come se ogni mezzo secondo arrivasse
    /// la risposta di `/api/account/me` con dati un po' diversi (stesso utente, email che va e viene). Serve a provare che
    /// i fogli dell'account (cambia password, email, ...) restano aperti mentre i dati dell'account si aggiornano.
    private func simulaRisposteDemo(_ u: Utente) {
        Task { @MainActor [weak self] in
            for giro in 1...600 {
                try? await Task.sleep(nanoseconds: 500_000_000)
                guard let self, !Task.isCancelled else { return }
                let pari = giro.isMultiple(of: 2)
                email = pari ? nil : "mister.rossi@example.invalid"
                stato = .connesso(Utente(id: u.id, nomeUtente: u.nomeUtente, ruolo: u.ruolo, creato: pari ? nil : "2026-09-01"))
            }
        }
    }

    deinit {
        if let osservatore { NotificationCenter.default.removeObserver(osservatore) }
    }

    /// Senza aspettare la rete: con un token si parte come «connesso» (con l'ultimo utente noto), se si sa che il server ha gli account
    /// ma il token non c'è si parte dall'accesso, altrimenti come sempre. Poi `verifica()` conferma.
    static func statoIniziale(server: String, archivio: any ArchivioToken, memoria: UserDefaults) -> StatoAccesso {
        if let token = archivio.leggi(server: server), !token.isEmpty {
            if let dati = memoria.data(forKey: chiaveUtente), let utente = try? JSONDecoder().decode(Utente.self, from: dati) { return .connesso(utente) }
            return .connesso(Utente(id: 0, nomeUtente: "…", ruolo: "utente", creato: nil))
        }
        return memoria.bool(forKey: chiaveMultiutente) ? .daAccedere : .nonRichiesto
    }

    var utente: Utente? {
        if case .connesso(let u) = stato { return u }
        return nil
    }

    /// Le funzioni dell'amministratore (aggiornare i dati del server, lo stato dei dati): sempre senza account, solo per
    /// l'amministratore con gli account (agli altri il server risponde 403).
    var puoAmministrare: Bool { !ProvaEsempio.attiva && (!multiutente || (utente?.amministratore ?? false)) }

    // MARK: stato

    /// Chiede al server chi sono (`GET /api/account/me`) e allinea lo stato. Se il server non risponde si resta dov'eravamo.
    func verifica() async {
        if Demo.accesso != nil || ProvaEsempio.attiva { return }   // fotografie e prova con dati di esempio: nessun server vero da interrogare
        do {
            let r: RispostaAccount = try await server.get("/api/account/me")
            if r.multiutente == true {
                if let u = r.utente {
                    // si scrive solo ciò che cambia: ogni scrittura ridisegna le schermate che guardano l'account
                    if email != r.email { email = r.email }
                    if emailInAttesa != r.emailInAttesa { emailInAttesa = r.emailInAttesa }
                    if emailOrigine != r.emailOrigine { emailOrigine = r.emailOrigine }
                    ServiziSociali.salva(ServiziSociali.pulisci(r.social), in: memoria)
                    let nuoviAccessi = ServiziSociali.googleAcceso(in: memoria) ? r.accessi : nil
                    if accessi != nuoviAccessi { accessi = nuoviAccessi }
                    imposta(.connesso(u))
                    // il widget ha il suo token a scopo limitato (mai quello della sessione)
                    let s = server
                    Task { await TokenWidget.assicura(server: s) }
                } else { imposta(.daAccedere) }
            } else {
                archivio.cancella(server: server.indirizzo)
                imposta(.nonRichiesto)
            }
        } catch ErroreApi.accessoRichiesto {
            // Gli account ci sono e la sessione no (scaduta, chiusa da un altro dispositivo, o mai fatta).
            sessioneFinita(daServer: server.indirizzo, impronta: nil)
        } catch {
            // Server spento o rete non raggiungibile: l'app resta com'è (con i dati salvati).
        }
    }

    /// Il server è cambiato (Lega > Server): si riparte dallo stato di quel server.
    func cambiaServer() async {
        if Demo.accesso != nil || ProvaEsempio.attiva { return }
        // Un altro server: il token del vecchio non deve MAI essere mandato al nuovo. Si butta, con i dati locali del vecchio.
        let attuale = server.indirizzo
        if let vecchio = memoria.string(forKey: Self.chiaveIndirizzo), vecchio != attuale {
            Self.lasciaServerVecchio(vecchio, nuovo: attuale, archivio: archivio, memoria: memoria, pulisci: pulisci)
            codiceDaMostrare = nil
            avviso = nil
        }
        serverSpostato = memoria.bool(forKey: MigrazioneServer.chiaveSpostato)
        if serverSpostato { multiutente = true }
        let nuovo = Self.statoIniziale(server: server.indirizzo, archivio: archivio, memoria: memoria)
        if nuovo != stato { generazione += 1 }
        stato = nuovo
        await verifica()
    }

    /// Si lascia un server: il suo token, i dati salvati e l'utente ricordato si buttano. Se è uno spostamento automatico
    /// (`MigrazioneServer`) si resta «con gli account», così si parte dalla schermata Accedi.
    @MainActor private static func lasciaServerVecchio(_ vecchio: String, nuovo: String, archivio: any ArchivioToken, memoria: UserDefaults,
                                            pulisci: @MainActor () -> Void) {
        archivio.cancella(server: vecchio)
        TokenWidget.pulisciLocale(indirizzo: vecchio)
        pulisci()
        memoria.removeObject(forKey: chiaveUtente)
        memoria.removeObject(forKey: chiaveMultiutente)
        memoria.set(nuovo, forKey: chiaveIndirizzo)
        if memoria.bool(forKey: MigrazioneServer.chiaveSpostato) { memoria.set(true, forKey: chiaveMultiutente) }
    }

    private func imposta(_ nuovo: StatoAccesso) {
        let eraMultiutente = multiutente
        var nuovoId: Int?
        if case .connesso(let u) = nuovo {
            nuovoId = u.id
            if let dati = try? JSONEncoder().encode(u) { memoria.set(dati, forKey: Self.chiaveUtente) }
        }
        multiutente = nuovo != .nonRichiesto
        memoria.set(multiutente, forKey: Self.chiaveMultiutente)
        if nuovo == .nonRichiesto { memoria.removeObject(forKey: Self.chiaveUtente) }
        if nuovo != stato {
            // Un utente diverso (o nessuno): le schermate si ricostruiscono. Lo stesso utente che si conferma non le tocca.
            let cambiaUtente = utente?.id != nuovoId && utente?.id != 0   // 0 = utente ancora ignoto (partenza con il token): non è un cambio
            stato = nuovo
            if cambiaUtente || eraMultiutente != multiutente { generazione += 1 }
        }
    }

    /// Un 401 fuori dall'accesso: il token non vale più. Si butta, si svuotano i dati del telefono e si torna all'accesso.
    /// Un 401 arrivato da una pagina qualsiasi (`impronta` presente) prima si conferma con `/api/account/me`: un solo 401
    /// sospetto (un proxy, un server appena riavviato, una richiesta andata storta) non deve buttare fuori l'utente.
    private func sessioneFinita(daServer indirizzo: String?, impronta: Int?) {
        if let indirizzo, indirizzo != server.indirizzo { return }   // un'altra richiesta, di un server che non è più in uso
        if stato == .daAccedere { return }
        // Un 401 di una richiesta fatta con un token che non è più quello di adesso (nel frattempo c'è stato un nuovo accesso): si ignora.
        if let impronta, archivio.leggi(server: server.indirizzo)?.hashValue != impronta { return }
        if impronta != nil {
            guard !ricontrolloInCorso else { return }   // anche il 401 di /api/account/me passa di qui: si aspetta il suo esito
            ricontrolloInCorso = true
            Task { await ricontrollaSessione(impronta: impronta) }
            return
        }
        chiudiLocale()
    }

    /// Un ricontrollo alla volta, dopo un 401 da una pagina qualsiasi.
    private var ricontrolloInCorso = false

    /// Chiede al server se la sessione vale ancora. Chiude solo se il server lo conferma (401, o «account senza utente»);
    /// con la rete assente o una risposta strana si resta dentro, con i dati salvati.
    private func ricontrollaSessione(impronta: Int?) async {
        defer { ricontrolloInCorso = false }
        let confermata: Bool
        do {
            let r: RispostaAccount = try await server.get("/api/account/me")
            confermata = r.multiutente == true && r.utente == nil
        } catch ErroreApi.accessoRichiesto {
            confermata = true
        } catch {
            confermata = false
        }
        // Nel frattempo può essere cambiato tutto (uscita, nuovo accesso): si chiude solo se il token è ancora quello del 401.
        guard confermata, stato != .daAccedere, archivio.leggi(server: server.indirizzo)?.hashValue == impronta else { return }
        chiudiLocale()
    }

    /// Chiude l'accesso SOLO sul telefono: butta il token, svuota i dati locali, mostra la schermata di accesso.
    private func chiudiLocale() {
        archivio.cancella(server: server.indirizzo)
        TokenWidget.pulisciLocale(indirizzo: server.indirizzo)
        pulisci()
        multiutente = true
        memoria.set(true, forKey: Self.chiaveMultiutente)
        memoria.removeObject(forKey: Self.chiaveUtente)
        codiceDaMostrare = nil
        avviso = nil
        accessi = nil
        stato = .daAccedere
        generazione += 1
    }

    // MARK: azioni

    /// Una sola richiesta di account alla volta (doppio tocco, due schermate): la seconda si rifiuta con un messaggio.
    private func inizia() throws {
        if inCorso { throw Errore.occupato }
        inCorso = true
    }

    /// Una risposta che non si può leggere (HTML al posto del JSON, forma strana) non è un errore del server: probabilmente l'indirizzo è sbagliato.
    private func conTraduzione<T>(_ lavoro: () async throws -> T) async throws -> T {
        do {
            return try await lavoro()
        } catch ErroreApi.dati {
            throw Errore.serverNonValido
        }
    }

    /// Salva il token ricevuto e passa a «connesso». I dati locali di una sessione precedente si cancellano.
    /// Un server ostile potrebbe mandare qualsiasi cosa: token, nome e codice si controllano prima di usarli.
    private func conferma(_ r: RispostaAccount) throws {
        try conferma(token: r.token, utente: r.utente, codiceRecupero: r.codiceRecupero)
    }

    private func conferma(token: String?, utente: Utente?, codiceRecupero: String?) throws {
        guard let token, let utente else { throw Errore.serverNonValido }
        guard Accesso.tokenValido(token), utente.nomeUtente.count <= 100, utente.ruolo.count <= 40 else { throw Errore.rispostaNonValida }
        if let codice = codiceRecupero, !Accesso.codiceRecuperoValido(codice) { throw Errore.rispostaNonValida }
        accessi = nil
        pulisci()
        memoria.removeObject(forKey: MigrazioneServer.chiaveSpostato)
        serverSpostato = false
        let alSicuro = archivio.salva(token, server: server.indirizzo)
        avviso = alSicuro ? nil : "Non riesco a salvare l'accesso in modo sicuro su questo telefono: funziona finché l'app è aperta, poi dovrai accedere di nuovo."
        memoria.set(server.indirizzo, forKey: Self.chiaveIndirizzo)
        multiutente = true
        memoria.set(true, forKey: Self.chiaveMultiutente)
        if let dati = try? JSONEncoder().encode(utente) { memoria.set(dati, forKey: Self.chiaveUtente) }
        stato = .connesso(utente)
        generazione += 1
        let s = server
        Task { await TokenWidget.assicura(server: s) }
    }

    func accedi(nomeUtente: String, password: String) async throws {
        try inizia()
        defer { inCorso = false }
        let corpo = CorpoAccesso(nomeUtente: RegoleAccount.pulisciNome(nomeUtente), password: password)
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/accedi", corpo) }
        try conferma(r)
    }

    /// Crea l'account. Con l'invito (e senza email) l'account nasce subito e il codice di recupero finisce in `codiceDaMostrare`.
    /// Con l'email (server con registrazione «email» o «aperta») nasce solo dopo il codice arrivato per posta: in quel caso
    /// restituisce l'iscrizione in attesa da confermare con `confermaIscrizione`.
    @discardableResult
    func registra(nomeUtente: String, password: String, invito: String = "", email: String? = nil, accettoTermini: Bool = true) async throws -> IscrizioneInAttesa? {
        try inizia()
        defer { inCorso = false }
        let invitoPulito = invito.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        let emailPulita = email?.trimmingCharacters(in: .whitespacesAndNewlines)
        let corpo = CorpoRegistrazione(nomeUtente: RegoleAccount.pulisciNome(nomeUtente), password: password,
                                       invito: invitoPulito.isEmpty ? nil : invitoPulito,
                                       email: (emailPulita?.isEmpty ?? true) ? nil : emailPulita,
                                       accettoTermini: accettoTermini)
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/registra", corpo) }
        if r.verificaEmail == true {
            guard let iscrizione = r.iscrizione, let indirizzo = corpo.email, !iscrizione.isEmpty else { throw Errore.rispostaNonValida }
            return IscrizioneInAttesa(email: indirizzo, iscrizione: iscrizione)
        }
        try conferma(r)
        codiceDaMostrare = r.codiceRecupero
        return nil
    }

    /// Seconda metà della registrazione con email: il codice arrivato per posta apre l'account.
    func confermaIscrizione(_ attesa: IscrizioneInAttesa, codice: String) async throws {
        try inizia()
        defer { inCorso = false }
        let corpo = CorpoConfermaIscrizione(email: attesa.email, codice: codice.trimmingCharacters(in: .whitespacesAndNewlines), iscrizione: attesa.iscrizione)
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/registra/conferma", corpo) }
        try conferma(r)
        codiceDaMostrare = r.codiceRecupero
    }

    /// Nuova password con il codice di recupero. Restituisce il NUOVO codice di recupero (il vecchio non vale più), da far salvare.
    func recupera(nomeUtente: String, codice: String, nuovaPassword: String) async throws -> String? {
        try inizia()
        defer { inCorso = false }
        let corpo = CorpoRecupero(nomeUtente: RegoleAccount.pulisciNome(nomeUtente),
                                  codice: codice.trimmingCharacters(in: .whitespacesAndNewlines).uppercased(), nuova: nuovaPassword)
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/recupero", corpo) }
        if let nuovo = r.codiceRecupero, !Accesso.codiceRecuperoValido(nuovo) { throw Errore.rispostaNonValida }
        return r.codiceRecupero
    }

    /// Esce da questo telefono (il server chiude la sessione, se risponde) e svuota i dati locali.
    func esci() async {
        // Uscire non si rifiuta mai, nemmeno se c'è un'altra richiesta in corso: la richiesta al server è facoltativa.
        inCorso = true
        defer { inCorso = false }
        await TokenWidget.revoca(server: server)   // serve ancora la sessione: prima di chiuderla
        _ = try? await server.corpoJSON("POST", "/api/account/esci", [String: String]())
        chiudiLocale()
    }

    func cambiaPassword(attuale: String, nuova: String) async throws {
        try inizia()
        defer { inCorso = false }
        _ = try await server.corpoJSON("POST", "/api/account/cambia-password", CorpoCambioPassword(attuale: attuale, nuova: nuova))
    }

    /// Un nuovo codice di recupero al posto del vecchio (serve la password).
    func nuovoCodiceRecupero(password: String) async throws -> String {
        try inizia()
        defer { inCorso = false }
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/codice-recupero", CorpoSoloPassword(password: password)) }
        guard let codice = r.codiceRecupero, Accesso.codiceRecuperoValido(codice) else { throw Errore.rispostaNonValida }
        return codice
    }

    /// Chiede al server di verificare un indirizzo email: arriva un codice a quell'indirizzo. La risposta è sempre la stessa.
    func aggiungiEmail(_ email: String, password: String) async throws {
        try inizia()
        defer { inCorso = false }
        let pulita = email.trimmingCharacters(in: .whitespacesAndNewlines)
        _ = try await server.corpoJSON("POST", "/api/account/email", CorpoEmail(email: pulita, password: passwordPerServer(password)))
        emailInAttesa = pulita
    }

    func confermaEmail(codice: String) async throws {
        try inizia()
        defer { inCorso = false }
        _ = try await server.corpoJSON("POST", "/api/account/email/conferma", CorpoCodiceEmail(codice: codice.trimmingCharacters(in: .whitespacesAndNewlines)))
        await verifica()
    }

    func togliEmail(password: String) async throws {
        try inizia()
        defer { inCorso = false }
        _ = try await server.corpoJSON("POST", "/api/account/email/togli", CorpoSoloPassword(password: passwordPerServer(password)))
        email = nil
        emailInAttesa = nil
    }

    /// Cancella l'account e tutti i suoi dati sul server (non si può annullare), poi svuota il telefono.
    func elimina(password: String) async throws {
        try inizia()
        defer { inCorso = false }
        _ = try await server.corpoJSON("POST", "/api/account/elimina", CorpoSoloPassword(password: passwordPerServer(password)))
        chiudiLocale()
    }

    // MARK: accesso con Google

    /// Entra solo con Google: non ha una password. Per le azioni delicate il server chiede una riconferma con Google, non la password.
    var senzaPassword: Bool { accessi?.soloGoogle ?? false }

    /// Google è collegato a questo account (solo se il server ha Google acceso e ce l'ha detto).
    var googleCollegato: Bool { accessi?.google != nil || emailOrigine == "google" }

    /// L'email mostrata viene da Google (nota «da Google»).
    var emailDaGoogle: Bool { emailOrigine == "google" || (email == nil && emailInAttesa == nil && accessi?.google?.email != nil) }

    /// L'email da mostrare in «Il tuo account»: quella dell'account o, se manca, quella di Google.
    var emailMostrata: String? {
        ProfiloAccount.email(account: email, inAttesa: emailInAttesa, google: accessi?.google?.email)
    }

    /// Il campo password delle azioni delicate: chi non ha una password manda un segnaposto (il server guarda la riconferma recente).
    private func passwordPerServer(_ scritta: String) -> String { senzaPassword ? "google" : scritta }

    /// Il giro completo: chiede al server l'indirizzo, lo apre nel browser di sistema, e al ritorno riscatta il codice monouso.
    /// Il segreto (`verificatore`) resta solo in memoria per la durata del giro.
    private func giroGoogle(_ scopo: ScopoSocial, password: String = "", avvio: any AvvioWeb) async throws -> RispostaSocial {
        try inizia()
        defer { inCorso = false }
        let coppia = CoppiaPKCE.nuova()
        let avviato: RispostaSocial = try await conTraduzione {
            try await server.posta("POST", "/api/account/social/google/inizia", CorpoAvvioSocial(scopo: scopo.rawValue, sfida: coppia.sfida, password: password))
        }
        guard let indirizzo = IndirizzoAvvioSocial.valido(avviato.url) else { throw Errore.rispostaNonValida }
        let ritorno = try await avvio.apri(indirizzo, schema: Collegamenti.schema)
        guard let esito = RitornoSocial.interpreta(ritorno) else { throw ErroreSocial.nonValido }
        switch esito {
        case .errore(let motivo):
            throw ErroreSocial(motivo)
        case .codice(let codice):
            return try await conTraduzione {
                try await server.posta("POST", "/api/account/social/scambio", CorpoScambioSocial(codice: codice, verificatore: coppia.verificatore))
            }
        }
    }

    /// Entrare (o iniziare a registrarsi) con Google. `.entrato` = accesso fatto; `.nuovoAccount` = manca la scelta del nome utente.
    func accediConGoogle(avvio: any AvvioWeb) async throws -> EsitoSocial {
        let r = try await giroGoogle(.accedi, avvio: avvio)
        switch r.stato {
        case "ok":
            try conferma(token: r.token, utente: r.utente, codiceRecupero: nil)
            return .entrato
        case "nuovo":
            guard let iscrizione = r.iscrizione, !iscrizione.isEmpty, iscrizione.count <= 200 else { throw Errore.rispostaNonValida }
            return .nuovoAccount(NuovoAccountSocial(iscrizione: iscrizione, provider: r.provider ?? "google",
                                                    nomeSuggerito: r.nomeSuggerito, serveInvito: r.serveInvito ?? false))
        default:
            throw Errore.rispostaNonValida
        }
    }

    /// Crea l'account nuovo con il nome scelto (e il codice d'invito, se il server lo chiede).
    func completaConGoogle(_ nuovo: NuovoAccountSocial, nomeUtente: String, invito: String, accettoTermini: Bool) async throws {
        try inizia()
        defer { inCorso = false }
        let invitoPulito = invito.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        let corpo = CorpoCompletaSocial(iscrizione: nuovo.iscrizione, nomeUtente: RegoleAccount.pulisciNome(nomeUtente),
                                        invito: invitoPulito.isEmpty ? nil : invitoPulito, accettoTermini: accettoTermini)
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/social/completa", corpo) }
        try conferma(r)
    }

    /// Collega Google all'account con cui si è già dentro. Il server vuole la password attuale (chi non ne ha una usa la riconferma).
    func collegaGoogle(password: String, avvio: any AvvioWeb) async throws {
        let r = try await giroGoogle(.collega, password: passwordPerServer(password), avvio: avvio)
        guard r.stato == "collegato" else { throw Errore.rispostaNonValida }
        if let a = r.accessi { accessi = a } else { await aggiornaAccessi() }
    }

    /// Riconferma con Google (vale 5 minuti): serve a chi non ha una password per eliminare l'account, cambiare l'email o aggiungere una password.
    func riconfermaGoogle(avvio: any AvvioWeb) async throws {
        let r = try await giroGoogle(.riconferma, avvio: avvio)
        guard r.stato == "riconfermato" else { throw Errore.rispostaNonValida }
    }

    func scollegaGoogle() async throws {
        try inizia()
        defer { inCorso = false }
        let dati = try await server.richiesta("DELETE", "/api/account/social/google", corpo: nil)
        let r: RispostaSocial = try await conTraduzione { try Decodifica.decodifica(dati) }
        if let a = r.accessi { accessi = a } else { accessi = nil }
    }

    /// Rilegge come si entra in questo account (solo con Google acceso). Se il server non risponde si resta com'è.
    func aggiornaAccessi() async {
        if Demo.accesso != nil || ProvaEsempio.attiva || !ServiziSociali.googleAcceso(in: memoria) { return }
        if let a: AccessiAccount = try? await server.get("/api/account/social/accessi"), a != accessi { accessi = a }
    }

    /// Per chi è entrato solo con Google: aggiunge una password (dopo la riconferma). Il codice di recupero nuovo compare a schermo intero.
    func impostaPassword(_ nuova: String) async throws {
        try inizia()
        defer { inCorso = false }
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/imposta-password", CorpoSoloPassword(password: nuova)) }
        guard let codice = r.codiceRecupero, Accesso.codiceRecuperoValido(codice) else { throw Errore.rispostaNonValida }
        codiceDaMostrare = codice
        if var a = accessi { a.password = true; accessi = a }
        await aggiornaAccessi()
    }

    /// Solo per la modalità demo (`-DEMO_ACCESSO`): porta la sessione in uno stato deciso a mano, senza server.
    func scenarioDemo(_ nuovo: StatoAccesso, codice: String? = nil) {
        stato = nuovo
        multiutente = nuovo != .nonRichiesto
        codiceDaMostrare = codice
    }
}
