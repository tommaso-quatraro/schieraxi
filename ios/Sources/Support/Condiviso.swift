import Foundation

// Dati condivisi tra l'app e il widget tramite un App Group.
//
// Con l'Apple ID gratuito e SideStore/AltStore gli App Group funzionano così: l'app e l'estensione dichiarano il gruppo nei loro
// permessi (entitlements, incorporati nell'IPA con ldid dal workflow) e SideStore lo registra col nome vero (con un suffisso della
// squadra), scrivendolo in Info.plist alla chiave `ALTAppGroups`. Perciò l'identificativo si legge a runtime da lì
// (poi il nome base, per il simulatore e per un'installazione normale).
//
// Nel contenitore c'è UN file (`condiviso.json`): l'indirizzo del server, il token del WIDGET (`fw_`, mai quello della sessione; protetto dalla protezione dei dati
// di iOS e dal sandbox, mai in UserDefaults) e l'ultimo riassunto di «Oggi», così il widget mostra subito qualcosa. Lo scrive solo
// l'app; il widget lo legge. Se il gruppo non è disponibile tutto funziona come prima (indirizzo nelle impostazioni del widget,
// nessun token: il widget chiede l'accesso).

/// Un giocatore della formazione da controllare (dubbio, infortunio, squalifica), per il widget «Da controllare».
struct DubbioRiassunto: Codable, Equatable, Identifiable {
    var id: Int
    var nome: String
    var ruolo: String?
    var tipo: String?
    /// Probabilità di giocare (0-1), per i dubbi.
    var pVoto: Double?

    /// «Dubbio 55%», «Infortunato»...: una riga breve.
    var descrizione: String {
        let base = (tipo ?? "da controllare").prefix(1).uppercased() + (tipo ?? "da controllare").dropFirst()
        guard let p = pVoto else { return base }
        return "\(base) \(Int((p * 100).rounded()))%"
    }
}

/// Quello che serve al widget, in forma compatta e salvabile.
struct RiassuntoOggi: Codable, Equatable {
    var giornata: Int?
    var inizio: Date?
    var modulo: String?
    var punti: Double?
    var daControllare: Int
    var probabili: Bool?
    var scaricatoIl: Date
    /// Chi della formazione ha un dubbio (al massimo 6). Opzionale: un riassunto salvato da una versione vecchia non li ha.
    var dubbi: [DubbioRiassunto]?
    /// Il numero nella lega (opzionale: un riassunto salvato da una versione vecchia non ce l'ha).
    var giornataLega: Int?

    var etichettaGiornata: String { giornata.map { TempiLega.etichetta(serieA: $0, lega: giornataLega) } ?? "Nessuna giornata" }
    var siglaGiornata: String { giornata.map { TempiLega.sigla(serieA: $0, lega: giornataLega) } ?? "G–" }

    static let esempio = RiassuntoOggi(giornata: 9, inizio: Date().addingTimeInterval(3 * 3600 + 25 * 60), modulo: "3-4-3", punti: 64.5,
                                       daControllare: 2, probabili: true, scaricatoIl: Date())

    init(giornata: Int?, inizio: Date?, modulo: String?, punti: Double?, daControllare: Int, probabili: Bool?, scaricatoIl: Date,
         dubbi: [DubbioRiassunto]? = nil, giornataLega: Int? = nil) {
        self.giornata = giornata
        self.inizio = inizio
        self.modulo = modulo
        self.punti = punti
        self.daControllare = daControllare
        self.probabili = probabili
        self.scaricatoIl = scaricatoIl
        self.dubbi = dubbi
        self.giornataLega = giornataLega
    }

    /// Dalla risposta di «oggi» (la stessa per l'app e per il widget).
    init(oggi: Oggi, scaricatoIl: Date = Date()) {
        let daControllare = (oggi.avvisi ?? []).filter { $0.inFormazione == true }
        self.init(giornata: oggi.giornata,
                  inizio: Quando.data(oggi.chiusura),
                  modulo: oggi.formazione?.modulo,
                  punti: oggi.formazione?.punteggioAtteso,
                  daControllare: daControllare.count,
                  probabili: oggi.conProbabili,
                  scaricatoIl: scaricatoIl,
                  dubbi: daControllare.prefix(6).map { DubbioRiassunto(id: $0.id, nome: $0.nome, ruolo: $0.ruolo, tipo: $0.tipo, pVoto: $0.pVoto) },
                  giornataLega: oggi.giornataLega)
    }
}

