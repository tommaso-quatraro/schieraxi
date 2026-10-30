import Foundation

/// Diario delle giornate (`GET /api/diario`): per ogni giornata finita, la formazione schierata contro quella consigliata.
/// Tutti i campi sono opzionali: un server più vecchio o dati incompleti non devono rompere la schermata.
struct DiarioRisposta: Decodable {
    let giornate: [VoceDiario]?
    let sintesi: SintesiDiario?
}

struct VoceDiario: Decodable, Identifiable {
    let stagione: String?
    let giornata: Int?
    let consigliata: FormazioneDiario?
    let schierata: FormazioneDiario?

    var id: String { "\(stagione ?? "")-\(giornata ?? 0)" }

    /// Una frase sulle differenze tra la formazione schierata e quella del modello.
    var differenze: String? {
        guard let tue = schierata?.titolari, let loro = consigliata?.titolari else { return nil }
        let idTue = Set(tue.compactMap(\.id)), idLoro = Set(loro.compactMap(\.id))
        let fuori = tue.filter { $0.id.map { !idLoro.contains($0) } ?? false }.compactMap(\.nome)
        let dentro = loro.filter { $0.id.map { !idTue.contains($0) } ?? false }.compactMap(\.nome)
        if fuori.isEmpty { return "Stessi 11 del modello." }
        return "Il modello avrebbe messo \(dentro.joined(separator: ", ")) al posto di \(fuori.joined(separator: ", "))."
    }
}

struct FormazioneDiario: Decodable {
    let modulo: String?
    let atteso: Double?
    let reale: Double?
    let titolari: [TitolareDiario]?
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
