import Foundation
import SwiftUI

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

    /// Una riga breve SOLO se c'è qualcosa da guardare: «Infortunato», «Squalificato», «Non convocato», «In dubbio · gioca 55%», «Panchina».
    /// Titolare (o nessuno stato) = stringa vuota. Il server manda `stato` = titolare | panchina | non_convocato | infortunato |
    /// squalificato e il dubbio a parte (`dubbio`); negli avvisi c'è `tipo`. Stesso ordine di `Giocatore.etichette`: prima
    /// l'assenza sicura, poi il dubbio, poi la panchina. Un valore nuovo si scrive leggibile («nuovo_stato» → «Nuovo stato»).
    var descrizioneStato: String {
        let chiave = (stato ?? tipo ?? "").lowercased()
        switch chiave {
        case "infortunato": return "Infortunato"
        case "squalificato": return "Squalificato"
        case "non_convocato": return "Non convocato"
        default: break
        }
        if dubbio == true || chiave == "dubbio" {
            // una sola percentuale in tutta l'app: «gioca N%» da `p_voto` (la percentuale delle probabili non si mostra)
            return DubbioRiassunto.inDubbio(pVoto)
        }
        switch chiave {
        case "", "titolare", "disponibile": return ""
        case "panchina": return "Panchina"
        default:
            let t = chiave.replacingOccurrences(of: "_", with: " ")
            return t.prefix(1).uppercased() + t.dropFirst()
        }
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
    /// true se il server manda la formazione salvata dall'utente (non la consigliata). Facoltativo e tollerante.
    var tuaScelta: Bool?

    private enum CodingKeys: String, CodingKey { case modulo, puntiAttesi, titolari, panchina, intervallo, tuaScelta }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        modulo = try? c.decodeIfPresent(String.self, forKey: .modulo)
        puntiAttesi = try? c.decodeIfPresent(Double.self, forKey: .puntiAttesi)
        titolari = try? c.decodeIfPresent([GiocatoreWidget].self, forKey: .titolari)
        panchina = try? c.decodeIfPresent([Int].self, forKey: .panchina)
        intervallo = try? c.decodeIfPresent(IntervalloWidget.self, forKey: .intervallo)
        tuaScelta = try? c.decodeIfPresent(Bool.self, forKey: .tuaScelta)
    }
}

struct PuntiGiornata: Codable, Equatable, Identifiable {
    /// Il numero di Serie A mandato dal server; in `giornateGiocate` diventa il numero da mostrare (quello della lega se c'è).
    var giornata: Int
    /// Il numero nella lega e la stagione della voce, gli stessi di `GET /api/diario` (server dal 2/11/2026; uno vecchio non li
    /// manda). `giornataLega` è nil fuori dalla stagione in corso.
    var giornataLega: Int?
    var stagione: String?
    var attesi: Double?
    var fatti: Double?
    /// La fascia prevista per quella giornata (facoltativa: un server vecchio non la manda).
    var intervallo: IntervalloWidget?
    var id: String { "\(stagione ?? "")/\(numero)" }

    private enum Chiavi: String, CodingKey { case giornata, giornataLega, stagione, attesi, fatti, intervallo }

    init(giornata: Int, giornataLega: Int? = nil, stagione: String? = nil, attesi: Double? = nil, fatti: Double? = nil,
         intervallo: IntervalloWidget? = nil) {
        self.giornata = giornata; self.giornataLega = giornataLega; self.stagione = stagione
        self.attesi = attesi; self.fatti = fatti; self.intervallo = intervallo
    }

