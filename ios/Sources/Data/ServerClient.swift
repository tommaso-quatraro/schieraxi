import SwiftUI

// Livello Data: tutto ciò che parla con il server sta qui. Le schermate (ViewModel) conoscono solo il protocollo `ServerClient`,
// così si possono usare dati finti nelle anteprime e nei test.
/// Il server pubblico dell'app è il predefinito (un dominio pubblico, non un indirizzo privato). Chi ne ha uno proprio lo scrive
/// in Impostazioni > Server (o nell'area avanzata dell'accesso) e resta sul telefono, in `UserDefaults` («indirizzo»).
enum Config {
    /// Il server pubblico dell'app (un dominio pubblico, non un indirizzo privato). Chi ne ha uno proprio lo cambia in Impostazioni > Server;
    /// chi ha già un indirizzo salvato lo tiene. In modalità demo (fotografie nel simulatore) c'è un indirizzo finto.
    static var indirizzoPredefinito: String {
        Demo.attivo ? "https://server-demo.invalid:443" : ServerPubblico.indirizzo
    }
    /// Esempio mostrato nei campi di testo (non è un indirizzo vero e non viene mai usato).
    static let esempioIndirizzo = "https://nome-del-server.example"
}

enum IndirizzoServer {
    /// Solo indirizzi https:// sono accettati (il server parla in HTTPS).
    static func valido(_ testo: String) -> Bool {
        let t = testo.trimmingCharacters(in: .whitespaces)
        guard let url = URL(string: t), let host = url.host?.lowercased(), !host.isEmpty else { return false }
        // niente «utente:password@» dentro l'indirizzo
        if url.user != nil || url.password != nil { return false }
        switch url.scheme?.lowercased() {
        case "https": return true
        case "http": return eLocale(host)   // il testo in chiaro solo verso questo stesso computer (prove), mai verso la rete
        default: return false
        }
    }

    /// localhost, 127.0.0.1, ::1: il traffico non esce dal computer.
    static func eLocale(_ host: String) -> Bool {
        ["localhost", "127.0.0.1", "::1", "[::1]"].contains(host.lowercased())
    }

    /// Manca l'indirizzo: non succede mai (senza uno scelto vale il predefinito), resta per sicurezza.
    static var manca: Bool { attuale.isEmpty }

    /// Indirizzo in uso: quello scritto dall'utente (se valido, senza «/» finali), altrimenti il predefinito pubblico dell'app (in demo uno finto).
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
    /// 401: serve l'accesso (account) oppure nome utente e password sono sbagliati. Il testo è quello del server, già in italiano.
    case accessoRichiesto(String)
    /// 429 (o altro limite): troppi tentativi o troppe richieste; con l'attesa in secondi se il server la indica (`Retry-After`).
    case troppiTentativi(String, riprovaTra: Int?)
    /// 412: i dati sono stati cambiati da un altro dispositivo dopo l'ultima lettura (If-Match non corrisponde).
    case conflitto
    /// 404 con il campo `funzione`: la funzione è spenta per questo utente. Non è un guasto: niente «Riprova».
    case funzioneSpenta(funzione: String, messaggio: String)
    /// Un errore con un nome breve per l'app (campo `codice`, per esempio «serve_riconferma»), accanto al messaggio del server.
    case codificato(codice: String, messaggio: String)

    /// Il server ha detto 412: i dati sono cambiati da un altro dispositivo (la schermata deve ricaricare).
    var eConflitto: Bool { if case .conflitto = self { return true } else { return false } }

