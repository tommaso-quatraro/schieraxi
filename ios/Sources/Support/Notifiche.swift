import UserNotifications

/// Promemoria locali di iOS: non servono server né l'account a pagamento di Apple (le notifiche push, invece, sì).
/// Un'ora e un quarto d'ora prima della scadenza della formazione, e l'avviso quando cambia la formazione consigliata, solo con
/// «Avvisi su questo dispositivo» acceso (un interruttore unico come la web, #673 passo 3: le scelte per singolo avviso non si usano
/// più). Si programmano quando l'app legge la giornata, quando l'interruttore si riaccende e quando cambiano le ore tranquille;
/// spegnendolo si tolgono subito (vedi `TelefonoAvvisi`).
enum Notifiche {
    /// Un promemoria locale pronto da programmare: identificativo, quando suona, titolo e testo.
    struct Promemoria: Equatable, Sendable {
        let id: String
        let quando: Date
        let titolo: String
        let testo: String
    }

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
    /// `attivi`: i minuti dei promemoria da mandare (60 e 15 con gli avvisi accesi, nessuno spenti). `tace`: il promemoria della
    /// giornata non serve (`tacePromemoria`: la regola del server, «L'ho messa» e nessun titolare a rischio): nessuno.
    static func promemoriaConsentiti(inizio: Date, ore: OreTranquille, attivi: Set<Int> = [60, 15], tace: Bool = false,
                                     adesso: Date = Date()) -> [(id: String, minuti: Int, quando: Date)] {
        var elenco: [(id: String, minuti: Int, quando: Date)] = []
        if tace { return elenco }
        for (id, minuti) in [("fanta-60", 60), ("fanta-15", 15)] where attivi.contains(minuti) {
            let quando = inizio.addingTimeInterval(-Double(minuti) * 60)
            guard quando > adesso, !ore.inSilenzio(quando) else { continue }
            elenco.append((id: id, minuti: minuti, quando: quando))
        }
        return elenco
    }

    // SCHELETRO PER I TEST (da sostituire): il comportamento di prima.
    static func promemoriaDaProgrammare(giornata: NomeGiornata, inizio: Date, testi: [TestoPromemoria]?, lettaIl: Date?,
                                        ore: OreTranquille, attivi: Set<Int>, tace: Bool, dalServer: Bool,
                                        adesso: Date = Date()) -> [Promemoria] {
        promemoriaConsentiti(inizio: inizio, ore: ore, attivi: attivi, tace: tace, adesso: adesso).map { voce in
            Promemoria(id: voce.id, quando: voce.quando,
                       titolo: voce.minuti == 60 ? "SchieraXI · Manca un'ora" : "SchieraXI · Mancano 15 minuti",
                       testo: corpoPromemoria(giornata: giornata, modulo: nil))
        }
    }

    // SCHELETRO PER I TEST (da sostituire): il comportamento di prima.
    static func promemoriaCertificato(scadenza: Date, ore: OreTranquille, adesso: Date = Date()) -> [Promemoria] {
        [("fanta-cert-24", 24), ("fanta-cert-6", 6)].compactMap { id, h in
            let quando = scadenza.addingTimeInterval(-Double(h) * 3600)
            guard quando > adesso else { return nil }
            return Promemoria(id: id, quando: quando, titolo: "SchieraXI · Da rinnovare",
                              testo: "Tra circa \(h) ore l'app smette di aprirsi. Rinnovala dall'app con cui l'hai installata.")
        }
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

    /// Il promemoria della scadenza tace? Una spunta toccata sul telefono dopo l'ultima lettura di Oggi vale subito (`toccata`: vero
    /// messa, falso tolta); altrimenti decide il server (`serve`, il campo `serve_promemoria` di Oggi): tace solo se dice che non
    /// serve. Senza il campo (server di prima, lettura non riuscita) il promemoria parte: mai tacere per un dato incerto.
    static func tacePromemoria(serve: Bool?, toccata: Bool?) -> Bool {
        if let toccata { return toccata }
        return serve == false
    }

    static func programma(giornata: NomeGiornata, inizio: Date, modulo: String?, tace: Bool = false) async {
        let centro = UNUserNotificationCenter.current()
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return }
        centro.removePendingNotificationRequests(withIdentifiers: ["fanta-60", "fanta-15"])
        for (id, minuti, quando) in promemoriaConsentiti(inizio: inizio, ore: ArchivioOreTranquille.leggi(), attivi: ArchivioAvvisiQui.minutiAttivi(),
                                                         tace: tace) {
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
    /// Ricorda sul telefono gli avvisi come li ha il server (`GET` o `PUT /api/avvisi`): le ore tranquille e se il server manda già
    /// gli avvisi a questo telefono (`ArchivioAvvisiDalServer`). Li usa ogni programmazione successiva, anche in background.
    var ricorda: @MainActor @Sendable (StatoAvvisi) -> Void
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
        ricorda: { stato in
            ArchivioOreTranquille.salva(stato.impostazioni.oreTranquille)
            ArchivioAvvisiDalServer.salva(stato.mandaGiaIlServer)
        },
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
