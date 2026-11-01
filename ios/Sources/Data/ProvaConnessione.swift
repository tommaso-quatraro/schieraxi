import Foundation

/// Com'è andata la prova di connessione al server. Un 401 vuol dire «raggiunto, chiede l'accesso»: è un successo
/// (con gli account accesi il server risponde 401 anche a /api/stato).
enum EsitoConnessione: Equatable {
    case raggiunto(versione: String?, squadra: String?)
    /// Raggiunto e con una sessione valida: «Connesso come <nome>».
    case connesso(utente: String)
    /// Raggiunto, ma la sessione salvata non vale più (scaduta o chiusa altrove): serve accedere di nuovo.
    case sessioneScaduta
    case chiedeAccesso
    case rifiutato(Int)
    case nonSchieraxi
    case nonRaggiungibile
    case certificato
    case timeout
    case erroreServer(Int)
    case indirizzoNonValido

    /// Il server giusto c'è: si può salvare l'indirizzo.
    var raggiunto: Bool {
        switch self {
        case .raggiunto, .connesso, .chiedeAccesso, .sessioneScaduta: return true
        default: return false
        }
    }

    var titolo: String {
        switch self {
        case .raggiunto: return "Server raggiunto"
        case .connesso(let utente): return "Connesso come \(utente)"
        case .sessioneScaduta: return "Server raggiunto: la sessione è scaduta"
        case .chiedeAccesso: return "Server raggiunto: chiede l'accesso"
        case .rifiutato(let codice): return "Il server ha rifiutato la richiesta (codice \(codice))"
        case .nonSchieraxi: return "Non sembra un server di SchieraXI"
        case .nonRaggiungibile: return "Server non raggiungibile"
        case .certificato: return "Collegamento sicuro non riuscito"
        case .timeout: return "Il server non risponde in tempo"
        case .erroreServer(let codice): return "Il server ha un problema (codice \(codice))"
        case .indirizzoNonValido: return "Indirizzo non valido"
        }
    }

    var dettaglio: String {
        switch self {
        case .raggiunto(let versione, let squadra):
            let parti = [versione.map { "versione \($0)" }, squadra.map { "squadra \($0)" }].compactMap { $0 }
            return parti.isEmpty ? "Tutto a posto." : "SchieraXI, " + parti.joined(separator: ", ") + "."
        case .connesso:
            return "Il server risponde e la tua sessione è valida."
        case .sessioneScaduta:
            return "È il server giusto, ma la sessione non vale più: esci e accedi di nuovo."
        case .chiedeAccesso:
            return "È il server giusto e vuole nome utente e password: accedi dalla schermata di accesso."
        case .rifiutato:
            return "Qualcosa lungo la strada (firewall o proxy) blocca l'app. Controlla la connessione e l'indirizzo."
        case .nonSchieraxi:
            return "L'indirizzo risponde, ma non è il server di SchieraXI. Controlla l'indirizzo e la porta."
        case .nonRaggiungibile:
            return "Controlla la connessione e che l'indirizzo sia scritto giusto. Se il tuo server si raggiunge solo con una VPN, tienila accesa."
        case .certificato:
            return "Il collegamento sicuro non è riuscito: il certificato di sicurezza del server non è valido o l'indirizzo non inizia con https. Controlla l'indirizzo."
        case .timeout:
            return "Il server ci mette troppo. Controlla la connessione e riprova tra poco."
        case .erroreServer:
            return "Il server è raggiungibile ma ha un problema. Riprova tra poco."
        case .indirizzoNonValido:
            return "Deve iniziare con https:// e non contenere nome utente o password."
        }
    }

    var icona: String {
        switch self {
        case .raggiunto, .connesso: return "checkmark.circle.fill"
        case .sessioneScaduta: return "person.crop.circle.badge.exclamationmark"
        case .chiedeAccesso: return "lock.circle.fill"
        case .rifiutato: return "hand.raised.circle.fill"
        case .nonSchieraxi: return "questionmark.circle.fill"
        case .nonRaggiungibile: return "wifi.exclamationmark"
        case .certificato: return "lock.trianglebadge.exclamationmark.fill"
        case .timeout: return "clock.badge.exclamationmark.fill"
        case .erroreServer: return "exclamationmark.triangle.fill"
        case .indirizzoNonValido: return "exclamationmark.triangle.fill"
        }
    }
}

