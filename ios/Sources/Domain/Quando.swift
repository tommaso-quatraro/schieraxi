import Foundation

/// Date del server: "2026-10-27 18:30", ora italiana.
enum Quando {
    private static let italia = Locale(identifier: "it_IT")

    private static let lettura: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f
    }()

    private static let scrittura: DateFormatter = {
        let f = DateFormatter()
        f.locale = italia
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "EEE d MMM, HH:mm"
        return f
    }()

    private static let soloGiorno: DateFormatter = {
        let f = DateFormatter()
        f.locale = italia
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "EEEE d MMMM"
        return f
    }()

    private static let soloOra: DateFormatter = {
        let f = DateFormatter()
        f.locale = italia
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "HH:mm"
        return f
    }()

    private static let calendario: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Europe/Rome") ?? .current
        return c
    }()

    /// «31 ott»: per le date oltre la settimana (la web scrive `fData`).
    private static let giornoMese: DateFormatter = {
        let f = DateFormatter()
        f.locale = italia
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "d MMM"
        return f
    }()

    /// Come `tempo.giorno_0…6` della web, dalla domenica (`Calendar.weekday` parte da 1 = domenica).
    private static let sigleGiorni = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"]

    private static func formato(_ f: String, locale: Locale) -> DateFormatter {
        let d = DateFormatter()
        d.locale = locale
        d.timeZone = TimeZone(identifier: "Europe/Rome")
        d.dateFormat = f
        return d
    }

    private static let versioneConOra = formato("yyyy-MM-dd'T'HH:mm:ss", locale: Locale(identifier: "en_US_POSIX"))
    private static let versioneSoloData = formato("yyyy-MM-dd", locale: Locale(identifier: "en_US_POSIX"))
    private static let versioneConOraScritta = formato("d MMM yyyy, HH:mm:ss", locale: italia)
    private static let versioneSoloDataScritta = formato("d MMM yyyy", locale: italia)

    /// La data di una versione (novità): «2026-10-30T14:05:09» (ora italiana) diventa «30 ott 2026, 14:05:09»; «2026-10-30» solo
    /// «30 ott 2026». Accetta anche uno spazio al posto della «T». Un testo che non si capisce resta com'è.
    static func dataVersione(_ testo: String?) -> String {
        guard let testo else { return "" }
        let t = testo.trimmingCharacters(in: .whitespaces)
        if t.count >= 19 {
            let ora = String(t.prefix(19)).replacingOccurrences(of: " ", with: "T")
            if let d = versioneConOra.date(from: ora) { return versioneConOraScritta.string(from: d) }
        }
        if t.count == 10, let d = versioneSoloData.date(from: t) { return versioneSoloDataScritta.string(from: d) }
        return t
    }

    /// «sabato 31 ottobre», per i titoli dei giorni delle partite.
    static func giorno(_ data: Date) -> String { soloGiorno.string(from: data) }

    /// «18:30».
    static func ora(_ data: Date) -> String { soloOra.string(from: data) }

    /// «2026-10-27 18:30» e anche con la «T» di ISO 8601 («2026-10-26T23:55:13», per esempio `ultimo_aggiornamento`):
    /// contano i primi 16 caratteri (secondi e resto si ignorano), sempre ora italiana.
    static func data(_ testo: String?) -> Date? {
        guard let testo else { return nil }
        return lettura.date(from: String(testo.prefix(16)).replacingOccurrences(of: "T", with: " "))
    }

    /// La data di una partita o di una scadenza scritta come la web (`quando` di `app.js`), ora italiana:
    /// «oggi 20:45», «ieri 15:00», «domani 18:30»; entro la settimana «sab 31 20:45»; oltre, con il mese «sab 8 nov 18:30».
    /// Un testo che non si capisce resta com'è (nil: vuoto). `adesso` serve solo ai test.
    /// L'app è solo in italiano: niente inglese («today», «Sat»).
    static func leggibile(_ testo: String?, adesso: Date = Date()) -> String {
        guard let d = data(testo) else { return testo ?? "" }
        return relativa(d, adesso: adesso)
    }

    /// Come `leggibile(_:adesso:)`, per una data già pronta.
    static func relativa(_ d: Date, adesso: Date = Date()) -> String {
        let c = calendario
        let giorni = c.dateComponents([.day], from: c.startOfDay(for: adesso), to: c.startOfDay(for: d)).day ?? 0
        let ora = soloOra.string(from: d)
        switch giorni {
        case 0: return "oggi \(ora)"
        case 1: return "domani \(ora)"
        case -1: return "ieri \(ora)"
        default:
            let nome = sigleGiorni[min(max(c.component(.weekday, from: d) - 1, 0), 6)]
            let giorno = abs(giorni) > 6 ? giornoMese.string(from: d) : String(c.component(.day, from: d))
            return "\(nome) \(giorno) \(ora)"
        }
    }

    /// Un momento già pronto (non la data di una partita), con giorno e mese: «sab 8 nov, 18:30», ora italiana.
    static func leggibile(_ data: Date) -> String {
        scrittura.string(from: data)
    }
}

