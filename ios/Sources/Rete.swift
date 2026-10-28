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

    var errorDescription: String? {
        switch self {
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

    static func get<T: Decodable>(_ percorso: String) async throws -> T {
        let dati = try await scarica(percorso)
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        do {
            return try d.decode(T.self, from: dati)
        } catch {
            throw ErroreApi.dati(String(describing: error).prefix(160).description)
        }
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
    let percorso: String

    init(_ percorso: String) { self.percorso = percorso }

    func ricarica() async {
        inCorso = true
        defer { inCorso = false }
        do {
            dato = try await Api.get(percorso)
            errore = nil
        } catch {
            errore = error.localizedDescription
        }
    }
}
