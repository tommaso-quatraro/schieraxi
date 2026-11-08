import Foundation
import WidgetKit
import AppIntents

// Dati del widget. Il widget è un programma a parte. L'indirizzo del server e il token del widget (`fw_`) glieli dà l'app da sola:
// App Group (`Condiviso`, il nome vero si trova nel profilo della firma) o, se manca, Keychain condiviso (`PortachiaviCondiviso`).
// L'utente non scrive niente; senza indirizzo vale il server pubblico dell'app. Solo se nessuno dei due funziona il widget dice
// «Tocca per collegare» e apre l'app (`schieraxi://widget/collega`), che al tocco su «Collega» copia il codice; l'utente lo incolla una
// volta in «Modifica widget» > «Collegamento manuale» (`CollegamentoWidget`).
// Il modello `Oggi`, `Quando` e `RiassuntoOggi` sono condivisi con l'app.

/// Un istante della timeline del widget.
struct Voce: TimelineEntry {
    let date: Date
    let riassunto: RiassuntoOggi?
    /// true se il server non ha risposto e si mostra l'ultimo riassunto salvato.
    let datiSalvati: Bool
    /// true se il server ha gli account e chiede l'accesso (nessun token condiviso, o scaduto): non mostra niente di un altro utente.
    var accessoRichiesto = false
    /// true se nelle impostazioni del widget manca l'indirizzo del server (o non è valido).
    var indirizzoMancante = false
    /// Il riassunto completo di `/api/widget` (per i widget nuovi); nil con un server che non lo ha ancora.
    var widget: RiassuntoWidget? = nil

    /// Il widget va (ri)collegato: dice «Tocca per collegare» (con un 401 le copie sono già cancellate, quindi niente dati vecchi).
    var daCollegare: Bool {
        CollegamentoWidget.daCollegare(haDati: riassunto != nil || widget != nil, indirizzoMancante: indirizzoMancante, accessoRichiesto: accessoRichiesto)
    }

    /// Dove porta il tocco: alla schermata «Collega il widget» se va collegato, altrimenti dove porterebbe di solito.
    func tocco(_ normale: URL?) -> URL? { daCollegare ? CollegamentoWidget.url : normale }

    /// La stessa voce in un altro istante: i dati sono gli stessi, cambia solo l'ora con cui si contano conto alla rovescia e date.
    func spostata(a data: Date) -> Voce {
        Voce(date: data, riassunto: riassunto, datiSalvati: datiSalvati, accessoRichiesto: accessoRichiesto,
             indirizzoMancante: indirizzoMancante, widget: widget)
    }
}

/// Le impostazioni del widget: niente da compilare. Il collegamento è automatico; il codice (lo copia l'app) compare solo
/// attivando «Collegamento manuale», l'ultimo ripiego. L'indirizzo del server non si chiede più: lo passa l'app, altrimenti
/// vale il server pubblico. Un codice incollato con una versione di prima resta valido (stesso nome del parametro).
struct ConfigurazioneWidget: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Widget di SchieraXI"
    static var description = IntentDescription("Si collega da solo all'app. «Collegamento manuale» serve solo se il widget dice «Tocca per collegare» anche dopo averlo toccato.")

    @Parameter(title: "Collegamento manuale", default: false)
    var manuale: Bool

    @Parameter(title: "Codice di collegamento", default: "")
    var codice: String

    static var parameterSummary: some ParameterSummary {
        When(\.$manuale, .equalTo, true) {
            Summary("Collegamento manuale") {
                \.$manuale
                \.$codice
            }
        } otherwise: {
            Summary("Collegamento automatico") {
                \.$manuale
            }
        }
    }
}

enum ScaricaOggi {
    private static let chiave = MemoriaWidget.chiaveRiassunto

    /// L'indirizzo dell'API «oggi» dall'indirizzo scritto nelle impostazioni del widget; `nil` se manca o non è ammesso
    /// (solo https; http solo verso questo stesso computer; niente nome utente e password dentro l'indirizzo).
    static func indirizzoOggi(_ scritto: String) -> String? { indirizzoBase(scritto).map { $0 + "/api/oggi" } }

    /// L'indirizzo del server pulito (spazi e «/» finali), solo se ammesso.
    static func indirizzoBase(_ scritto: String) -> String? {
        var t = scritto.trimmingCharacters(in: .whitespacesAndNewlines)
        while t.hasSuffix("/") { t.removeLast() }
        guard let url = URL(string: t), let host = url.host?.lowercased(), !host.isEmpty, url.user == nil, url.password == nil else { return nil }
        switch url.scheme?.lowercased() {
        case "https": break
        case "http" where ["localhost", "127.0.0.1", "::1", "[::1]"].contains(host): break
        default: return nil
        }
        return t
    }

    /// Il riassunto che il widget salva per sé (solo con un server senza `/api/widget`), con l'impronta del collegamento.
    private struct RiassuntoDelWidget: Codable {
        var riassunto: RiassuntoOggi
        var chi: String
    }

