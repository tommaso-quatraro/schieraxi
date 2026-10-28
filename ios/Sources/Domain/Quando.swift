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

    /// «sabato 31 ottobre», per i titoli dei giorni delle partite.
    static func giorno(_ data: Date) -> String { soloGiorno.string(from: data) }

    /// «18:30».
    static func ora(_ data: Date) -> String { soloOra.string(from: data) }

    static func data(_ testo: String?) -> Date? {
        guard let testo else { return nil }
        return lettura.date(from: String(testo.prefix(16)))
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
