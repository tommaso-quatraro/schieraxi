import Foundation

/// La giornata di oggi, dal server o (se non risponde) dall'ultima copia salvata.
/// Lo usano l'aggiornamento in background, Siri e Comandi: posti dove non c'è una schermata con il suo ViewModel.
struct OggiRepository {
    static let base = "/api/oggi"

    /// Con i giorni che mancano alla scadenza del certificato di SideStore (negativi se scaduto), se si leggono: il server li usa per
    /// la voce «Rinnova l'app» del «Da fare». Senza profilo leggibile (simulatore, test) è l'indirizzo di sempre.
    static var percorso: String { percorso(giorniCertificato: Certificato.giorniMancanti()) }

    static func percorso(giorniCertificato: Int?) -> String {
        giorniCertificato.map { "\(base)?certificato_giorni=\($0)" } ?? base
    }
    let server: any ServerClient

    /// Scarica la giornata e la salva nella cache.
    func aggiornato() async throws -> Oggi {
        let dati = try await server.grezzo(Self.percorso)
        let oggi: Oggi = try Decodifica.decodifica(dati)
        Cache.salva(dati, Self.percorso, indirizzo: server.indirizzo)
        return oggi
    }

    /// L'ultima copia salvata, se c'è.
    func salvato() async -> Oggi? {
        guard let copia = await Cache.leggi(Self.percorso, indirizzo: server.indirizzo) else { return nil }
        return try? Decodifica.decodifica(copia.dati)
    }

    /// Dal server; se non risponde, dalla cache (con `salvato` true).
    func ultimo() async -> (oggi: Oggi, salvato: Bool)? {
        if let oggi = try? await aggiornato() { return (oggi, false) }
        if let oggi = await salvato() { return (oggi, true) }
        return nil
    }
}
