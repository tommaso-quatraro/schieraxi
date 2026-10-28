import SwiftUI

// Livello Data: tutto ciò che parla con il server sta qui. Le schermate (ViewModel) conoscono solo il protocollo `ServerClient`,
// così si possono usare dati finti nelle anteprime e nei test.

/// Indirizzo del server: predefinito dalla compilazione (Info.plist), modificabile dalla schermata Lega.
enum Config {
    static func testo(_ chiave: String) -> String {
        (Bundle.main.object(forInfoDictionaryKey: chiave) as? String) ?? ""
    }
    static var indirizzoPredefinito: String {
        // In modalità demo (fotografie nel simulatore) l'indirizzo vero non deve comparire.
        if Demo.attivo { return "https://server-demo.invalid:443" }
        return "https://\(testo("FantaHost")):\(testo("FantaPort"))"
    }
}

enum IndirizzoServer {
    /// Solo indirizzi https:// sono accettati (il traffico passa da rete privata ma il server parla in HTTPS).
    static func valido(_ testo: String) -> Bool {
        let t = testo.trimmingCharacters(in: .whitespaces)
        guard t.lowercased().hasPrefix("https://"), let url = URL(string: t), url.host != nil else { return false }
        return true
    }

    /// Indirizzo in uso: quello scritto nella schermata Lega (se valido, senza «/» finali), altrimenti quello della compilazione.
    static var attuale: String {
        var salvato = (UserDefaults.standard.string(forKey: "indirizzo") ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        while salvato.hasSuffix("/") { salvato.removeLast() }
        return valido(salvato) ? salvato : Config.indirizzoPredefinito
    }

    /// Testo da inserire in un indirizzo (nomi con spazi e simboli).
    static func codifica(_ testo: String) -> String {
        testo.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed.subtracting(CharacterSet(charactersIn: "&+=?#"))) ?? testo
    }
}

enum ErroreApi: LocalizedError {
    case indirizzoNonValido
    case risposta(Int)
    case dati(String)
    case rete(String)
    case timeout
    case server(String)

    var errorDescription: String? {
        switch self {
        case .server(let messaggio): return "Il server dice: \(messaggio)"
        case .indirizzoNonValido: return "L'indirizzo del server non è valido."
        case .risposta(let codice): return "Il server ha risposto con un errore (\(codice))."
        case .dati(let dettaglio): return "Risposta inattesa dal server. \(dettaglio)"
        case .timeout: return "Il server ci mette troppo a rispondere. Riprova tra poco."
        case .rete: return "Non riesco a raggiungere il server. Controlla che rete privata sia attivo."
        }
    }
}

/// Trasporto verso il server. Due soli metodi: tutto il resto (JSON, errori, testo) è nelle estensioni qui sotto.
protocol ServerClient: Sendable {
    /// Identifica il server in uso (la cache è separata per server).
    var indirizzo: String { get }
    /// Una richiesta HTTP; con `corpo` lo invia come JSON. Lancia `ErroreApi` se il server risponde con un errore.
    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data
    /// Carica un file (campo «file») in multipart e restituisce la risposta.
    func carica(_ percorso: String, nome: String, dati: Data) async throws -> Data
}

extension ServerClient {
    /// La risposta grezza (JSON) di un indirizzo, per poterla anche salvare nella cache.
    func grezzo(_ percorso: String) async throws -> Data {
        try await richiesta("GET", percorso, corpo: nil)
    }

    func get<T: Decodable>(_ percorso: String, snake: Bool = true) async throws -> T {
        try Decodifica.decodifica(try await grezzo(percorso), snake: snake)
    }

    /// Un file del server (foto, stemma): i byte così come arrivano.
    func binario(_ percorso: String) async throws -> Data {
        try await grezzo(percorso)
    }

    func testo(_ percorso: String) async throws -> String {
        String(decoding: try await grezzo(percorso), as: UTF8.self)
    }

    /// PUT/DELETE/POST senza corpo e senza risposta da leggere (osservati, ecc.).
    func invia(_ metodo: String, _ percorso: String) async throws {
        _ = try await richiesta(metodo, percorso, corpo: nil)
    }

    /// Invia un corpo JSON (POST/PUT) e restituisce la risposta grezza.
    func corpoJSON<B: Encodable>(_ metodo: String, _ percorso: String, _ corpo: B) async throws -> Data {
        try await richiesta(metodo, percorso, corpo: try JSONEncoder().encode(corpo))
    }

    func posta<T: Decodable, B: Encodable>(_ metodo: String = "POST", _ percorso: String, _ corpo: B, snake: Bool = true) async throws -> T {
        try Decodifica.decodifica(try await corpoJSON(metodo, percorso, corpo), snake: snake)
    }

    func caricaFile<T: Decodable>(_ percorso: String, nome: String, dati: Data) async throws -> T {
        try Decodifica.decodifica(try await carica(percorso, nome: nome, dati: dati))
    }
}

enum Decodifica {
    static func decodifica<T: Decodable>(_ dati: Data, snake: Bool = true) throws -> T {
        let d = JSONDecoder()
        if snake { d.keyDecodingStrategy = .convertFromSnakeCase }
        do {
            return try d.decode(T.self, from: dati)
        } catch {
            throw ErroreApi.dati(String(describing: error).prefix(160).description)
        }
    }
}

