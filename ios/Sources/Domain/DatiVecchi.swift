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

    /// La frase della striscia, con `data` il momento in cui è stata salvata la copia. `motivo` nil = server non raggiungibile;
    /// altrimenti il messaggio dell'errore (già in italiano), in testa e con la nota fra parentesi come la web nello stesso caso
    /// (`comune.cache_errore` in `app.js`, #830): così un motivo come «Il server non risponde: riprova fra poco» non finisce dopo
    /// altri due punti, con la maiuscola a metà frase. Nella nota il giorno e l'ora della copia, ora italiana, scritti come
    /// `fData` e `fOra` della web: «dati salvati il 17 nov alle 10:05» (#845). Senza motivo lo stesso giorno e la stessa ora
    /// (prima l'orologio del telefono: a Londra la stessa copia era «alle 10:05» con il 502 e «09:05» senza rete).
    static func frase(salvatiIl data: Date, motivo: String?) -> String {
        let giorno = giornoEMese.string(from: data), ora = Quando.ora(data)
        guard let m = motivo?.trimmingCharacters(in: .whitespacesAndNewlines), !m.isEmpty else {
            return elidiGiorno("Non riesco a raggiungere SchieraXI. Quello che vedi è stato salvato il \(giorno) alle \(ora) e può essere vecchio.")
        }
        return elidiGiorno(Catalogo.Comune.cacheErrore(errore: m, giorno: giorno, ora: ora))
    }

    /// «il 8 nov» → «l'8 nov», «del 11 nov» → «dell'11 nov»: davanti a 8 e 11 (otto, undici) l'articolo perde la vocale, come
    /// `elidiGiorno` della web (`testi.js`). Anche le date con la barra: «dal 8/1» → «dall'8/1» (#859). Le altre date restano
    /// («il 18 nov», «il 1 nov»); gli ordinali («l'8ª») li fa `TempiLega.elidiOrdinali`. La usano anche le altre frasi con una
    /// data dopo l'articolo: «Utente · dall'8 ottobre 2026» (`TestiAccount`), «Rose aggiornate l'8 novembre 2026»
    /// (`ParoleSquadre`), «attiva dall'8/1» (`ParoleRegistro.taratura`).
    static func elidiGiorno(_ testo: String) -> String {
        testo.replacingOccurrences(of: #"\bil (0?8|11)(?=[ /])"#, with: "l'$1", options: .regularExpression)
            .replacingOccurrences(of: #"\b(del|al|dal|nel|sul) (0?8|11)(?=[ /])"#, with: "$1l'$2", options: .regularExpression)
    }

    /// «17 nov», ora italiana: come `fData` della web.
    private static let giornoEMese: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "d MMM"
        return f
    }()

    /// Dopo quanto tempo fuori dall'app, tornando, si ricarica tutto (anche dopo la mezzanotte, comunque).
    static let sogliaRitorno: TimeInterval = 10 * 60

    /// Tornando nell'app: si ricarica se si era usciti da almeno `sogliaRitorno` o se nel frattempo è cambiato il giorno (ora italiana).
    static func serveAggiornareAlRitorno(uscitaIl: Date?, adesso: Date) -> Bool {
        guard let uscitaIl else { return false }
        if adesso.timeIntervalSince(uscitaIl) >= sogliaRitorno { return true }
        return !calendario.isDate(uscitaIl, inSameDayAs: adesso)
    }

    static func rileggiPerLaScadenza(_ scadenza: Date?, fuoriDal: Date?, inBackgroundDal: Date?, adesso: Date) -> Bool {
        false
    }

    private static let calendario: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Europe/Rome") ?? .current
        return c
    }()
}
