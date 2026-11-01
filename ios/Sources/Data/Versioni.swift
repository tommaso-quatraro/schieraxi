import Foundation

/// ETag delle risorse personali del server (regole, rose, avvisi, osservati, scelta di una giornata). Chi legge riceve l'ETag; chi scrive lo rimanda
/// in `If-Match`: se un altro dispositivo ha cambiato i dati nel frattempo il server risponde 412 e l'app ricarica.
/// Senza un ETag ricordato (prima lettura, dopo l'uscita da un account) si scrive come sempre.
final class VersioniRisorse: @unchecked Sendable {
    static let condivise = VersioniRisorse()

    private let blocco = NSLock()
    private var etag: [String: String] = [:]

    /// A quale risorsa del server appartiene una richiesta. `nil` se non ha un ETag.
    /// La scelta salvata ha un ETag per giornata (come sulla web): `scelta:<giornata>`, dalla query di `/api/scelta`
    /// o dal corpo di `POST /api/formazione/valuta` quando salva la propria formazione (`salva: true`, senza `squadra`).
    static func risorsa(per percorso: String, corpo: Data? = nil) -> String? {
        let solo = percorso.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false).first.map(String.init) ?? percorso
        func inizia(_ prefisso: String) -> Bool { solo == prefisso || solo.hasPrefix(prefisso + "/") }
        if solo == "/api/scelta" { return scelta(giornataNellIndirizzo(percorso)) }
        if solo == "/api/formazione/valuta" { return scelta(giornataSalvata(corpo)) }
        if inizia("/api/avvisi/prova") { return nil }
        if inizia("/api/regole") { return "regole" }
        if inizia("/api/avvisi") { return "avvisi" }
        if inizia("/api/osservati") { return "osservati" }
        if inizia("/api/squadre") || inizia("/api/crediti") || inizia("/api/mia-squadra") || inizia("/api/rose") { return "rose" }
        return nil
    }

    private static func scelta(_ giornata: Int?) -> String? { giornata.map { "scelta:\($0)" } }

    /// `giornata=N` nella query (`/api/scelta?giornata=9`).
    private static func giornataNellIndirizzo(_ percorso: String) -> Int? {
        guard let valore = URLComponents(string: percorso)?.queryItems?.first(where: { $0.name == "giornata" })?.value,
              let g = Int(valore), g > 0 else { return nil }
        return g
    }

    /// La giornata di una valutazione che SALVA la propria scelta; `nil` per una valutazione e basta o per un'altra squadra
    /// (il server non salva niente e non controlla If-Match).
    private static func giornataSalvata(_ corpo: Data?) -> Int? {
        guard let corpo, let o = (try? JSONSerialization.jsonObject(with: corpo)) as? [String: Any],
              (o["salva"] as? Bool) == true else { return nil }
        if let squadra = o["squadra"] as? String, !squadra.isEmpty { return nil }
        guard let g = o["giornata"] as? Int, g > 0 else { return nil }
        return g
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

    /// Si dimenticano tutti (uscita da un account, cambio di server, nuova stagione).
    func azzera() {
        blocco.lock(); defer { blocco.unlock() }
        etag.removeAll()
    }
}
