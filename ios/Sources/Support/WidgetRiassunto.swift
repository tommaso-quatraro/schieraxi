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
    var intervallo: IntervalloWidget?
}

struct PuntiGiornata: Codable, Equatable, Identifiable {
    var giornata: Int
    var attesi: Double?
    var fatti: Double?
    /// La fascia prevista per quella giornata (facoltativa: un server vecchio non la manda).
    var intervallo: IntervalloWidget?
    var id: Int { giornata }

    private enum Chiavi: String, CodingKey { case giornata, attesi, fatti, intervallo }

    init(giornata: Int, attesi: Double? = nil, fatti: Double? = nil, intervallo: IntervalloWidget? = nil) {
        self.giornata = giornata; self.attesi = attesi; self.fatti = fatti; self.intervallo = intervallo
    }

    /// Tollerante: una fascia con la forma sbagliata si ignora, la giornata resta.
    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        giornata = try k.decode(Int.self, forKey: .giornata)
        attesi = (try? k.decodeIfPresent(Double.self, forKey: .attesi)) ?? nil
        fatti = (try? k.decodeIfPresent(Double.self, forKey: .fatti)) ?? nil
        intervallo = (try? k.decodeIfPresent(IntervalloWidget.self, forKey: .intervallo)) ?? nil
    }
}

struct SvincolatoWidget: Codable, Equatable {
    var esce: GiocatoreWidget?
    var entra: GiocatoreWidget?
    var guadagno: Double?
    var fattibile: Bool?
}

/// Un pezzo facoltativo del riassunto: se ha una forma inattesa diventa nil invece di far fallire tutto il resto.
struct Facoltativo<T: Decodable>: Decodable {
    let valore: T?
    init(from decoder: Decoder) throws { valore = try? T(from: decoder) }
}

/// Un giocatore dentro uno scambio proposto (tutti i campi sono facoltativi).
struct GiocatoreScambio: Decodable, Equatable {
    var id: Int?
    var nome: String?
    var ruolo: String?
    var squadra: String?
    var quotazione: Double?

    var cognome: String { (nome ?? "").split(separator: " ").last.map(String.init) ?? (nome ?? "—") }
    /// Il giocatore nella forma usata dai volti.
    var comeGiocatore: GiocatoreWidget { GiocatoreWidget(id: id ?? 0, nome: nome ?? "—", ruolo: ruolo) }
}

/// Il miglior scambio con un'altra squadra (solo se il server lo aveva già calcolato). Il guadagno è in punti attesi.
struct ScambioWidget: Decodable, Equatable {
    var mia: String?
    var altra: String?
    var `do`: [GiocatoreScambio]?
    var ricevo: [GiocatoreScambio]?
    var guadagnoMio: Double?
    var guadagnoLoro: Double?
    var percentualeMio: Double?
    var valido: Bool?
}

struct DatiAggiornamentoWidget: Codable, Equatable {
    var ultimoAggiornamento: String?
}

struct RiassuntoWidget: Decodable {
    var giornata: Int?
    /// Il numero nella lega (facoltativo: server vecchio, o lega non ancora partita).
    var giornataLega: Int?
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
    /// Il miglior scambio e il miglior svincolo: solo se il server li aveva già in cache (se hanno una forma strana si ignorano).
    private var scambioLetto: Facoltativo<ScambioWidget>?
    private var svincolatoLetto: Facoltativo<SvincolatoWidget>?
    private var liveLetto: Facoltativo<LiveWidget>?
    var mancano: [String]?

    var scambio: ScambioWidget? { scambioLetto?.valore }
    var svincolato: SvincolatoWidget? { svincolatoLetto?.valore }
    var live: LiveWidget? { liveLetto?.valore }

    enum CodingKeys: String, CodingKey {
        case giornata, giornataLega, primaPartita, scadenza, oreMancanti, iniziata, conProbabili, squadra, creditiResidui, formazione, avvisi, rosa
        case squalificati, diffidati, rigoristi, diario, osservati, dati, mancano
        case scambioLetto = "scambio"
        case svincolatoLetto = "svincolato"
        case liveLetto = "live"
    }

    /// «Giornata 7 di lega (Serie A 10)», «Giornata 10» o nil se la giornata non si conosce.
    var etichettaGiornata: String? { giornata.map { TempiLega.etichetta(serieA: $0, lega: giornataLega) } }
    var siglaGiornata: String? { giornata.map { TempiLega.sigla(serieA: $0, lega: giornataLega) } }

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
                             dubbi: dubbi.prefix(6).map { DubbioRiassunto(id: $0.id, nome: $0.nome, ruolo: $0.ruolo, tipo: $0.tipo, pVoto: $0.pVoto) },
                             giornataLega: giornataLega)
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