    /// L'ultimo riassunto dello stesso collegamento (`chi`): quello salvato dal widget o quello che l'app ha messo nel file condiviso,
    /// il più recente. Mai quello di un altro collegamento: di prima dell'uscita dall'account o di un altro account.
    private static func ultimoSalvato(chi: String) -> RiassuntoOggi? {
        let suo = UserDefaults.standard.data(forKey: chiave)
            .flatMap { try? JSONDecoder().decode(RiassuntoDelWidget.self, from: $0) }
            .flatMap { $0.chi == chi ? $0.riassunto : nil }
        let dellApp = MemoriaWidget.riassuntoDellApp(Condiviso.leggi(), per: chi)
        switch (suo, dellApp) {
        case let (a?, b?): return a.scaricatoIl >= b.scaricatoIl ? a : b
        case let (a?, nil): return a
        case let (nil, b?): return b
        default: return nil
        }
    }

    /// Dove e con quale token scaricare. Ordine (logica in `CodiceWidget.destinazione`, provata nei test): dati dell'app con il token
    /// (App Group, poi Keychain condiviso) > codice di collegamento incollato nel widget > indirizzo dell'app senza token > server pubblico.
    static func destinazione(codice: String) -> (indirizzo: String, token: String?)? {
        CodiceWidget.destinazione(condiviso: Condiviso.leggi(), portachiavi: PortachiaviCondiviso.leggi(), codice: codice, pulisci: indirizzoBase)
    }

    /// Tutto in una chiamata: `/api/widget` con If-None-Match. Se il server non ha la rotta si ricade su `/api/oggi` (solo i widget
    /// «vecchi»). Senza rete o con il server che calcola si mostra la copia dello stesso collegamento, con la sua ora; con un 401
    /// niente copie: «Tocca per collegare».
    struct Risultato {
        var widget: RiassuntoWidget?
        var riassunto: RiassuntoOggi?
        var scaricatoIl: Date?
        var salvato: Bool
        var accessoRichiesto: Bool
    }

    static func leggiTutto(base: String, token: String?) async -> Risultato {
        // Di chi sono i dati: una copia scaricata con un altro collegamento (prima dell'uscita dall'account, con un altro account o con
        // un codice di prima) non si mostra, nemmeno quando il gruppo condiviso manca e l'app non la può cancellare (#482).
        let chi = MemoriaWidget.impronta(indirizzo: base, token: token)
        let copia = MemoriaWidget.leggi(per: chi)
        let esito = await ScaricoWidget.scarica(base: base, token: token, etag: copia?.etag)
        // salva, rinfresca o cancella le copie (con un 401 tutte, anche quelle che l'app non raggiunge): logica provata nei test
        let r = MemoriaWidget.applica(esito, copia: copia, chi: chi)
        if r.nonDisponibile {
            let vecchio = await leggi(indirizzo: base + "/api/oggi", token: token, chi: chi)
            return Risultato(widget: nil, riassunto: vecchio.riassunto, scaricatoIl: vecchio.riassunto?.scaricatoIl, salvato: vecchio.salvato,
                             accessoRichiesto: vecchio.accessoRichiesto)
        }
        // 401: «Tocca per collegare», mai dati vecchi
        if r.accessoRichiesto {
            return Risultato(widget: nil, riassunto: nil, scaricatoIl: nil, salvato: false, accessoRichiesto: true)
        }
        if let c = r.copia, let w = c.riassunto {
            return Risultato(widget: w, riassunto: w.comeRiassuntoOggi(scaricatoIl: c.scaricatoIl), scaricatoIl: c.scaricatoIl, salvato: !r.fresca,
                             accessoRichiesto: false)
        }
        if let ultimo = ultimoSalvato(chi: chi) {
            return Risultato(widget: nil, riassunto: ultimo, scaricatoIl: ultimo.scaricatoIl, salvato: true, accessoRichiesto: false)
        }
        return Risultato(widget: nil, riassunto: nil, scaricatoIl: nil, salvato: false, accessoRichiesto: false)
    }

    /// Scarica la giornata; se non riesce restituisce l'ultimo riassunto salvato dello stesso collegamento (con `salvato` true).
    /// Se il server risponde 401 (account attivi: serve l'accesso) i riassunti salvati si cancellano e non si mostrano:
    /// potrebbero essere di un altro utente.
    static func leggi(indirizzo: String, token: String?, chi: String) async -> (riassunto: RiassuntoOggi?, salvato: Bool, accessoRichiesto: Bool) {
        switch await scarica(indirizzo: indirizzo, token: token) {
        case .dati(let nuovo):
            if let dati = try? JSONEncoder().encode(RiassuntoDelWidget(riassunto: nuovo, chi: chi)) { UserDefaults.standard.set(dati, forKey: chiave) }
            return (nuovo, false, false)
        case .accessoRichiesto:
            MemoriaWidget.accessoNegato()
            return (nil, false, true)
        case .errore:
            return (ultimoSalvato(chi: chi), true, false)
        }
    }

