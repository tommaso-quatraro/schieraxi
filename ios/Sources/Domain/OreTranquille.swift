import Foundation

/// Le «ore tranquille» degli avvisi: niente avvisi dalle `da` alle `a` (ora italiana), anche a cavallo della mezzanotte.
/// Stessa regola del server (`notifiche.in_silenzio`): con `da == a` o spente non c'è silenzio.
struct OreTranquille: Equatable, Sendable {
    var attive: Bool
    var da: Int
    var a: Int

    static let predefinite = OreTranquille(attive: false, da: 23, a: 7)

    /// Ore valide: 0...23 (un valore fuori scala si riporta nel giro).
    init(attive: Bool, da: Int, a: Int) {
        self.attive = attive
        self.da = Self.ora(da)
        self.a = Self.ora(a)
    }

    private static func ora(_ valore: Int) -> Int { ((valore % 24) + 24) % 24 }

    private static let calendario: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Europe/Rome") ?? .current
        return c
    }()

    func inSilenzio(_ data: Date) -> Bool {
        guard attive, da != a else { return false }
        let h = Self.calendario.component(.hour, from: data)
        return da < a ? (h >= da && h < a) : (h >= da || h < a)
    }

    /// Quando finisce il silenzio che comprende `data` (le `a` in punto); `nil` se non si è in silenzio.
    func fine(da data: Date) -> Date? {
        guard inSilenzio(data) else { return nil }
        return Self.calendario.nextDate(after: data, matching: DateComponents(hour: a, minute: 0, second: 0), matchingPolicy: .nextTime)
    }

    /// «dalle 23 alle 7» per i testi e per VoiceOver.
    var descrizione: String { attive ? "dalle \(da) alle \(a)" : "spente" }
}

/// Dove l'app ricorda le ore tranquille lette dal server (per i promemoria locali, anche quando l'app è in background).
enum ArchivioOreTranquille {
    private static let chiaveAttive = "silenzio"
    private static let chiaveDa = "silenzio_da"
    private static let chiaveA = "silenzio_a"

    static func leggi(_ memoria: UserDefaults = .standard) -> OreTranquille {
        let p = OreTranquille.predefinite
        return OreTranquille(attive: memoria.bool(forKey: chiaveAttive),
                             da: memoria.object(forKey: chiaveDa) as? Int ?? p.da,
                             a: memoria.object(forKey: chiaveA) as? Int ?? p.a)
    }

    static func salva(_ ore: OreTranquille, _ memoria: UserDefaults = .standard) {
        memoria.set(ore.attive, forKey: chiaveAttive)
        memoria.set(ore.da, forKey: chiaveDa)
        memoria.set(ore.a, forKey: chiaveA)
    }
}
