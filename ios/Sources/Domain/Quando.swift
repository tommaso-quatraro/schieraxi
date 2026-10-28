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