    /// Tollerante: una fascia, un numero di lega o una stagione con la forma sbagliata si ignorano, la giornata resta.
    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        giornata = try k.decode(Int.self, forKey: .giornata)
        giornataLega = ((try? k.decodeIfPresent(Int.self, forKey: .giornataLega)) ?? nil).flatMap { $0 > 0 ? $0 : nil }
        stagione = ((try? k.decodeIfPresent(String.self, forKey: .stagione)) ?? nil).flatMap { $0.isEmpty ? nil : $0 }
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

/// Gli id delle funzioni che interessano ai widget (campo `funzioni` di `/api/widget`).
enum FunzioneWidget {
    /// «Widget aggiuntivi»: oltre a Prossima giornata e Formazione (qui: Da controllare).
    static let extra = "widget_extra"
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
    /// Fase della giornata e i suoi blocchi, come in `/api/oggi` (facoltativi: un server che non li manda = comportamento di sempre).
    private var faseLetta: Facoltativo<String>?
    var fase: String? { faseLetta?.valore }
    private var inCorsoLetto: Facoltativo<GiornataInCorso>?
    private var riepilogoLetto: Facoltativo<RiepilogoGiornata>?
    var mancano: [String]?
    /// Quali funzioni sono accese per questo utente (facoltativo: un server vecchio non lo manda). Chiave assente = acceso.
    var funzioni: [String: Bool]?

    /// Vero se la funzione è accesa. Con `convertFromSnakeCase` anche le chiavi del dizionario diventano «widgetExtra»: si guardano entrambe.
    func acceso(_ id: String) -> Bool {
        let camelCase = id.split(separator: "_").enumerated().map { $0.offset == 0 ? String($0.element) : $0.element.capitalized }.joined()
        return (funzioni?[id] ?? funzioni?[camelCase]) != false
    }

    var scambio: ScambioWidget? { scambioLetto?.valore }
    var svincolato: SvincolatoWidget? { svincolatoLetto?.valore }
    var live: LiveWidget? { liveLetto?.valore }

    enum CodingKeys: String, CodingKey {
        case giornata, giornataLega, primaPartita, scadenza, oreMancanti, iniziata, conProbabili, squadra, creditiResidui, formazione, avvisi, rosa
        case squalificati, diffidati, rigoristi, diario, osservati, dati, mancano, funzioni
        case scambioLetto = "scambio"
        case svincolatoLetto = "svincolato"
        case liveLetto = "live"
        // con convertFromSnakeCase «in_corso» arriva come «inCorso»
        case faseLetta = "fase"
        case inCorsoLetto = "inCorso"
        case riepilogoLetto = "riepilogo"
    }

    /// La fase con i suoi blocchi (ognuno solo nella sua fase).
    var faseGiornata: FaseRiassunto { FaseRiassunto(fase: fase, inCorso: inCorsoLetto?.valore, riepilogo: riepilogoLetto?.valore) }

    /// «Giornata 7 di lega (Serie A 10)», «Giornata 10» o nil se la giornata non si conosce.
    var etichettaGiornata: String? { giornata.map { TempiLega.etichetta(serieA: $0, lega: giornataLega) } }
    var siglaGiornata: String? { giornata.map { TempiLega.sigla(serieA: $0, lega: giornataLega) } }

    /// Quando comincia la giornata (la scadenza della formazione).
    var inizio: Date? { Quando.data(scadenza) }

    /// Chi della formazione ha un dubbio, un infortunio o una squalifica. Vuoto a formazione chiusa (giornata in corso o finita).
    var daControllare: [GiocatoreWidget] { faseGiornata.chiusa ? [] : (avvisi ?? []).filter { $0.inFormazione == true } }

    /// I giocatori della mia rosa che giocano a breve, in ordine di orario (solo con la partita nota).
    func giocanoPresto(dopo adesso: Date = Date(), massimo: Int = 8) -> [GiocatoreWidget] {
        (rosa ?? []).filter { ($0.quando ?? .distantPast) > adesso.addingTimeInterval(-2 * 3600) && $0.stato != "infortunato" && $0.stato != "squalificato" && $0.stato != "non_convocato" }
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
                             giornataLega: giornataLega, fase: faseGiornata)
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
        LinguaServer.applica(&r)
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

    /// Il numero da mostrare: `giornata_lega ?? giornata`, come l'app e la web.
    var numero: Int { giornataLega ?? giornata }

    /// La stagione da scrivere accanto al numero, solo per le voci di un'altra stagione: il server manda `giornata_lega` null
    /// fuori dalla stagione in corso. Un server vecchio non manda la stagione: nil.
    var altraStagione: String? { giornataLega == nil ? stagione : nil }

