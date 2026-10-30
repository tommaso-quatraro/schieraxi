import Foundation

/// ETag delle risorse personali del server (regole, rose, avvisi, osservati). Chi legge riceve l'ETag; chi scrive lo rimanda
/// in `If-Match`: se un altro dispositivo ha cambiato i dati nel frattempo il server risponde 412 e l'app ricarica.
/// Senza un ETag ricordato (prima lettura, dopo l'uscita da un account) si scrive come sempre.
final class VersioniRisorse: @unchecked Sendable {
    static let condivise = VersioniRisorse()

    private let blocco = NSLock()
    private var etag: [String: String] = [:]

    /// A quale risorsa del server appartiene un indirizzo (senza query). `nil` se non ha un ETag.
    static func risorsa(per percorso: String) -> String? {
        let solo = percorso.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false).first.map(String.init) ?? percorso
        func inizia(_ prefisso: String) -> Bool { solo == prefisso || solo.hasPrefix(prefisso + "/") }
        if inizia("/api/avvisi/prova") { return nil }
        if inizia("/api/regole") { return "regole" }
        if inizia("/api/avvisi") { return "avvisi" }
        if inizia("/api/osservati") { return "osservati" }
        if inizia("/api/squadre") || inizia("/api/crediti") || inizia("/api/mia-squadra") || inizia("/api/rose") { return "rose" }
        return nil
    }

    private func chiave(_ server: String, _ risorsa: String) -> String { server + "|" + risorsa }

    func leggi(server: String, risorsa: String) -> String? {
        blocco.lock(); defer { blocco.unlock() }
        return etag[chiave(server, risorsa)]
    }

    func imposta(_ valore: String, server: String, risorsa: String) {
        // Un ETag è una stringa breve tra virgolette: niente a capo né testi enormi nelle intestazioni.
        guard !valore.isEmpty, valore.count <= 200, !valore.contains(where: \.isNewline) else { return }
        blocco.lock(); defer { blocco.unlock() }
        etag[chiave(server, risorsa)] = valore
    }

    /// Si dimenticano tutti (uscita da un account, cambio di server).
    func azzera() {
        blocco.lock(); defer { blocco.unlock() }
        etag.removeAll()
    }
}
