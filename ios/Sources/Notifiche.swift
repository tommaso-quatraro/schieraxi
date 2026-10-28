import UserNotifications

/// Promemoria locali di iOS: non servono server né l'account a pagamento di Apple (le notifiche push, invece, sì).
/// Si programmano ogni volta che l'app legge la giornata: un'ora e un quarto d'ora prima del calcio d'inizio.
enum Notifiche {
    static func stato() async -> UNAuthorizationStatus {
        await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    }

    static func chiediPermesso() async -> Bool {
        (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    static func programma(giornata: Int, inizio: Date, modulo: String?) async {
        let centro = UNUserNotificationCenter.current()
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return }
        centro.removePendingNotificationRequests(withIdentifiers: ["fanta-60", "fanta-15"])
        for (id, minuti) in [("fanta-60", 60), ("fanta-15", 15)] {
            let quando = inizio.addingTimeInterval(-Double(minuti) * 60)
            guard quando > Date() else { continue }
            let contenuto = UNMutableNotificationContent()
            contenuto.title = minuti == 60 ? "Formazione: manca un'ora" : "Formazione: mancano 15 minuti"
            contenuto.body = "Giornata \(giornata)" + (modulo.map { ", modulo consigliato \($0)" } ?? "") + ". Apri l'app per controllare."
            contenuto.sound = .default
            let componenti = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: quando)
            let trigger = UNCalendarNotificationTrigger(dateMatching: componenti, repeats: false)
            try? await centro.add(UNNotificationRequest(identifier: id, content: contenuto, trigger: trigger))
        }
    }
}