// MARK: Testi e calcoli dei widget (qui perche' si provano con i test; i disegni stanno in WidgetSources)

extension PuntiGiornata {
    /// Punti fatti meno punti attesi; nil se manca uno dei due.
    var scarto: Double? {
        guard let attesi, let fatti else { return nil }
        return fatti - attesi
    }

    /// Dove sono caduti i punti fatti rispetto alla fascia prevista; nil se manca la fascia o i punti.
    enum PostoNellaFascia: Equatable { case sotto, dentro, sopra }

    var postoNellaFascia: PostoNellaFascia? {
        guard let fatti, fatti.isFinite, let basso = intervallo?.basso, let alto = intervallo?.alto,
              basso.isFinite, alto.isFinite, basso <= alto else { return nil }
        if fatti < basso { return .sotto }
        return fatti > alto ? .sopra : .dentro
    }

    /// «dentro la fascia», «sopra la fascia», «sotto la fascia»; nil senza fascia.
    var fasciaTesto: String? {
        switch postoNellaFascia {
        case .dentro: return "dentro la fascia"
        case .sopra: return "sopra la fascia"
        case .sotto: return "sotto la fascia"
        case nil: return nil
        }
    }

    /// Una frase per VoiceOver: «Giornata 10: 63,5 punti fatti, 66,0 attesi, dentro la fascia prevista, tra 62 e 85».
    var descrizione: String {
        var t = "Giornata \(giornata): "
        t += fatti.map { "\(Formato.punti($0)) punti fatti" } ?? "punti fatti non noti"
        if let attesi { t += ", \(Formato.punti(attesi)) attesi" }
        if let f = fasciaTesto, let fascia = intervallo?.testo { t += ", \(f) prevista, \(fascia)" }
        return t
    }
}

extension ScambioWidget {
    /// «Giovanni Rossi, Mario Bianchi» -> «Rossi, Bianchi»
    static func cognomi(_ elenco: [GiocatoreScambio]?) -> String {
        let nomi = (elenco ?? []).map(\.cognome)
        return nomi.isEmpty ? "—" : nomi.joined(separator: ", ")
    }

    var daiTesto: String { Self.cognomi(`do`) }
    var ricevoTesto: String { Self.cognomi(ricevo) }

    /// Una frase per VoiceOver.
    var frase: String {
        var t = "Scambio con \(altra ?? "un'altra squadra"): dai \(daiTesto), ricevi \(ricevoTesto)."
        if let g = guadagnoMio { t += " Per te \(Formato.conSegno(g)) punti attesi." }
        if let g = guadagnoLoro { t += " Per loro \(Formato.conSegno(g))." }
        return t
    }
}

extension RiassuntoWidget {
    /// Quante delle giornate date sono cadute dentro la fascia prevista, e su quante la fascia c'era.
    static func quanteDentro(_ giornate: [PuntiGiornata]) -> (dentro: Int, su: Int) {
        let con = giornate.compactMap(\.postoNellaFascia)
        return (con.filter { $0 == .dentro }.count, con.count)
    }

    /// Le giornate del diario che hanno i punti fatti, dalla più recente.
    var giornateGiocate: [PuntiGiornata] {
        (diario ?? []).filter { $0.fatti != nil }.sorted { $0.giornata > $1.giornata }
    }
}

// MARK: Partite in diretta (campo `live` di /api/widget, copia piccola di GET /api/live). Tutto facoltativo: un client deve ignorare
// stati e tipi nuovi e trattare «stato sconosciuto con un punteggio» come partita in corso.

struct EventoLive: Decodable, Equatable {
    var tipo: String?
    var minuto: String?
    var squadra: String?
    var chi: String?
}

struct PartitaLive: Decodable, Equatable, Identifiable {
    var casa: String?
    var trasferta: String?
    var data: String?
    var stato: String?
    var minuto: String?
    var golCasa: Int?
    var golTrasferta: Int?
    var eventi: [EventoLive]?

    var id: String { "\(casa ?? "?")-\(trasferta ?? "?")" }
    var quando: Date? { Quando.data(data) }

    /// In gioco ora (compresi intervallo e sospesa); uno stato nuovo con un punteggio conta come in corso.
    var inGioco: Bool {
        switch stato ?? "" {
        case "primo_tempo", "secondo_tempo", "intervallo", "in_corso", "sospesa": return true
        case "da_giocare", "finita", "rinviata", "": return false
        default: return golCasa != nil && golTrasferta != nil
        }
    }

    var finita: Bool { stato == "finita" }

    /// «2–1», o «–» se non ci sono dati.
    var punteggio: String {
        guard let c = golCasa, let t = golTrasferta else { return "–" }
        return "\(c)–\(t)"
    }