    var errorDescription: String? {
        switch self {
        case .server(let messaggio): return "Il server dice: \(messaggio)"
        case .accessoRichiesto(let messaggio): return messaggio
        case .troppiTentativi(let messaggio, let attesa):
            guard let attesa, attesa > 0 else { return messaggio }
            // Il messaggio del server può già dire «Riprova domani»: si toglie, resta il tempo vero, una volta sola.
            return "\(Self.senzaInvitoARiprovare(messaggio)) Riprova tra \(Self.tempoLeggibile(attesa))."
        case .conflitto: return "È cambiato da un altro dispositivo: ho ricaricato i dati. Controlla e rifai la modifica."
        case .funzioneSpenta(_, let messaggio): return messaggio
        case .codificato(let codice, let messaggio): return TestiSocial.errore(codice: codice) ?? messaggio
        case .indirizzoNonValido:
            return IndirizzoServer.manca ? "Manca l'indirizzo del server: scrivilo nelle Impostazioni." : "L'indirizzo del server non è valido."
        case .risposta(let codice): return Self.testoRisposta(codice)
        case .dati: return "Il server ha mandato una risposta che l'app non capisce. Riprova tra poco; se succede ancora, aggiorna l'app."
        case .timeout: return "Il server ci mette troppo a rispondere. Controlla la connessione e riprova tra poco."
        case .rete: return "Non riesco a raggiungere il server. Controlla la connessione e che il server sia acceso."
        }
    }

    /// Una risposta d'errore senza il JSON del server (pagina HTML, testo): per 401 e 403 di solito c'è di mezzo una rete o un indirizzo
    /// sbagliato, non un guasto del server.
    static func testoRisposta(_ codice: Int) -> String {
        if codice == 401 || codice == 403 {
            return "Il server ha rifiutato la richiesta (codice \(codice)). Controlla l'indirizzo del server e la rete (un Wi-Fi con accesso da fare, un blocco di rete) e riprova."
        }
        return "Il server ha un problema (codice \(codice)). Riprova tra poco."
    }

    /// Un'attesa in parole: «30 secondi», «10 minuti», «6 h 55 min», «2 giorni».
    static func tempoLeggibile(_ secondi: Int) -> String {
        if secondi < 90 { return "\(secondi) secondi" }
        let minuti = (secondi + 59) / 60
        if minuti < 90 { return "\(minuti) minuti" }
        let ore = minuti / 60
        if ore >= 48 { return "\(ore / 24) giorni" }
        let resto = minuti % 60
        return resto == 0 ? "\(ore) h" : "\(ore) h \(resto) min"
    }

