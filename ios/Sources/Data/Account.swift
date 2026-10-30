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

    var amministratore: Bool { ruolo == "amministratore" }
    var ruoloLeggibile: String { amministratore ? "Amministratore" : "Utente" }
}

/// Le risposte delle rotte `/api/account/...` (alcuni campi ci sono solo in certi casi).
struct RispostaAccount: Decodable {
    var multiutente: Bool?
    var utente: Utente?
    var token: String?
    var codiceRecupero: String?
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
    let invito: String
    let nativo = true
    enum CodingKeys: String, CodingKey { case nomeUtente = "nome_utente", password, invito, nativo }
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
        Immagini.condivise.azzera()
        VersioniRisorse.condivise.azzera()
        Condiviso.dimentica()
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
        let iniziale = Self.statoIniziale(server: server.indirizzo, archivio: archivio, memoria: memoria)
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
            default:
                stato = .daAccedere
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
    var puoAmministrare: Bool { !multiutente || (utente?.amministratore ?? false) }

    // MARK: stato

    /// Chiede al server chi sono (`GET /api/account/me`) e allinea lo stato. Se il server non risponde si resta dov'eravamo.
    func verifica() async {
        if Demo.accesso != nil { return }   // fotografie: lo stato è quello dello scenario
        do {
            let r: RispostaAccount = try await server.get("/api/account/me")
            if r.multiutente == true {
                if let u = r.utente { imposta(.connesso(u)) } else { imposta(.daAccedere) }
            } else {
                archivio.cancella(server: server.indirizzo)
                imposta(.nonRichiesto)
            }
        } catch ErroreApi.accessoRichiesto {
            // Gli account ci sono e la sessione no (scaduta, chiusa da un altro dispositivo, o mai fatta).
            sessioneFinita(daServer: server.indirizzo, impronta: nil)
        } catch {
            // Server spento o rete privata non attivo: l'app resta com'è (con i dati salvati).
        }
    }

    /// Il server è cambiato (Lega > Server): si riparte dallo stato di quel server.
    func cambiaServer() async {
        if Demo.accesso != nil { return }
        // Un altro server: il token del vecchio non deve MAI essere mandato al nuovo. Si butta, con i dati locali del vecchio.
        let attuale = server.indirizzo
        if let vecchio = memoria.string(forKey: Self.chiaveIndirizzo), vecchio != attuale {
            archivio.cancella(server: vecchio)
            pulisci()
            memoria.removeObject(forKey: Self.chiaveUtente)
            memoria.removeObject(forKey: Self.chiaveMultiutente)
            memoria.set(attuale, forKey: Self.chiaveIndirizzo)
            codiceDaMostrare = nil
            avviso = nil
        }
        let nuovo = Self.statoIniziale(server: server.indirizzo, archivio: archivio, memoria: memoria)
        if nuovo != stato { generazione += 1 }
        stato = nuovo
        await verifica()
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
    private func sessioneFinita(daServer indirizzo: String?, impronta: Int?) {
        if let indirizzo, indirizzo != server.indirizzo { return }   // un'altra richiesta, di un server che non è più in uso
        if stato == .daAccedere { return }
        // Un 401 di una richiesta fatta con un token che non è più quello di adesso (nel frattempo c'è stato un nuovo accesso): si ignora.
        if let impronta, archivio.leggi(server: server.indirizzo)?.hashValue != impronta { return }
        chiudiLocale()
    }

    /// Chiude l'accesso SOLO sul telefono: butta il token, svuota i dati locali, mostra la schermata di accesso.
    private func chiudiLocale() {
        archivio.cancella(server: server.indirizzo)
        pulisci()
        multiutente = true
        memoria.set(true, forKey: Self.chiaveMultiutente)
        memoria.removeObject(forKey: Self.chiaveUtente)
        codiceDaMostrare = nil
        avviso = nil
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
        guard let token = r.token, let utente = r.utente else { throw Errore.serverNonValido }
        guard Accesso.tokenValido(token), utente.nomeUtente.count <= 100, utente.ruolo.count <= 40 else { throw Errore.rispostaNonValida }
        if let codice = r.codiceRecupero, !Accesso.codiceRecuperoValido(codice) { throw Errore.rispostaNonValida }
        pulisci()
        let alSicuro = archivio.salva(token, server: server.indirizzo)
        avviso = alSicuro ? nil : "Non riesco a salvare l'accesso in modo sicuro su questo telefono: funziona finché l'app è aperta, poi dovrai accedere di nuovo."
        memoria.set(server.indirizzo, forKey: Self.chiaveIndirizzo)
        multiutente = true
        memoria.set(true, forKey: Self.chiaveMultiutente)
        if let dati = try? JSONEncoder().encode(utente) { memoria.set(dati, forKey: Self.chiaveUtente) }
        stato = .connesso(utente)
        generazione += 1
    }

    func accedi(nomeUtente: String, password: String) async throws {
        try inizia()
        defer { inCorso = false }
        let corpo = CorpoAccesso(nomeUtente: RegoleAccount.pulisciNome(nomeUtente), password: password)
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/accedi", corpo) }
        try conferma(r)
    }

    /// Crea l'account con un invito. Il codice di recupero arriva una volta sola: finisce in `codiceDaMostrare`.
    func registra(nomeUtente: String, password: String, invito: String) async throws {
        try inizia()
        defer { inCorso = false }
        let corpo = CorpoRegistrazione(nomeUtente: RegoleAccount.pulisciNome(nomeUtente), password: password,
                                       invito: invito.trimmingCharacters(in: .whitespacesAndNewlines).uppercased())
        let r: RispostaAccount = try await conTraduzione { try await server.posta("POST", "/api/account/registra", corpo) }
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
        _ = try? await server.corpoJSON("POST", "/api/account/esci", [String: String]())
        chiudiLocale()
    }

    /// Chiude le sessioni di tutti i dispositivi (compreso questo).
    func esciDaTutti() async throws {
        try inizia()
        defer { inCorso = false }
        _ = try await server.corpoJSON("POST", "/api/account/esci-da-tutti", [String: String]())
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

    /// Cancella l'account e tutti i suoi dati sul server (non si può annullare), poi svuota il telefono.
    func elimina(password: String) async throws {
        try inizia()
        defer { inCorso = false }
        _ = try await server.corpoJSON("POST", "/api/account/elimina", CorpoSoloPassword(password: password))
        chiudiLocale()
    }

    /// Solo per la modalità demo (`-DEMO_ACCESSO`): porta la sessione in uno stato deciso a mano, senza server.
    func scenarioDemo(_ nuovo: StatoAccesso, codice: String? = nil) {
        stato = nuovo
        multiutente = nuovo != .nonRichiesto
        codiceDaMostrare = codice
    }
}
