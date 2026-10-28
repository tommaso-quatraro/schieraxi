import Foundation

/// Copia su disco dell'ultima risposta riuscita di ogni indirizzo (cartella Caches dell'app).
/// Serve a mostrare subito i dati all'apertura e quando il server non risponde (rete privata spento, server irraggiungibile).
/// iOS può svuotare questa cartella quando serve spazio: non è un problema, i dati si riscaricano.
enum Cache {
    private static var cartella: URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("api", isDirectory: true)
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    /// Nome file stabile ricavato dall'indirizzo (hash FNV-1a a 64 bit: lo stesso testo dà sempre lo stesso nome).
    private static func nomeFile(_ percorso: String) -> String {
        var h: UInt64 = 0xcbf29ce484222325
        for byte in percorso.utf8 {
            h ^= UInt64(byte)
            h = h &* 0x100000001b3
        }
        return String(h, radix: 16) + ".json"
    }

    private static func url(_ percorso: String) -> URL {
        cartella.appendingPathComponent(nomeFile(percorso))
    }

    static func salva(_ dati: Data, _ percorso: String) {
        try? dati.write(to: url(percorso), options: .atomic)
    }

    /// I dati salvati e il momento in cui sono stati scaricati.
    static func leggi(_ percorso: String) -> (dati: Data, data: Date)? {
        let u = url(percorso)
        guard let dati = try? Data(contentsOf: u) else { return nil }
        let attributi = try? FileManager.default.attributesOfItem(atPath: u.path)
        let data = attributi?[.modificationDate] as? Date
        return (dati, data ?? Date())
    }
}
