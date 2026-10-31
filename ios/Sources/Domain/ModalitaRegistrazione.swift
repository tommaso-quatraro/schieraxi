import Foundation

/// Come ci si registra su un server (campo `registrazione` della risposta 401): serve l'invito, l'email verificata con un codice,
/// oppure entrambe (`email`: invito ed email) o niente invito (`aperta`: email verificata, invito facoltativo).
enum ModalitaRegistrazione: String, Equatable {
    case invito, email, aperta

    static let chiave = "modoRegistrazione"

    /// Legge il campo dal corpo di una risposta; mancante o sconosciuto = invito (il modo di sempre).
    static func leggi(corpo: Data) -> ModalitaRegistrazione {
        guard let json = try? JSONSerialization.jsonObject(with: corpo) as? [String: Any],
              let testo = json["registrazione"] as? String, let modo = ModalitaRegistrazione(rawValue: testo) else { return .invito }
        return modo
    }

    /// L'ultimo modo visto dal server (ricordato sul telefono).
    static var salvato: ModalitaRegistrazione {
        ModalitaRegistrazione(rawValue: UserDefaults.standard.string(forKey: chiave) ?? "") ?? .invito
    }

    var chiedeInvito: Bool { self != .aperta }
    var invitoObbligatorio: Bool { self != .aperta }
    var chiedeEmail: Bool { self != .invito }
}

/// Registrazione con email a metà: l'account nasce quando arriva il codice.
struct IscrizioneInAttesa: Equatable {
    let email: String
    let iscrizione: String
}
