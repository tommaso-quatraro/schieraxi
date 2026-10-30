import Foundation
import WidgetKit

// Dati del widget. Il widget è un programma a parte: non può leggere la cache dell'app (niente App Group con l'Apple ID gratuito),
// quindi scarica da solo /api/oggi dall'indirizzo dell'Info.plist (FANTA_HOST / FANTA_PORT) e tiene una sua copia dell'ultimo riassunto.
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
}

enum ScaricaOggi {
    private static let chiave = "ultimoRiassunto"

    private static var indirizzo: String {
        let host = (Bundle.main.object(forInfoDictionaryKey: "FantaHost") as? String) ?? ""
        let porta = (Bundle.main.object(forInfoDictionaryKey: "FantaPort") as? String) ?? ""
        return "https://\(host):\(porta)/api/oggi"
    }

    private static func ultimoSalvato() -> RiassuntoOggi? {
        guard let dati = UserDefaults.standard.data(forKey: chiave) else { return nil }
        return try? JSONDecoder().decode(RiassuntoOggi.self, from: dati)
    }

    /// Scarica la giornata; se non riesce restituisce l'ultimo riassunto salvato (con `salvato` true).
    /// Se il server risponde 401 (account attivi: serve l'accesso) il riassunto salvato si cancella e non si mostra:
    /// potrebbe essere di un altro utente.
    static func leggi() async -> (riassunto: RiassuntoOggi?, salvato: Bool, accessoRichiesto: Bool) {
        switch await scarica() {
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

    private static func scarica() async -> Scarico {
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
struct Fornitore: TimelineProvider {
    func placeholder(in context: Context) -> Voce {
        Voce(date: Date(), riassunto: .esempio, datiSalvati: false)
    }

    func getSnapshot(in context: Context, completion: @escaping (Voce) -> Void) {
        if context.isPreview {
            completion(placeholder(in: context))
            return
        }
        Task {
            let r = await ScaricaOggi.leggi()
            completion(Voce(date: Date(), riassunto: r.riassunto, datiSalvati: r.salvato, accessoRichiesto: r.accessoRichiesto))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Voce>) -> Void) {
        Task {
            let r = await ScaricaOggi.leggi()
            let adesso = Date()
            var voci = [Voce(date: adesso, riassunto: r.riassunto, datiSalvati: r.salvato, accessoRichiesto: r.accessoRichiesto)]
            var prossimo = adesso.addingTimeInterval(30 * 60)
            if let inizio = r.riassunto?.inizio, inizio > adesso {
                voci.append(Voce(date: inizio, riassunto: r.riassunto, datiSalvati: r.salvato, accessoRichiesto: r.accessoRichiesto))
                if inizio < prossimo { prossimo = inizio.addingTimeInterval(60) }
            }
            completion(Timeline(entries: voci, policy: .after(prossimo)))
        }
    }
}