    /// «Giornata 8», «Giornata 38 · 2025-26» (un'altra stagione, come il Diario dell'app e della web).
    var titolo: String { "Giornata \(numero)" + (altraStagione.map { " · \($0)" } ?? "") }

    /// «G8»: per gli spazi stretti, solo il numero (la stagione resta nel titolo e in VoiceOver).
    var sigla: String { "G\(numero)" }

    /// Le giornate per il grafico, dalla più vecchia alla più recente: le ultime `massimo` con almeno un numero. `giornate` arriva
    /// dalla più recente (`giornateGiocate`): a inizio stagione la 38 dell'anno prima viene prima della giornata 1, non dopo.
    static func perGrafico(_ giornate: [PuntiGiornata], massimo: Int) -> [PuntiGiornata] {
        Array(giornate.filter { $0.fatti != nil || $0.attesi != nil }.prefix(max(0, massimo)).reversed())
    }

    /// Una frase per VoiceOver: «Giornata 10: 63,5 punti fatti, 66,0 attesi, dentro la fascia prevista, tra 62 e 85»;
    /// per un'altra stagione «Giornata 38 del 2025-26: …». Stesso numero del testo sullo schermo.
    var descrizione: String {
        var t = "Giornata \(numero)" + (altraStagione.map { " del \($0)" } ?? "") + ": "
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

    /// Le giornate del diario che hanno i punti fatti, dalla più recente, con il numero della LEGA (come «Giornata 8» in Oggi).
    /// Prima la stagione in corso, poi le ultime della stagione prima (a inizio stagione il diario le ha ancora).
    /// Server dal 2/11/2026: ogni voce porta `giornata_lega` e `stagione`, gli stessi del Diario; ordine e numeri sono i suoi.
    /// Server vecchio (nessuna voce con i due campi): il numero si ricava con lo scarto della giornata in corso (`numeroDiLega`).
    var giornateGiocate: [PuntiGiornata] {
        let giocate = (diario ?? []).filter { $0.fatti != nil }
        if giocate.contains(where: { $0.stagione != nil || $0.giornataLega != nil }) {
            return giocate.map { g in
                var x = g
                x.giornata = g.numero
                return x
            }
        }
        let attuale = giornata ?? Int.max
        return giocate
            .sorted { a, b in
                let (aInCorso, bInCorso) = (a.giornata <= attuale, b.giornata <= attuale)
                return aInCorso != bInCorso ? aInCorso : a.giornata > b.giornata
            }
            .compactMap { g in
                guard let n = numeroDiLega(g.giornata) else { return nil }
                var x = g
                x.giornata = n
                return x
            }
    }

    /// Il numero di lega di una giornata di Serie A del diario, con lo scarto della giornata attuale; senza numero di lega, quello di Serie A.
    /// SOLO ripiego per un server vecchio, che non manda la stagione delle voci (quello nuovo manda `giornata_lega`): una giornata DOPO
    /// quella attuale è della stagione prima e resta di Serie A (a inizio stagione la 38 resta 38, non diventa 35). Una giornata giocata
    /// prima che la lega partisse non è della lega: nil, così non si confonde con la giornata della lega che ha lo stesso numero.
    func numeroDiLega(_ serieA: Int) -> Int? {
        guard let g = giornata, let l = giornataLega, l > 0, g >= l, serieA <= g else { return serieA }
        let n = serieA - (g - l)
        return n > 0 ? n : nil
    }
}

// MARK: Partite in diretta (campo `live` di /api/widget, copia piccola di GET /api/live). Tutto facoltativo: un client deve ignorare
// stati e tipi nuovi e trattare «stato sconosciuto con un punteggio» come partita in corso.

struct EventoLive: Decodable, Equatable {
    var tipo: String?
    var minuto: String?
    var squadra: String?
    var chi: String?
    /// Chi ha fatto l'assist (solo per i gol, se il server lo sa).
    var assist: String?

