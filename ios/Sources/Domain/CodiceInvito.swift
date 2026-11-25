import Foundation

/// Il codice d'invito scritto nel campo «Codice d'invito» della registrazione (anche dopo «Continua con Google»).
enum CodiceInvito {
    /// Il codice da mandare al server: senza spazi ai lati e in maiuscolo, come i codici del server.
    static func daCampo(_ scritto: String) -> String {
        scritto.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
    }
}
