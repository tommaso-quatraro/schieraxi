import Foundation

// «Sotto il cofano»: come ragiona SchieraXI, spiegato con i testi del server (GET /api/sotto-il-cofano). L'app non ha testi suoi,
// solo il disegno: una correzione arriva a tutti con un aggiornamento del server. Tutto facoltativo e tollerante: un campo
// nuovo, mancante o sbagliato non deve rompere la pagina. Si legge SENZA conversione dei nomi (`snake: false`): le chiavi dei
// numeri («app.errore_modello») sono dati, non nomi di campi.

/// Un elemento letto senza far fallire l'elenco: se è sbagliato, `valore` resta nil.
private struct Elemento<T: Decodable>: Decodable {
    let valore: T?
    init(from decoder: Decoder) throws { valore = try? T(from: decoder) }
}

private extension KeyedDecodingContainer {
    /// Il valore se c'è ed è del tipo giusto, altrimenti nil (mai un errore).
    func lettoOpz<T: Decodable>(_ chiave: Key) -> T? {
        (try? decodeIfPresent(T.self, forKey: chiave)) ?? nil
    }

    /// Un elenco letto elemento per elemento: quelli sbagliati si saltano.
    func elenco<T: Decodable>(_ chiave: Key) -> [T] {
        let grezzo: [Elemento<T>]? = lettoOpz(chiave)
        return (grezzo ?? []).compactMap(\.valore)
    }
}

struct SottoIlCofano: Decodable {
    /// Versione della struttura che questa app sa leggere.
    static let formatoSupportato = 1

    var formato: Int?
    var titolo: String?
    var sottotitolo: String?
    var aggiornato: String?
    var livelli: [String: String]?
    var introduzione: [String] = []
    var sezioni: [SezioneCofano] = []
    var glossario: [TermineCofano] = []
    var misure: MisureCofano?

    private enum Chiavi: String, CodingKey {
        case formato, titolo, sottotitolo, aggiornato, livelli, introduzione, sezioni, glossario, misure
    }

    init() {}

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        formato = k.lettoOpz(.formato)
        titolo = k.lettoOpz(.titolo)
        sottotitolo = k.lettoOpz(.sottotitolo)
        aggiornato = k.lettoOpz(.aggiornato)
        livelli = k.lettoOpz(.livelli)
        introduzione = k.elenco(.introduzione)
        sezioni = k.elenco(.sezioni)
        glossario = k.elenco(.glossario)
        misure = k.lettoOpz(.misure)
    }

    /// La struttura è più nuova di quella che l'app conosce: si mostra quello che si capisce e un invito ad aggiornare.
    var piuNuovaDellApp: Bool { (formato ?? Self.formatoSupportato) > Self.formatoSupportato }

    /// «Testi aggiornati il 30 ott 2026; misure del 30 ott 2026».
    var rigaDate: String? {
        var pezzi: [String] = []
        if let a = aggiornato, !a.isEmpty { pezzi.append("Testi aggiornati il \(Quando.dataVersione(a))") }
        if let d = misure?.riferimento?.data, !d.isEmpty { pezzi.append("misure del \(Quando.dataVersione(d))") }
        return pezzi.isEmpty ? nil : pezzi.joined(separator: "; ")
    }

    func sezioniVisibili(_ livello: LivelloCofano) -> [SezioneCofano] {
        sezioni.filter { livello.mostra($0) }
    }

    /// Il glossario in ordine alfabetico, filtrato da quello che l'utente scrive (senza badare a maiuscole e accenti).
    func glossario(cercando ricerca: String) -> [TermineCofano] {
        let ordinato = glossario.sorted { $0.termine.compare($1.termine, locale: Formato.locale) == .orderedAscending }
        let q = ricerca.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return ordinato }
        func norma(_ t: String) -> String { t.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Formato.locale) }
        let cerca = norma(q)
        return ordinato.filter { norma($0.termine).contains(cerca) || norma($0.spiegazione).contains(cerca) }
    }

    /// I numeri citati da una sezione: il valore attuale se il server lo ha, altrimenti quello di riferimento.
    func numeri(di sezione: SezioneCofano) -> [NumeroCofano] {
        sezione.numeri.compactMap { chiave -> NumeroCofano? in
            let rif = misure?.riferimento?.voci?[chiave]
            if let a = misure?.attuali?.voci?[chiave], let v = a.valore, v.isFinite {
                return NumeroCofano(chiave: chiave, etichetta: rif?.etichetta ?? Self.nomeDaChiave(chiave),
                                    valore: Self.formattaValore(v, unita: rif?.unita), attuale: true,
                                    quando: Self.soloData(a.aggiornato))
            }
            if let r = rif, let v = r.valore, v.isFinite {
                return NumeroCofano(chiave: chiave, etichetta: r.etichetta ?? Self.nomeDaChiave(chiave),
                                    valore: Self.formattaValore(v, unita: r.unita), attuale: false,
                                    quando: Self.soloData(misure?.riferimento?.data))
            }
            return nil
        }
    }

    static func soloData(_ testo: String?) -> String? {
        guard let t = testo?.trimmingCharacters(in: .whitespaces), t.count >= 10 else { return nil }
        let data = Quando.dataVersione(String(t.prefix(10)))
        return data.isEmpty ? nil : data
    }

    /// «1,46 punti», «47%», «8 giornate». Intero senza decimali, altrimenti fino a due.
    static func formattaValore(_ v: Double, unita: String?) -> String {
        guard v.isFinite else { return "—" }
        let numero = (v == v.rounded() && abs(v) < 1e12) ? Formato.decimali(v, cifre: 0) : Formato.decimali(v, cifre: 2)
        guard let u = unita?.trimmingCharacters(in: .whitespaces), !u.isEmpty else { return numero }
        return u == "%" ? "\(numero)%" : "\(numero) \(u)"
    }

    /// «backtest.errore_modello» diventa «errore modello» quando il server non manda un'etichetta.
    static func nomeDaChiave(_ chiave: String) -> String {
        (chiave.split(separator: ".").last.map(String.init) ?? chiave).replacingOccurrences(of: "_", with: " ")
    }
}

