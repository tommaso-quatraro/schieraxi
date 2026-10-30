import Foundation
import WidgetKit
import AppIntents

// Dati del widget. Il widget è un programma a parte. L'indirizzo del server e il token della sessione glieli dà l'app tramite un
// App Group (`Condiviso`, file nel contenitore condiviso): se il gruppo funziona il widget non chiede niente. Se non funziona
// (installazione senza App Group) resta il ripiego di una volta: l'indirizzo si scrive nelle impostazioni del widget
// (tenere premuto > Modifica widget) e, con gli account, il widget chiede l'accesso (non ha il token).
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
    /// Una riga di diagnostica sulla condivisione con l'app (si vede solo quando non ci sono dati).
    var diagnostica: String?
    /// Il riassunto completo di `/api/widget` (per i widget nuovi); nil con un server che non lo ha ancora.
    var widget: RiassuntoWidget? = nil
}

/// Le impostazioni del widget: l'indirizzo del server (solo https, o localhost per le prove).
struct ConfigurazioneWidget: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Server di SchieraXI"
    static var description = IntentDescription("Di solito non serve: l'app dice al widget dove sta il server. Scrivi l'indirizzo qui solo se il widget dice che manca.")

    @Parameter(title: "Indirizzo del server (solo se manca)", default: "")
    var indirizzo: String

    @Parameter(title: "Codice di collegamento", default: "")
    var codice: String
}

enum ScaricaOggi {
    private static let chiave = "ultimoRiassunto"

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

    /// L'ultimo riassunto: quello salvato dal widget o quello che l'app ha messo nel file condiviso, il più recente.
    private static func ultimoSalvato() -> RiassuntoOggi? {
        let suo = UserDefaults.standard.data(forKey: chiave).flatMap { try? JSONDecoder().decode(RiassuntoOggi.self, from: $0) }
        let dellApp = Condiviso.leggi().riassunto
        switch (suo, dellApp) {
        case let (a?, b?): return a.scaricatoIl >= b.scaricatoIl ? a : b
        case let (a?, nil): return a
        case let (nil, b?): return b
        default: return nil
        }
    }

    /// Dove e con quale token scaricare: prima i dati dell'app (App Group), poi l'indirizzo scritto nelle impostazioni del widget.
    /// Ordine: dati dell'app (App Group) > codice di collegamento incollato nel widget > solo indirizzo scritto nel widget.
    static func destinazione(indirizzo scritto: String, codice: String) -> (indirizzo: String, token: String?)? {
        let condiviso = Condiviso.leggi()
        if let base = condiviso.indirizzo, let pulito = indirizzoBase(base) {
            return (pulito, condiviso.token(per: base))
        }
        if let c = CodiceWidget.leggi(codice), let pulito = indirizzoBase(c.i) {
            return (pulito, c.t)
        }
        guard let pulito = indirizzoBase(scritto) else { return nil }
        return (pulito, nil)
    }

    /// Tutto in una chiamata: `/api/widget` con If-None-Match. Se il server non ha la rotta si ricade su `/api/oggi` (solo i widget
    /// «vecchi»). Mai «serve l'accesso» a vuoto: se c'è una copia (del widget o dell'app) si mostra con la sua ora.
    struct Risultato {
        var widget: RiassuntoWidget?
        var riassunto: RiassuntoOggi?
        var scaricatoIl: Date?
        var salvato: Bool
        var accessoRichiesto: Bool
    }

