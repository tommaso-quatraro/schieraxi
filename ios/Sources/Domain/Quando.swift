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

    // TODO(#189): da scrivere dopo i test.
    static func contoAllaRovescia(fino scadenza: Date, adesso: Date = Date()) -> String? { nil }
    static func contoAllaRovesciaParlato(fino scadenza: Date, adesso: Date = Date()) -> String? { nil }
    static func istantiDelConto(fino scadenza: Date, adesso: Date, entro: Date, massimo: Int = 90) -> [Date] { [] }
}
