import Foundation

/// Il token del widget (`fw_...`): un token a scopo limitato, emesso dal server (`POST /api/account/token-widget`), valido 90 giorni,
/// uno per dispositivo (legato alla sessione che lo chiede: iPhone e iPad dello stesso account hanno ognuno il suo, dal 26/11/2026),
/// che permette SOLO di leggere `/api/oggi`, `/api/widget` e la diretta (live). È l'unica cosa che l'app dà al widget (nel file condiviso
/// dell'App Group e nel codice di collegamento): il token della SESSIONE non esce mai dal Keychain dell'app.
enum TokenWidget {
    static let servizio = "it.schieraxi.app.widget"
    private static let chiaveScadenza = "tokenWidgetScade"
    nonisolated(unsafe) static var archivio: any ArchivioToken = Demo.daLancio ? MemoriaToken() : KeychainToken(servizio: servizio)

    /// Dove stanno il token del widget e le copie per il widget. `sistema`: il Keychain, il file del gruppo e il Keychain condiviso
    /// veri, letti al momento della chiamata. I test ne passano di finti, così non scrivono mai nei file veri.
    struct Luoghi {
        var archivio: any ArchivioToken
        /// La scadenza del token e la copia del widget fuori dal gruppo.
        var memoria: UserDefaults
        /// La cartella del gruppo (nil = il gruppo non c'è).
        var cartella: () -> URL?
        /// Il Keychain condiviso con il widget (`PortachiaviCondiviso`).
        var portachiavi: any ArchivioCollegamento
        /// Ripassa al widget indirizzo e token (`Accesso.sincronizzaConIlWidget`).
        var sincronizza: () -> Void

        static var sistema: Luoghi {
            Luoghi(archivio: TokenWidget.archivio, memoria: .standard, cartella: { Condiviso.cartella() },
                   portachiavi: PortachiaviCondiviso.archivio, sincronizza: { _ = Accesso.sincronizzaConIlWidget() })
        }
    }

    /// Un token del widget accettabile: comincia per `fw_`, breve e di caratteri semplici (un server ostile potrebbe mandare altro).
    static func valido(_ testo: String) -> Bool {
        testo.hasPrefix("fw_") && testo.utf8.count >= 12 && Accesso.tokenValido(testo)
    }

    static func leggi(server indirizzo: String) -> String? {
        leggi(server: indirizzo, in: archivio)
    }

    /// Il token del widget per questo indirizzo, solo se il widget non ha segnalato che il server lo rifiuta (`rifiutato`): è quello
    /// che dice se il widget è collegato (Impostazioni > App).
    static func accettato(server indirizzo: String, cartella: URL? = Condiviso.cartella()) -> String? {
        guard let t = leggi(server: indirizzo), !rifiutato(t, indirizzo: indirizzo, cartella: cartella) else { return nil }
        return t
    }

    /// Il widget ha segnalato (`SegnaleWidget`) che il server gli ha rifiutato proprio questo token (401)? Il segnale porta solo
    /// l'impronta del collegamento: si confronta con quella di indirizzo e token. Senza gruppo, senza segnale o senza token: no.
    static func rifiutato(_ token: String?, indirizzo: String, cartella: URL?) -> Bool {
        guard let token, let segnale = SegnaleWidget.leggi(cartella: cartella) else { return false }
        return segnale.chi == MemoriaWidget.impronta(indirizzo: indirizzo, token: token)
    }

    private static func leggi(server indirizzo: String, in archivio: any ArchivioToken) -> String? {
        guard let t = archivio.leggi(server: indirizzo), valido(t) else { return nil }
        return t
    }

