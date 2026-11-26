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

    /// Quando è cominciato il silenzio che comprende `data` (le `da` in punto, anche `data` stessa); `nil` se non si è in silenzio.
    func inizio(di data: Date) -> Date? {
        guard inSilenzio(data) else { return nil }
        // all'indietro da un secondo dopo: se `data` è proprio l'inizio (le 23:00 in punto) vale lei
        return Self.calendario.nextDate(after: data.addingTimeInterval(1), matching: DateComponents(hour: da, minute: 0, second: 0),
                                        matchingPolicy: .nextTime, direction: .backward)
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

/// La spunta «L'ho messa» appena toccata sul telefono, per i promemoria locali (un'ora e un quarto d'ora prima): vale subito dopo il
/// tocco (spuntata, tolta, o caduta perché gli 11 sono cambiati), finché non arriva una lettura di Oggi partita dopo il tocco; da lì
/// decide il server (`serve_promemoria`, `Aggiornamento.promemoriaTace`). La scrive la Formazione dopo un tuo salvataggio, mai dopo
/// una semplice lettura. Si ricorda un tocco solo: la giornata (numero di Serie A), la spunta e l'ora.
enum ArchivioMessa {
    static let chiave = "promemoria.messa"

    /// La spunta toccata per questa giornata (vero messa, falso tolta), o nil se dall'ultima lettura di Oggi non è stata toccata.
    static func toccata(giornata: Int?, _ memoria: UserDefaults = .standard) -> Bool? {
        guard let giornata, let voce = memoria.dictionary(forKey: chiave), (voce["giornata"] as? Int) == giornata else { return nil }
        return voce["messa"] as? Bool
    }

    static func ricorda(giornata: Int, messa: Bool, _ memoria: UserDefaults = .standard, il quando: Date = Date()) {
        let voce: [String: Any] = ["giornata": giornata, "messa": messa, "il": quando.timeIntervalSince1970]
        memoria.set(voce, forKey: chiave)
    }

    /// Una lettura di Oggi partita a `data` comprende già i tocchi di prima: quelli si dimenticano, i più recenti restano.
    static func dimentica(primaDi data: Date, _ memoria: UserDefaults = .standard) {
        guard let voce = memoria.dictionary(forKey: chiave) else { return }
        if ((voce["il"] as? Double) ?? 0) < data.timeIntervalSince1970 {
            memoria.removeObject(forKey: chiave)
        }
    }
}

/// Il server manda già i promemoria a questo telefono (la web app di un iPhone con gli avvisi accesi, o ntfy per l'app
/// nativa: `promemoria_da`)? Si ricorda a ogni lettura di `GET /api/avvisi` (`StatoAvvisi.mandaGiaIlServer`): se sì, l'app non
/// programma i suoi promemoria della scadenza, perché arriva già quello del server, con lo stesso testo. Senza una lettura (mai
/// riuscita) vale «no»: i promemoria del telefono partono.
enum ArchivioAvvisiDalServer {
    static let chiave = "avvisi.dalServer"

    static func mandaGia(_ memoria: UserDefaults = .standard) -> Bool {
        memoria.bool(forKey: chiave)
    }

    static func salva(_ manda: Bool, _ memoria: UserDefaults = .standard) {
        memoria.set(manda, forKey: chiave)
    }
}

/// «Avvisi su questo dispositivo» (Impostazioni > Avvisi, come la web): un interruttore solo per i promemoria locali (un'ora e 15
/// minuti prima; l'avviso quando cambia la consigliata non parte più dal telefono, #906). Senza una scelta salvata è acceso, come
/// prima: chi aveva il permesso continua a ricevere i promemoria. Le scelte per singolo avviso del server (`promemoria_60`,
/// `promemoria_15`) non si usano più (#693).
enum ArchivioAvvisiQui {
    static let chiave = "avvisiQui"

    static func acceso(_ memoria: UserDefaults = .standard) -> Bool {
        memoria.object(forKey: chiave) as? Bool ?? true
    }

    static func salva(_ acceso: Bool, _ memoria: UserDefaults = .standard) {
        memoria.set(acceso, forKey: chiave)
    }

    /// I minuti dei promemoria da mandare: tutti e due con gli avvisi accesi, nessuno spenti.
    static func minutiAttivi(_ memoria: UserDefaults = .standard) -> Set<Int> {
        acceso(memoria) ? [60, 15] : []
    }
}
