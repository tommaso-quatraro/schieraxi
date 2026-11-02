import Foundation

/// Diario delle giornate (`GET /api/diario`): per ogni giornata finita, la formazione schierata contro quella consigliata.
/// Tutti i campi sono opzionali: un server più vecchio o dati incompleti non devono rompere la schermata.
struct DiarioRisposta: Decodable {
    let giornate: [VoceDiario]?
    let sintesi: SintesiDiario?
    /// Facoltativo: i server più vecchi non lo mandano.
    let scelteTue: ScelteTue?
    /// «Quanto ci abbiamo preso» (facoltativo: i server più vecchi non lo mandano; tollerante).
    let affidabilita: AffidabilitaDiario?
    /// «Quanto ci abbiamo preso» nella forma nuova (fantavoto, «gioca N%», consigliata contro tua, squadra). Facoltativo: se manca
    /// (server vecchio) resta la scheda di `affidabilita`; tollerante, un formato strano vale «niente da mostrare».
    let precisione: PrecisioneDiario?
}

struct VoceDiario: Decodable, Identifiable {
    let stagione: String?
    let giornata: Int?
    /// La ricostruzione di oggi con i dati di allora (porta i punti fatti).
    let consigliata: FormazioneDiario?
    let schierata: FormazioneDiario?
    /// Facoltativo: la formazione che SchieraXI consigliava davvero prima della giornata. `null` o assente = non registrata.
    let istantanea: IstantaneaDiario?
    /// Facoltativo: punti attesi contro punti fatti della consigliata, con la fascia (server nuovi).
    let attesoVsFatto: AttesoVsFatto?

    var id: String { "\(stagione ?? "")-\(giornata ?? 0)" }

    private enum Chiavi: String, CodingKey { case stagione, giornata, consigliata, schierata, istantanea, attesoVsFatto }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: Chiavi.self)
        stagione = try? c.decodeIfPresent(String.self, forKey: .stagione)
        giornata = try? c.decodeIfPresent(Int.self, forKey: .giornata)
        consigliata = try? c.decodeIfPresent(FormazioneDiario.self, forKey: .consigliata)
        schierata = try? c.decodeIfPresent(FormazioneDiario.self, forKey: .schierata)
        // Un'istantanea in un formato che non conosco vale come «non registrata»: il resto del Diario si legge lo stesso.
        istantanea = try? c.decodeIfPresent(IstantaneaDiario.self, forKey: .istantanea)
        attesoVsFatto = (try? c.decodeIfPresent(AttesoVsFatto.self, forKey: .attesoVsFatto)) ?? nil
    }

    /// Il confronto «Cosa consigliava SchieraXI» contro «Cosa hai schierato»; `nil` se non c'è nessuna formazione consigliata da mostrare.
    var confronto: ConfrontoDiario? { ConfrontoDiario(self) }
}

/// La formazione consigliata salvata dal server per una giornata (`istantanea` di `GET /api/diario`).
struct IstantaneaDiario: Decodable {
    let giornata: Int?
    let modulo: String?
    let titolari: [TitolareDiario]?
    let panchina: [TitolareDiario]?
    let atteso: Double?
    /// Può mancare o essere `null`.
    let stile: String?
    /// Ora italiana ISO senza fuso, per esempio `2026-10-31T10:05:00`.
    let calcolata: String?
}

struct FormazioneDiario: Decodable {
    let modulo: String?
    let atteso: Double?
    let reale: Double?
    let dev: Double?
    let intervallo: IntervalloPunti?
    let titolari: [TitolareDiario]?
    /// «consigliata» se hai segnato con un tocco di aver schierato la consigliata.
    let tipo: String?
}

struct TitolareDiario: Decodable {
    let id: Int?
    let nome: String?
    let ruolo: String?
}

struct SintesiDiario: Decodable {
    let giornate: Int?
    let puntiSchierata: Double?
    let puntiConsigliata: Double?
    let attesiSchierata: Double?
    let meglioTua: Int?
    let meglioConsigliata: Int?
}

/// Legge un numero senza far fallire niente: un tipo sbagliato o un numero non finito valgono «manca».
private func numeroDiario<K: CodingKey>(_ c: KeyedDecodingContainer<K>, _ chiave: K) -> Double? {
    guard let v = (try? c.decodeIfPresent(Double.self, forKey: chiave)) ?? nil, v.isFinite else { return nil }
    return v
}

/// Punti attesi contro punti fatti della formazione consigliata in una giornata (`atteso_vs_fatto` di `GET /api/diario`).
/// Tollerante: se manca qualcosa resta vuoto e la riga non si mostra.
struct AttesoVsFatto: Decodable, Equatable {
    var atteso: Double?
    var fatti: Double?
    /// Fatti meno attesi: positivo = meglio del previsto.
    var scarto: Double?
    /// nil se la fascia non c'era.
    var nellaFascia: Bool?
    var intervallo: IntervalloPunti?

    private enum Chiavi: String, CodingKey { case atteso, fatti, scarto, nellaFascia, intervallo }

    init(atteso: Double? = nil, fatti: Double? = nil, scarto: Double? = nil, nellaFascia: Bool? = nil, intervallo: IntervalloPunti? = nil) {
        self.atteso = atteso; self.fatti = fatti; self.scarto = scarto; self.nellaFascia = nellaFascia; self.intervallo = intervallo
    }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        atteso = numeroDiario(k, .atteso)
        fatti = numeroDiario(k, .fatti)
        scarto = numeroDiario(k, .scarto)
        nellaFascia = (try? k.decodeIfPresent(Bool.self, forKey: .nellaFascia)) ?? nil
        intervallo = (try? k.decodeIfPresent(IntervalloPunti.self, forKey: .intervallo)) ?? nil
    }
}

