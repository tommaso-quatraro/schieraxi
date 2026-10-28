import Foundation

/// La giornata di oggi, dal server o (se non risponde) dall'ultima copia salvata.
/// Lo usano l'aggiornamento in background, Siri e Comandi: posti dove non c'è una schermata con il suo ViewModel.
struct OggiRepository {
    static let percorso = "/api/oggi"
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
