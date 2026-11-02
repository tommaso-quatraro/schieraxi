import Foundation

/// L'invio delle email sul server: il campo `email_attiva` del corpo dei 401 (e di `/api/account/me`). `false` vuol dire che
/// nessun codice per posta può arrivare: niente email nella registrazione con l'invito e niente recupero con l'email, come
/// `stato.emailAttiva` della web. Mai saputo, o server vecchio senza il campo: accesa, come prima.
enum PostaServer {
    static let chiave = "emailAttiva"

    private struct Campo: Decodable {
        let emailAttiva: Bool?
        enum CodingKeys: String, CodingKey { case emailAttiva = "email_attiva" }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            emailAttiva = (try? c.decodeIfPresent(Bool.self, forKey: .emailAttiva)) ?? nil
        }
    }

    /// Il valore del campo solo se è vero o falso (come `typeof === "boolean"` della web); altrimenti nil.
    static func leggi(corpo: Data) -> Bool? {
        (try? JSONDecoder().decode(Campo.self, from: corpo))?.emailAttiva
    }

    /// Lo ricorda solo se il server l'ha detto: un 401 senza il campo (nome o password sbagliati) lascia quello di prima.
    static func salva(corpo: Data, in memoria: UserDefaults = .standard) {
        if let attiva = leggi(corpo: corpo) { memoria.set(attiva, forKey: chiave) }
    }

    /// Accesa, a meno che il server non abbia detto il contrario.
    static func accesa(in memoria: UserDefaults = .standard) -> Bool {
        memoria.object(forKey: chiave) as? Bool ?? true
    }
}
