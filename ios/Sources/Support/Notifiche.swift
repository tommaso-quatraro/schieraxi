import UserNotifications

/// Promemoria locali di iOS: non servono server né l'account a pagamento di Apple (le notifiche push, invece, sì).
/// Un'ora e un quarto d'ora prima della scadenza della formazione, e l'avviso quando cambia la formazione consigliata, solo con
/// «Avvisi su questo dispositivo» acceso (un interruttore unico come la web, #673 passo 3: le scelte per singolo avviso non si usano
/// più). Si programmano quando l'app legge la giornata, quando l'interruttore si riaccende e quando cambiano le ore tranquille;
/// spegnendolo si tolgono subito (vedi `TelefonoAvvisi`).
enum Notifiche {
    static func stato() async -> UNAuthorizationStatus {
        await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    }

    static func chiediPermesso() async -> Bool {
        if Demo.attivo { return false }   // demo: nessuna richiesta di permessi
        return (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    /// Notifica locale subito (usata dall'aggiornamento in background quando la formazione consigliata cambia), solo con «Avvisi su
    /// questo dispositivo» acceso. Nelle ore tranquille non suona: arriva alla fine del silenzio. Dice se l'avviso è partito.
    @discardableResult
    static func avviso(id: String, titolo: String, corpo: String, ore: OreTranquille = ArchivioOreTranquille.leggi(), adesso: Date = Date()) async -> Bool {
        guard ArchivioAvvisiQui.acceso() else { return false }
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return false }
        let contenuto = UNMutableNotificationContent()
        contenuto.title = titolo
        contenuto.body = corpo
        contenuto.sound = .default
        var trigger: UNNotificationTrigger?
        if let fine = ore.fine(da: adesso) {
            let componenti = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: fine)
            trigger = UNCalendarNotificationTrigger(dateMatching: componenti, repeats: false)
        }
        do {
            try await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: contenuto, trigger: trigger))
            return true
        } catch {
            return false
        }
    }

    /// I promemoria che cadono nelle ore tranquille si saltano (come fa il server): sono utili solo a quell'ora.
    /// `attivi`: i minuti dei promemoria da mandare (60 e 15 con gli avvisi accesi, nessuno spenti). `messa`: la formazione della
    /// giornata è spuntata «L'ho messa»: nessun promemoria, come il server (`imp.avvisi_qui_aiuto`).
    static func promemoriaConsentiti(inizio: Date, ore: OreTranquille, attivi: Set<Int> = [60, 15], messa: Bool = false,
                                     adesso: Date = Date()) -> [(id: String, minuti: Int, quando: Date)] {
        var elenco: [(id: String, minuti: Int, quando: Date)] = []
        if messa { return elenco }
        for (id, minuti) in [("fanta-60", 60), ("fanta-15", 15)] where attivi.contains(minuti) {
            let quando = inizio.addingTimeInterval(-Double(minuti) * 60)
            guard quando > adesso, !ore.inSilenzio(quando) else { continue }
            elenco.append((id: id, minuti: minuti, quando: quando))
        }
        return elenco
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
            contenuto.title = "SchieraXI · Da rinnovare"
            contenuto.body = "Tra circa \(ore) ore l'app smette di aprirsi. Rinnovala dall'app con cui l'hai installata."
            contenuto.sound = .default
            let componenti = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: quando)
            let trigger = UNCalendarNotificationTrigger(dateMatching: componenti, repeats: false)
            try? await centro.add(UNNotificationRequest(identifier: id, content: contenuto, trigger: trigger))
        }
    }

    /// Toglie subito i promemoria e gli avvisi già programmati (l'utente ha spento «Avvisi su questo dispositivo»). Restano i due
    /// promemoria della scadenza del certificato: senza rinnovo l'app smette di aprirsi.
    static func togliPromemoria() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(
            withIdentifiers: ["fanta-60", "fanta-15", "fanta-cambio", "fanta-probabili"])
    }

    /// Il testo dei promemoria: la giornata con i due numeri in testa, come gli avvisi del server (#299).
    static func corpoPromemoria(giornata: NomeGiornata, modulo: String?) -> String {
        "\(giornata.intero): " + (modulo.map { "modulo consigliato \($0). Mister, dai un'occhiata alla formazione." }
                                   ?? "mister, dai un'occhiata alla formazione.")
    }

    static func programma(giornata: NomeGiornata, inizio: Date, modulo: String?, messa: Bool = false) async {
        let centro = UNUserNotificationCenter.current()
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return }
        centro.removePendingNotificationRequests(withIdentifiers: ["fanta-60", "fanta-15"])
        for (id, minuti, quando) in promemoriaConsentiti(inizio: inizio, ore: ArchivioOreTranquille.leggi(), attivi: ArchivioAvvisiQui.minutiAttivi(),
                                                         messa: messa) {
            let contenuto = UNMutableNotificationContent()
            contenuto.title = minuti == 60 ? "SchieraXI · Manca un'ora" : "SchieraXI · Mancano 15 minuti"
            contenuto.body = corpoPromemoria(giornata: giornata, modulo: modulo)
            contenuto.sound = .default
            let componenti = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: quando)
            let trigger = UNCalendarNotificationTrigger(dateMatching: componenti, repeats: false)
            try? await centro.add(UNNotificationRequest(identifier: id, content: contenuto, trigger: trigger))
        }
    }
}

/// Cosa fa «Avvisi su questo dispositivo» al telefono: il permesso di iOS, le ore tranquille ricordate per i promemoria, i promemoria
/// tolti o rimessi in programma. I test passano una versione che annota le chiamate: così si vede che l'interruttore arriva davvero
/// ai promemoria.
struct TelefonoAvvisi: Sendable {
    /// iOS permette le notifiche dell'app?
    var permesso: @MainActor @Sendable () async -> Bool
    /// Chiede il permesso a iOS (la prima volta compare la domanda di sistema); dice se c'è.
    var chiediPermesso: @MainActor @Sendable () async -> Bool
    /// Ricorda sul telefono le ore tranquille lette dal server: le usa ogni programmazione successiva, anche in background.
    var ricordaOre: @MainActor @Sendable (OreTranquille) -> Void
    /// Toglie subito i promemoria e gli avvisi già programmati.
    var togliTutti: @MainActor @Sendable () -> Void
    /// Rimette in programma i promemoria con l'ultima giornata salvata (e quelli del certificato).
    var riprogramma: @MainActor @Sendable () async -> Void

    static let veri = TelefonoAvvisi(
        permesso: {
            if Demo.attivo { return true }   // demo: l'interruttore acceso, senza chiedere niente
            let stato = await Notifiche.stato()
            return stato == .authorized || stato == .provisional || stato == .ephemeral
        },
        chiediPermesso: { await Notifiche.chiediPermesso() },
        ricordaOre: { ore in ArchivioOreTranquille.salva(ore) },
        togliTutti: {
            if !Ambiente.ospiteDeiTest { Notifiche.togliPromemoria() }
        },
        riprogramma: {
            if !Ambiente.ospiteDeiTest {
                await Aggiornamento.riprogrammaPromemoria()
                await Aggiornamento.riprogrammaScadenza()
            }
        })
}
