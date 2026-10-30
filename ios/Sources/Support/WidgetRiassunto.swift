import Foundation

// Il riassunto compatto per i widget (`GET /api/widget`): TUTTO in una chiamata, meno di 20 kB, con ETag (If-None-Match -> 304).
// Lo leggono i widget (con il token `fw_` a scopo limitato, o con la sessione per l'app). Il server non fa mai partire calcoli per il
// widget: se il nucleo non è pronto risponde 202 e si tengono i dati di prima. Tutti i campi sono opzionali: il server può aggiungerne.
// Niente capitano (la lega non lo usa) e niente classifica della lega (non esiste nei dati).

struct GiocatoreWidget: Codable, Identifiable, Equatable {
    var id: Int
    var nome: String
    var ruolo: String?
    var puntiAttesi: Double?
    var pVoto: Double?
    var votoAtteso: Double?
    /// Tratti grossolani del volto (versione 2 degli avatar), se il server li ha.
    var avatar: TrattiVolto?
    // avvisi
    var tipo: String?
    var inFormazione: Bool?
    // la mia rosa e gli osservati
    var avversario: String?
    var inCasa: Bool?
    var dataPartita: String?
    var stato: String?
    var percentuale: Double?
    var dubbio: Bool?
    var diffidato: Bool?
    var titolare: Bool?
    var rigorista: Bool?
    var quotazione: Double?

    /// Quando gioca (ora italiana), se la partita è nota.
    var quando: Date? { Quando.data(dataPartita) }

    /// «Dubbio 55%», «Infortunato», «Squalificato»: una riga breve sullo stato.
    var descrizioneStato: String {
        let base = stato ?? tipo ?? (dubbio == true ? "dubbio" : "")
        guard !base.isEmpty else { return "" }
        let testo = base.prefix(1).uppercased() + base.dropFirst()
        if base == "dubbio", let p = pVoto ?? percentuale.map({ $0 / 100 }), p < 1 {
            return "\(testo) \(Int((p * 100).rounded()))%"
        }
        return testo
    }
}

extension GiocatoreWidget {
    /// «18:30», o «—» se la partita non è nota.
    var oraBreve: String { quando.map { Quando.ora($0) } ?? "—" }

    /// «vs ROM · 18:30» / «@ MIL · 18:30».
    var partitaBreve: String {
        guard let avversario else { return oraBreve }
        return "\(inCasa == true ? "vs" : "@") \(ColoriSquadra.sigla(avversario)) · \(oraBreve)"
    }

    /// Il cognome (l'ultima parola), per i campi stretti.
    var cognome: String { nome.split(separator: " ").last.map(String.init) ?? nome }
}

struct FormazioneWidget: Codable, Equatable {
    var modulo: String?
    var puntiAttesi: Double?
    var titolari: [GiocatoreWidget]?
    var panchina: [Int]?
}

struct PuntiGiornata: Codable, Equatable, Identifiable {
    var giornata: Int
    var attesi: Double?
    var fatti: Double?
    var id: Int { giornata }
}

struct SvincolatoWidget: Codable, Equatable {
    var esce: GiocatoreWidget?
    var entra: GiocatoreWidget?
    var guadagno: Double?
    var fattibile: Bool?
}

struct DatiAggiornamentoWidget: Codable, Equatable {
    var ultimoAggiornamento: String?
}

struct RiassuntoWidget: Decodable {
    var giornata: Int?
    var primaPartita: String?
    var scadenza: String?
    var oreMancanti: Double?
    var iniziata: Bool?
    var conProbabili: Bool?
    var squadra: String?
    var creditiResidui: Double?
    var formazione: FormazioneWidget?
    var avvisi: [GiocatoreWidget]?
    var rosa: [GiocatoreWidget]?
    var squalificati: [Int]?
    var diffidati: [Int]?
    var rigoristi: [Int]?
    var diario: [PuntiGiornata]?
    var osservati: [GiocatoreWidget]?
    var dati: DatiAggiornamentoWidget?
    /// Il miglior scambio e il miglior svincolo: solo se il server li aveva già in cache.
    var scambio: PropostaScambio?
    var svincolato: SvincolatoWidget?
    var mancano: [String]?

    /// Quando comincia la giornata (la scadenza della formazione).
    var inizio: Date? { Quando.data(scadenza) }

    /// Chi della formazione ha un dubbio, un infortunio o una squalifica.
    var daControllare: [GiocatoreWidget] { (avvisi ?? []).filter { $0.inFormazione == true } }

