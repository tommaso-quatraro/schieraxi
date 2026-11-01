import Foundation
import BackgroundTasks
import WidgetKit

/// Aggiornamento in background: ogni tanto iOS sveglia l'app (BGAppRefreshTask), che riscarica la giornata,
/// riprogramma i promemoria e, se la formazione consigliata è cambiata, manda una notifica locale.
/// iOS decide quando svegliarla (di solito poche volte al giorno, di più se usi spesso l'app): non c'è un orario garantito.
enum Aggiornamento {
    static let identificativo = "it.schieraxi.app.aggiorna"

    /// Chiede a iOS di svegliare l'app fra non meno di due ore.
    static func programma() {
        if Demo.attivo { return }   // demo: nessun lavoro in background
        let richiesta = BGAppRefreshTaskRequest(identifier: identificativo)
        richiesta.earliestBeginDate = Date(timeIntervalSinceNow: 2 * 3600)
        try? BGTaskScheduler.shared.submit(richiesta)
    }

    /// Riprogramma i promemoria sulla scadenza del certificato (se il profilo si legge).
    static func riprogrammaScadenza() async {
        if Demo.attivo { return }
        if let scadenza = Certificato.scadenza() { await Notifiche.programmaScadenza(scadenza) }
    }

    /// Il lavoro vero: scarica /api/oggi, lo salva nella cache e confronta con l'ultima volta.
    static func esegui() async {
        if Demo.attivo { return }
        programma()   // prima di tutto: riprogramma il prossimo risveglio
        await riprogrammaScadenza()
        await NuovaVersione.controllaEAvvisa()
        await aggiornaOreTranquille()
        guard let oggi = try? await OggiRepository(server: ServerCorrente.condiviso).aggiornato() else { return }
        await elabora(oggi, avvisaSeCambia: true)
    }

    /// Riempie in anticipo la copia di `/api/widget` (con If-None-Match), così i widget mostrano subito dati freschi.
    static func precaricaWidget() async {
        let base = IndirizzoServer.attuale
        if Demo.attivo || base.isEmpty { return }
        // Nei test unitari l'app che li ospita non deve scaricare niente dal server predefinito (scriverebbe la copia mentre un test la controlla).
        if ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil { return }
        let copia = MemoriaWidget.leggi()
        if case .dati(_, let grezzo, let etag) = await ScaricoWidget.scarica(base: base, token: Accesso.archivio.leggi(server: base), etag: copia?.etag) {
            MemoriaWidget.salva(CopiaWidget(dati: grezzo, etag: etag, scaricatoIl: Date()))
        }
    }

    /// Rilegge le ore tranquille dal server (se risponde) per i promemoria locali.
    static func aggiornaOreTranquille() async {
        if Demo.attivo { return }
        if let stato: StatoAvvisi = try? await ServerCorrente.condiviso.get("/api/avvisi", snake: false) {
            ArchivioOreTranquille.salva(stato.impostazioni.oreTranquille)
        }
    }

    /// Promemoria, widget e (se richiesto) notifica quando la formazione consigliata cambia nella stessa giornata.
    static func elabora(_ oggi: Oggi, avvisaSeCambia: Bool) async {
        if Demo.attivo { return }   // demo: niente promemoria, widget o notifiche
        if let inizio = Quando.data(oggi.chiusura), let numero = oggi.giornataMostrata {
            await Notifiche.programma(giornata: numero, inizio: inizio, modulo: oggi.formazione?.modulo)
        }
        // Il widget trova subito l'ultima giornata (senza aspettare il suo scarico) e si ridisegna.
        Condiviso.salvaRiassunto(RiassuntoOggi(oggi: oggi))
        await precaricaWidget()
        WidgetCenter.shared.reloadAllTimelines()
        // Senza una formazione vera (modulo mancante o «–», punti assenti) non si confronta né si ricorda niente.
        guard let f = oggi.formazione, f.disponibile, let modulo = f.modulo, let giornata = oggi.giornata else { return }
        let memoria = UserDefaults.standard
        let probabili = oggi.conProbabili ?? false
        let giornataPrima = memoria.object(forKey: "bg.giornata") as? Int
        let moduloPrima = memoria.string(forKey: "bg.modulo")
        let probabiliPrima = memoria.object(forKey: "bg.probabili") as? Bool

        if avvisaSeCambia, giornataPrima == giornata {
            let punti = Formato.punti(f.punteggioAtteso)
            if let moduloPrima, moduloPrima != modulo {
                await Notifiche.avviso(id: "fanta-cambio", titolo: "SchieraXI · Cambio di modulo",
                                       corpo: corpoCambioModulo(oggi, modulo: modulo, punti: punti, moduloPrima: moduloPrima))
            } else if probabiliPrima == false, probabili {
                await Notifiche.avviso(id: "fanta-probabili", titolo: "SchieraXI · Escono le probabili",
                                       corpo: corpoProbabili(oggi, modulo: modulo, punti: punti))
            }
        }
        memoria.set(giornata, forKey: "bg.giornata")
        memoria.set(modulo, forKey: "bg.modulo")
        memoria.set(probabili, forKey: "bg.probabili")
    }

    /// I testi degli avvisi: il numero è quello della LEGA (lo stesso che l'utente vede nell'app), non quello di Serie A.
    static func corpoCambioModulo(_ oggi: Oggi, modulo: String, punti: String, moduloPrima: String) -> String {
        "Mister, \(oggi.giornataMostrata.map { "giornata \($0)" } ?? "prossima giornata"): ora \(modulo), \(punti) punti attesi (prima \(moduloPrima))."
    }

    static func corpoProbabili(_ oggi: Oggi, modulo: String, punti: String) -> String {
        "\(oggi.giornataMostrata.map { "Giornata \($0)" } ?? "Prossima giornata"): modulo consigliato \(modulo), \(punti) punti attesi."
    }

    /// La giornata di oggi per Siri e Comandi: dal server, o dalla cache se non risponde.
    static func leggiOggi() async -> (oggi: Oggi, salvato: Bool)? {
        await OggiRepository(server: ServerCorrente.condiviso).ultimo()
    }
}
