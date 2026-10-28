import SwiftUI
import Combine

/// Indirizzo del server: predefinito dalla compilazione (Info.plist), modificabile dalla schermata Lega.
enum Config {
    static func testo(_ chiave: String) -> String {
        (Bundle.main.object(forInfoDictionaryKey: chiave) as? String) ?? ""
    }
    static var indirizzoPredefinito: String { "https://\(testo("FantaHost")):\(testo("FantaPort"))" }
}

enum ErroreApi: LocalizedError {
    case indirizzoNonValido
    case risposta(Int)
    case dati(String)
    case rete(String)
    case server(String)

    var errorDescription: String? {
        switch self {
        case .server(let messaggio): return "Il server dice: \(messaggio)"
        case .indirizzoNonValido: return "L'indirizzo del server non è valido."
        case .risposta(let codice): return "Il server ha risposto con un errore (\(codice))."
        case .dati(let dettaglio): return "Risposta inattesa dal server. \(dettaglio)"
        case .rete: return "Non riesco a raggiungere il server. Controlla che rete privata sia attivo."
        }
    }
}

enum Api {
    static var base: String {
        let salvato = (UserDefaults.standard.string(forKey: "indirizzo") ?? "").trimmingCharacters(in: .whitespaces)
        return salvato.isEmpty ? Config.indirizzoPredefinito : salvato
    }

    private static func richiesta(_ percorso: String) throws -> URLRequest {
        guard let url = URL(string: base + percorso) else { throw ErroreApi.indirizzoNonValido }
        var r = URLRequest(url: url, timeoutInterval: 25)
        r.setValue("1", forHTTPHeaderField: "X-Fanta")
        return r
    }

    private static func scarica(_ percorso: String) async throws -> Data {
        let r = try richiesta(percorso)
        do {
            let (dati, risposta) = try await URLSession.shared.data(for: r)
            if let h = risposta as? HTTPURLResponse, !(200..<300).contains(h.statusCode) { throw ErroreApi.risposta(h.statusCode) }
            return dati
        } catch let e as ErroreApi {
            throw e
        } catch {
            throw ErroreApi.rete(error.localizedDescription)
        }
    }

    /// Il messaggio d'errore del server ({"detail": "..."}), se c'è.
    private static func messaggioServer(_ dati: Data, _ codice: Int) -> String {
        if let o = try? JSONSerialization.jsonObject(with: dati) as? [String: Any], let m = o["detail"] as? String { return m }
        return "errore \(codice)"
    }

    /// Invia un corpo JSON (POST/PUT) e restituisce la risposta grezza.
    static func corpoJSON<B: Encodable>(_ metodo: String, _ percorso: String, _ corpo: B) async throws -> Data {
        var r = try richiesta(percorso)
        r.httpMethod = metodo
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.httpBody = try JSONEncoder().encode(corpo)
        do {
            let (dati, risposta) = try await URLSession.shared.data(for: r)
            if let h = risposta as? HTTPURLResponse, !(200..<300).contains(h.statusCode) {
                throw ErroreApi.server(messaggioServer(dati, h.statusCode))
            }
            return dati
        } catch let e as ErroreApi {
            throw e
        } catch {
            throw ErroreApi.rete(error.localizedDescription)
        }
    }

    static func posta<T: Decodable, B: Encodable>(_ metodo: String = "POST", _ percorso: String, _ corpo: B, snake: Bool = true) async throws -> T {
        let dati = try await corpoJSON(metodo, percorso, corpo)
        let d = JSONDecoder()
        if snake { d.keyDecodingStrategy = .convertFromSnakeCase }
        do {
            return try d.decode(T.self, from: dati)
        } catch {
            throw ErroreApi.dati(String(describing: error).prefix(160).description)
        }
    }

    static func get<T: Decodable>(_ percorso: String, snake: Bool = true) async throws -> T {
        let dati = try await scarica(percorso)
        return try decodifica(dati, snake: snake)
    }

    /// La risposta grezza (JSON) di un indirizzo, per poterla anche salvare nella cache.
    static func grezzo(_ percorso: String) async throws -> Data {
        try await scarica(percorso)
    }

    static func decodifica<T: Decodable>(_ dati: Data, snake: Bool = true) throws -> T {
        let d = JSONDecoder()
        if snake { d.keyDecodingStrategy = .convertFromSnakeCase }
        do {
            return try d.decode(T.self, from: dati)
        } catch {
            throw ErroreApi.dati(String(describing: error).prefix(160).description)
        }
    }

    /// PUT/DELETE/POST senza risposta da leggere (osservati, ecc.).
    static func invia(_ metodo: String, _ percorso: String) async throws {
        var r = try richiesta(percorso)
        r.httpMethod = metodo
        do {
            let (_, risposta) = try await URLSession.shared.data(for: r)
            if let h = risposta as? HTTPURLResponse, !(200..<300).contains(h.statusCode) { throw ErroreApi.risposta(h.statusCode) }
        } catch let e as ErroreApi {
            throw e
        } catch {
            throw ErroreApi.rete(error.localizedDescription)
        }
    }