    private enum Scarico {
        case dati(RiassuntoOggi)
        case accessoRichiesto
        case errore
    }

    private static func scarica(indirizzo: String, token: String?) async -> Scarico {
        guard let url = URL(string: indirizzo) else { return .errore }
        var richiesta = URLRequest(url: url, timeoutInterval: 15)
        richiesta.setValue("1", forHTTPHeaderField: "X-Fanta")
        LinguaServer.applica(&richiesta)
        // La sessione dell'app (se il gruppo condiviso funziona): il token va solo all'indirizzo per cui è stato salvato.
        if let token { richiesta.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        do {
            let (dati, risposta) = try await URLSession.shared.data(for: richiesta)
            guard let h = risposta as? HTTPURLResponse else { return .errore }
            if h.statusCode == 401 { return .accessoRichiesto }
            guard (200..<300).contains(h.statusCode) else { return .errore }
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let oggi = try decoder.decode(Oggi.self, from: dati)
            return .dati(RiassuntoOggi(oggi: oggi))
        } catch {
            return .errore
        }
    }
}

/// Decide quando il widget si ricarica: ogni mezz'ora, e di nuovo al calcio d'inizio (per passare da conto alla rovescia a «Chiusa»).
struct Fornitore: AppIntentTimelineProvider {
    /// Per i widget con il conto alla rovescia («6 h 44 min», come la web): una voce in più per ogni minuto in cui il testo cambia,
    /// per l'ora che viene (`Quando.istantiDelConto`). Sono voci della stessa timeline, non ricariche: non toccano il limite di iOS.
    var conConto = false

    func placeholder(in context: Context) -> Voce {
        Voce(date: Date(), riassunto: .esempio, datiSalvati: false)
    }

    func snapshot(for configuration: ConfigurazioneWidget, in context: Context) async -> Voce {
        if context.isPreview { return placeholder(in: context) }
        return await voce(configuration)
    }

    func timeline(for configuration: ConfigurazioneWidget, in context: Context) async -> Timeline<Voce> {
        let primo = await voce(configuration)
        let adesso = primo.date
        var voci = [primo]
        // Più spesso quando la partita è vicina (probabili, dubbi e formazioni cambiano), meno quando mancano giorni.
        var minuti = 30.0
        if let inizio = primo.riassunto?.inizio {
            let manca = inizio.timeIntervalSince(adesso)
            if manca > 0 && manca < 3 * 3600 { minuti = 10 } else if manca > 0 && manca < 24 * 3600 { minuti = 20 } else if manca < 0 && manca > -3 * 3600 { minuti = 15 }
        }
        // Partite in gioco (o che stanno per iniziare): ogni 2 minuti. iOS decide poi quando ricaricare davvero (budget giornaliero): se
        // rimanda, il widget mostra l'ultimo punteggio con l'ora dell'aggiornamento.
        var prossimoCalcio: Date?
        if let w = primo.widget {
            if w.finestraLive(adesso: adesso) { minuti = 2 }
            prossimoCalcio = w.prossimaPartita(dopo: adesso)?.quando?.addingTimeInterval(-10 * 60)
        }
        var prossimo = adesso.addingTimeInterval(minuti * 60)
        if let c = prossimoCalcio, c > adesso, c < prossimo { prossimo = c }
        if primo.indirizzoMancante { prossimo = adesso.addingTimeInterval(60 * 60) }
        if let inizio = primo.riassunto?.inizio, inizio > adesso, inizio < prossimo { prossimo = inizio.addingTimeInterval(60) }
        // senza voci il testo resterebbe fermo fino alla prossima ricarica, che iOS può rimandare (di notte anche di ore): voci per
        // il conto alla rovescia, la scadenza e la mezzanotte, dove «domani 12:30» diventa «oggi 12:30»
        voci += VociTimeline.istanti(adesso: adesso, scadenza: primo.riassunto?.inizio, conConto: conConto).map { primo.spostata(a: $0) }
        return Timeline(entries: voci, policy: .after(prossimo))
    }

    private func voce(_ configurazione: ConfigurazioneWidget) async -> Voce {
        guard let dove = ScaricaOggi.destinazione(codice: configurazione.codice) else {
            // Nessun indirizzo: se l'app ha già un riassunto lo si mostra, altrimenti si dice cosa fare.
            if let r = Condiviso.leggi().riassunto { return Voce(date: Date(), riassunto: r, datiSalvati: true) }
            return Voce(date: Date(), riassunto: nil, datiSalvati: false, indirizzoMancante: true)
        }
        let r = await ScaricaOggi.leggiTutto(base: dove.indirizzo, token: dove.token)
        return Voce(date: Date(), riassunto: r.riassunto, datiSalvati: r.salvato, accessoRichiesto: r.accessoRichiesto,
                    widget: r.widget)
    }
}
