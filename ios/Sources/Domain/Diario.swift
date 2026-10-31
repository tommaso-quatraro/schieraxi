import Foundation

/// Diario delle giornate (`GET /api/diario`): per ogni giornata finita, la formazione schierata contro quella consigliata.
/// Tutti i campi sono opzionali: un server più vecchio o dati incompleti non devono rompere la schermata.
struct DiarioRisposta: Decodable {
    let giornate: [VoceDiario]?
    let sintesi: SintesiDiario?
    /// Facoltativo: i server più vecchi non lo mandano.
    let scelteTue: ScelteTue?
}

struct VoceDiario: Decodable, Identifiable {
    let stagione: String?
    let giornata: Int?
    /// La ricostruzione di oggi con i dati di allora (porta i punti fatti).
    let consigliata: FormazioneDiario?
    let schierata: FormazioneDiario?
    /// Facoltativo: la formazione che SchieraXI consigliava davvero prima della giornata. `null` o assente = non registrata.
    let istantanea: IstantaneaDiario?

    var id: String { "\(stagione ?? "")-\(giornata ?? 0)" }

    private enum Chiavi: String, CodingKey { case stagione, giornata, consigliata, schierata, istantanea }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: Chiavi.self)
        stagione = try? c.decodeIfPresent(String.self, forKey: .stagione)
        giornata = try? c.decodeIfPresent(Int.self, forKey: .giornata)
        consigliata = try? c.decodeIfPresent(FormazioneDiario.self, forKey: .consigliata)
        schierata = try? c.decodeIfPresent(FormazioneDiario.self, forKey: .schierata)
        // Un'istantanea in un formato che non conosco vale come «non registrata»: il resto del Diario si legge lo stesso.
        istantanea = try? c.decodeIfPresent(IstantaneaDiario.self, forKey: .istantanea)
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
            case .troppoGrande: return "Il file è troppo grande per essere un backup di SchieraXI."
            case .nonEUnBackup: return "Questo file non è un backup di SchieraXI."
            case .piuNuovo: return "Il backup viene da una versione più nuova dell'app: aggiorna l'app e riprova."
            }
        }
    }

    /// Controlla il contenuto (formato e versione, almeno un file dentro). Non cambia i dati.
    static func controlla(_ dati: Data) -> Result<Void, Errore> {
        if dati.isEmpty { return .failure(.vuoto) }
        if dati.count > massimoByte { return .failure(.troppoGrande) }
        guard let radice = (try? JSONSerialization.jsonObject(with: dati)) as? [String: Any],
              radice["formato"] as? String == formato,
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