/// La prova di connessione: una richiesta a /api/stato, SENZA token e senza passare dal client normale (così un 401 non
/// manda l'app alla schermata di accesso e l'indirizzo si prova prima di salvarlo).
enum ProvaConnessione {
    /// Come si legge una risposta (funzione pura, provata con risposte finte).
    static func interpreta(codice: Int, corpo: Data) -> EsitoConnessione {
        let oggetto = (try? JSONSerialization.jsonObject(with: corpo)) as? [String: Any]
        switch codice {
        case 200..<300:
            // Il server di SchieraXI manda lo stato con questi campi; una pagina HTML o un altro JSON non è il nostro server.
            let chiavi = ["stagione", "prossima_giornata", "ultimo_aggiornamento", "mia_squadra", "versione"]
            guard let oggetto, chiavi.contains(where: { oggetto[$0] != nil }) else { return .nonSchieraxi }
            return .raggiunto(versione: oggetto["versione"] as? String, squadra: oggetto["mia_squadra"] as? String)
        case 401:
            // Il nostro server risponde {"detail": "..."}; una pagina di accesso HTML di un altro servizio no.
            return oggetto?["detail"] is String ? .chiedeAccesso : .nonSchieraxi
        case 403:
            return .rifiutato(403)
        case 500..<600:
            return .erroreServer(codice)
        default:
            return .nonSchieraxi
        }
    }

    /// Come si legge un errore di rete.
    static func interpreta(errore: Error) -> EsitoConnessione {
        guard let u = errore as? URLError else { return .nonRaggiungibile }
        switch u.code {
        case .timedOut: return .timeout
        case .secureConnectionFailed, .serverCertificateUntrusted, .serverCertificateHasBadDate, .serverCertificateHasUnknownRoot,
             .serverCertificateNotYetValid, .clientCertificateRejected, .clientCertificateRequired, .appTransportSecurityRequiresSecureConnection:
            return .certificato
        default: return .nonRaggiungibile
        }
    }

    /// L'indirizzo ripulito (spazi e «/» finali), o `nil` se non è ammesso (solo https, o http verso questo stesso computer).
    static func pulisci(_ testo: String) -> String? {
        var t = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        while t.hasSuffix("/") { t.removeLast() }
        return IndirizzoServer.valido(t) ? t : nil
    }

    static func sessionePredefinita() -> URLSession {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 8
        c.timeoutIntervalForResource = 10
        c.waitsForConnectivity = false
        return URLSession(configuration: c)
    }

    /// Con `token` (la sessione salvata per QUESTO indirizzo) la prova dice se la sessione vale ancora.
    /// Il token si manda solo all'indirizzo per cui è stato salvato (l'archivio è per indirizzo): mai a uno nuovo.
    static func prova(_ indirizzo: String, sessione: URLSession? = nil, archivio: (any ArchivioToken)? = Accesso.archivio) async -> EsitoConnessione {
        guard let base = pulisci(indirizzo), let url = URL(string: base + "/api/stato") else { return .indirizzoNonValido }
        var r = URLRequest(url: url, timeoutInterval: 8)
        r.setValue("1", forHTTPHeaderField: "X-Fanta")
        LinguaServer.applica(&r)
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        let token = archivio?.leggi(server: base)
        if let token, !token.isEmpty { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        do {
            let (dati, risposta) = try await (sessione ?? sessionePredefinita()).data(for: r)
            guard let h = risposta as? HTTPURLResponse else { return .nonSchieraxi }
            // Un corpo enorme non è lo stato del nostro server: non lo si legge per intero.
            let esito = interpreta(codice: h.statusCode, corpo: dati.count > 1_000_000 ? Data() : dati)
            // Con un token mandato, un 401 vuol dire «sessione scaduta», non «serve il primo accesso».
            if token != nil, case .chiedeAccesso = esito { return .sessioneScaduta }
            return esito
        } catch {
            return interpreta(errore: error)
        }
    }
}