    /// Cosa scrivere accanto al punteggio: «34'», «Intervallo», «Finita», «18:30».
    var etichetta: String {
        switch stato ?? "" {
        case "intervallo": return "Intervallo"
        case "finita": return "Finita"
        case "rinviata": return "Rinviata"
        case "sospesa": return "Sospesa"
        case "da_giocare", "": return quando.map { Quando.ora($0) } ?? "—"
        default: return minuto ?? "In corso"
        }
    }

    /// Frase per VoiceOver: «Inter 1, Roma 0, 34 minuti».
    var frase: String {
        let a = ColoriSquadra.sigla(casa), b = ColoriSquadra.sigla(trasferta)
        guard golCasa != nil else { return "\(a) contro \(b), \(etichetta)" }
        return "\(a) \(golCasa ?? 0), \(b) \(golTrasferta ?? 0), \(etichetta)"
    }
}

struct LiveWidget: Decodable, Equatable {
    var aggiornatoIl: String?
    var fonte: String?
    var inCorso: Int?
    var partite: [PartitaLive]?
}

extension RiassuntoWidget {
    /// Le partite da mostrare: prima quelle in gioco, poi quelle da giocare per orario, poi le finite.
    var partiteLive: [PartitaLive] {
        let tutte = live?.partite ?? []
        func rango(_ p: PartitaLive) -> Int { p.inGioco ? 0 : (p.finita ? 2 : 1) }
        return tutte.sorted { (rango($0), $0.quando ?? .distantFuture) < (rango($1), $1.quando ?? .distantFuture) }
    }

    var partiteInGioco: [PartitaLive] { partiteLive.filter(\.inGioco) }

    /// La prossima partita da giocare (dopo adesso o iniziata da poco senza dati).
    func prossimaPartita(dopo adesso: Date = Date()) -> PartitaLive? {
        partiteLive.filter { !$0.inGioco && !$0.finita && $0.stato != "rinviata" && ($0.quando ?? .distantPast) > adesso.addingTimeInterval(-15 * 60) }
            .min { ($0.quando ?? .distantFuture) < ($1.quando ?? .distantFuture) }
    }

    /// I miei titolari che giocano in questa partita: la mia rosa dice contro chi e se in casa.
    func mieiTitolari(in p: PartitaLive) -> [GiocatoreWidget] {
        let titolari = Set((formazione?.titolari ?? []).map(\.id))
        return (rosa ?? []).filter { g in
            guard titolari.contains(g.id) || g.titolare == true, let avv = g.avversario else { return false }
            return g.inCasa == true ? (p.trasferta == avv) : (p.casa == avv)
        }
    }

    /// true se ha senso aggiornare spesso: c'è una partita in gioco o sta per iniziare (da 10 minuti prima).
    func finestraLive(adesso: Date = Date()) -> Bool {
        if !partiteInGioco.isEmpty { return true }
        return partiteLive.contains { p in
            guard !p.finita, p.stato != "rinviata", let q = p.quando else { return false }
            return q.timeIntervalSince(adesso) < 10 * 60 && adesso.timeIntervalSince(q) < 130 * 60
        }
    }
}

// MARK: Intervallo dei punti attesi (campo `intervallo` di /api/widget: «tra X e Y», 8 volte su 10)

struct IntervalloWidget: Codable, Equatable {
    var basso: Double?
    var alto: Double?
    var confidenza: Double?
    /// true se il modello e' ancora poco provato: l'intervallo e' solo una stima.
    var indicativo: Bool?

    /// «tra 62 e 84», o nil se mancano i due estremi.
    var testo: String? {
        guard let basso, let alto, basso.isFinite, alto.isFinite else { return nil }
        return "tra \(Formato.intero(basso)) e \(Formato.intero(alto))"
    }

    /// «tra 62 e 84 (8 volte su 10)», con «indicativo» se serve.
    var testoLungo: String? {
        guard let t = testo else { return nil }
        let volte = Formato.intero((confidenza ?? 0.8) * 10)
        return "\(t) (\(volte) volte su 10)" + (indicativo == true ? ", indicativo" : "")
    }
}

extension RiassuntoWidget {
    /// Il giocatore scelto (tra osservati, mia rosa, titolari); senza scelta o se non c'e' piu', il primo osservato.
    func osservato(_ scelto: Int?) -> GiocatoreWidget? {
        if let scelto {
            let trovato = (osservati ?? []).first { $0.id == scelto } ?? (rosa ?? []).first { $0.id == scelto }
                ?? (formazione?.titolari ?? []).first { $0.id == scelto }
            if let trovato { return trovato }
        }
        return osservati?.first
    }
}
