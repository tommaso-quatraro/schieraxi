import Foundation

/// Lettura sicura di un file scelto dall'utente (selettore di file, «Apri con», Condividi).
/// - `startAccessingSecurityScopedResource`: i file scelti dal selettore stanno fuori dal contenitore dell'app e vanno «aperti» con questo permesso;
/// - `NSFileCoordinator`: per i file su iCloud Drive non ancora scaricati (li fa scaricare e aspetta);
/// - fuori dal thread principale e con un tetto alla dimensione (si controlla prima di leggere e dopo).
enum LetturaFile {
    static func leggi(_ url: URL, massimo: Int = FileRose.massimoByte) async throws -> Data {
        try await Task.detached(priority: .userInitiated) { () throws -> Data in
            let accesso = url.startAccessingSecurityScopedResource()
            defer { if accesso { url.stopAccessingSecurityScopedResource() } }
            let grandezza = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
            if grandezza > massimo { throw FileRose.Errore.troppoGrande }
            var erroreCoordinatore: NSError?
            var letto: Result<Data, Error>?
            NSFileCoordinator().coordinate(readingItemAt: url, options: [.withoutChanges], error: &erroreCoordinatore) { copia in
                letto = Result { try Data(contentsOf: copia, options: .mappedIfSafe) }
            }
            if let erroreCoordinatore { throw erroreCoordinatore }
            guard let dati = try letto?.get() else { throw FileRose.Errore.vuoto }
            if dati.count > massimo { throw FileRose.Errore.troppoGrande }
            return dati
        }.value
    }
}
