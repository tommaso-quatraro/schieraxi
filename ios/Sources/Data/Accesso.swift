import Foundation
import Security

// Il token di accesso (account del server con più utenti) sta SOLO nel Keychain di iOS: mai in UserDefaults, mai nei log,
// mai in git. Un token per server (la chiave è l'indirizzo): cambiando server non si manda il token sbagliato.

extension Notification.Name {
    /// Il server ha risposto 401 a una richiesta che non era un accesso: la sessione è finita (o non c'è) e serve l'accesso.
    static let accessoRichiesto = Notification.Name("it.schieraxi.app.accessoRichiesto")
}

/// Dove si tiene il token. Due implementazioni: il Keychain vero e una in memoria (demo e test).
protocol ArchivioToken: Sendable {
    func leggi(server: String) -> String?
    /// true se il token è stato messo al sicuro nel Keychain; false se iOS l'ha rifiutato (Keychain pieno, non permesso...):
    /// in quel caso il token vive solo in memoria, fino alla chiusura dell'app (e chi chiama lo dice all'utente).
    @discardableResult func salva(_ token: String, server: String) -> Bool
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

    @discardableResult func salva(_ token: String, server: String) -> Bool {
        blocco.lock(); defer { blocco.unlock() }
        valori[server] = token
        return true
    }

    func cancella(server: String) {
        blocco.lock(); defer { blocco.unlock() }
        valori[server] = nil
    }
}

/// Il Keychain di iOS (`kSecClassGenericPassword`), accessibile dopo il primo sblocco del telefono (serve all'aggiornamento
/// in background e a Siri, che girano a telefono bloccato) e solo su questo telefono: non entra nei backup trasferibili. Il widget non legge questo
/// Keychain (senza App Group non lo potrebbe): usa il suo codice di collegamento, quindi la restrizione non lo tocca.
/// Se iOS rifiuta il Keychain perché l'app non ha i permessi (succede solo nelle compilazioni senza firma per i test) il token resta in
/// memoria: l'app funziona, ma ci si dovrà accedere di nuovo alla prossima apertura.
struct KeychainToken: ArchivioToken {
    var servizio = "it.schieraxi.app.account"
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

    @discardableResult func salva(_ token: String, server: String) -> Bool {
        SecItemDelete(base(server) as CFDictionary)
        var nuovo = base(server)
        nuovo[kSecValueData as String] = Data(token.utf8)
        nuovo[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let esito = SecItemAdd(nuovo as CFDictionary, nil)
        if esito == errSecSuccess {
            Self.riserva.cancella(server: servizio + "|" + server)
            return true
        }
        // Keychain rifiutato: il token resta solo in memoria (mai su disco in chiaro, mai in UserDefaults).
        Self.riserva.salva(token, server: servizio + "|" + server)
        return false
    }

    func cancella(server: String) {
        SecItemDelete(base(server) as CFDictionary)
        Self.riserva.cancella(server: servizio + "|" + server)
    }
}

enum Accesso {
    /// Un token ricevuto dal server è accettabile solo se è un testo breve di caratteri semplici: un server ostile potrebbe mandare
    /// qualsiasi cosa (enorme, con a capo, con caratteri di controllo) che finirebbe in un'intestazione HTTP o nel Keychain.
    static func tokenValido(_ testo: String) -> Bool {
        guard !testo.isEmpty, testo.utf8.count <= 512 else { return false }
        return testo.utf8.allSatisfy { $0 > 0x20 && $0 < 0x7F }
    }

    /// Un codice di recupero accettabile: breve, lettere, cifre e trattini.
    static func codiceRecuperoValido(_ testo: String) -> Bool {
        guard !testo.isEmpty, testo.utf8.count <= 100 else { return false }
        return testo.utf8.allSatisfy { ($0 >= 0x30 && $0 <= 0x39) || ($0 >= 0x41 && $0 <= 0x5A) || ($0 >= 0x61 && $0 <= 0x7A) || $0 == 0x2D }
    }

    /// L'archivio dei token in uso: il Keychain, o la memoria in modalità demo (le fotografie non toccano il Keychain).
    nonisolated(unsafe) static var archivio: any ArchivioToken = Demo.daLancio ? MemoriaToken() : KeychainToken()

    /// Rimette nel file condiviso l'indirizzo e il TOKEN DEL WIDGET (`fw_`, a scopo limitato: solo lettura di oggi e widget) di adesso.
    /// Il token della sessione non va mai nel file condiviso.
    static func sincronizzaConIlWidget() {
        if Demo.attivo { return }
        let indirizzo = IndirizzoServer.attuale
        Condiviso.sincronizza(indirizzo: indirizzo, token: indirizzo.isEmpty ? nil : TokenWidget.leggi(server: indirizzo))
    }
}