/// Quali sezioni mostrare: solo le «base», solo quelle per i più nerd, o tutte.
enum LivelloCofano: String, CaseIterable, Identifiable {
    case base, nerd, tutto
    var id: String { rawValue }

    var titolo: String {
        switch self {
        case .base: return "Base"
        case .nerd: return "Nerd"
        case .tutto: return "Tutto"
        }
    }

    func mostra(_ sezione: SezioneCofano) -> Bool {
        switch self {
        case .tutto: return true
        case .base: return sezione.livello != "nerd"
        case .nerd: return sezione.livello == "nerd"
        }
    }

    /// Dal valore ricordato sul dispositivo (uno sconosciuto torna a «base»).
    init(ricordato: String) { self = LivelloCofano(rawValue: ricordato) ?? .base }
}

struct SezioneCofano: Decodable, Identifiable {
    var id: String
    var titolo: String
    /// «base» o «nerd»; uno sconosciuto conta come base.
    var livello: String?
    var paragrafi: [String] = []
    var formula: String?
    var esempio: EsempioCofano?
    var numeri: [String] = []
    var rimandi: [RimandoCofano] = []

    private enum Chiavi: String, CodingKey { case id, titolo, livello, paragrafi, formula, esempio, numeri, rimandi }

    init(id: String, titolo: String, livello: String? = nil, paragrafi: [String] = [], formula: String? = nil,
         esempio: EsempioCofano? = nil, numeri: [String] = [], rimandi: [RimandoCofano] = []) {
        self.id = id; self.titolo = titolo; self.livello = livello; self.paragrafi = paragrafi; self.formula = formula
        self.esempio = esempio; self.numeri = numeri; self.rimandi = rimandi
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        let idLetto: String? = k.lettoOpz(.id)
        // Una sezione senza titolo non si può mostrare: l'elenco la salta.
        guard let nome: String = k.lettoOpz(.titolo), !nome.isEmpty else {
            throw DecodingError.dataCorruptedError(forKey: .titolo, in: k, debugDescription: "sezione senza titolo")
        }
        id = idLetto ?? nome
        titolo = nome
        livello = k.lettoOpz(.livello)
        paragrafi = k.elenco(.paragrafi)
        formula = k.lettoOpz(.formula)
        esempio = k.lettoOpz(.esempio)
        numeri = k.elenco(.numeri)
        rimandi = k.elenco(.rimandi)
    }

    var eNerd: Bool { livello == "nerd" }
}

struct EsempioCofano: Decodable {
    var titolo: String?
    var testo: String?
    /// «vero» (numeri veri della lega) o «di calcolo» (esempio inventato per spiegare).
    var origine: String?

    private enum Chiavi: String, CodingKey { case titolo, testo, origine }

    init(titolo: String? = nil, testo: String? = nil, origine: String? = nil) {
        self.titolo = titolo; self.testo = testo; self.origine = origine
    }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        titolo = k.lettoOpz(.titolo)
        testo = k.lettoOpz(.testo)
        origine = k.lettoOpz(.origine)
    }

    /// L'etichetta dell'esempio.
    var etichetta: String { origine == "vero" ? "Numeri veri" : "Esempio di calcolo" }
}

