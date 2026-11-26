import Foundation

/// Come ci si registra su un server (campo `registrazione` della risposta 401): serve l'invito (`invito`), l'invito e l'email
/// verificata con un codice (`email`), oppure niente (`aperta`, dal 26/11/2026 quando il server lo accende: nome utente e
/// password, email facoltativa come con l'invito).
enum ModalitaRegistrazione: String, Equatable {
    case invito, email, aperta

    static let chiave = "modoRegistrazione"

    /// Legge il campo dal corpo di una risposta; mancante o sconosciuto = invito (il modo di sempre).
    static func leggi(corpo: Data) -> ModalitaRegistrazione {
        letto(corpo: corpo) ?? .invito
    }

    /// Il modo, solo se il corpo lo dice (un testo non vuoto, come la web; sconosciuto = invito). nil se il campo manca:
    /// il 401 di nome o password sbagliati ha solo `detail`.
    static func letto(corpo: Data) -> ModalitaRegistrazione? {
        guard let json = try? JSONSerialization.jsonObject(with: corpo) as? [String: Any],
              let testo = json["registrazione"] as? String, !testo.isEmpty else { return nil }
        return ModalitaRegistrazione(rawValue: testo) ?? .invito
    }

    /// Lo ricorda solo se il server l'ha detto: un 401 senza il campo lascia quello di prima (issue #173).
    static func salva(corpo: Data, in memoria: UserDefaults = .standard) {
        guard let modo = letto(corpo: corpo), memoria.string(forKey: chiave) != modo.rawValue else { return }
        memoria.set(modo.rawValue, forKey: chiave)
    }

    /// L'ultimo modo visto dal server (ricordato sul telefono).
    static var salvato: ModalitaRegistrazione { ricordato(in: .standard) }

    static func ricordato(in memoria: UserDefaults) -> ModalitaRegistrazione {
        ModalitaRegistrazione(rawValue: memoria.string(forKey: chiave) ?? "") ?? .invito
    }

    var chiedeInvito: Bool { self != .aperta }
    var invitoObbligatorio: Bool { self != .aperta }
    /// L'email obbligatoria (verificata con il codice per posta prima che l'account nasca): solo con il modo `email`.
    var chiedeEmail: Bool { self == .email }
}

/// Registrazione con email a metà: l'account nasce quando arriva il codice.
struct IscrizioneInAttesa: Equatable {
    let email: String
    let iscrizione: String
}
