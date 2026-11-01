import Foundation
import CryptoKit

// Accesso con Google, parte pura (nessuna rete, nessuna schermata). Il giro con Google lo fa il SERVER: l'app apre nel browser di sistema
// l'indirizzo che il server le dà e, alla fine, riceve un codice monouso (60 secondi) con cui chiede la sessione.
// Qui non c'è nessun identificativo di Google e nessun indirizzo: tutto arriva dal server.

/// Perché si apre Google: entrare, collegare Google a un account che c'è già, oppure riconfermare (per le azioni delicate).
enum ScopoSocial: String, Equatable {
    case accedi, collega, riconferma
}

/// Segreto casuale (`verificatore`) e la sua impronta (`sfida`). Al server si manda solo la sfida; il verificatore si mostra alla fine,
/// così chi intercetta il codice di ritorno non può usarlo. Il verificatore resta solo in memoria.
struct CoppiaPKCE: Equatable {
    let verificatore: String
    let sfida: String

    static func nuova() -> CoppiaPKCE {
        var generatore = SystemRandomNumberGenerator()
        let byte = (0..<32).map { _ in UInt8.random(in: 0...255, using: &generatore) }
        let verificatore = base64Url(Data(byte))        // 43 caratteri
        return CoppiaPKCE(verificatore: verificatore, sfida: sfida(per: verificatore))
    }

    /// base64url(SHA-256(verificatore)) senza `=`.
    static func sfida(per verificatore: String) -> String {
        base64Url(Data(SHA256.hash(data: Data(verificatore.utf8))))
    }

    /// Il verificatore è lungo da 43 a 128 caratteri tra `A-Za-z0-9._~-`.
    static func verificatoreValido(_ testo: String) -> Bool {
        guard (43...128).contains(testo.count) else { return false }
        return testo.unicodeScalars.allSatisfy { s in
            ("A"..."Z").contains(s) || ("a"..."z").contains(s) || ("0"..."9").contains(s) || "._~-".unicodeScalars.contains(s)
        }
    }