    enum CodingKeys: String, CodingKey { case tipo, minuto, squadra, chi, assist }

    init(tipo: String? = nil, minuto: String? = nil, squadra: String? = nil, chi: String? = nil, assist: String? = nil) {
        self.tipo = tipo; self.minuto = minuto; self.squadra = squadra; self.chi = chi; self.assist = assist
    }

    /// Tollerante: un campo del tipo sbagliato (per esempio l'assist come oggetto) non rovina l'evento né la partita.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        tipo = try? c.decodeIfPresent(String.self, forKey: .tipo)
        minuto = (try? c.decodeIfPresent(String.self, forKey: .minuto)) ?? (try? c.decodeIfPresent(Int.self, forKey: .minuto)).map { "\($0)'" }
        squadra = try? c.decodeIfPresent(String.self, forKey: .squadra)
        chi = try? c.decodeIfPresent(String.self, forKey: .chi)
        assist = try? c.decodeIfPresent(String.self, forKey: .assist)
    }
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

extension RiassuntoWidget {
    /// «Dentro la fascia prevista in 1 giornata su 3.» (mai «1 giornate»).
    static func fraseDentro(dentro: Int, su: Int) -> String {
        "Dentro la fascia prevista in \(Formato.plurale(dentro, "giornata", "giornate")) su \(su)."
    }

    /// «In media +1,5 punti sul previsto nelle ultime 4 giornate.» / «…nell'ultima giornata.»
    static func fraseMedia(_ media: Double, giornate n: Int) -> String {
        "In media \(Formato.conSegno(media)) punti sul previsto " + (n == 1 ? "nell'ultima giornata." : "nelle ultime \(n) giornate.")
    }
}

extension RiassuntoWidget {
    /// «e un altro», «e altri 3» (mai «e altri 1»).
    static func altri(_ n: Int) -> String { n == 1 ? "e un altro" : "e altri \(n)" }
}

/// Scelte di disposizione dei widget che cambiano con il testo grande (Dynamic Type). Stanno qui, e non nelle viste, perché le
/// viste dei widget non entrano nei test: così si provano.
enum DisposizioneWidget {
    /// Quanti giocatori da controllare entrano nel widget medio «Prossima giornata»: due, uno solo appena il testo è più grande
    /// del normale (con due righe i nomi si sovrapponevano). Gli altri restano in «e altri N».
    static func righeDubbi(_ testo: DynamicTypeSize) -> Int { testo >= .xLarge ? 1 : 2 }

    /// La riga in linea del Cruscotto (Schermata di blocco): «3-4-3 · 2 da controllare». Lì il sistema mostra solo un testo e un
    /// simbolo e taglia quello che non entra, quindi con il testo più grande del normale resta solo «2 da controllare».
    static func rigaInLinea(modulo: String?, dubbi: Int, testo: DynamicTypeSize) -> String {
        let stato = dubbi > 0 ? "\(dubbi) da controllare" : "titolari a posto"
        return testo >= .xLarge ? stato : "\(modulo ?? "—") · \(stato)"
    }

    /// Quante righe provare in un elenco alto quanto il widget (dal massimo che c'è fino a una, al più sei prove): la vista tiene
    /// la prima che entra in altezza, le altre vanno in «e altri N». Senza nessuno: `[0]`.
    static func righeDaProvare(massimo: Int, totale: Int) -> [Int] {
        let quante = min(max(massimo, 0), max(totale, 0))
        guard quante > 0 else { return [0] }
        return Array(stride(from: quante, through: 1, by: -1).prefix(6))
    }

    /// Una prova per la parte bassa del widget Punti grande: quante righe della tabella e quante frasi di riepilogo.
    struct ProvaTabella: Equatable {
        let righe: Int
        let frasi: Int
    }

