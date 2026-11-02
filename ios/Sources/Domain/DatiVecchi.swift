import Foundation

/// Quando i dati a video non sono freschi: la frase della striscia «dati salvati» e quando ricaricare tornando nell'app.
enum DatiVecchi {
    /// Rete assente o server troppo lento: solo qui si dice «non riesco a raggiungere SchieraXI». Ogni altro errore
    /// (limite raggiunto, guasto del server, risposta che l'app non capisce) ha il suo messaggio, che va mostrato.
    static func eDiRete(_ errore: Error) -> Bool {
        if let e = errore as? ErroreApi {
            switch e {
            case .rete, .timeout: return true
            default: return false
            }
        }
        return errore is URLError
    }

    /// La frase della striscia. `motivo` nil = server non raggiungibile; altrimenti il messaggio dell'errore (già in italiano).
    static func frase(salvatiIl data: String, motivo: String?) -> String {
        guard let m = motivo?.trimmingCharacters(in: .whitespacesAndNewlines), !m.isEmpty else {
            return "Non riesco a raggiungere SchieraXI. Quello che vedi è stato salvato il \(data) e può essere vecchio."
        }
        let punto = m.last.map { ".!?".contains($0) } == true ? "" : "."
        return "Non ho potuto aggiornare: \(m)\(punto) Quello che vedi è del \(data) e può essere vecchio."
    }

    /// Dopo quanto tempo fuori dall'app, tornando, si ricarica tutto (anche dopo la mezzanotte, comunque).
    static let sogliaRitorno: TimeInterval = 10 * 60

    /// Tornando nell'app: si ricarica se si era usciti da almeno `sogliaRitorno` o se nel frattempo è cambiato il giorno (ora italiana).
    static func serveAggiornareAlRitorno(uscitaIl: Date?, adesso: Date) -> Bool {
        guard let uscitaIl else { return false }
        if adesso.timeIntervalSince(uscitaIl) >= sogliaRitorno { return true }
        return !calendario.isDate(uscitaIl, inSameDayAs: adesso)
    }

    private static let calendario: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Europe/Rome") ?? .current
        return c
    }()
}
