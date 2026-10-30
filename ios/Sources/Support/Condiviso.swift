import Foundation

// Dati condivisi tra l'app e il widget tramite un App Group.
//
// Con l'Apple ID gratuito e SideStore/AltStore gli App Group funzionano così: l'app e l'estensione dichiarano il gruppo nei loro
// permessi (entitlements, incorporati nell'IPA con ldid dal workflow) e SideStore lo registra col nome vero (con un suffisso della
// squadra), scrivendolo in Info.plist alla chiave `ALTAppGroups`. Perciò l'identificativo si legge a runtime da lì
// (poi il nome base, per il simulatore e per un'installazione normale).
//
// Nel contenitore c'è UN file (`condiviso.json`): l'indirizzo del server, il token della sessione (protetto dalla protezione dei dati
// di iOS e dal sandbox, mai in UserDefaults) e l'ultimo riassunto di «Oggi», così il widget mostra subito qualcosa. Lo scrive solo
// l'app; il widget lo legge. Se il gruppo non è disponibile tutto funziona come prima (indirizzo nelle impostazioni del widget,
// nessun token: il widget chiede l'accesso).

/// Quello che serve al widget, in forma compatta e salvabile.
struct RiassuntoOggi: Codable, Equatable {
    var giornata: Int
    var inizio: Date?
    var modulo: String?
    var punti: Double?
    var daControllare: Int
    var probabili: Bool?
    var scaricatoIl: Date

    static let esempio = RiassuntoOggi(giornata: 9, inizio: Date().addingTimeInterval(3 * 3600 + 25 * 60), modulo: "3-4-3", punti: 64.5,
                                       daControllare: 2, probabili: true, scaricatoIl: Date())

    init(giornata: Int, inizio: Date?, modulo: String?, punti: Double?, daControllare: Int, probabili: Bool?, scaricatoIl: Date) {
        self.giornata = giornata
        self.inizio = inizio
        self.modulo = modulo
        self.punti = punti
        self.daControllare = daControllare
        self.probabili = probabili
        self.scaricatoIl = scaricatoIl
    }

    /// Dalla risposta di «oggi» (la stessa per l'app e per il widget).
    init(oggi: Oggi, scaricatoIl: Date = Date()) {
        self.init(giornata: oggi.giornata,
                  inizio: Quando.data(oggi.inizio),
                  modulo: oggi.formazione?.modulo,
                  punti: oggi.formazione?.punteggioAtteso,
                  daControllare: (oggi.avvisi ?? []).filter { $0.inFormazione == true }.count,
                  probabili: oggi.conProbabili,
                  scaricatoIl: scaricatoIl)
    }
}

/// Il contenuto del file condiviso.
struct DatiCondivisi: Codable, Equatable {
    var indirizzo: String?
    /// Il token della sessione e il server a cui appartiene (non si manda mai a un altro indirizzo).
    var token: String?
    var tokenPerIndirizzo: String?
    var riassunto: RiassuntoOggi?
    var aggiornato: Date?

    /// Il token valido per questo indirizzo, se c'è.
    func token(per indirizzo: String) -> String? {
        guard let token, !token.isEmpty, tokenPerIndirizzo == indirizzo else { return nil }
        return token
    }
}

enum Condiviso {
    static let gruppoBase = "group.<vecchio identificativo>"
    private static let nomeFile = "condiviso.json"
    private static let blocco = NSLock()
    /// Per i test: una cartella al posto del contenitore del gruppo.
    nonisolated(unsafe) static var cartellaDiProva: URL?

    /// Gli identificativi da provare, in ordine: quelli scritti da SideStore (`ALTAppGroups`) che derivano dal nome base, poi il nome base.
    static func identificativi(info: [String: Any]? = Bundle.main.infoDictionary) -> [String] {
        var elenco: [String] = []
        if let scritti = info?["ALTAppGroups"] as? [String] {
            for g in scritti where g.hasPrefix(gruppoBase) && !elenco.contains(g) { elenco.append(g) }
        }
        if !elenco.contains(gruppoBase) { elenco.append(gruppoBase) }
        return elenco
    }

    /// La cartella condivisa, se il gruppo funziona su questo dispositivo.
    static func cartella() -> URL? {
        if let prova = cartellaDiProva { return prova }
        for g in identificativi() {
            if let url = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: g) { return url }
        }
        return nil
    }

    /// true se l'App Group c'è (la condivisione funziona).
    static var disponibile: Bool { cartella() != nil }

    private static func percorso() -> URL? { cartella()?.appendingPathComponent(nomeFile) }

    static func leggi() -> DatiCondivisi {
        blocco.lock(); defer { blocco.unlock() }
        return leggiSenzaBlocco()
    }

    private static func leggiSenzaBlocco() -> DatiCondivisi {
        guard let url = percorso(), let dati = try? Data(contentsOf: url) else { return DatiCondivisi() }
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return (try? d.decode(DatiCondivisi.self, from: dati)) ?? DatiCondivisi()
    }

    /// Cambia i dati condivisi (lo fa solo l'app). Scrittura atomica, protetta fino al primo sblocco: il widget e l'aggiornamento
    /// in background leggono anche a telefono bloccato.
    @discardableResult
    static func aggiorna(_ modifica: (inout DatiCondivisi) -> Void) -> Bool {
        blocco.lock(); defer { blocco.unlock() }
        guard let url = percorso() else { return false }
        var dati = leggiSenzaBlocco()
        let prima = dati
        modifica(&dati)
        if dati == prima { return true }
        dati.aggiornato = Date()
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        guard let fuori = try? e.encode(dati) else { return false }
        do {
            try fuori.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
            return true
        } catch {
            return false
        }
    }

    /// Dice al widget dove sta il server e (se c'è una sessione) con quale token parlare.
    static func sincronizza(indirizzo: String, token: String?) {
        aggiorna {
            $0.indirizzo = indirizzo.isEmpty ? nil : indirizzo
            if let token, !token.isEmpty, !indirizzo.isEmpty {
                $0.token = token
                $0.tokenPerIndirizzo = indirizzo
            } else if $0.tokenPerIndirizzo != indirizzo {
                $0.token = nil
                $0.tokenPerIndirizzo = nil
            }
        }
    }

    /// Via il token e il riassunto (uscita da un account): chi entra dopo non deve vedere niente di chi c'era prima.
    static func dimentica() {
        aggiorna {
            $0.token = nil
            $0.tokenPerIndirizzo = nil
            $0.riassunto = nil
        }
    }

    static func salvaRiassunto(_ r: RiassuntoOggi) {
        aggiorna { $0.riassunto = r }
    }
}
