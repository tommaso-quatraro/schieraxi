import Foundation

/// Un JSON qualsiasi, da leggere e rimandare identico al server (regole della lega). Gli interi restano interi.
indirect enum JSONValue: Codable, Equatable {
    case nullo
    case booleano(Bool)
    case intero(Int)
    case decimale(Double)
    case testo(String)
    case lista([JSONValue])
    case oggetto([String: JSONValue])

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .nullo }
        else if let v = try? c.decode(Bool.self) { self = .booleano(v) }
        else if let v = try? c.decode(Int.self) { self = .intero(v) }
        else if let v = try? c.decode(Double.self) { self = .decimale(v) }
        else if let v = try? c.decode(String.self) { self = .testo(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .lista(v) }
        else { self = .oggetto(try c.decode([String: JSONValue].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .nullo: try c.encodeNil()
        case .booleano(let v): try c.encode(v)
        case .intero(let v): try c.encode(v)
        case .decimale(let v): try c.encode(v)
        case .testo(let v): try c.encode(v)
        case .lista(let v): try c.encode(v)
        case .oggetto(let v): try c.encode(v)
        }
    }

    /// Testo breve per i valori che l'app non modifica (liste, vuoti).
    var descrizione: String {
        switch self {
        case .nullo: return "—"
        case .booleano(let v): return v ? "sì" : "no"
        case .intero(let v): return String(v)
        case .decimale(let v): return String(v)
        case .testo(let v): return v
        case .lista(let v): return v.map(\.descrizione).joined(separator: ", ")
        case .oggetto: return "…"
        }
    }
}

/// Impostazioni degli avvisi del server: chiavi identiche a quelle del server (si leggono senza conversione).
struct ImpostazioniAvvisi: Codable, Equatable {
    var cambi: Bool
    var promemoria_60: Bool
    var promemoria_15: Bool
    var riepilogo: Bool
    /// «Reparto della rosa scoperto» (opzionale: un server più vecchio non lo manda e allora non si rimanda; di base è acceso).
    var copertura: Bool?
    /// Avvisi anche con ntfy, il cui tocco apre l'app nativa. Opzionale: un server più vecchio non lo manda
    /// (e se è nil non viene rimandato, quindi non si azzera niente).
    var app_nativa: Bool?
    /// Ore tranquille (opzionali: un server più vecchio non le manda e allora non si rimandano).
    var silenzio: Bool?
    var silenzio_da: Int?
    var silenzio_a: Int?
    /// «Avviso se il consiglio cambia»: da quanti minuti prima della scadenza (0 = spento, 30, 60, 90; di base 60).
    /// Opzionale: un server più vecchio non lo manda, e allora la scelta non si mostra e il campo non si rimanda.
    var avviso_prima: Int?

    var oreTranquille: OreTranquille {
        let p = OreTranquille.predefinite
        return OreTranquille(attive: silenzio ?? false, da: silenzio_da ?? p.da, a: silenzio_a ?? p.a)
    }
}

extension ImpostazioniAvvisi {
    /// Lettura tollerante dei campi facoltativi: un valore di tipo strano vale «non mandato» (e quindi non si rimanda),
    /// senza far fallire tutta la pagina degli avvisi. I quattro interruttori di base restano obbligatori.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        cambi = try c.decode(Bool.self, forKey: .cambi)
        promemoria_60 = try c.decode(Bool.self, forKey: .promemoria_60)
        promemoria_15 = try c.decode(Bool.self, forKey: .promemoria_15)
        riepilogo = try c.decode(Bool.self, forKey: .riepilogo)
        copertura = (try? c.decodeIfPresent(Bool.self, forKey: .copertura)) ?? nil
        app_nativa = (try? c.decodeIfPresent(Bool.self, forKey: .app_nativa)) ?? nil
        silenzio = (try? c.decodeIfPresent(Bool.self, forKey: .silenzio)) ?? nil
        silenzio_da = (try? c.decodeIfPresent(Int.self, forKey: .silenzio_da)) ?? nil
        silenzio_a = (try? c.decodeIfPresent(Int.self, forKey: .silenzio_a)) ?? nil
        avviso_prima = (try? c.decodeIfPresent(Int.self, forKey: .avviso_prima)) ?? nil
    }
}

struct StatoAvvisi: Decodable {
    let impostazioni: ImpostazioniAvvisi
    let canale: Bool?
    let dispositivi: Int?
    /// Facoltativo: il server lo manda (a `true`) solo se le ore tranquille salvate avevano inizio = fine e le ha spente.
    /// Mancante, nullo o di tipo strano vale «niente da dire».
    let oreTranquilleSpente: Bool

    private enum CodingKeys: String, CodingKey {
        case impostazioni, canale, dispositivi
        case oreTranquilleSpente = "ore_tranquille_spente"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        impostazioni = try c.decode(ImpostazioniAvvisi.self, forKey: .impostazioni)
        canale = try? c.decodeIfPresent(Bool.self, forKey: .canale)
        dispositivi = try? c.decodeIfPresent(Int.self, forKey: .dispositivi)
        oreTranquilleSpente = (try? c.decodeIfPresent(Bool.self, forKey: .oreTranquilleSpente)) ?? false
    }
}

struct SceltaSalvata: Decodable, Equatable {
    let titolari: [Int]
    var modulo: String? = nil
    var salvata: String? = nil
    /// Gli 11 salvati erano quelli della consigliata (`era_consigliata`, c'è solo se è vero): se la consigliata poi cambia, la riga
    /// dello stato dice «La consigliata è cambiata da quando l'hai salvata».
    var eraConsigliata: Bool? = nil
    /// «L'ho messa» (`messa`, c'è solo se è vero): l'utente ha detto di aver messo questi 11 nell'app della lega.
    var messa: Bool? = nil
}

struct ValutazioneManuale: Decodable {
    let modulo: String
    let punteggioAtteso: Double
    let dev: Double?
    let panchina: [Int]
    let differenza: Double?
    let consigliata: Double?
    let consigliataStessoModulo: Double?
    let bruttaGiornata: Double?
    let giornataEccezionale: Double?
    let intervallo: IntervalloPunti?
}

struct RichiestaValutazione: Encodable {
    let titolari: [Int]
    let salva: Bool
    /// Se si guarda la formazione di un'altra squadra (altrimenti la propria).
    var squadra: String? = nil
    var giornata: Int? = nil
    /// La spunta «L'ho messa» (solo con `salva`): vero o falso; senza, il server la lascia com'era finché gli 11 sono gli stessi.
    var messa: Bool? = nil
}

struct CreditiSquadre: Encodable {
    let crediti: [String: Int]
}

struct NomeSquadra: Encodable {
    let nome: String
}