    /// Le prove della parte bassa del widget Punti grande, dalla più ricca alla più povera (al più sei): con il testo grande prima
    /// spariscono le frasi di riepilogo, poi le righe più vecchie, fino a due (o quelle che ci sono). La vista tiene la prima che
    /// entra in altezza: niente righe o frasi tagliate.
    static func provePuntiGrande(righe: Int, frasi: Int) -> [ProvaTabella] {
        let r = max(righe, 0), f = max(frasi, 0)
        var prove = (0...f).reversed().map { ProvaTabella(righe: r, frasi: $0) }
        let minimo = min(2, r)
        if r > minimo { prove += (minimo..<r).reversed().map { ProvaTabella(righe: $0, frasi: 0) } }
        return Array(prove.prefix(6))
    }
}

// MARK: Testi che si accorciano (mai una parola tagliata a metà)

/// Le parole dei widget e le forme dei testi, dalla più lunga alla più corta. La vista mostra la prima che entra (`TestoCheEntra`,
/// `PrimaCheEntra` in WidgetSources): dove non c'è spazio il testo perde parole intere («4 da controllare» → «4»), mai
/// «4 da contr…»; VoiceOver legge sempre la prima. Stanno qui, e non nelle viste, perché le viste dei widget non entrano nei test.
enum ParoleWidget {
    /// Il conto alla rovescia dopo la scadenza, come la web (`oggi.chiusa`): per la giornata mai «In corso».
    static let chiusa = "Chiusa"

    /// Il simbolo dei crediti, lo stesso dell'app («C» nel cerchio): i crediti non sono euro.
    static let simboloCrediti = "c.circle"

    /// «6 h 44 min» fino alla scadenza, «Chiusa» dopo, «—» se la scadenza non si sa.
    static func conto(fino scadenza: Date?, adesso: Date) -> String {
        guard let scadenza else { return "—" }
        return Quando.contoAllaRovescia(fino: scadenza, adesso: adesso) ?? chiusa
    }

    /// «4 da controllare» → «4»; senza niente da controllare «titolari a posto» → «a posto».
    static func daControllare(_ n: Int) -> [String] {
        n > 0 ? ["\(n) da controllare", "\(n)"] : ["titolari a posto", "a posto"]
    }

    /// Lo stato di un giocatore: «In dubbio · gioca 70%» → «gioca 70%», come la pillola del campo; uno stato di un pezzo solo resta.
    static func stato(_ testo: String) -> [String] {
        guard let ultima = testo.components(separatedBy: " · ").last, !ultima.isEmpty, ultima != testo else { return [testo] }
        return [testo, ultima]
    }

    /// «73,7 punti attesi» → «73,7 attesi»; con la scelta tua «… · la tua scelta» finché entra.
    static func puntiAttesi(_ punti: Double?, tuaScelta: Bool = false) -> [String] {
        let p = Formato.punti(punti)
        return tuaScelta ? ["\(p) punti attesi · la tua scelta", "\(p) attesi · la tua scelta", "\(p) attesi"]
                         : ["\(p) punti attesi", "\(p) attesi"]
    }

    /// «73,7 attesi · tra 62 e 85» → «73,7 attesi»; senza fascia come `puntiAttesi`.
    static func puntiConFascia(_ punti: Double?, fascia: String?) -> [String] {
        guard let fascia else { return puntiAttesi(punti) }
        let p = Formato.punti(punti)
        return ["\(p) attesi · \(fascia)", "\(p) attesi"]
    }

    /// «3-4-3 · 73,7 punti · tra 62 e 85» → «3-4-3 · 73,7 punti» → «3-4-3 · 73,7».
    static func moduloEPunti(_ modulo: String?, punti: Double?, fascia: String?) -> [String] {
        let m = modulo ?? "—", p = Formato.punti(punti)
        let corte = ["\(m) · \(p) punti", "\(m) · \(p)"]
        return fascia.map { ["\(m) · \(p) punti · \($0)"] + corte } ?? corte
    }

    /// «Formazione 3-4-3» (o «La tua scelta 3-4-3») → «3-4-3».
    static func titoloFormazione(_ modulo: String?, tuaScelta: Bool) -> [String] {
        let m = modulo ?? "—"
        return ["\(tuaScelta ? "La tua scelta" : "Formazione") \(m)", m]
    }