/// Il contenuto del file condiviso.
struct DatiCondivisi: Codable, Equatable {
    var indirizzo: String?
    /// Il token del widget (`fw_`) e il server a cui appartiene (non si manda mai a un altro indirizzo).
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
    static let gruppoBase = "group.it.schieraxi.app"
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

    // MARK: diagnostica

    /// Com'è messa la condivisione su questo dispositivo: serve a capire perché il widget non vede i dati dell'app.
    struct Diagnostica: Equatable {
        /// I gruppi scritti da SideStore in Info.plist (`ALTAppGroups`), come sono.
        var scrittiDaSideStore: [String]
        /// I gruppi provati, in ordine.
        var provati: [String]
        /// Il primo gruppo di cui iOS ha dato la cartella (nil = il gruppo non c'è per questo programma).
        var gruppoFunzionante: String?
        var filePresente: Bool
        var ultimaScrittura: Date?
        var haIndirizzo: Bool
        var haToken: Bool
        var haRiassunto: Bool

        /// Una riga breve per il widget: «G:no F:no A:no T:no».
        var breve: String {
            func s(_ b: Bool) -> String { b ? "sì" : "no" }
            return "gruppo \(s(gruppoFunzionante != nil)) · file \(s(filePresente)) · indirizzo \(s(haIndirizzo)) · token \(s(haToken))"
        }

        /// Il dettaglio per Lega.
        var lungo: String {
            func s(_ b: Bool) -> String { b ? "sì" : "no" }
            var righe = [
                "Gruppo di SideStore (ALTAppGroups): " + (scrittiDaSideStore.isEmpty ? "nessuno" : scrittiDaSideStore.joined(separator: ", ")),
                "Gruppi provati: " + provati.joined(separator: ", "),
                "Cartella condivisa: " + (gruppoFunzionante.map { "sì (\($0))" } ?? "NO (iOS non dà il gruppo a questo programma)"),
                "File presente: \(s(filePresente))",
            ]
            if let ultimaScrittura { righe.append("Ultima scrittura dell'app: " + ultimaScrittura.formatted(date: .abbreviated, time: .standard)) }
            righe.append("Indirizzo: \(s(haIndirizzo)) · token: \(s(haToken)) · riassunto: \(s(haRiassunto))")
            return righe.joined(separator: "\n")
        }
    }

    static func diagnostica(info: [String: Any]? = Bundle.main.infoDictionary) -> Diagnostica {
        let provati = identificativi(info: info)
        var funzionante: String?
        if cartellaDiProva == nil {
            funzionante = provati.first { FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: $0) != nil }
        } else {
            funzionante = provati.first
        }
        let url = cartella()?.appendingPathComponent(nomeFile)
        let presente = url.map { FileManager.default.fileExists(atPath: $0.path) } ?? false
        let dati = leggi()
        return Diagnostica(scrittiDaSideStore: (info?["ALTAppGroups"] as? [String]) ?? [], provati: provati, gruppoFunzionante: funzionante,
                           filePresente: presente, ultimaScrittura: dati.aggiornato, haIndirizzo: dati.indirizzo != nil,
                           haToken: dati.token != nil, haRiassunto: dati.riassunto != nil)
    }
}

/// Il codice di collegamento del widget: indirizzo e (se c'è una sessione) token in un testo breve da copiare dall'app e incollare
/// nelle impostazioni del widget. È il ripiego quando l'App Group non c'è. Il token è quello del WIDGET (`fw_`, solo lettura di
/// /api/oggi e /api/widget, 90 giorni, revocabile): mai quello della sessione.
enum CodiceWidget {
    static let prefisso = "schieraxi1."

    struct Contenuto: Codable, Equatable {
        var i: String
        var t: String?
    }

    static func crea(indirizzo: String, token: String?) -> String {
        let c = Contenuto(i: indirizzo, t: (token?.isEmpty ?? true) ? nil : token)
        let dati = (try? JSONEncoder().encode(c)) ?? Data()
        let b64 = dati.base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        return prefisso + b64
    }

    /// Legge un codice (o, per comodità, un semplice indirizzo https). `nil` se non si capisce.
    static func leggi(_ testo: String) -> Contenuto? {
        let t = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard t.count <= 2000 else { return nil }
        if t.hasPrefix(prefisso) {
            var b64 = String(t.dropFirst(prefisso.count)).replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
            while b64.count % 4 != 0 { b64.append("=") }
            guard let dati = Data(base64Encoded: b64), let c = try? JSONDecoder().decode(Contenuto.self, from: dati), !c.i.isEmpty else { return nil }
            return c
        }
        return t.lowercased().hasPrefix("http") ? Contenuto(i: t, t: nil) : nil
    }
}
