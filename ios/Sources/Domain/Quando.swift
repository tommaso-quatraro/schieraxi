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

    static func leggibile(_ testo: String?) -> String {
        guard let d = data(testo) else { return testo ?? "" }
        return scrittura.string(from: d)
    }

    /// Una data già pronta, scritta come la scrive il server («sab 8 nov, 18:30», ora italiana).
    static func leggibile(_ data: Date) -> String {
        scrittura.string(from: data)
    }
}
