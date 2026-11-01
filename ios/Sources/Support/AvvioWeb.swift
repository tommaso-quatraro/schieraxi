import AuthenticationServices
import UIKit

/// Apre una pagina nel browser di sistema e aspetta che torni all'app con un indirizzo `schieraxi://...`.
/// È un protocollo per poterlo sostituire nei test (nessun browser nei test).
protocol AvvioWeb {
    /// Apre `url`; quando la pagina rimanda a `schema://...` restituisce quell'indirizzo.
    /// Lancia `ErroreSocial.annullato` se l'utente chiude la finestra.
    @MainActor func apri(_ url: URL, schema: String) async throws -> URL
}

/// Il vero: ASWebAuthenticationSession (finestra di sistema, senza SDK di terzi). Una istanza per volta.
@MainActor
final class AvvioWebSistema: NSObject, AvvioWeb, ASWebAuthenticationPresentationContextProviding {
    private var sessione: ASWebAuthenticationSession?

    func apri(_ url: URL, schema: String) async throws -> URL {
        try await withCheckedThrowingContinuation { (continuazione: CheckedContinuation<URL, Error>) in
            let s = ASWebAuthenticationSession(url: url, callbackURLScheme: schema) { ritorno, errore in
                if let ritorno {
                    continuazione.resume(returning: ritorno)
                } else if let e = errore as? ASWebAuthenticationSessionError, e.code == .canceledLogin {
                    continuazione.resume(throwing: ErroreSocial.annullato)
                } else {
                    continuazione.resume(throwing: ErroreSocial.nonValido)
                }
            }
            s.presentationContextProvider = self
            sessione = s
            if !s.start() {
                sessione = nil
                continuazione.resume(throwing: ErroreSocial.nonValido)
            }
        }
    }

    nonisolated func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            let scene = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            return scene.flatMap(\.windows).first(where: \.isKeyWindow) ?? scene.first?.windows.first ?? ASPresentationAnchor()
        }
    }
}
