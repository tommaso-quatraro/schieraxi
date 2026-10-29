import UserNotifications

/// Promemoria locali di iOS: non servono server né l'account a pagamento di Apple (le notifiche push, invece, sì).
/// Si programmano ogni volta che l'app legge la giornata: un'ora e un quarto d'ora prima del calcio d'inizio.
enum Notifiche {
    static func stato() async -> UNAuthorizationStatus {
        await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    }

    static func chiediPermesso() async -> Bool {
        if Demo.attivo { return false }   // demo: nessuna richiesta di permessi
        return (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    /// Notifica locale subito (usata dall'aggiornamento in background quando la formazione consigliata cambia).
    static func avviso(id: String, titolo: String, corpo: String) async {
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return }
        let contenuto = UNMutableNotificationContent()
        contenuto.title = titolo
        contenuto.body = corpo
        contenuto.sound = .default
        try? await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: contenuto, trigger: nil))
    }

    /// Due promemoria locali prima che scada il certificato: 24 ore e 6 ore prima. Si richiamano a ogni apertura e a ogni
    /// aggiornamento in background: con lo stesso identificativo sostituiscono quelli vecchi (dopo un rinnovo la data cambia).
    static func programmaScadenza(_ scadenza: Date) async {
        let centro = UNUserNotificationCenter.current()
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return }
        centro.removePendingNotificationRequests(withIdentifiers: ["fanta-cert-24", "fanta-cert-6"])
        for (id, ore) in [("fanta-cert-24", 24), ("fanta-cert-6", 6)] {
            let quando = scadenza.addingTimeInterval(-Double(ore) * 3600)
            guard quando > Date() else { continue }
            let contenuto = UNMutableNotificationContent()
            contenuto.title = "SchieraXI · L'app sta per scadere"
            contenuto.body = "Il certificato scade tra circa \(ore) ore. Rinnovala con SideStore."
            contenuto.sound = .default
            let componenti = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: quando)
            let trigger = UNCalendarNotificationTrigger(dateMatching: componenti, repeats: false)
            try? await centro.add(UNNotificationRequest(identifier: id, content: contenuto, trigger: trigger))
        }
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
            contenuto.title = minuti == 60 ? "SchieraXI · Manca un'ora" : "SchieraXI · Mancano 15 minuti"
            contenuto.body = "Giornata \(giornata)" + (modulo.map { ", modulo consigliato \($0)" } ?? "") + ". Mister, dai un'occhiata alla formazione."
            contenuto.sound = .default
            let componenti = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: quando)
            let trigger = UNCalendarNotificationTrigger(dateMatching: componenti, repeats: false)
            try? await centro.add(UNNotificationRequest(identifier: id, content: contenuto, trigger: trigger))
        }
    }
}