// MARK: - Conto alla rovescia

extension Quando {
    /// Il conto alla rovescia alla scadenza come la web (`testoConto` di `app.js`): i minuti che mancano, arrotondati come
    /// `Math.round`; «2 giorni 3 h» (un giorno: «1 giorno 3 h»), «6 h 44 min», «12 min». Niente secondi.
    /// nil se, arrotondato, non manca più niente (meno di mezzo minuto, o scadenza passata): lì la web scrive «Chiusa».
    /// Lo usano Oggi, la barra sotto le schede e i widget.
    static func contoAllaRovescia(fino scadenza: Date, adesso: Date = Date()) -> String? {
        guard let p = partiDelConto(fino: scadenza, adesso: adesso) else { return nil }
        if p.giorni >= 1 { return "\(Formato.plurale(p.giorni, "giorno", "giorni")) \(p.ore) h" }
        if p.ore >= 1 { return "\(p.ore) h \(p.minuti) min" }
        return "\(p.minuti) min"
    }

    /// Lo stesso conto a parole intere, per VoiceOver: «2 giorni e 3 ore», «6 ore e 44 minuti», «1 minuto».
    static func contoAllaRovesciaParlato(fino scadenza: Date, adesso: Date = Date()) -> String? {
        guard let p = partiDelConto(fino: scadenza, adesso: adesso) else { return nil }
        var pezzi: [String] = []
        if p.giorni >= 1 { pezzi.append(Formato.plurale(p.giorni, "giorno", "giorni")) }
        if p.ore >= 1 { pezzi.append(Formato.plurale(p.ore, "ora", "ore")) }
        if p.giorni == 0, p.minuti >= 1 { pezzi.append(Formato.plurale(p.minuti, "minuto", "minuti")) }
        return pezzi.joined(separator: " e ")
    }

    /// Gli istanti, dopo `adesso` e prima di `entro` (e della scadenza, che ha già la sua voce), in cui cambia il testo del conto
    /// alla rovescia: ogni minuto sotto le 24 ore, ogni ora sopra. In più la mezzanotte, dove «domani» diventa «oggi».
    /// Servono al widget: un testo come «6 h 44 min» non conta da solo, ogni cambio è una voce della timeline (non una ricarica).
    /// In ordine, al massimo `massimo`.
    static func istantiDelConto(fino scadenza: Date, adesso: Date, entro: Date, massimo: Int = 90) -> [Date] {
        let fine = min(entro, scadenza)
        let mancano = scadenza.timeIntervalSince(adesso) / 60
        guard fine > adesso, mancano.isFinite, mancano < 1e9 else { return [] }
        var istanti: [Date] = []
        var ultimo = contoAllaRovescia(fino: scadenza, adesso: adesso)
        // gli istanti a minuti interi dalla scadenza, dal primo dopo «adesso»: lì il testo è esatto
        var k = Int(mancano.rounded(.up)) - 1
        while k >= 1 {
            let istante = scadenza.addingTimeInterval(-Double(k) * 60)
            if istante >= fine { break }
            let testo = contoAllaRovescia(fino: scadenza, adesso: istante)
            if testo != ultimo {
                istanti.append(istante)
                ultimo = testo
            }
            k -= 1
        }
        if let notte = calendario.date(byAdding: .day, value: 1, to: calendario.startOfDay(for: adesso)),
           notte > adesso, notte < fine, !istanti.contains(notte) {
            istanti.append(notte)
            istanti.sort()
        }
        return Array(istanti.prefix(max(massimo, 0)))
    }

    /// Giorni, ore e minuti che mancano, dai minuti arrotondati (come la web); nil se non manca niente.
    private static func partiDelConto(fino scadenza: Date, adesso: Date) -> (giorni: Int, ore: Int, minuti: Int)? {
        let minuti = Formato.intero(scadenza.timeIntervalSince(adesso) / 60)
        guard minuti > 0 else { return nil }
        return (minuti / 1440, (minuti % 1440) / 60, minuti % 60)
    }
}
