import Foundation
import Security

// Il token di accesso (account del server con più utenti) sta SOLO nel Keychain di iOS: mai in UserDefaults, mai nei log,
// mai in git. Un token per server (la chiave è l'indirizzo): cambiando server non si manda il token sbagliato.

extension Notification.Name {
    /// Il server ha risposto 401 a una richiesta che non era un accesso: la sessione è finita (o non c'è) e serve l'accesso.
    static let accessoRichiesto = Notification.Name("<vecchio identificativo>.accessoRichiesto")
}

/// Dove si tiene il token. Due implementazioni: il Keychain vero e una in memoria (demo e test).
protocol ArchivioToken: Sendable {
    func leggi(server: String) -> String?
    func salva(_ token: String, server: String)
    func cancella(server: String)
}

/// In memoria, per la modalità demo e i test: sparisce quando l'app si chiude.
final class MemoriaToken: ArchivioToken, @unchecked Sendable {
    private let blocco = NSLock()
    private var valori: [String: String] = [:]

    func leggi(server: String) -> String? {
        blocco.lock(); defer { blocco.unlock() }
        return valori[server]
    }

    func salva(_ token: String, server: String) {
        blocco.lock(); defer { blocco.unlock() }
        valori[server] = token
    }

    func cancella(server: String) {
        blocco.lock(); defer { blocco.unlock() }
        valori[server] = nil
    }
}

/// Il Keychain di iOS (`kSecClassGenericPassword`), accessibile dopo il primo sblocco del telefono: serve anche all'aggiornamento
/// in background e a Siri, che girano a telefono bloccato.
/// Se iOS rifiuta il Keychain perché l'app non ha i permessi (succede solo nelle compilazioni senza firma per i test) il token resta in
/// memoria: l'app funziona, ma ci si dovrà accedere di nuovo alla prossima apertura.
struct KeychainToken: ArchivioToken {
    var servizio = "<vecchio identificativo>.account"
    private static let riserva = MemoriaToken()

    private func base(_ server: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: servizio,
         kSecAttrAccount as String: server]
    }

    func leggi(server: String) -> String? {
        var cerca = base(server)
        cerca[kSecReturnData as String] = true
        cerca[kSecMatchLimit as String] = kSecMatchLimitOne
        var risultato: CFTypeRef?
        if SecItemCopyMatching(cerca as CFDictionary, &risultato) == errSecSuccess,
           let dati = risultato as? Data, let testo = String(data: dati, encoding: .utf8) {
            return testo
        }
        return Self.riserva.leggi(server: servizio + "|" + server)
    }

    func salva(_ token: String, server: String) {
        SecItemDelete(base(server) as CFDictionary)
        var nuovo = base(server)
        nuovo[kSecValueData as String] = Data(token.utf8)
        nuovo[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        let esito = SecItemAdd(nuovo as CFDictionary, nil)
        if esito == errSecSuccess {
            Self.riserva.cancella(server: servizio + "|" + server)
        } else {
            Self.riserva.salva(token, server: servizio + "|" + server)
        }
    }

    func cancella(server: String) {
        SecItemDelete(base(server) as CFDictionary)
        Self.riserva.cancella(server: servizio + "|" + server)
    }
}

enum Accesso {
    /// L'archivio dei token in uso: il Keychain, o la memoria in modalità demo (le fotografie non toccano il Keychain).
    nonisolated(unsafe) static var archivio: any ArchivioToken = Demo.attivo ? MemoriaToken() : KeychainToken()
}
