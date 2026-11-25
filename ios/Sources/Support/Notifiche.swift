import UserNotifications

/// Promemoria locali di iOS: non servono server né l'account a pagamento di Apple (le notifiche push, invece, sì).
/// Un'ora e un quarto d'ora prima della scadenza della formazione, solo con «Avvisi su questo dispositivo» acceso (un interruttore
/// unico come la web, #673 passo 3). Titolo e testo li scrive il server (`testi_promemoria` di Oggi, #906): l'app non compone frasi
/// sue. Se il server manda già i suoi avvisi proprio a questa app (ntfy per l'app nativa) l'app non programma i suoi; con le sole
/// notifiche della web sì (potrebbero essere sul computer). Gli avvisi quando cambia la formazione li manda solo il server (#676, #906).
/// Si programmano quando l'app legge la giornata, quando l'interruttore si riaccende e quando cambiano le ore tranquille;
/// spegnendolo si tolgono subito (vedi `TelefonoAvvisi`).
enum Notifiche {
    /// Un promemoria locale pronto da programmare: identificativo, quando suona, titolo e testo.
    struct Promemoria: Equatable, Sendable {
        let id: String
        let quando: Date
        let titolo: String
        let testo: String
    }

    /// I promemoria della scadenza, con gli avvisi che l'app non manda più («Cambio di modulo» ed «Escono le probabili», tolti con
    /// #906 come sul server con #676): togliendo i promemoria si toglie anche un avviso vecchio rimasto in attesa.
    static let identificativiPromemoria = ["fanta-60", "fanta-15", "fanta-cambio", "fanta-probabili"]
    /// I due promemoria della scadenza del certificato.
    static let identificativiCertificato = ["fanta-cert-24", "fanta-cert-6"]

    static func stato() async -> UNAuthorizationStatus {
        await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    }