    /// Il messaggio senza le frasi che cominciano con «Riprova» (le sostituisce il tempo che manca).
    static func senzaInvitoARiprovare(_ messaggio: String) -> String {
        let pulito = messaggio.replacingOccurrences(of: #"\s*Riprova[^.!]*[.!]?"#, with: "", options: [.regularExpression, .caseInsensitive])
        return pulito.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Un limite raggiunto (429): riprovare subito non serve a niente.
    var eLimite: Bool { if case .troppiTentativi = self { return true } else { return false } }
}

/// Trasporto verso il server. Due soli metodi: tutto il resto (JSON, errori, testo) è nelle estensioni qui sotto.
protocol ServerClient: Sendable {
    /// Identifica il server in uso (la cache è separata per server).
    var indirizzo: String { get }
    /// Una richiesta HTTP; con `corpo` lo invia come JSON. Lancia `ErroreApi` se il server risponde con un errore.
    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data
    /// Carica un file (campo «file») in multipart, con il suo tipo (Content-Type), e restituisce la risposta.
    func carica(_ percorso: String, nome: String, dati: Data, tipo: String) async throws -> Data
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

    /// Un file senza un tipo preciso (immagini): `application/octet-stream`.
    func carica(_ percorso: String, nome: String, dati: Data) async throws -> Data {
        try await carica(percorso, nome: nome, dati: dati, tipo: "application/octet-stream")
    }

    func caricaFile<T: Decodable>(_ percorso: String, nome: String, dati: Data, tipo: String = "application/octet-stream") async throws -> T {
        try Decodifica.decodifica(try await carica(percorso, nome: nome, dati: dati, tipo: tipo))
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

/// Dove gira l'app.
enum Ambiente {
    /// true quando l'app fa da contenitore dei test automatici (XCTest la avvia con questa variabile): niente schermate e niente rete vera.
    static let ospiteDeiTest = ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil
}

/// Il server vero, via URLSession.
struct ServerHTTP: ServerClient {
    var sessione: URLSession = .shared
    /// Dove sta il token di accesso (Keychain). Con un server senza account non c'è nessun token e non si manda niente.
    var archivioToken: any ArchivioToken = Accesso.archivio
    /// Il server risponde 202 «sto calcolando»: si riprova dopo questi secondi (se il server non dice altro) fino a `massimoTentativiCalcolo` volte.
    var attesaCalcolo: TimeInterval = 3
    var massimoTentativiCalcolo = 40

    var indirizzo: String { IndirizzoServer.attuale }

    private func costruisci(_ percorso: String, token: String?) throws -> URLRequest {
        // Nei test automatici la rete vera è vietata: ogni test passa una sessione finta (URLProtocol). Una richiesta con la
        // sessione di sistema arriverebbe al server di produzione dai Mac di GitHub: si ferma qui, senza partire.
        if Ambiente.ospiteDeiTest, sessione === URLSession.shared {
            throw ErroreApi.rete("rete vera vietata nei test")
        }
        let base = indirizzo
        // Il token e le password non viaggiano mai in chiaro: solo https (o questo stesso computer, per le prove).
        guard IndirizzoServer.valido(base), let url = URL(string: base + percorso) else { throw ErroreApi.indirizzoNonValido }
        // Gli scambi (soprattutto 2 contro 2) fanno molti calcoli sul server: più tempo. Accesso e account: 20 secondi,
        // poi un messaggio chiaro e si può riprovare.
        let attesa: TimeInterval = percorso.hasPrefix("/api/scambi") ? 90 : (percorso.hasPrefix("/api/account/") ? 20 : 25)
        var r = URLRequest(url: url, timeoutInterval: attesa)
        r.setValue("1", forHTTPHeaderField: "X-Fanta")
        LinguaServer.applica(&r)
        // Account: l'app nativa manda il token come «Bearer» (niente cookie). Il token non si scrive mai nei log.
        if let token, !token.isEmpty {
            r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return r
    }

    /// I percorsi in cui un 401 vuol dire «nome o password sbagliati» e non «la sessione è finita».
    private static func eDiAccesso(_ percorso: String) -> Bool {
        ["/api/account/accedi", "/api/account/registra", "/api/account/recupero"].contains { percorso.hasPrefix($0) }
    }

    private static func secondi(_ h: HTTPURLResponse) -> Int? {
        Int((h.value(forHTTPHeaderField: "Retry-After") ?? "").trimmingCharacters(in: .whitespaces))
    }

    /// Il messaggio d'errore del server ({"detail": "..."}), se c'è.
    private func messaggioServer(_ dati: Data, _ codice: Int) -> String {
        if let o = try? JSONSerialization.jsonObject(with: dati) as? [String: Any] {
            if let m = o["detail"] as? String { return m }
            if let lista = o["detail"] as? [[String: Any]], let m = lista.first?["msg"] as? String { return m }
        }
        return "errore \(codice)"
    }

    /// La risposta è il JSON d'errore del nostro server: un oggetto con il campo `detail` di testo.
    static func eJsonDelServer(_ dati: Data) -> Bool {
        ((try? JSONSerialization.jsonObject(with: dati)) as? [String: Any])?["detail"] is String
    }

    /// Il campo `funzione` di un 404 ({"detail": "...", "funzione": "live"}), se c'è e non è vuoto.
    static func funzioneSpenta(_ dati: Data) -> String? {
        guard let o = try? JSONSerialization.jsonObject(with: dati) as? [String: Any],
              let f = o["funzione"] as? String, !f.isEmpty else { return nil }
        return f
    }

    /// Se il server ha risposto con un errore, lo lancia con il suo messaggio (es. «Indica la tua squadra nella sezione Lega»).
    /// 401 e 429 hanno errori a parte (accesso richiesto, troppi tentativi con l'attesa); un 401 fuori dalle schermate di accesso
    /// avvisa l'app (notifica `.accessoRichiesto`): la sessione è finita e si torna alla schermata di accesso.
    private func controlla(_ risposta: URLResponse, _ dati: Data, percorso: String, token: String?) throws {
        guard let h = risposta as? HTTPURLResponse, !(200..<300).contains(h.statusCode) else { return }
        let messaggio = messaggioServer(dati, h.statusCode)
        switch h.statusCode {
        case 401:
            // Solo un 401 col JSON del nostro server ({"detail": "..."}) chiude la sessione o cambia le modalità: una pagina di accesso
            // di un Wi-Fi pubblico, un proxy o un altro servizio no (come in `ProvaConnessione`).
            guard Self.eJsonDelServer(dati) else { throw ErroreApi.risposta(401) }
            UserDefaults.standard.set(ModalitaRegistrazione.leggi(corpo: dati).rawValue, forKey: ModalitaRegistrazione.chiave)
            ServiziSociali.salva(ServiziSociali.leggi(corpo: dati))   // i pulsanti «Continua con Google» solo se il server li dichiara
            if !Self.eDiAccesso(percorso) {
                // Si dice quale token ha fallito (solo un'impronta): se nel frattempo si è fatto un nuovo accesso, un 401 in ritardo
                // di una richiesta vecchia non deve buttare fuori la sessione nuova.
                var info: [String: Any] = ["server": indirizzo, "percorso": percorso]
                if let token { info["impronta"] = token.hashValue }
                DispatchQueue.main.async {
                    NotificationCenter.default.post(name: .accessoRichiesto, object: nil, userInfo: info)
                }
            }
            throw ErroreApi.accessoRichiesto(messaggio)
        case 412:
            throw ErroreApi.conflitto
        case 404:
            // Funzione spenta: il server lo dice con il campo «funzione». Si avvisa l'app (la nasconde) e si spiega, senza «Riprova».
            if let funzione = Self.funzioneSpenta(dati) {
                let testo = messaggio.dicePerFunzioneSpenta ? messaggio : "Questa funzione \(String.fraseFunzioneSpenta)."
                DispatchQueue.main.async {
                    NotificationCenter.default.post(name: .funzioneSpenta, object: nil, userInfo: ["funzione": funzione])
                }
                throw ErroreApi.funzioneSpenta(funzione: funzione, messaggio: testo)
            }
            if messaggio == "errore \(h.statusCode)" { throw ErroreApi.risposta(h.statusCode) }
            throw ErroreApi.server(messaggio)
        case 429:
            throw ErroreApi.troppiTentativi(messaggio, riprovaTra: Self.secondi(h))
        default:
            // Una pagina HTML o un testo qualsiasi al posto del JSON di errore (proxy, server sbagliato): niente messaggio del server.
            if messaggio == "errore \(h.statusCode)" { throw ErroreApi.risposta(h.statusCode) }
            if let codice = Self.codiceErrore(dati) { throw ErroreApi.codificato(codice: codice, messaggio: messaggio) }
            throw ErroreApi.server(messaggio)
        }
    }

    /// Il campo `codice` di un errore ({"detail": "...", "codice": "serve_riconferma"}), se c'è: solo lettere minuscole e trattino basso.
    static func codiceErrore(_ dati: Data) -> String? {
        guard let o = try? JSONSerialization.jsonObject(with: dati) as? [String: Any],
              let c = o["codice"] as? String, !c.isEmpty, c.count <= 40,
              c.allSatisfy({ $0.isASCII && ($0.isLowercase || $0 == "_") }) else { return nil }
        return c
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
        var tentativiDiCalcolo = 0
        while true {
            let token = archivioToken.leggi(server: indirizzo)
            var r = try costruisci(percorso, token: token)
            r.httpMethod = metodo
            if let corpo {
                r.setValue("application/json", forHTTPHeaderField: "Content-Type")
                r.httpBody = corpo
            }
            // Risorse personali con ETag: chi scrive rimanda l'ETag che ha letto; se nel frattempo è cambiato il server risponde 412.
            let risorsa = VersioniRisorse.risorsa(per: percorso, corpo: corpo)
            if let risorsa, metodo != "GET", metodo != "HEAD",
               let visto = VersioniRisorse.condivise.leggi(server: indirizzo, risorsa: risorsa) {
                r.setValue(visto, forHTTPHeaderField: "If-Match")
            }
            do {
                let (dati, risposta) = try await sessione.data(for: r)
                if let risorsa, let h = risposta as? HTTPURLResponse, let nuovo = h.value(forHTTPHeaderField: "ETag") {
                    VersioniRisorse.condivise.imposta(nuovo, server: indirizzo, risorsa: risorsa)
                }
                // 202: il server sta calcolando (formazione, scambi con gli account accesi). Si riprova da soli: la schermata
                // intanto mostra il marchio che si muove.
                if let h = risposta as? HTTPURLResponse, h.statusCode == 202, !Self.eDiAccesso(percorso) {
                    tentativiDiCalcolo += 1
                    if tentativiDiCalcolo > massimoTentativiCalcolo {
                        throw ErroreApi.server("Il calcolo sta durando più del solito. Riprova tra poco.")
                    }
                    let attesa = Self.secondi(h).map(TimeInterval.init) ?? attesaCalcolo
                    try await Task.sleep(nanoseconds: UInt64(max(0, attesa) * 1_000_000_000))
                    continue
                }
                try controlla(risposta, dati, percorso: percorso, token: token)
                return dati
            } catch {
                throw traduci(error)
            }
        }
    }

    func carica(_ percorso: String, nome: String, dati: Data, tipo: String) async throws -> Data {
        let token = archivioToken.leggi(server: indirizzo)
        var r = try costruisci(percorso, token: token)
        r.httpMethod = "POST"
        r.timeoutInterval = 120
        let confine = "Schieraxi-\(UUID().uuidString)"
        r.setValue("multipart/form-data; boundary=\(confine)", forHTTPHeaderField: "Content-Type")
        // Nel nome del file niente virgolette né a capo: romperebbero l'intestazione del multipart.
        let nomePulito = String(nome.filter { $0 != "\"" && !$0.isNewline && $0 != "\\" })
        // Anche il tipo finisce in un'intestazione: niente a capo (altrimenti si potrebbero iniettare altre intestazioni).
        let tipoPulito = String(tipo.filter { !$0.isNewline && $0 != "\r" })
        var corpo = Data()
        corpo.append(Data("--\(confine)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(nomePulito)\"\r\nContent-Type: \(tipoPulito)\r\n\r\n".utf8))
        corpo.append(dati)
        corpo.append(Data("\r\n--\(confine)--\r\n".utf8))
        do {
            let (risposta, resp) = try await sessione.upload(for: r, from: corpo)
            try controlla(resp, risposta, percorso: percorso, token: token)
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
    /// Indirizzi (per prefisso) a cui il server finto risponde con un errore del server, col messaggio dato (per le demo).
    var errori: [String: String] = [:]
    /// Come `errori`, ma con un errore preciso (rete, limite di tentativi...): per le demo degli stati d'errore.
    var fallimenti: [String: ErroreApi] = [:]
    /// L'indirizzo che dichiara (la cache su disco è per indirizzo: una demo con dati diversi ne usa uno suo).
    var indirizzoFinto = "https://finto.invalid"
    var indirizzo: String { indirizzoFinto }

    func richiesta(_ metodo: String, _ percorso: String, corpo: Data?) async throws -> Data {
        if let chiave = fallimenti.keys.first(where: { percorso.hasPrefix($0) }), let errore = fallimenti[chiave] { throw errore }
        if let chiave = errori.keys.first(where: { percorso.hasPrefix($0) }), let messaggio = errori[chiave] { throw ErroreApi.server(messaggio) }
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

    func carica(_ percorso: String, nome: String, dati: Data, tipo: String) async throws -> Data {
        try await richiesta("POST", percorso, corpo: nil)
    }
}