struct RimandoCofano: Decodable, Identifiable {
    var schermata: String?
    var etichetta: String?

    private enum Chiavi: String, CodingKey { case schermata, etichetta }

    init(schermata: String? = nil, etichetta: String? = nil) { self.schermata = schermata; self.etichetta = etichetta }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        schermata = k.lettoOpz(.schermata)
        etichetta = k.lettoOpz(.etichetta)
    }

    var id: String { (schermata ?? "?") + "|" + (etichetta ?? "") }
    var testo: String { (etichetta?.isEmpty == false ? etichetta : schermata) ?? "" }
}

struct TermineCofano: Decodable, Identifiable {
    var termine: String
    var spiegazione: String
    var id: String { termine }

    private enum Chiavi: String, CodingKey { case termine, spiegazione }

    init(termine: String, spiegazione: String) { self.termine = termine; self.spiegazione = spiegazione }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        guard let t: String = k.lettoOpz(.termine), !t.isEmpty else {
            throw DecodingError.dataCorruptedError(forKey: .termine, in: k, debugDescription: "termine mancante")
        }
        termine = t
        spiegazione = k.lettoOpz(.spiegazione) ?? ""
    }
}

struct MisureCofano: Decodable {
    var riferimento: RiferimentoMisure?
    var attuali: AttualiMisure?

    private enum Chiavi: String, CodingKey { case riferimento, attuali }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        riferimento = k.lettoOpz(.riferimento)
        attuali = k.lettoOpz(.attuali)
    }
}

struct RiferimentoMisure: Decodable {
    var data: String?
    var come: String?
    var nota: String?
    var voci: [String: VoceMisura]?

    private enum Chiavi: String, CodingKey { case data, come, nota, voci }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        data = k.lettoOpz(.data)
        come = k.lettoOpz(.come)
        nota = k.lettoOpz(.nota)
        let grezze: [String: Elemento<VoceMisura>]? = k.lettoOpz(.voci)
        voci = grezze?.compactMapValues(\.valore)
    }
}

struct AttualiMisure: Decodable {
    var voci: [String: VoceAttuale]?

    private enum Chiavi: String, CodingKey { case voci }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        let grezze: [String: Elemento<VoceAttuale>]? = k.lettoOpz(.voci)
        voci = grezze?.compactMapValues(\.valore)
    }
}

struct VoceMisura: Decodable {
    var valore: Double?
    var etichetta: String?
    var unita: String?

    private enum Chiavi: String, CodingKey { case valore, etichetta, unita }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        valore = k.lettoOpz(.valore)
        etichetta = k.lettoOpz(.etichetta)
        unita = k.lettoOpz(.unita)
    }
}

struct VoceAttuale: Decodable {
    var valore: Double?
    var aggiornato: String?

    private enum Chiavi: String, CodingKey { case valore, aggiornato }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        valore = k.lettoOpz(.valore)
        aggiornato = k.lettoOpz(.aggiornato)
    }
}

/// Un numero citato da una sezione, pronto da mostrare.
struct NumeroCofano: Identifiable, Equatable {
    let chiave: String
    let etichetta: String
    let valore: String
    /// true se è il valore calcolato dal server adesso; false se è la misura di riferimento di una data.
    let attuale: Bool
    let quando: String?
    var id: String { chiave }

    /// «misurato il 30 ott 2026».
    var nota: String { quando.map { "misurato il \($0)" } ?? (attuale ? "misura attuale" : "misura di riferimento") }
}

/// Dove porta un rimando di «Sotto il cofano». Gli identificatori di schermata sconosciuti non portano da nessuna parte (testo semplice).
enum DestinazioneCofano: Equatable {
    case sezione(Sezione)
    case lega(PaginaLega)
    case impostazioni(PaginaImpostazioni)

    static func da(_ schermata: String?) -> DestinazioneCofano? {
        switch schermata ?? "" {
        case "oggi": return .sezione(.oggi)
        case "formazione": return .sezione(.formazione)
        case "scambi": return .sezione(.scambi)
        case "mercato": return .sezione(.mercato)
        case "lega": return .sezione(.lega)
        case "regole": return .lega(.regole)
        case "crediti": return .lega(.crediti)
        case "stato-dati": return .lega(.stato)
        case "diario": return .lega(.diario)
        case "novita": return .impostazioni(.novita)
        default: return nil   // «giocatore» (serve un codice) e quelli nuovi
        }
    }
}
