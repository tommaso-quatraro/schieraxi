import Foundation

/// Impostazioni > Avvisi, come la web (#673 passo 3, #693): «Avvisi su questo dispositivo» e «Ore tranquille»; in Gestione, senza
/// account, «Avvisi anche per l'app nativa». Quali avvisi arrivano lo decide il server; qui l'interruttore unico accende o spegne il
/// permesso di iOS e i promemoria locali (un'ora e un quarto d'ora prima, con i testi del server, #906). Le scelte per
/// singolo avviso restano sul server come sono e non si mostrano. Si salva solo ciò che si cambia (`PUT /api/avvisi` con un campo).
@MainActor
final class AvvisiDispositivoViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<StatoAvvisi>
    /// «Avvisi su questo dispositivo»: acceso solo con la scelta accesa e il permesso di iOS.
    @Published private(set) var qui = false
    /// Le ore tranquille come le ha il server (lette o appena salvate).
    @Published private(set) var oreTranquille = OreTranquille.predefinite
    /// «Avvisi anche per l'app nativa» (ntfy); nil se il server non lo manda.
    @Published private(set) var appNativa: Bool?
    /// Il server ha spento le ore tranquille (inizio e fine alla stessa ora): si dice finché non si salva di nuovo.
    @Published private(set) var oreTranquilleSpente = false
    /// I promemoria arrivano già dalla web app, con gli avvisi accesi su un dispositivo Apple (`promemoria_da` «web»): qui non si
    /// programmano, e la riga sotto «Avvisi su questo dispositivo» lo dice (`aiutoQui`).
    @Published private(set) var promemoriaDaWeb = false
    /// Cosa è successo all'ultimo tocco sull'interruttore del dispositivo (permesso negato, avvisi spenti).
    @Published private(set) var messaggio: String?
    /// Un salvataggio non riuscito, detto in parole semplici.
    @Published private(set) var erroreSalvataggio: String?
    /// Un salvataggio o una richiesta di permesso in corso: gli interruttori aspettano (due tocchi in fretta non partono insieme).
    @Published private(set) var inCorso = false
    private let telefono: TelefonoAvvisi
    private let memoria: UserDefaults

    init(server: any ServerClient, telefono: TelefonoAvvisi = .veri, memoria: UserDefaults = .standard) {
        self.server = server
        self.telefono = telefono
        self.memoria = memoria
        caricatore = Caricatore<StatoAvvisi>("/api/avvisi", snake: false, cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    /// La riga sotto «Ore tranquille», con le ore del server, come `avvisiTelefono` della web: accese la fascia
    /// (`imp.ore_tranquille_aiuto`); spente lo dice, con la fascia che varrebbe accendendole (`imp.ore_tranquille_spente`, #873:
    /// «Niente avvisi dalle 23 alle 7» sotto l'interruttore spento le faceva sembrare accese). Segue l'interruttore: cambia al tocco
    /// e torna com'era se il salvataggio non riesce (`salva`).
    nonisolated static func aiutoOreTranquille(_ ore: OreTranquille) -> String {
        let a = String(ore.a), da = String(ore.da)
        return ore.attive ? Catalogo.Imp.oreTranquilleAiuto(a: a, da: da) : Catalogo.Imp.oreTranquilleSpente(a: a, da: da)
    }

    /// La riga sotto «Avvisi su questo dispositivo»: di solito il promemoria che l'interruttore accende (`imp.avvisi_qui_aiuto_app`);
    /// se il promemoria arriva già dalla web app (`promemoriaDaWeb`), che qui non si ripete (`imp.avvisi_qui_aiuto_web`). Con ntfy
    /// per l'app nativa resta quella di sempre: il promemoria arriva lo stesso su questo telefono e il suo tocco apre l'app.
    var aiutoQui: String {
        promemoriaDaWeb ? Catalogo.Imp.avvisiQuiAiutoWeb : Catalogo.Imp.avvisiQuiAiutoApp
    }

    /// Legge gli avvisi dal server. Se per i promemoria è cambiato qualcosa (ore tranquille, avvisi del server a questa app), li
    /// rimette subito in programma: niente doppioni o promemoria mancanti fino alla prossima lettura di Oggi (#906).
    func carica() async {
        await caricatore.ricarica()
        if let stato = caricatore.dato {
            let cambiato = applica(stato)
            oreTranquilleSpente = stato.oreTranquilleSpente
            if cambiato { await telefono.riprogramma() }
        }
        qui = await statoQui()
    }

    private func statoQui() async -> Bool {
        guard ArchivioAvvisiQui.acceso(memoria) else { return false }
        return await telefono.permesso()
    }

    /// «Avvisi su questo dispositivo»: acceso chiede il permesso a iOS e rimette in programma i promemoria; spento li toglie subito.
    func cambiaQui(_ acceso: Bool) async {
        guard !inCorso else { return }
        inCorso = true
        defer { inCorso = false }
        messaggio = nil
        guard acceso else {
            ArchivioAvvisiQui.salva(false, memoria)
            qui = false
            telefono.togliTutti()
            messaggio = Catalogo.Avv.notificheDisattivateQuesto
            return
        }
        guard await telefono.chiediPermesso() else {
            qui = false
            messaggio = Catalogo.Avv.permessoNegatoAbilita
            return
        }
        ArchivioAvvisiQui.salva(true, memoria)
        qui = true
        await telefono.riprogramma()
    }

    /// «Ore tranquille»: si manda il solo `silenzio`, come la web; poi i promemoria tornano in programma con le ore nuove.
    func cambiaOreTranquille(_ acceso: Bool) async {
        await salva(SoloSilenzio(silenzio: acceso), riprogramma: true) { $0.oreTranquille.attive = acceso }
    }

    /// «Avvisi anche per l'app nativa» (Gestione, senza account): si manda il solo `app_nativa`; poi i promemoria del telefono
    /// tornano in programma, perché con ntfy acceso arriva già quello del server (#906).
    func cambiaAppNativa(_ acceso: Bool) async {
        await salva(SoloAppNativa(app_nativa: acceso), riprogramma: true) { $0.appNativa = acceso }
    }

    /// Salva un campo: l'interruttore si sposta subito e, se il server non risponde, torna come lo ha il server e lo si dice.
    /// Dopo un 412 (cambiato da un altro dispositivo) si rilegge.
    private func salva<Corpo: Encodable>(_ corpo: Corpo, riprogramma: Bool, subito: (AvvisiDispositivoViewModel) -> Void) async {
        guard !inCorso else { return }
        inCorso = true
        defer { inCorso = false }
        let ore = oreTranquille, nativa = appNativa
        subito(self)
        do {
            let stato: StatoAvvisi = try await server.posta("PUT", "/api/avvisi", corpo, snake: false)
            let cambiato = applica(stato)
            oreTranquilleSpente = false
            erroreSalvataggio = nil
            if riprogramma || cambiato, !Demo.attivo { await telefono.riprogramma() }
        } catch {
            oreTranquille = ore
            appNativa = nativa
            erroreSalvataggio = "Non ho salvato la modifica. " + error.localizedDescription
            if (error as? ErroreApi)?.eConflitto == true { await rileggi() }
        }
    }

    /// Rilegge dal server dopo un conflitto, lasciando l'errore in vista.
    private func rileggi() async {
        await caricatore.ricarica()
        if let stato = caricatore.dato, applica(stato) { await telefono.riprogramma() }
    }

    /// Gli avvisi come li ha il server: ore tranquille, app nativa e da dove arrivano già i promemoria, ricordati anche sul telefono
    /// con il fatto che il server manda già i promemoria a questo telefono (per i promemoria locali, `TelefonoAvvisi.ricorda`). Dice
    /// se per i promemoria è cambiato qualcosa (nella demo mai: niente promemoria).
    private func applica(_ stato: StatoAvvisi) -> Bool {
        oreTranquille = stato.impostazioni.oreTranquille
        appNativa = stato.impostazioni.app_nativa
        promemoriaDaWeb = stato.promemoriaDa == .web
        return Demo.attivo ? false : telefono.ricorda(stato)
    }
}

/// Il corpo di `PUT /api/avvisi` con le sole ore tranquille accese o spente.
private struct SoloSilenzio: Encodable {
    let silenzio: Bool
}

/// Il corpo di `PUT /api/avvisi` con il solo «Avvisi anche per l'app nativa».
private struct SoloAppNativa: Encodable {
    // swiftlint:disable:next identifier_name
    let app_nativa: Bool
}
