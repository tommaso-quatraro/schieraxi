import UserNotifications

/// Il delegato delle notifiche di iOS: cosa fare di un avviso dell'app che arriva con l'app aperta e del tocco su un avviso. Senza
/// delegato iOS non mostra un avviso che arriva con l'app aperta (il promemoria di un quarto d'ora prima, con la Formazione sullo
/// schermo, non si vedeva) e il tocco apre l'app dov'era rimasta. Con questo l'app fa come la web (`fanta/web/sw.js`): l'avviso si
/// vede sempre, con banner e suono (`Notifiche.conAppAperta`), e il tocco su un promemoria della scadenza apre la Formazione con lo
/// stesso percorso di `schieraxi://formazione` (`Notifiche.destinazione`, `AvvisiToccati`, `Navigazione.vai`).
/// iOS chiama il delegato fuori dal thread principale: qui si legge solo l'identificativo, e il tocco passa all'attore principale.
final class DelegatoAvvisi: NSObject, UNUserNotificationCenterDelegate, Sendable {
    static let condiviso = DelegatoAvvisi()

    /// Va messo prima che l'app finisca di partire (`SchieraxiApp.init`): così arriva anche il tocco che ha aperto l'app.
    /// iOS tiene il delegato con un riferimento debole: lo tiene in vita `condiviso`.
    static func installa() {
        UNUserNotificationCenter.current().delegate = condiviso
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler(Notifiche.conAppAperta)
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        if response.actionIdentifier == UNNotificationDefaultActionIdentifier {
            let identificativo = response.notification.request.identifier
            Task { @MainActor in AvvisiToccati.condiviso.tocca(identificativo: identificativo) }
        }
        completionHandler()
    }
}
