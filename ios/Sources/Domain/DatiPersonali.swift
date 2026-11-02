import Foundation

/// «Scarica i tuoi dati» (Impostazioni > Il tuo account): il file del server con regole, rose, scelte e dati dell'account,
/// salvato così com'è in una cartella temporanea, da passare al foglio Condividi. Nessun ripristino da qui.
/// Contratto: `GET /api/backup` con la sessione normale (il token del widget riceve 403).
enum DatiPersonali {
    static let percorso = "/api/backup"
    /// La cartella (dentro quella temporanea) dove sta l'ultimo file scaricato: si svuota a ogni nuovo scaricamento.
    static let nomeCartella = "dati-personali"

    /// `schieraxi-i-miei-dati-2026-11-01.json`: il giorno è quello italiano del momento dello scaricamento.
    static func nomeFile(_ adesso: Date = Date()) -> String {
        var calendario = Calendar(identifier: .gregorian)
        calendario.timeZone = TimeZone(identifier: "Europe/Rome") ?? .current
        let c = calendario.dateComponents([.year, .month, .day], from: adesso)
        let giorno = String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
        return "schieraxi-i-miei-dati-\(giorno).json"
    }

    /// Controllo leggero: è davvero il file del server (un oggetto JSON con `formato` giusto), non una pagina di un Wi-Fi o di un proxy.
    static func eValido(_ dati: Data) -> Bool {
        guard !dati.isEmpty, let radice = (try? JSONSerialization.jsonObject(with: dati)) as? [String: Any] else { return false }
        return (radice["formato"] as? String) == FileBackup.formato
    }

    /// Scarica il file e lo salva in `cartella` (di norma quella temporanea dell'app). Restituisce dove l'ha messo.
    static func scarica(server: any ServerClient, adesso: Date = Date(),
                        cartella: URL = FileManager.default.temporaryDirectory) async throws -> URL {
        let dati = try await server.grezzo(percorso)
        guard eValido(dati) else { throw ErroreApi.dati("non è il file dei dati") }
        let dove = cartella.appendingPathComponent(nomeCartella, isDirectory: true)
        let fm = FileManager.default
        // Un solo file alla volta: quello di prima (anche di un altro account) non resta in giro.
        if fm.fileExists(atPath: dove.path) { try? fm.removeItem(at: dove) }
        try fm.createDirectory(at: dove, withIntermediateDirectories: true)
        let file = dove.appendingPathComponent(nomeFile(adesso))
        try dati.write(to: file, options: [.atomic, .completeFileProtection])
        return file
    }

    /// Toglie il file scaricato (per esempio dopo l'uscita dall'account).
    static func pulisci(cartella: URL = FileManager.default.temporaryDirectory) {
        try? FileManager.default.removeItem(at: cartella.appendingPathComponent(nomeCartella, isDirectory: true))
    }

    /// Il messaggio per l'utente, semplice.
    static func testoErrore(_ errore: Error) -> String {
        guard let e = errore as? ErroreApi else {
            return "Non sono riuscito a salvare il file sul telefono. Controlla lo spazio libero e riprova."
        }
        switch e {
        case .accessoRichiesto:
            return "La sessione è scaduta: rientra nel tuo account e riprova."
        case .rete, .timeout:
            return ErroreApi.testoNonRaggiungibile
        case .dati:
            return "Il server non ha mandato il file dei dati. Riprova tra poco."
        default:
            return e.errorDescription ?? "Non sono riuscito a scaricare il file. Riprova tra poco."
        }
    }
}
