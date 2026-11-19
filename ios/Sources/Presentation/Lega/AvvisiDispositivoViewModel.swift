import Foundation

/// Impostazioni > Avvisi, come la web (#673 passo 3, #693): «Avvisi su questo dispositivo» e «Ore tranquille»; in Gestione, senza
/// account, «Avvisi anche per l'app nativa». Quali avvisi arrivano lo decide il server; qui l'interruttore unico accende o spegne il
/// permesso di iOS e i promemoria locali (un'ora e un quarto d'ora prima, l'avviso quando cambia la consigliata). Le scelte per
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

    /// La riga sotto «Ore tranquille»: la fascia scelta, con le ore del server (`imp.ore_tranquille_aiuto`).
    nonisolated static func aiutoOreTranquille(_ ore: OreTranquille) -> String {
        Catalogo.Imp.oreTranquilleAiuto(a: String(ore.a), da: String(ore.da))
    }

    func carica() async {
        await caricatore.ricarica()
        if let stato = caricatore.dato {
            applica(stato.impostazioni)
            oreTranquilleSpente = stato.oreTranquilleSpente
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

    /// «Avvisi anche per l'app nativa» (Gestione, senza account): si manda il solo `app_nativa`.
    func cambiaAppNativa(_ acceso: Bool) async {
        await salva(SoloAppNativa(app_nativa: acceso), riprogramma: false) { $0.appNativa = acceso }
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
            applica(stato.impostazioni)
            oreTranquilleSpente = false
            erroreSalvataggio = nil
            if riprogramma, !Demo.attivo { await telefono.riprogramma() }
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
        if let stato = caricatore.dato { applica(stato.impostazioni) }
    }

    /// Le impostazioni come le ha il server: ore tranquille (ricordate anche sul telefono, per i promemoria) e app nativa.
    private func applica(_ impostazioni: ImpostazioniAvvisi) {
        oreTranquille = impostazioni.oreTranquille
        appNativa = impostazioni.app_nativa
        if !Demo.attivo { telefono.ricordaOre(oreTranquille) }
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
