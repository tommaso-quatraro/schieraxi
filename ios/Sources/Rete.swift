import SwiftUI

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

/// Carica un dato dal server e tiene lo stato (in caricamento, errore) per le schermate.
@MainActor
final class Caricatore<T: Decodable>: ObservableObject {
    @Published var dato: T?
    @Published var errore: String?
    @Published var inCorso = false
    var percorso: String
    let snake: Bool

    /// `snake: false` per i dati che vanno rimandati al server con le stesse chiavi (regole, impostazioni degli avvisi).
    init(_ percorso: String, snake: Bool = true) {
        self.percorso = percorso
        self.snake = snake
    }

    func ricarica(_ nuovoPercorso: String) async {
        percorso = nuovoPercorso
        await ricarica()
    }

    func ricarica() async {
        inCorso = true
        defer { inCorso = false }
        do {
            dato = try await Api.get(percorso, snake: snake)
            errore = nil
        } catch {
            errore = error.localizedDescription
        }
    }
}
