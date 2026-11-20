import Foundation

/// Quando i dati a video non sono freschi: la frase della striscia «dati salvati» e quando ricaricare tornando nell'app.
enum DatiVecchi {
    /// Telefono senza rete, server che non risponde o troppo lento: solo qui si dice «non riesco a raggiungere SchieraXI». Ogni
    /// altro errore (limite raggiunto, guasto del server, risposta che l'app non capisce) ha il suo messaggio, che va mostrato.
    static func eDiRete(_ errore: Error) -> Bool {
        if let e = errore as? ErroreApi {
            switch e {
            case .rete, .senzaRete, .timeout: return true
            default: return false
            }
        }
        return errore is URLError
    }

    /// La frase della striscia. `motivo` nil = server non raggiungibile; altrimenti il messaggio dell'errore (già in italiano), in
    /// testa e con la nota fra parentesi come la web nello stesso caso (`comune.cache_errore` in `app.js`, #830): così un motivo
    /// come «Il server non risponde: riprova fra poco» non finisce dopo altri due punti, con la maiuscola a metà frase.
    static func frase(salvatiIl data: Date, motivo: String?) -> String {
        guard let m = motivo?.trimmingCharacters(in: .whitespacesAndNewlines), !m.isEmpty else {
            let quando = data.formatted(date: .abbreviated, time: .shortened)
            return "Non riesco a raggiungere SchieraXI. Quello che vedi è stato salvato il \(quando) e può essere vecchio."
        }
        return Catalogo.Comune.cacheErrore(errore: m)
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