/// Il server vero, via URLSession.
struct ServerHTTP: ServerClient {
    var sessione: URLSession = .shared

    var indirizzo: String { IndirizzoServer.attuale }

    private func costruisci(_ percorso: String) throws -> URLRequest {
        guard let url = URL(string: indirizzo + percorso) else { throw ErroreApi.indirizzoNonValido }
        // Gli scambi (soprattutto 2 contro 2) fanno molti calcoli sul server: più tempo.
        var r = URLRequest(url: url, timeoutInterval: percorso.hasPrefix("/api/scambi") ? 90 : 25)
        r.setValue("1", forHTTPHeaderField: "X-Fanta")
        return r
    }

    /// Il messaggio d'errore del server ({"detail": "..."}), se c'è.
    private func messaggioServer(_ dati: Data, _ codice: Int) -> String {
        if let o = try? JSONSerialization.jsonObject(with: dati) as? [String: Any] {
            if let m = o["detail"] as? String { return m }
            if let lista = o["detail"] as? [[String: Any]], let m = lista.first?["msg"] as? String { return m }
        }
        return "errore \(codice)"
    }

    /// Se il server ha risposto con un errore, lo lancia con il suo messaggio (es. «Indica la tua squadra nella sezione Lega»).
    private func controlla(_ risposta: URLResponse, _ dati: Data) throws {
        if let h = risposta as? HTTPURLResponse, !(200..<300).contains(h.statusCode) {
            throw ErroreApi.server(messaggioServer(dati, h.statusCode))
        }
    }

    /// Traduce gli errori di rete: annullamento (resta tale), tempo scaduto, server non raggiungibile.
    private func traduci(_ e: Error) -> Error {
        if e is ErroreApi || e is CancellationError { return e }
        if let u = e as? URLError {
            if u.code == .cancelled { return CancellationError() }
            if u.code == .timedOut { return ErroreApi.timeout }
        }
        return ErroreApi.rete(e.localizedDescription)
    }

    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data {
        var r = try costruisci(percorso)
        r.httpMethod = metodo
        if let corpo {
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = corpo
        }
        do {
            let (dati, risposta) = try await sessione.data(for: r)
            try controlla(risposta, dati)
            return dati
        } catch {
            throw traduci(error)
        }
    }

    func carica(_ percorso: String, nome: String, dati: Data) async throws -> Data {
        var r = try costruisci(percorso)
        r.httpMethod = "POST"
        r.timeoutInterval = 120
        let confine = "Fanta-\(UUID().uuidString)"
        r.setValue("multipart/form-data; boundary=\(confine)", forHTTPHeaderField: "Content-Type")
        // Nel nome del file niente virgolette né a capo: romperebbero l'intestazione del multipart.
        let nomePulito = String(nome.filter { $0 != "\"" && !$0.isNewline && $0 != "\\" })
        var corpo = Data()
        corpo.append(Data("--\(confine)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(nomePulito)\"\r\nContent-Type: application/octet-stream\r\n\r\n".utf8))
        corpo.append(dati)
        corpo.append(Data("\r\n--\(confine)--\r\n".utf8))
        do {
            let (risposta, resp) = try await sessione.upload(for: r, from: corpo)
            try controlla(resp, risposta)
            return risposta
        } catch {
            throw traduci(error)
        }
    }
}

/// Il server che usano le parti dell'app fuori da SwiftUI (aggiornamento in background, Siri e Comandi, schermate secondarie di Lega).
/// Le schermate principali ricevono invece il client nel loro ViewModel; per le anteprime si sostituisce con `FinteServer`.
enum ServerCorrente {
    static var condiviso: any ServerClient = Demo.serverPredefinito()   // con l'argomento di lancio -DEMO: dati finti, senza rete
}

private struct ServerChiave: EnvironmentKey {
    static let defaultValue: any ServerClient = Demo.serverPredefinito()
}

extension EnvironmentValues {
    /// Il client del server, per chi lo preferisce nell'ambiente di SwiftUI.
    var server: any ServerClient {
        get { self[ServerChiave.self] }
        set { self[ServerChiave.self] = newValue }
    }
}

/// Server finto per le anteprime (`#Preview`) e i test: risponde con JSON preparati, scelti per prefisso dell'indirizzo.
struct FinteServer: ServerClient {
    var risposte: [String: String]
    /// Risposte non di testo (immagini): se restituisce dei byte per quell'indirizzo, vincono sulle risposte di testo.
    var binari: (@Sendable (String) -> Data?)? = nil
    var indirizzo: String { "https://finto.invalid" }

    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data {
        if metodo == "GET", let dati = binari?(percorso) { return dati }
        // Si sceglie la risposta con il prefisso più lungo che corrisponde.
        let chiavi = risposte.keys.filter { percorso.hasPrefix($0) }.sorted { $0.count > $1.count }
        guard let chiave = chiavi.first, let testo = risposte[chiave] else {
            // Salvataggi e modifiche (PUT, POST, DELETE) senza una risposta preparata vanno a buon fine con una risposta vuota.
            if metodo != "GET" { return Data("{}".utf8) }
            throw ErroreApi.server("anteprima: nessun dato per \(percorso)")
        }
        return Data(testo.utf8)
    }

    func carica(_ percorso: String, nome: String, dati: Data) async throws -> Data {
        try await richiesta("POST", percorso, corpo: nil)
    }
}