    static func chiediPermesso() async -> Bool {
        if Demo.attivo { return false }   // demo: nessuna richiesta di permessi
        return (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    /// Notifica locale subito (la versione nuova dell'app, `NuovaVersione`), solo con «Avvisi su questo dispositivo» acceso. Nelle
    /// ore tranquille non suona: arriva alla fine del silenzio. Dice se l'avviso è partito.
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

    /// Il testo del server del promemoria di un'ora prima può avere numeri calcolati alla lettura di Oggi («Consigliato: 4-3-3, 71,2
    /// punti attesi», chi è da controllare): si usa solo se la giornata è stata letta al massimo due ore prima che il promemoria
    /// suoni. iOS non sveglia l'app a un'ora precisa, quindi rileggere Oggi vicino alla finestra non si può promettere.
    static let freschezzaTesti: TimeInterval = 2 * 3600

    /// I promemoria della scadenza da programmare (#906). Nessuno se il server manda già i suoi avvisi a questa app
    /// (`dalServer`: ntfy per l'app nativa, `StatoAvvisi.mandaGiaIlServer`), se il promemoria non serve (`tace`) o con gli avvisi spenti (`attivi`); quelli
    /// nelle ore tranquille o già passati si saltano (`promemoriaConsentiti`). Titolo e testo sono quelli del server (`testi`, la
    /// voce con gli stessi minuti), così come sono; quello di un'ora prima solo se letto da poco (`freschezzaTesti`; `lettaIl`:
    /// quando è stata letta la giornata, nil se non si sa). Senza il testo del server (server di prima, lettura vecchia, spunta appena
    /// tolta con la lista vuota) il promemoria minimo del catalogo, senza titolo: la giornata e l'ora della scadenza
    /// (`oggi.prossima_chiude`, la frase della web), mai una frase composta qui.
    static func promemoriaDaProgrammare(giornata: NomeGiornata, inizio: Date, testi: [TestoPromemoria]?, lettaIl: Date?,
                                        ore: OreTranquille, attivi: Set<Int>, tace: Bool, dalServer: Bool,
                                        adesso: Date = Date()) -> [Promemoria] {
        if dalServer { return [] }
        return promemoriaConsentiti(inizio: inizio, ore: ore, attivi: attivi, tace: tace, adesso: adesso).map { voce -> Promemoria in
            let fresco = voce.minuti != 60 || lettaIl.map { voce.quando.timeIntervalSince($0) <= freschezzaTesti } == true
            if fresco, let delServer = testi?.first(where: { $0.minuti == voce.minuti }) {
                return Promemoria(id: voce.id, quando: voce.quando, titolo: delServer.titolo, testo: delServer.testo)
            }
            let scadenza = Quando.relativa(inizio, adesso: voce.quando)
            return Promemoria(id: voce.id, quando: voce.quando, titolo: "",
                              testo: Catalogo.Oggi.prossimaChiude(g: giornata.intero, quando: scadenza))
        }
    }

    /// I due promemoria del certificato, 24 e 6 ore prima della scadenza, mai nelle ore tranquille (#906). Uno che ci cade suona un
    /// minuto prima che comincino (prima si rinnova, meglio è); se quel momento è già passato, quando finiscono, purché manchi ancora
    /// almeno un'ora alla scadenza; altrimenti non suona. Il testo dice le ore che mancano davvero.
    static func promemoriaCertificato(scadenza: Date, ore: OreTranquille, adesso: Date = Date()) -> [Promemoria] {
        var elenco: [Promemoria] = []
        for (id, orePrima) in zip(identificativiCertificato, [24.0, 6.0]) {
            let previsto = scadenza.addingTimeInterval(-orePrima * 3600)
            guard let quando = momentoCertificato(previsto, scadenza: scadenza, ore: ore, adesso: adesso),
                  !elenco.contains(where: { $0.quando == quando }) else { continue }
            elenco.append(Promemoria(id: id, quando: quando, titolo: "SchieraXI · Da rinnovare",
                                     testo: testoCertificato(ore: scadenza.timeIntervalSince(quando) / 3600)))
        }
        return elenco
    }

    /// Quando suona un promemoria del certificato previsto a `previsto` (vedi `promemoriaCertificato`); nil se non suona.
    private static func momentoCertificato(_ previsto: Date, scadenza: Date, ore: OreTranquille, adesso: Date) -> Date? {
        guard previsto > adesso else { return nil }
        guard let inizio = ore.inizio(di: previsto) else { return previsto }
        let primaDelSilenzio = inizio.addingTimeInterval(-60)
        if primaDelSilenzio > adesso { return primaDelSilenzio }
        guard let fine = ore.fine(da: previsto), scadenza.timeIntervalSince(fine) >= 3600 else { return nil }
        return fine
    }

    /// «Tra circa 6 ore l'app smette di aprirsi. …», con le ore che mancano arrotondate («circa un'ora» per una).
    static func testoCertificato(ore: Double) -> String {
        let n = max(1, Int(ore.rounded()))
        let fra = n == 1 ? "Tra circa un'ora" : "Tra circa \(n) ore"
        return "\(fra) l'app smette di aprirsi. Rinnovala dall'app con cui l'hai installata."
    }

    /// I due promemoria del certificato (`promemoriaCertificato`), con le ore tranquille ricordate sul telefono. Si richiamano a ogni
    /// apertura, a ogni aggiornamento in background e quando cambiano le ore tranquille: con lo stesso identificativo sostituiscono
    /// quelli vecchi (dopo un rinnovo la data cambia).
    static func programmaScadenza(_ scadenza: Date) async {
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return }
        await sostituisci(identificativiCertificato, con: promemoriaCertificato(scadenza: scadenza, ore: ArchivioOreTranquille.leggi()))
    }

    /// Toglie subito i promemoria e gli avvisi già programmati (l'utente ha spento «Avvisi su questo dispositivo»). Restano i due
    /// promemoria della scadenza del certificato: senza rinnovo l'app smette di aprirsi.
    static func togliPromemoria() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: identificativiPromemoria)
    }

    /// Il promemoria della scadenza tace? Una spunta toccata sul telefono dopo l'ultima lettura di Oggi vale subito (`toccata`: vero
    /// messa, falso tolta); altrimenti decide il server (`serve`: `serve_promemoria` di Oggi, o la lista dei testi vuota): tace solo
    /// se dice che non serve. Senza il campo (server di prima, lettura non riuscita) il promemoria parte: mai tacere per un dato incerto.
    static func tacePromemoria(serve: Bool?, toccata: Bool?) -> Bool {
        if let toccata { return toccata }
        return serve == false
    }

    /// Programma i promemoria della scadenza (`promemoriaDaProgrammare`) al posto di quelli di prima: un elenco vuoto li toglie.
    static func programma(_ elenco: [Promemoria]) async {
        let stato = await stato()
        guard stato == .authorized || stato == .provisional else { return }
        await sostituisci(identificativiPromemoria, con: elenco)
    }

    /// Toglie i promemoria in attesa con gli identificativi `vecchi` e programma quelli dell'elenco, al minuto del loro `quando`.
    private static func sostituisci(_ vecchi: [String], con elenco: [Promemoria]) async {
        let centro = UNUserNotificationCenter.current()
        centro.removePendingNotificationRequests(withIdentifiers: vecchi)
        for promemoria in elenco {
            let contenuto = UNMutableNotificationContent()
            contenuto.title = promemoria.titolo
            contenuto.body = promemoria.testo
            contenuto.sound = .default
            let componenti = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: promemoria.quando)
            let trigger = UNCalendarNotificationTrigger(dateMatching: componenti, repeats: false)
            try? await centro.add(UNNotificationRequest(identifier: promemoria.id, content: contenuto, trigger: trigger))
        }
    }
}

/// Cosa fa «Avvisi su questo dispositivo» al telefono: il permesso di iOS, gli avvisi del server ricordati per i promemoria, i
/// promemoria tolti o rimessi in programma. I test passano una versione che annota le chiamate: così si vede che l'interruttore arriva
/// davvero ai promemoria.
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
        ricorda: { stato in Aggiornamento.ricordaAvvisi(stato) },
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
