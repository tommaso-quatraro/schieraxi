import Foundation

/// Copia su disco dell'ultima risposta riuscita di ogni indirizzo (cartella Caches dell'app).
/// Serve a mostrare subito i dati all'apertura e quando il server non risponde (rete assente o server irraggiungibile).
/// iOS può svuotare questa cartella quando serve spazio: non è un problema, i dati si riscaricano.
/// Lettura e scrittura avvengono fuori dal thread principale, così le schermate non si bloccano.
enum Cache {
    /// Oltre questo numero di file si cancellano i più vecchi (le ricerche e le schede dei giocatori ne creano molti).
    private static let massimoFile = 150
    private static let dopoPulizia = 100
    /// Una sola coda, in ordine, per scrivere, togliere, svuotare e leggere. Prima ogni scrittura era un compito staccato a bassa
    /// priorità: sotto carico poteva arrivare DOPO `rimuovi` o `svuotaTutto` e rimettere su disco la copia vecchia (per esempio lo
    /// stemma appena cambiato, o i dati di chi è appena uscito), e una lettura subito dopo una scrittura poteva non trovarla.
    private static let coda = DispatchQueue(label: "schieraxi.cache", qos: .utility)

    /// La cartella dentro Caches: «api» per le risposte JSON, «img» per le immagini (così la pulizia dei file JSON non le cancella).
    private static func cartella(_ nome: String) -> URL {
        let base = (FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first ?? FileManager.default.temporaryDirectory).appendingPathComponent(nome, isDirectory: true)
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    /// Il percorso senza i parametri che cambiano da soli ogni giorno: `/api/oggi?certificato_giorni=5` e `...=4` sono la stessa
    /// risposta. Con il numero nel nome del file la copia salvata ieri non si ritrovava più oggi, proprio quando il server non risponde.
    static func percorsoStabile(_ percorso: String) -> String {
        let pezzi = percorso.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false)
        guard pezzi.count == 2 else { return percorso }
        let altri = pezzi[1].split(separator: "&", omittingEmptySubsequences: true).filter { !$0.hasPrefix("certificato_giorni=") }
        return altri.isEmpty ? String(pezzi[0]) : String(pezzi[0]) + "?" + altri.joined(separator: "&")
    }

    /// Nome file stabile ricavato dall'indirizzo completo del server + percorso
    /// (hash FNV-1a a 64 bit: lo stesso testo dà sempre lo stesso nome; cambiando server la cache non si mescola).
    static func nomeFile(_ percorso: String, _ indirizzo: String) -> String {
        var h: UInt64 = 0xcbf29ce484222325
        for byte in (indirizzo + percorsoStabile(percorso)).utf8 {
            h ^= UInt64(byte)
            h = h &* 0x100000001b3
        }
        return String(h, radix: 16) + ".json"
    }

    /// Cancella TUTTE le copie su disco (risposte e immagini): all'uscita da un account, perché chi entra dopo non veda i dati di chi c'era prima.
    /// Aspetta le scritture già in coda, poi cancella: al ritorno nessuna copia vecchia può ricomparire.
    static func svuotaTutto() {
        let cartelle = ["api", "img"].map(cartella)
        coda.sync {
            for url in cartelle {
                let file = (try? FileManager.default.contentsOfDirectory(at: url, includingPropertiesForKeys: nil)) ?? []
                for f in file { try? FileManager.default.removeItem(at: f) }
            }
        }
    }

    /// Salva senza aspettare (in coda su un thread di servizio, nell'ordine delle chiamate).
    static func salva(_ dati: Data, _ percorso: String, indirizzo: String, cartella nome: String = "api") {
        let cartellaDiLavoro = cartella(nome)
        let url = cartellaDiLavoro.appendingPathComponent(nomeFile(percorso, indirizzo))
        coda.async {
            try? dati.write(to: url, options: .atomic)
            pulisci(cartellaDiLavoro)
        }
    }

    /// Toglie la copia su disco di un indirizzo (per esempio uno stemma appena cambiato), dopo le scritture già in coda.
    static func rimuovi(_ percorso: String, indirizzo: String, cartella nome: String = "api") {
        let url = cartella(nome).appendingPathComponent(nomeFile(percorso, indirizzo))
        coda.sync { try? FileManager.default.removeItem(at: url) }
    }

    /// I dati salvati e il momento in cui sono stati scaricati (dopo le scritture già in coda: si legge sempre l'ultima copia).
    static func leggi(_ percorso: String, indirizzo: String, cartella nome: String = "api") async -> (dati: Data, data: Date)? {
        let url = cartella(nome).appendingPathComponent(nomeFile(percorso, indirizzo))
        return await withCheckedContinuation { continuazione in
            coda.async(qos: .userInitiated) {
                guard let dati = try? Data(contentsOf: url) else { continuazione.resume(returning: nil); return }
                let attributi = try? FileManager.default.attributesOfItem(atPath: url.path)
                let data = attributi?[.modificationDate] as? Date
                continuazione.resume(returning: (dati: dati, data: data ?? Date()))
            }
        }
    }

    /// Tiene la cartella sotto il limite cancellando i file meno recenti.
    private static func pulisci(_ cartella: URL) {
        let chiavi: [URLResourceKey] = [.contentModificationDateKey]
        guard let file = try? FileManager.default.contentsOfDirectory(at: cartella, includingPropertiesForKeys: chiavi),
              file.count > massimoFile else { return }
        let ordinati = file.sorted {
            let a = (try? $0.resourceValues(forKeys: Set(chiavi)).contentModificationDate) ?? .distantPast
            let b = (try? $1.resourceValues(forKeys: Set(chiavi)).contentModificationDate) ?? .distantPast
            return a > b
        }
        for url in ordinati.dropFirst(dopoPulizia) {
            try? FileManager.default.removeItem(at: url)
        }
    }
}