    /// Due parti che si accorciano insieme: prima tutta la seconda (la meno importante), poi la prima.
    static func coppie(_ a: [String], _ b: [String]) -> [(String, String)] {
        guard let primaA = a.first, let ultimaB = b.last else { return [] }
        return b.map { (primaA, $0) } + a.dropFirst().map { ($0, ultimaB) }
    }

    /// «Sorvani, Bastrani, Dimarzi» → «Sorvani, Bastrani e un altro» → «Sorvani e altri 2» (al più `massimo` nomi).
    static func nomi(_ nomi: [String], massimo: Int = 3) -> [String] {
        let quanti = min(nomi.count, max(massimo, 1))
        guard quanti > 0 else { return [] }
        return stride(from: quanti, through: 1, by: -1).map { k in
            let elenco = nomi.prefix(k).joined(separator: ", ")
            return k == nomi.count ? elenco : "\(elenco) \(RiassuntoWidget.altri(nomi.count - k))"
        }
    }

    /// Lo stato dei dati in una riga: «Dati delle 14:32 · probabili uscite» → «14:32 · probabili uscite» → «Dati delle 14:32».
    static func statoDati(ora: String, probabili: String) -> [String] {
        ["Dati delle \(ora) · \(probabili)", "\(ora) · \(probabili)", "Dati delle \(ora)"]
    }
}

extension PuntiGiornata {
    /// Le forme di una riga della tabella dei punti, dalla più lunga: «G7» al posto di «Giornata 7», poi via la fascia, poi solo i fatti.
    enum FormaRiga: CaseIterable { case completa, siglaConFascia, sigla, soloFatti }

    /// «G7», o «G38 · 2025-26» per una giornata di un'altra stagione (la stagione non si perde mai).
    var siglaConStagione: String { altraStagione.map { "\(sigla) · \($0)" } ?? sigla }

    /// I pezzi di una riga della tabella in quella forma: titolo, fascia (se c'è) e punti.
    func riga(_ forma: FormaRiga) -> (titolo: String, fascia: String?, punti: String) {
        let suAttesi = "\(Formato.punti(fatti)) su \(Formato.punti(attesi))"
        switch forma {
        case .completa: return (titolo, fasciaTesto, suAttesi)
        case .siglaConFascia: return (siglaConStagione, fasciaTesto, suAttesi)
        case .sigla: return (siglaConStagione, nil, suAttesi)
        case .soloFatti: return (siglaConStagione, nil, Formato.punti(fatti))
        }
    }

    /// Il titolo del rettangolo della schermata di blocco: «Giornata 7: 63,5 punti» → «G7: 63,5 punti» → «G7: 63,5».
    var formeTitolo: [String] {
        let f = Formato.punti(fatti)
        if altraStagione != nil { return ["\(siglaConStagione): \(f) punti", "\(siglaConStagione): \(f)"] }
        return ["Giornata \(numero): \(f) punti", "\(sigla): \(f) punti", "\(sigla): \(f)"]
    }

    /// La riga in linea: «G7 63,5 fatti, 66,0 attesi» → «G7 63,5 su 66,0» → «G7 63,5 fatti».
    var formeInLinea: [String] {
        let f = Formato.punti(fatti), a = Formato.punti(attesi)
        return ["\(sigla) \(f) fatti, \(a) attesi", "\(sigla) \(f) su \(a)", "\(sigla) \(f) fatti"]
    }
}

extension DubbioRiassunto {
    /// Una riga del rettangolo «Da controllare»: «Fabio Dimarzi · In dubbio · gioca 70%» → «Dimarzi · In dubbio · gioca 70%» →
    /// «Dimarzi · gioca 70%».
    var formeRiga: [String] {
        let cognome = nome.split(separator: " ").last.map(String.init) ?? nome
        var forme = ["\(nome) · \(descrizione)"]
        if cognome != nome { forme.append("\(cognome) · \(descrizione)") }
        if let corto = ParoleWidget.stato(descrizione).last, corto != descrizione { forme.append("\(cognome) · \(corto)") }
        return forme
    }
}

extension ScambioWidget {
    /// La riga in linea: «Scambio +3,4: Zanvolo, Carsetti per Zaviani» → «Scambio +3,4 punti».
    var formeInLinea: [String] {
        let g = Formato.conSegno(guadagnoMio ?? 0)
        return ["Scambio \(g): \(daiTesto) per \(ricevoTesto)", "Scambio \(g) punti"]
    }
}

// MARK: Parole delle fasi della giornata nei widget (le stesse della web: `oggi.chiusa`, `oggi.chiusa_dettaglio`, `oggi.giornata_finita`)

extension RiassuntoOggi {
    /// La giornata nella testata: a giornata finita quella appena chiusa (giornata e scadenza sono già della prossima);
    /// nil se il server non dice quale (meglio niente che il numero sbagliato).
    var etichettaTestata: String? {
        guard finita else { return etichettaGiornata }
        return giornataChiusa.map { TempiLega.etichetta(serieA: $0, lega: giornataChiusaLega) }
    }