    /// I giocatori della mia rosa che giocano a breve, in ordine di orario (solo con la partita nota).
    func giocanoPresto(dopo adesso: Date = Date(), massimo: Int = 8) -> [GiocatoreWidget] {
        (rosa ?? []).filter { ($0.quando ?? .distantPast) > adesso.addingTimeInterval(-2 * 3600) && $0.stato != "infortunato" && $0.stato != "squalificato" }
            .sorted { ($0.quando ?? .distantFuture, $0.nome) < ($1.quando ?? .distantFuture, $1.nome) }
            .prefix(massimo).map { $0 }
    }

    /// Per i widget «vecchi» (Prossima giornata, Da controllare): lo stesso riassunto di prima, dal nuovo contenuto.
    func comeRiassuntoOggi(scaricatoIl: Date = Date()) -> RiassuntoOggi? {
        guard let giornata else { return nil }
        let dubbi = daControllare
        return RiassuntoOggi(giornata: giornata, inizio: inizio, modulo: formazione?.modulo, punti: formazione?.puntiAttesi,
                             daControllare: dubbi.count, probabili: conProbabili, scaricatoIl: scaricatoIl,
                             dubbi: dubbi.prefix(6).map { DubbioRiassunto(id: $0.id, nome: $0.nome, ruolo: $0.ruolo, tipo: $0.tipo, pVoto: $0.pVoto) })
    }

    static func leggi(_ dati: Data) -> RiassuntoWidget? {
        guard !dati.isEmpty, dati.count <= 200_000 else { return nil }
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return try? d.decode(RiassuntoWidget.self, from: dati)
    }
}

/// Lo scarico di `/api/widget` (nel widget e nell'app): sempre con `If-None-Match`, mai calcoli.
enum ScaricoWidget {
    enum Esito {
        /// Dati nuovi, il testo grezzo e l'ETag.
        case dati(RiassuntoWidget, Data, String?)
        /// 304: va bene quello che si ha.
        case nonCambiato
        /// 202: il server sta calcolando; si tengono i dati di prima.
        case inCalcolo
        /// 401: token mancante, scaduto o revocato.
        case accessoRichiesto
        /// 404 e simili: il server non ha ancora questa rotta (si ricade su /api/oggi).
        case nonDisponibile
        case errore
    }

    static func scarica(base: String, token: String?, etag: String?, sessione: URLSession = .shared) async -> Esito {
        guard let url = URL(string: base + "/api/widget") else { return .errore }
        var r = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
        r.setValue("1", forHTTPHeaderField: "X-Fanta")
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let etag, !etag.isEmpty { r.setValue(etag, forHTTPHeaderField: "If-None-Match") }
        do {
            let (dati, risposta) = try await sessione.data(for: r)
            guard let h = risposta as? HTTPURLResponse else { return .errore }
            switch h.statusCode {
            case 200:
                guard let letto = RiassuntoWidget.leggi(dati) else { return .errore }
                return .dati(letto, dati, h.value(forHTTPHeaderField: "ETag"))
            case 304: return .nonCambiato
            case 202: return .inCalcolo
            case 401: return .accessoRichiesto
            case 403, 404, 405: return .nonDisponibile
            default: return .errore
            }
        } catch {
            return .errore
        }
    }
}

/// L'ultima risposta di `/api/widget` ricordata dal widget (con il suo ETag), per il 304 e per quando il server non risponde.
struct CopiaWidget: Codable, Equatable {
    var dati: Data
    var etag: String?
    var scaricatoIl: Date

    var riassunto: RiassuntoWidget? { RiassuntoWidget.leggi(dati) }
}

enum MemoriaWidget {
    private static let chiave = "copiaWidget"
    private static let nomeFile = "widget-cache.json"

    /// Scritta SOLO dal widget (e dall'app per riempirla in anticipo, in un file a parte da quello condiviso): nel contenitore del
    /// gruppo se c'è, altrimenti nelle UserDefaults del programma che scrive.
    private static func percorso() -> URL? { Condiviso.cartella()?.appendingPathComponent(nomeFile) }

    static func leggi() -> CopiaWidget? {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        if let url = percorso(), let dati = try? Data(contentsOf: url), let c = try? d.decode(CopiaWidget.self, from: dati) { return c }
        if let dati = UserDefaults.standard.data(forKey: chiave) { return try? d.decode(CopiaWidget.self, from: dati) }
        return nil
    }

    static func salva(_ copia: CopiaWidget) {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        guard let fuori = try? e.encode(copia) else { return }
        if let url = percorso() {
            try? fuori.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        } else {
            UserDefaults.standard.set(fuori, forKey: chiave)
        }
    }

    static func dimentica() {
        if let url = percorso() { try? FileManager.default.removeItem(at: url) }
        UserDefaults.standard.removeObject(forKey: chiave)
    }
}
