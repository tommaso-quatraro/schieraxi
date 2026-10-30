import Foundation

/// Il token del widget (`fw_...`): un token a scopo limitato, emesso dal server (`POST /api/account/token-widget`), valido 90 giorni,
/// uno per utente, che permette SOLO di leggere `/api/oggi` e `/api/widget`. È l'unica cosa che l'app dà al widget (nel file condiviso
/// dell'App Group e nel codice di collegamento): il token della SESSIONE non esce mai dal Keychain dell'app.
enum TokenWidget {
    static let servizio = "<vecchio identificativo>.widget"
    private static let chiaveScadenza = "tokenWidgetScade"
    nonisolated(unsafe) static var archivio: any ArchivioToken = Demo.attivo ? MemoriaToken() : KeychainToken(servizio: servizio)

    /// Un token del widget accettabile: comincia per `fw_`, breve e di caratteri semplici (un server ostile potrebbe mandare altro).
    static func valido(_ testo: String) -> Bool {
        testo.hasPrefix("fw_") && testo.utf8.count >= 12 && Accesso.tokenValido(testo)
    }

    static func leggi(server indirizzo: String) -> String? {
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
        guard let scade, let data = formatoScadenza.date(from: String(scade.prefix(19))) else { return true }
        return data.timeIntervalSince(adesso) < 7 * 24 * 3600
    }

    private struct Risposta: Decodable {
        let token: String?
        let scade: String?
    }

    /// Con una sessione valida: si assicura che il widget abbia il suo token (lo chiede se manca o sta per scadere) e lo mette nel
    /// file condiviso. Con un server senza account (nessuna sessione) non fa niente. Mai un errore all'utente: il widget ha il suo ripiego.
    static func assicura(server: any ServerClient, memoria: UserDefaults = .standard) async {
        if Demo.attivo { return }
        let indirizzo = server.indirizzo
        let esistente = leggi(server: indirizzo)
        let scade = memoria.string(forKey: chiaveScadenza + "|" + indirizzo)
        if daRinnovare(token: esistente, scade: scade) {
            guard let dati = try? await server.corpoJSON("POST", "/api/account/token-widget", [String: String]()),
                  let r: Risposta = try? Decodifica.decodifica(dati), let nuovo = r.token, valido(nuovo) else { return }
            archivio.salva(nuovo, server: indirizzo)
            memoria.set(r.scade ?? "", forKey: chiaveScadenza + "|" + indirizzo)
        }
        Accesso.sincronizzaConIlWidget()
    }

    /// All'uscita: il server toglie il token (serve ancora la sessione, quindi PRIMA di chiuderla) e il telefono lo dimentica.
    static func revoca(server: any ServerClient, memoria: UserDefaults = .standard) async {
        if Demo.attivo { return }
        _ = try? await server.richiesta("DELETE", "/api/account/token-widget", corpo: nil)
        pulisciLocale(indirizzo: server.indirizzo, memoria: memoria)
    }

    /// Via il token dal telefono (Keychain e file condiviso), senza chiamare il server (sessione già finita o server cambiato).
    static func pulisciLocale(indirizzo: String, memoria: UserDefaults = .standard) {
        archivio.cancella(server: indirizzo)
        MemoriaWidget.dimentica()
        memoria.removeObject(forKey: chiaveScadenza + "|" + indirizzo)
        Condiviso.aggiorna {
            if $0.tokenPerIndirizzo == indirizzo {
                $0.token = nil
                $0.tokenPerIndirizzo = nil
                $0.riassunto = nil
            }
        }
    }
}