/// «Quanto ci abbiamo preso» (`affidabilita` di `GET /api/diario`): tutte le giornate, anche quelle andate male.
/// Tollerante: un campo strano resta vuoto, senza rompere il Diario.
struct AffidabilitaDiario: Decodable, Equatable {
    var giornate: Int?
    var scartoMedio: Double?
    var erroreMedio: Double?
    var puntiMediAttesi: Double?
    var puntiMediFatti: Double?
    var dentroFascia: Int?
    var conFascia: Int?
    var percentualeDentro: Double?
    /// Quante volte su 100 i punti dovrebbero cadere nella fascia (80).
    var fasciaDichiarata: Double?
    var pochiDati: Bool?
    var giornateMinime: Int?
    /// `pochi_dati`, `in_linea`, `sotto_le_attese`, `sopra_le_attese` (un server più nuovo può aggiungerne).
    var giudizio: String?

    private enum Chiavi: String, CodingKey {
        case giornate, scartoMedio, erroreMedio, puntiMediAttesi, puntiMediFatti, dentroFascia, conFascia, percentualeDentro
        case fasciaDichiarata, pochiDati, giornateMinime, giudizio
    }

    init(giornate: Int? = nil, scartoMedio: Double? = nil, erroreMedio: Double? = nil, puntiMediAttesi: Double? = nil, puntiMediFatti: Double? = nil,
         dentroFascia: Int? = nil, conFascia: Int? = nil, percentualeDentro: Double? = nil, fasciaDichiarata: Double? = nil,
         pochiDati: Bool? = nil, giornateMinime: Int? = nil, giudizio: String? = nil) {
        self.giornate = giornate; self.scartoMedio = scartoMedio; self.erroreMedio = erroreMedio
        self.puntiMediAttesi = puntiMediAttesi; self.puntiMediFatti = puntiMediFatti
        self.dentroFascia = dentroFascia; self.conFascia = conFascia; self.percentualeDentro = percentualeDentro
        self.fasciaDichiarata = fasciaDichiarata; self.pochiDati = pochiDati; self.giornateMinime = giornateMinime; self.giudizio = giudizio
    }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        let intero: (Chiavi) -> Int? = { chiave in numeroDiario(k, chiave).map { Formato.intero($0) } }
        giornate = intero(.giornate)
        scartoMedio = numeroDiario(k, .scartoMedio)
        erroreMedio = numeroDiario(k, .erroreMedio)
        puntiMediAttesi = numeroDiario(k, .puntiMediAttesi)
        puntiMediFatti = numeroDiario(k, .puntiMediFatti)
        dentroFascia = intero(.dentroFascia)
        conFascia = intero(.conFascia)
        percentualeDentro = numeroDiario(k, .percentualeDentro)
        fasciaDichiarata = numeroDiario(k, .fasciaDichiarata)
        pochiDati = (try? k.decodeIfPresent(Bool.self, forKey: .pochiDati)) ?? nil
        giornateMinime = intero(.giornateMinime)
        giudizio = (try? k.decodeIfPresent(String.self, forKey: .giudizio)) ?? nil
    }
}

/// Il file di backup scaricato dal server o scelto per il ripristino: controlli fatti sul telefono PRIMA di inviare.
enum FileBackup {
    static let formato = "schieraxi-backup"
    static let versioneMassima = 1
    static let massimoByte = 10 * 1024 * 1024

    enum Errore: Error, Equatable, LocalizedError {
        case vuoto, troppoGrande, nonEUnBackup, piuNuovo

        var errorDescription: String? {
            switch self {
            case .vuoto: return "Il file è vuoto."
            case .troppoGrande: return "Il file è troppo grande per essere una copia di sicurezza di SchieraXI."
            case .nonEUnBackup: return "Questo file non è una copia di sicurezza di SchieraXI."
            case .piuNuovo: return "Questa copia di sicurezza viene da una versione più nuova dell'app: aggiorna l'app e riprova."
            }
        }
    }

    /// Controlla il contenuto (formato e versione, almeno un file dentro). Non cambia i dati.
    static func controlla(_ dati: Data) -> Result<Void, Errore> {
        if dati.isEmpty { return .failure(.vuoto) }
        if dati.count > massimoByte { return .failure(.troppoGrande) }
        guard let radice = (try? JSONSerialization.jsonObject(with: dati)) as? [String: Any],
              let nome = radice["formato"] as? String, nome == formato,
              let versione = radice["versione"] as? Int,
              let file = radice["file"] as? [String: Any], !file.isEmpty else { return .failure(.nonEUnBackup) }
        if versione > versioneMassima { return .failure(.piuNuovo) }
        return .success(())
    }

    /// Il nome del file da condividere: `schieraxi-backup-2026-10-30.json` (la data viene dal backup, ripulita).
    static func nomeFile(_ dati: Data) -> String {
        let creato = ((try? JSONSerialization.jsonObject(with: dati)) as? [String: Any])?["creato"] as? String ?? ""
        let giorno = String(creato.prefix(10).filter { $0.isNumber || $0 == "-" })
        return "schieraxi-backup" + (giorno.count == 10 ? "-" + giorno : "") + ".json"
    }
}

struct RisultatoRipristino: Decodable {
    let ripristinati: [String]?
}