    static func base64Url(_ dati: Data) -> String {
        dati.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

/// Perché il giro nel browser non è andato a buon fine (da `schieraxi://social?errore=...`).
enum MotivoErroreSocial: String, Equatable {
    case annullato, scaduto
    case nonValido = "non_valido"
}

/// Cosa torna al telefono alla fine del giro: `schieraxi://social?codice=...` oppure `schieraxi://social?errore=...`.
enum RitornoSocial: Equatable {
    case codice(String)
    case errore(MotivoErroreSocial)

    /// nil se l'indirizzo non è un ritorno dell'accesso con Google (o non porta niente di usabile).
    static func interpreta(_ url: URL) -> RitornoSocial? {
        guard url.scheme?.lowercased() == Collegamenti.schema, url.host?.lowercased() == "social",
              let voci = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems else { return nil }
        if let errore = voci.first(where: { $0.name == "errore" })?.value, !errore.isEmpty {
            return .errore(MotivoErroreSocial(rawValue: errore) ?? .nonValido)
        }
        if let codice = voci.first(where: { $0.name == "codice" })?.value, !codice.isEmpty, codice.count <= 200 {
            return .codice(codice)
        }
        return nil
    }

    /// true per gli indirizzi di ritorno: la navigazione normale dell'app li lascia stare.
    static func eRitorno(_ url: URL) -> Bool {
        url.scheme?.lowercased() == Collegamenti.schema && url.host?.lowercased() == "social"
    }
}

/// Gli errori del giro nel browser, con frasi semplici.
enum ErroreSocial: LocalizedError, Equatable {
    case annullato
    case scaduto
    case nonValido

    var errorDescription: String? {
        switch self {
        case .annullato: return "Hai chiuso Google prima di finire. Se vuoi, riprova."
        case .scaduto: return "Il tempo per entrare con Google è scaduto. Riprova."
        case .nonValido: return "Non sono riuscito a completare il passaggio con Google. Riprova tra poco."
        }
    }

    init(_ motivo: MotivoErroreSocial) {
        switch motivo {
        case .annullato: self = .annullato
        case .scaduto: self = .scaduto
        case .nonValido: self = .nonValido
        }
    }

    /// Chi ha solo chiuso la finestra non deve vedere un errore rosso: è una scelta, non un guasto.
    var eSoloUnaChiusura: Bool { self == .annullato }
}

/// Frasi per i codici d'errore del server (campo `codice`). Se il codice non si conosce resta il messaggio del server.
enum TestiSocial {
    static func errore(codice: String) -> String? {
        switch codice {
        case "email_gia_usata":
            return "Questo indirizzo ha già un account. Entra con nome utente e password, poi collega Google da Impostazioni."
        case "email_non_affidabile":
            return "Con questo account Google non posso creare l'account. Prova con un altro, oppure registrati con nome utente e password."
        case "google_gia_collegato":
            return "Questo account Google è già collegato a un account di SchieraXI."
        case "google_diverso":
            return "Hai scelto un altro account Google. Usa quello che hai già collegato."
        case "ultimo_accesso":
            return "Prima aggiungi una password: non puoi togliere l'unico modo per entrare."
        case "serve_riconferma":
            return "Per sicurezza conferma prima con Google (Impostazioni, Il tuo account, Accessi), poi riprova."
        default:
            return nil
        }
    }
}

/// I servizi di accesso che il server dichiara accesi (campo `social` del 401 e di `/api/account/me`). I pulsanti compaiono solo se
/// c'è «google». Si ricorda sul telefono come l'ultimo modo di registrazione.
enum ServiziSociali {
    static let chiave = "serviziSociali"

    /// Legge l'elenco dal corpo di una risposta; mancante o strano = nessuno.
    static func leggi(corpo: Data) -> [String] {
        guard let json = try? JSONSerialization.jsonObject(with: corpo) as? [String: Any] else { return [] }
        return pulisci(json["social"] as? [Any])
    }

    static func pulisci(_ elenco: [Any]?) -> [String] {
        (elenco ?? []).compactMap { $0 as? String }
            .map { $0.lowercased() }
            .filter { !$0.isEmpty && $0.count <= 20 && $0.allSatisfy { $0.isLetter || $0.isNumber } }
    }

    static func salva(_ elenco: [String], in memoria: UserDefaults = .standard) {
        memoria.set(elenco.joined(separator: ","), forKey: chiave)
    }

    static func elenco(_ testo: String) -> [String] {
        testo.split(separator: ",").map(String.init)
    }

    static func googleAcceso(_ testo: String) -> Bool {
        elenco(testo).contains("google")
    }

    static func googleAcceso(in memoria: UserDefaults = .standard) -> Bool {
        googleAcceso(memoria.string(forKey: chiave) ?? "")
    }
}

// MARK: risposte del server

/// Un accesso collegato all'account (per ora solo Google).
struct AccessoCollegato: Decodable, Equatable {
    var provider: String
    var email: String?
    var creata: String?
    var ultimoUso: String?

    private enum CodingKeys: String, CodingKey { case provider, email, creata, ultimoUso }

    init(provider: String, email: String? = nil, creata: String? = nil, ultimoUso: String? = nil) {
        self.provider = provider; self.email = email; self.creata = creata; self.ultimoUso = ultimoUso
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        provider = ((try? c.decodeIfPresent(String.self, forKey: .provider)) ?? nil) ?? ""
        email = (try? c.decodeIfPresent(String.self, forKey: .email)) ?? nil
        creata = (try? c.decodeIfPresent(String.self, forKey: .creata)) ?? nil
        ultimoUso = (try? c.decodeIfPresent(String.self, forKey: .ultimoUso)) ?? nil
    }
}

/// Come si può entrare in questo account: `{password, social: [...], disponibili: [...]}`.
struct AccessiAccount: Decodable, Equatable {
    var password: Bool?
    var social: [AccessoCollegato]
    var disponibili: [String]

    private enum CodingKeys: String, CodingKey { case password, social, disponibili }

    init(password: Bool? = nil, social: [AccessoCollegato] = [], disponibili: [String] = []) {
        self.password = password; self.social = social; self.disponibili = disponibili
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        password = (try? c.decodeIfPresent(Bool.self, forKey: .password)) ?? nil
        social = ((try? c.decodeIfPresent([AccessoCollegato].self, forKey: .social)) ?? nil) ?? []
        disponibili = ((try? c.decodeIfPresent([String].self, forKey: .disponibili)) ?? nil) ?? []
    }

    var google: AccessoCollegato? { social.first { $0.provider == "google" } }

    /// Entra solo con Google: nessuna password.
    var soloGoogle: Bool { password == false }

    /// Scollegare Google si può solo se resta un altro modo di entrare (la password o un altro servizio).
    var puoScollegareGoogle: Bool {
        google != nil && (password == true || social.contains { $0.provider != "google" })
    }
}

/// Un account da creare con Google: manca solo la scelta del nome utente (e, se serve, il codice d'invito).
struct NuovoAccountSocial: Equatable {
    let iscrizione: String
    let provider: String
    let nomeSuggerito: String?
    let serveInvito: Bool
}

/// Come finisce il giro con Google.
enum EsitoSocial: Equatable {
    /// Account esistente: l'accesso è fatto.
    case entrato
    /// Account nuovo: va scelto il nome utente.
    case nuovoAccount(NuovoAccountSocial)
    /// Google collegato all'account.
    case collegato
    /// Riconferma fatta (vale 5 minuti).
    case riconfermato
}

/// La risposta di `/api/account/social/scambio` (e di `DELETE .../google`): tutti i campi sono facoltativi.
struct RispostaSocial: Decodable {
    var stato: String?
    var iscrizione: String?
    var provider: String?
    var nomeSuggerito: String?
    var serveInvito: Bool?
    var token: String?
    var utente: Utente?
    var accessi: AccessiAccount?
    var url: String?

    private enum CodingKeys: String, CodingKey { case stato, iscrizione, provider, nomeSuggerito, serveInvito, token, utente, accessi, url }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        stato = (try? c.decodeIfPresent(String.self, forKey: .stato)) ?? nil
        iscrizione = (try? c.decodeIfPresent(String.self, forKey: .iscrizione)) ?? nil
        provider = (try? c.decodeIfPresent(String.self, forKey: .provider)) ?? nil
        nomeSuggerito = (try? c.decodeIfPresent(String.self, forKey: .nomeSuggerito)) ?? nil
        serveInvito = (try? c.decodeIfPresent(Bool.self, forKey: .serveInvito)) ?? nil
        token = (try? c.decodeIfPresent(String.self, forKey: .token)) ?? nil
        utente = (try? c.decodeIfPresent(Utente.self, forKey: .utente)) ?? nil
        accessi = (try? c.decodeIfPresent(AccessiAccount.self, forKey: .accessi)) ?? nil
        url = (try? c.decodeIfPresent(String.self, forKey: .url)) ?? nil
    }
}

/// L'indirizzo da aprire nel browser: solo https e con un nome di sito. Il resto (per esempio uno schema strano) si rifiuta.
enum IndirizzoAvvioSocial {
    static func valido(_ testo: String?) -> URL? {
        guard let testo, testo.count <= 4000, let url = URL(string: testo), url.scheme?.lowercased() == "https",
              let host = url.host, !host.isEmpty, url.user == nil, url.password == nil else { return nil }
        return url
    }
}

/// Il nome utente che il server suggerisce, ripulito per le nostre regole (può essere vuoto se non c'è nulla di buono).
enum NomeSuggerito {
    static func pulito(_ testo: String?) -> String {
        guard let testo else { return "" }
        let ammessi = Set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        let base = RegoleAccount.pulisciNome(testo.split(separator: "@").first.map(String.init) ?? testo)
            .map { ammessi.contains($0) ? $0 : Character("-") }
        var nome = String(base)
        while let primo = nome.first, !(primo.isLetter || primo.isNumber) { nome.removeFirst() }
        return String(nome.prefix(32))
    }
}