    /// Carica un file (campo "file") e legge la risposta JSON: importazione delle rose da Excel.
    static func caricaFile<T: Decodable>(_ percorso: String, nome: String, dati: Data) async throws -> T {
        var r = try richiesta(percorso)
        r.httpMethod = "POST"
        r.timeoutInterval = 120
        let confine = "Fanta-\(UUID().uuidString)"
        r.setValue("multipart/form-data; boundary=\(confine)", forHTTPHeaderField: "Content-Type")
        var corpo = Data()
        corpo.append(Data("--\(confine)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(nome)\"\r\nContent-Type: application/octet-stream\r\n\r\n".utf8))
        corpo.append(dati)
        corpo.append(Data("\r\n--\(confine)--\r\n".utf8))
        do {
            let (risposta, resp) = try await URLSession.shared.upload(for: r, from: corpo)
            if let h = resp as? HTTPURLResponse, !(200..<300).contains(h.statusCode) {
                let dettaglio = String(decoding: risposta, as: UTF8.self)
                throw ErroreApi.dati("Errore \(h.statusCode): \(dettaglio.prefix(200))")
            }
            let d = JSONDecoder()
            d.keyDecodingStrategy = .convertFromSnakeCase
            return try d.decode(T.self, from: risposta)
        } catch let e as ErroreApi {
            throw e
        } catch {
            throw ErroreApi.rete(error.localizedDescription)
        }
    }

    /// Testo da inserire in un indirizzo (nomi con spazi e simboli).
    static func codifica(_ testo: String) -> String {
        testo.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed.subtracting(CharacterSet(charactersIn: "&+=?#"))) ?? testo
    }

    static func testo(_ percorso: String) async throws -> String {
        String(decoding: try await scarica(percorso), as: UTF8.self)
    }
}

extension Notification.Name {
    /// Il comando «Aggiorna» (Cmd+R) chiede a tutte le schermate di ricaricare.
    static let aggiornaTutto = Notification.Name("<vecchio identificativo>.aggiornaTutto")
}

/// Carica un dato dal server e tiene lo stato (in caricamento, errore) per le schermate.
/// Mostra subito l'ultima risposta salvata (cache) mentre ricarica; se il server non risponde resta quella,
/// e `datiSalvati` dice di quando è.
@MainActor
final class Caricatore<T: Decodable>: ObservableObject {
    @Published var dato: T?
    @Published var errore: String?
    @Published var inCorso = false
    /// Valorizzato solo quando i dati mostrati vengono dalla cache perché il server non ha risposto: è la data in cui erano stati scaricati.
    @Published var datiSalvati: Date?
    var percorso: String
    let snake: Bool
    private let usaCache: Bool
    private var percorsoDelDato: String?
    private var scaricatoIl: Date?
    private var ascolto: AnyCancellable?

    /// `snake: false` per i dati che vanno rimandati al server con le stesse chiavi (regole, impostazioni degli avvisi).
    /// `cache: false` per i dati che si modificano e si rimandano (non si deve ripartire da una copia vecchia).
    init(_ percorso: String, snake: Bool = true, cache: Bool = true) {
        self.percorso = percorso
        self.snake = snake
        self.usaCache = cache
        ascolto = NotificationCenter.default.publisher(for: .aggiornaTutto)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                guard let self else { return }
                Task { await self.ricarica() }
            }
    }

    func ricarica(_ nuovoPercorso: String) async {
        percorso = nuovoPercorso
        await ricarica()
    }

    func ricarica() async {
        inCorso = true
        defer { inCorso = false }
        let richiesto = percorso
        // Subito l'ultima copia salvata (solo se non c'è già qualcosa di questo stesso indirizzo).
        if usaCache, dato == nil || percorsoDelDato != richiesto,
           let salvato = Cache.leggi(richiesto), let vecchio: T = try? Api.decodifica(salvato.dati, snake: snake) {
            dato = vecchio
            percorsoDelDato = richiesto
            scaricatoIl = salvato.data
            datiSalvati = salvato.data
        }
        do {
            let dati = try await Api.grezzo(richiesto)
            let nuovo: T = try Api.decodifica(dati, snake: snake)
            guard richiesto == percorso else { return }   // nel frattempo la schermata ha chiesto un altro indirizzo
            dato = nuovo
            percorsoDelDato = richiesto
            scaricatoIl = Date()
            datiSalvati = nil
            errore = nil
            if usaCache { Cache.salva(dati, richiesto) }
        } catch {
            guard richiesto == percorso else { return }
            if percorsoDelDato != richiesto {
                dato = nil   // niente dati di un altro indirizzo: meglio l'errore
            } else if dato != nil {
                datiSalvati = scaricatoIl   // il server non risponde: restano gli ultimi dati, con la loro data
            }
            errore = error.localizedDescription
        }
    }
}