    private static let formatoScadenza: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return f
    }()

    /// Va rinnovato? Manca il token, o scade entro 7 giorni (o la scadenza non si legge).
    static func daRinnovare(token: String?, scade: String?, adesso: Date = Date()) -> Bool {
        guard token != nil else { return true }
        guard let scade, let data = leggiScadenza(scade) else { return true }
        return data.timeIntervalSince(adesso) < 7 * 24 * 3600
    }

    /// La scadenza come la manda il server: con il fuso («...+00:00», «...Z») vale quello; senza fuso è ora italiana.
    static func leggiScadenza(_ testo: String) -> Date? {
        let t = testo.trimmingCharacters(in: .whitespaces)
        let resto = t.dropFirst(19)
        // I decimali dei secondi («.123456») si ignorano: contano solo l'ora e il fuso.
        let senzaDecimali = resto.drop(while: { $0 == "." || $0.isNumber })
        if senzaDecimali.isEmpty { return formatoScadenza.date(from: String(t.prefix(19))) }
        let completo = String(t.prefix(19)) + String(senzaDecimali)
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        return iso.date(from: completo)
    }

    private struct Risposta: Decodable {
        let token: String?
        let scade: String?
    }

    /// I luoghi veri, con la scadenza in `memoria` (i test vecchi ne passano una loro).
    private static func sistema(memoria: UserDefaults) -> Luoghi {
        var luoghi = Luoghi.sistema
        luoghi.memoria = memoria
        return luoghi
    }

    /// Con una sessione valida: si assicura che il widget abbia il suo token (lo chiede se manca, se sta per scadere o se il widget ha
    /// segnalato che il server lo rifiuta) e lo mette nel file condiviso. Con un server senza account (nessuna sessione) non fa
    /// niente. Mai un errore all'utente: il widget ha il suo ripiego.
    static func assicura(server: any ServerClient, memoria: UserDefaults = .standard) async {
        await assicura(server: server, luoghi: sistema(memoria: memoria), sessione: Accesso.archivio)
    }

    /// Come sopra, con i luoghi e l'archivio della sessione di chi chiede. Il token arriva dopo un'attesa: se nel frattempo la
    /// sessione è cambiata (uscita, un altro accesso) o il lavoro è stato annullato, non si tiene. Revocarlo non si può (la sessione
    /// che l'ha chiesto non c'è più): resta sul server senza che nessuno lo abbia, finché non scade.
    static func assicura(server: any ServerClient, luoghi: Luoghi, sessione: any ArchivioToken) async {
        _ = await chiedi(server: server, luoghi: luoghi, sessione: sessione, sempre: false)
    }

    /// «Collega» (26/11/2026): chiede SEMPRE un token nuovo, perché quello che il telefono ha può essere stato rifiutato dal server
    /// senza che l'app lo sappia (prima «Collega» diceva «collegato» e teneva il token vecchio). Restituisce il token nuovo, già
    /// passato al widget, o nil se il server non l'ha dato (allora resta quello di prima).
    static func nuovo(server: any ServerClient, memoria: UserDefaults = .standard) async -> String? {
        await nuovo(server: server, luoghi: sistema(memoria: memoria), sessione: Accesso.archivio)
    }

    static func nuovo(server: any ServerClient, luoghi: Luoghi, sessione: any ArchivioToken) async -> String? {
        await chiedi(server: server, luoghi: luoghi, sessione: sessione, sempre: true)
    }

    /// Il lavoro di `assicura` e `nuovo`. Prima il segnale del widget (`SegnaleWidget`): se il server ha rifiutato proprio il token di
    /// adesso, il telefono lo dimentica e ne chiede un altro; il segnale letto si toglie sempre (uno per un altro token, per esempio
    /// di un codice incollato o già sostituito, non serve più). `sempre`: il token si chiede anche se quello di adesso va bene.
    /// Restituisce il token che il widget ha dopo il lavoro, o nil se serviva e il server non l'ha dato.
    private static func chiedi(server: any ServerClient, luoghi: Luoghi, sessione: any ArchivioToken, sempre: Bool) async -> String? {
        if Demo.attivo { return nil }
        let indirizzo = server.indirizzo
        let cartella = luoghi.cartella()
        var esistente = leggi(server: indirizzo, in: luoghi.archivio)
        if rifiutato(esistente, indirizzo: indirizzo, cartella: cartella) {
            dimenticaToken(indirizzo: indirizzo, luoghi: luoghi)
            esistente = nil
        }
        SegnaleWidget.cancella(cartella: cartella)
        let scade = luoghi.memoria.string(forKey: chiaveScadenza + "|" + indirizzo)
        var tenuto = esistente
        if sempre || daRinnovare(token: esistente, scade: scade) {
            let impronta = sessione.leggi(server: indirizzo)
            guard let dati = try? await server.corpoJSON("POST", "/api/account/token-widget", [String: String]()),
                  let r: Risposta = try? Decodifica.decodifica(dati), let ricevuto = r.token, valido(ricevuto) else { return nil }
            guard !Task.isCancelled, sessione.leggi(server: indirizzo) == impronta else { return nil }
            luoghi.archivio.salva(ricevuto, server: indirizzo)
            luoghi.memoria.set(r.scade ?? "", forKey: chiaveScadenza + "|" + indirizzo)
            tenuto = ricevuto
        }
        luoghi.sincronizza()
        return tenuto
    }

    /// Via il token dal telefono (Keychain e file condiviso), senza chiamare il server (sessione già finita o server cambiato).
    static func pulisciLocale(indirizzo: String, memoria: UserDefaults = .standard) {
        pulisciLocale(indirizzo: indirizzo, luoghi: sistema(memoria: memoria))
    }

    /// Uscita o cambio di server: via il token e tutto quello che il widget ha di questo account (riassunto e copie).
    static func pulisciLocale(indirizzo: String, luoghi: Luoghi) {
        luoghi.archivio.cancella(server: indirizzo)
        let cartella = luoghi.cartella()
        MemoriaWidget.dimentica(cartella: cartella, memoria: luoghi.memoria)
        luoghi.memoria.removeObject(forKey: chiaveScadenza + "|" + indirizzo)
        Condiviso.aggiorna(cartella: cartella) {
            if $0.tokenPerIndirizzo == indirizzo {
                $0.token = nil
                $0.tokenPerIndirizzo = nil
                $0.riassunto = nil
            }
        }
        if collegamento(in: luoghi.portachiavi)?.i == indirizzo { luoghi.portachiavi.cancella() }
    }

    /// Il server ha revocato il token del widget ma l'account è lo stesso (cambio della password): via solo il token e la sua
    /// scadenza, dal Keychain, dal file del gruppo e dal Keychain condiviso. Riassunto e copie del widget restano.
    static func dimenticaToken(indirizzo: String, luoghi: Luoghi) {
        luoghi.archivio.cancella(server: indirizzo)
        luoghi.memoria.removeObject(forKey: chiaveScadenza + "|" + indirizzo)
        Condiviso.aggiorna(cartella: luoghi.cartella()) {
            if $0.tokenPerIndirizzo == indirizzo {
                $0.token = nil
                $0.tokenPerIndirizzo = nil
            }
        }
        // nel Keychain condiviso indirizzo e token stanno insieme: si toglie l'elemento, l'indirizzo lo ripassa `sincronizza`
        if let c = collegamento(in: luoghi.portachiavi), c.i == indirizzo, c.t != nil { luoghi.portachiavi.cancella() }
    }

    /// Indirizzo e token nel Keychain condiviso, letti come `PortachiaviCondiviso.leggi` ma da un archivio dato (i test ne passano uno finto).
    private static func collegamento(in portachiavi: any ArchivioCollegamento) -> CodiceWidget.Contenuto? {
        guard let dati = portachiavi.leggi(), dati.count <= 4000,
              let c = try? JSONDecoder().decode(CodiceWidget.Contenuto.self, from: dati), !c.i.isEmpty else { return nil }
        return c
    }
}
