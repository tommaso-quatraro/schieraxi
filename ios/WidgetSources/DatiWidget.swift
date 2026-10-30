import Foundation
import WidgetKit
import AppIntents

// Dati del widget. Il widget è un programma a parte: non può leggere la cache dell'app (niente App Group con l'Apple ID gratuito),
// quindi scarica da solo /api/oggi e tiene una sua copia dell'ultimo riassunto. L'indirizzo del server NON è dentro l'app (repository e IPA
// pubblici) e il widget non può leggere quello salvato dall'app: lo si scrive una volta nelle impostazioni del widget
// (tenere premuto sul widget > Modifica widget > Indirizzo del server).
// Il modello `Oggi` e `Quando` sono condivisi con l'app (Sources/Modelli.swift).

/// Quello che serve al widget, in forma compatta e salvabile.
struct RiassuntoOggi: Codable {
    var giornata: Int
    var inizio: Date?
    var modulo: String?
    var punti: Double?
    var daControllare: Int
    var probabili: Bool?
    var scaricatoIl: Date

    static let esempio = RiassuntoOggi(giornata: 9, inizio: Date().addingTimeInterval(3 * 3600 + 25 * 60), modulo: "3-4-3", punti: 64.5,
                                       daControllare: 2, probabili: true, scaricatoIl: Date())
}

/// Un istante della timeline del widget.
struct Voce: TimelineEntry {
    let date: Date
    let riassunto: RiassuntoOggi?
    /// true se il server non ha risposto e si mostra l'ultimo riassunto salvato.
    let datiSalvati: Bool
    /// true se il server ha gli account e chiede l'accesso: il widget non può avere il token (niente gruppo condiviso con l'app)
    /// e non mostra niente di un altro utente.
    var accessoRichiesto = false
    /// true se nelle impostazioni del widget manca l'indirizzo del server (o non è valido).
    var indirizzoMancante = false
}

/// Le impostazioni del widget: l'indirizzo del server (solo https, o localhost per le prove).
struct ConfigurazioneWidget: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Server di SchieraXI"
    static var description = IntentDescription("L'indirizzo del tuo server, lo stesso che hai scritto nell'app.")

    @Parameter(title: "Indirizzo del server", default: "")
    var indirizzo: String
}

enum ScaricaOggi {
    private static let chiave = "ultimoRiassunto"

    /// L'indirizzo dell'API «oggi» dall'indirizzo scritto nelle impostazioni del widget; `nil` se manca o non è ammesso
    /// (solo https; http solo verso questo stesso computer; niente nome utente e password dentro l'indirizzo).
    static func indirizzoOggi(_ scritto: String) -> String? {
        var t = scritto.trimmingCharacters(in: .whitespacesAndNewlines)
        while t.hasSuffix("/") { t.removeLast() }
        guard let url = URL(string: t), let host = url.host?.lowercased(), !host.isEmpty, url.user == nil, url.password == nil else { return nil }
        switch url.scheme?.lowercased() {
        case "https": break
        case "http" where ["localhost", "127.0.0.1", "::1", "[::1]"].contains(host): break
        default: return nil
        }
        return t + "/api/oggi"
    }

    private static func ultimoSalvato() -> RiassuntoOggi? {
        guard let dati = UserDefaults.standard.data(forKey: chiave) else { return nil }
        return try? JSONDecoder().decode(RiassuntoOggi.self, from: dati)
    }

    /// Scarica la giornata; se non riesce restituisce l'ultimo riassunto salvato (con `salvato` true).
    /// Se il server risponde 401 (account attivi: serve l'accesso) il riassunto salvato si cancella e non si mostra:
    /// potrebbe essere di un altro utente.
    static func leggi(indirizzo: String) async -> (riassunto: RiassuntoOggi?, salvato: Bool, accessoRichiesto: Bool) {
        switch await scarica(indirizzo: indirizzo) {
        case .dati(let nuovo):
            if let dati = try? JSONEncoder().encode(nuovo) { UserDefaults.standard.set(dati, forKey: chiave) }
            return (nuovo, false, false)
        case .accessoRichiesto:
            UserDefaults.standard.removeObject(forKey: chiave)
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

    private static func scarica(indirizzo: String) async -> Scarico {
        guard let url = URL(string: indirizzo) else { return .errore }
        var richiesta = URLRequest(url: url, timeoutInterval: 15)
        richiesta.setValue("1", forHTTPHeaderField: "X-Fanta")
        do {
            let (dati, risposta) = try await URLSession.shared.data(for: richiesta)
            guard let h = risposta as? HTTPURLResponse else { return .errore }
            if h.statusCode == 401 { return .accessoRichiesto }
            guard (200..<300).contains(h.statusCode) else { return .errore }
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let oggi = try decoder.decode(Oggi.self, from: dati)
            return .dati(RiassuntoOggi(
                giornata: oggi.giornata,
                inizio: Quando.data(oggi.inizio),
                modulo: oggi.formazione?.modulo,
                punti: oggi.formazione?.punteggioAtteso,
                daControllare: (oggi.avvisi ?? []).filter { $0.inFormazione == true }.count,
                probabili: oggi.conProbabili,
                scaricatoIl: Date()))
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
        var prossimo = adesso.addingTimeInterval(30 * 60)
        if primo.indirizzoMancante { prossimo = adesso.addingTimeInterval(60 * 60) }
        if let inizio = primo.riassunto?.inizio, inizio > adesso {
            var dopo = primo
            dopo = Voce(date: inizio, riassunto: primo.riassunto, datiSalvati: primo.datiSalvati, accessoRichiesto: primo.accessoRichiesto)
            voci.append(dopo)
            if inizio < prossimo { prossimo = inizio.addingTimeInterval(60) }
        }
        return Timeline(entries: voci, policy: .after(prossimo))
    }

    private func voce(_ configurazione: ConfigurazioneWidget) async -> Voce {
        guard let indirizzo = ScaricaOggi.indirizzoOggi(configurazione.indirizzo) else {
            return Voce(date: Date(), riassunto: nil, datiSalvati: false, indirizzoMancante: true)
        }
        let r = await ScaricaOggi.leggi(indirizzo: indirizzo)
        return Voce(date: Date(), riassunto: r.riassunto, datiSalvati: r.salvato, accessoRichiesto: r.accessoRichiesto)
    }
}
