import Foundation

/// Scadenza del certificato con cui l'app è firmata (7 giorni con l'Apple ID gratuito).
/// Si legge dal profilo incorporato nell'app (`embedded.mobileprovision`). Un'installazione rifirmata può non averlo:
/// in quel caso la scadenza è «non leggibile» e non è un errore.
enum Certificato {
    struct Info: Equatable {
        enum Livello { case ok, attenzione, scaduto, ignoto }
        let testo: String
        let livello: Livello
    }

    /// Scadenza dal profilo dell'app in esecuzione, se si riesce a leggerla.
    static func scadenza() -> Date? {
        guard let percorso = Bundle.main.path(forResource: "embedded", ofType: "mobileprovision"),
              let dati = try? Data(contentsOf: URL(fileURLWithPath: percorso)) else { return nil }
        return scadenza(nelProfilo: dati)
    }

    /// Il profilo è un messaggio firmato (CMS) che contiene un plist in chiaro: si ritaglia da `<?xml` a `</plist>`.
    static func scadenza(nelProfilo dati: Data) -> Date? {
        guard let inizio = dati.range(of: Data("<?xml".utf8)),
              let fine = dati.range(of: Data("</plist>".utf8), options: [], in: inizio.lowerBound..<dati.endIndex) else { return nil }
        let xml = dati.subdata(in: inizio.lowerBound..<fine.upperBound)
        guard let plist = try? PropertyListSerialization.propertyList(from: xml, options: [], format: nil) as? [String: Any] else { return nil }
        return plist["ExpirationDate"] as? Date
    }

    /// Testo e gravità da mostrare: arancio sotto i 2 giorni, rosso se scaduto.
    static func info(scadenza: Date?, adesso: Date = Date()) -> Info {
        guard let scadenza else { return Info(testo: "scadenza non leggibile", livello: .ignoto) }
        let resto = scadenza.timeIntervalSince(adesso)
        if resto <= 0 { return Info(testo: "Scaduto", livello: .scaduto) }
        if resto < 2 * 86_400 {
            let ore = Int(resto / 3600)
            if ore < 1 { return Info(testo: "Scade tra meno di un'ora", livello: .attenzione) }
            return Info(testo: "Scade tra \(ore) \(ore == 1 ? "ora" : "ore")", livello: .attenzione)
        }
        return Info(testo: "Scade tra \(Int(resto / 86_400)) giorni", livello: .ok)
    }
}