    static func leggiTutto(base: String, token: String?) async -> Risultato {
        let copia = MemoriaWidget.leggi()
        func daCopia(accesso: Bool) -> Risultato {
            if let copia, let w = copia.riassunto {
                return Risultato(widget: w, riassunto: w.comeRiassuntoOggi(scaricatoIl: copia.scaricatoIl), scaricatoIl: copia.scaricatoIl, salvato: true, accessoRichiesto: false)
            }
            if let ultimo = ultimoSalvato() {
                return Risultato(widget: nil, riassunto: ultimo, scaricatoIl: ultimo.scaricatoIl, salvato: true, accessoRichiesto: false)
            }
            return Risultato(widget: nil, riassunto: nil, scaricatoIl: nil, salvato: false, accessoRichiesto: accesso)
        }
        switch await ScaricoWidget.scarica(base: base, token: token, etag: copia?.etag) {
        case .dati(let w, let grezzo, let etag):
            let adesso = Date()
            MemoriaWidget.salva(CopiaWidget(dati: grezzo, etag: etag, scaricatoIl: adesso))
            return Risultato(widget: w, riassunto: w.comeRiassuntoOggi(scaricatoIl: adesso), scaricatoIl: adesso, salvato: false, accessoRichiesto: false)
        case .nonCambiato:
            if let copia, let w = copia.riassunto {
                let adesso = Date()
                MemoriaWidget.salva(CopiaWidget(dati: copia.dati, etag: copia.etag, scaricatoIl: adesso))
                return Risultato(widget: w, riassunto: w.comeRiassuntoOggi(scaricatoIl: adesso), scaricatoIl: adesso, salvato: false, accessoRichiesto: false)
            }
            return daCopia(accesso: false)
        case .inCalcolo, .errore:
            return daCopia(accesso: false)
        case .accessoRichiesto:
            return daCopia(accesso: true)
        case .nonDisponibile:
            let r = await leggi(indirizzo: base + "/api/oggi", token: token)
            return Risultato(widget: nil, riassunto: r.riassunto, scaricatoIl: r.riassunto?.scaricatoIl, salvato: r.salvato, accessoRichiesto: r.accessoRichiesto)
        }
    }

    /// Scarica la giornata; se non riesce restituisce l'ultimo riassunto salvato (con `salvato` true).
    /// Se il server risponde 401 (account attivi: serve l'accesso) il riassunto salvato si cancella e non si mostra:
    /// potrebbe essere di un altro utente.
    static func leggi(indirizzo: String, token: String?) async -> (riassunto: RiassuntoOggi?, salvato: Bool, accessoRichiesto: Bool) {
        switch await scarica(indirizzo: indirizzo, token: token) {
        case .dati(let nuovo):
            if let dati = try? JSONEncoder().encode(nuovo) { UserDefaults.standard.set(dati, forKey: chiave) }
            return (nuovo, false, false)
        case .accessoRichiesto:
            // Mai «Serve l'accesso» a vuoto: se c'è un ultimo riassunto (dell'app o del widget) si mostra, con la sua ora.
            if let ultimo = ultimoSalvato() { return (ultimo, true, false) }
            return (nil, false, true)
        case .errore:
            return (ultimoSalvato(), true, false)
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

/// Decide quando il widget si ricarica: ogni mezz'ora, e di nuovo al calcio d'inizio (per passare da conto alla rovescia a «In corso»).
struct Fornitore: AppIntentTimelineProvider {
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
        if let inizio = primo.riassunto?.inizio, inizio > adesso {
            var dopo = primo
            dopo = Voce(date: inizio, riassunto: primo.riassunto, datiSalvati: primo.datiSalvati, accessoRichiesto: primo.accessoRichiesto, diagnostica: primo.diagnostica, widget: primo.widget)
            voci.append(dopo)
            if inizio < prossimo { prossimo = inizio.addingTimeInterval(60) }
        }
        return Timeline(entries: voci, policy: .after(prossimo))
    }

    private func voce(_ configurazione: ConfigurazioneWidget) async -> Voce {
        let diagnostica = Condiviso.diagnostica().breve
        guard let dove = ScaricaOggi.destinazione(indirizzo: configurazione.indirizzo, codice: configurazione.codice) else {
            // Nessun indirizzo: se l'app ha già un riassunto lo si mostra, altrimenti si dice cosa fare.
            if let r = Condiviso.leggi().riassunto { return Voce(date: Date(), riassunto: r, datiSalvati: true, diagnostica: diagnostica) }
            return Voce(date: Date(), riassunto: nil, datiSalvati: false, indirizzoMancante: true, diagnostica: diagnostica)
        }
        let r = await ScaricaOggi.leggiTutto(base: dove.indirizzo, token: dove.token)
        return Voce(date: Date(), riassunto: r.riassunto, datiSalvati: r.salvato, accessoRichiesto: r.accessoRichiesto,
                    diagnostica: diagnostica, widget: r.widget)
    }
}