    /// Il titolo della fase: «Chiusa» dopo la scadenza, «Giornata 8 finita» a giornata finita; nil prima della scadenza.
    var titoloFase: String? {
        if inCorso { return ParoleWidget.chiusa }
        if finita { return giornataChiusa == nil ? "Giornata finita" : "\(etichettaGiornataChiusa) finita" }
        return nil
    }

    /// La frase sotto il titolo della fase: dopo la scadenza come la web («La formazione della giornata 8 si è chiusa oggi 14:50»)
    /// e dove sono i punti; a giornata finita cosa succede ora. nil prima della scadenza.
    func fraseFase(adesso: Date) -> String? {
        if inCorso {
            var t = giornata == nil ? "La formazione si è chiusa" : "La formazione della \(etichettaGiornata.lowercased()) si è chiusa"
            if let inizio { t += " \(Quando.relativa(inizio, adesso: adesso))" }
            return t + ". I punti fatti sono in Oggi."
        }
        return finita ? "Si ricomincia con la prossima giornata." : nil
    }

    /// La prima riga del rettangolo della schermata di blocco: «G8 · Chiusa» dopo la scadenza, «G8 finita» a giornata finita.
    var testaRettangoloFase: String {
        inCorso ? "\(siglaGiornata) · \(ParoleWidget.chiusa)" : "\(siglaGiornataChiusa) finita"
    }

    /// La riga in linea: «G8: 41,5 punti fatti finora» dopo la scadenza, «G8: 69,5 punti fatti» a giornata finita.
    var rigaInLineaFase: String {
        inCorso ? "\(siglaGiornata): \(puntiFattiTesto) punti fatti finora" : "\(siglaGiornataChiusa): \(puntiFattiTesto) punti fatti"
    }

    /// Sotto il titolo del rettangolo «Da controllare» quando non ci sono nomi: la giornata, o a giornata finita la prossima.
    var sottotitoloRettangolo: String { finita ? "Prossima: \(etichettaGiornata)" : etichettaGiornata }
}

// MARK: Widget «Osservato» e «Chi gioca» (passo 1: il comportamento di prima, da correggere)

extension GiocatoreWidget {
    var giocaTesto: String? { percentuale.map { "gioca al \(Formato.intero($0))%" } }

    var statoOGioca: String? { descrizioneStato.isEmpty ? giocaTesto : descrizioneStato }

    var formeChiGioca: [String] {
        let s = descrizioneStato
        return [s.isEmpty ? partitaBreve : "\(partitaBreve) · \(s)"]
    }

    var daGuardare: Bool { !descrizioneStato.isEmpty || diffidato == true }

    func quandoGioca(adesso: Date) -> String { oraBreve }
}

enum VuotoOsservato: Equatable {
    case nessunSeguito
    case seguitiNellApp

    var titolo: String { "Nessun giocatore" }
    var frase: String { "Aggiungi un giocatore ai Seguiti (Squadra), poi scegli qui." }
    var riga: String { "Nessun osservato" }
}

extension RiassuntoWidget {
    var vuotoOsservato: VuotoOsservato { .nessunSeguito }
}
