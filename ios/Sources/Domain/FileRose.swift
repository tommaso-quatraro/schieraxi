import Foundation
import UniformTypeIdentifiers

/// Quali file si possono usare per importare le rose, e come si preparano per il server.
/// Il server legge Excel (.xlsx, .xlsm), CSV e testo (.txt); un file Excel vero è un archivio zip (comincia con «PK»).
/// Qui si decide cosa accettare PRIMA di inviare, con messaggi chiari, e con che nome e tipo mandarlo.
enum FileRose {
    static let messaggioFormato = "Usa un Excel (.xlsx), un CSV o un file di testo."
    /// Dimensione massima (come il server): un file delle rose è di poche decine di KB.
    static let massimoByte = 5 * 1024 * 1024

    /// Il file così come si manda al server.
    struct Preparato: Equatable {
        let nome: String
        let tipo: String
    }

    enum Errore: Error, Equatable, LocalizedError {
        case formato
        case vecchioExcel
        case vuoto
        case troppoGrande
        case excelRovinato
        case nonETesto

        var errorDescription: String? {
            switch self {
            case .formato: return FileRose.messaggioFormato
            case .vecchioExcel: return "Il vecchio formato Excel (.xls) non si legge: salvalo come Excel (.xlsx) oppure come CSV."
            case .vuoto: return "Il file è vuoto."
            case .troppoGrande: return "Il file è troppo grande (massimo 5 MB): non sembra un file delle rose."
            case .excelRovinato: return "Il file non sembra un vero Excel (.xlsx): salvalo di nuovo da Excel o esportalo come CSV."
            case .nonETesto: return "Il file non è un testo leggibile: salvalo come CSV (testo) o come Excel (.xlsx)."
            }
        }
    }

    static let tipoExcel = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    /// Le estensioni che si capiscono (l'elenco del selettore di file è più largo, poi si controlla il file vero).
    static let estensioni = ["xlsx", "xlsm", "xls", "csv", "tsv", "txt", "text"]

    /// I tipi del selettore di file di iOS. Permissivo: oltre ai tipi noti c'è `.data`, perché con un CSV salvato da altre app iOS non
    /// sempre riconosce il tipo (file senza estensione, tipi strani): dopo la scelta si controlla estensione e contenuto.
    static var tipiAmmessi: [UTType] {
        var tipi: [UTType] = [.spreadsheet, .commaSeparatedText, .tabSeparatedText, .plainText, .text]
        for estensione in estensioni {
            if let tipo = UTType(filenameExtension: estensione) { tipi.append(tipo) }
        }
        tipi.append(.data)
        var visti = Set<String>()
        return tipi.filter { visti.insert($0.identifier).inserted }
    }

    private static func eZip(_ dati: Data) -> Bool {
        dati.starts(with: [0x50, 0x4B, 0x03, 0x04])
    }

    /// Un testo vero: niente byte nulli (un file binario o un .xls) e leggibile come UTF-8 (anche con la firma BOM) o come Latin-1
    /// (l'export di certi Excel italiani).
    private static func eTesto(_ dati: Data) -> Bool {
        let campione = dati.prefix(64 * 1024)
        return !campione.contains(0)
    }

    /// Controlla il file e dice con che nome e tipo mandarlo; oppure perché non va.
    static func prepara(nome: String, dati: Data) -> Result<Preparato, Errore> {
        let estensione = (nome as NSString).pathExtension.lowercased()
        if dati.isEmpty { return .failure(.vuoto) }
        if dati.count > massimoByte { return .failure(.troppoGrande) }
        let base = pulisciNome((nome as NSString).deletingPathExtension)
        switch estensione {
        case "xlsx", "xlsm":
            return eZip(dati) ? .success(Preparato(nome: base + "." + estensione, tipo: tipoExcel)) : .failure(.excelRovinato)
        case "xls":
            // Un .xls che in realtà è uno zip (nome sbagliato) si manda come .xlsx; quello vero (formato vecchio) il server non lo legge.
            return eZip(dati) ? .success(Preparato(nome: base + ".xlsx", tipo: tipoExcel)) : .failure(.vecchioExcel)
        case "csv", "tsv":
            // Il server legge i CSV riconoscendo da solo il separatore (virgola, punto e virgola, tabulazione): un .tsv va come .csv.
            return eTesto(dati) ? .success(Preparato(nome: base + ".csv", tipo: "text/csv")) : .failure(.nonETesto)
        case "txt", "text":
            return eTesto(dati) ? .success(Preparato(nome: base + ".txt", tipo: "text/plain")) : .failure(.nonETesto)
        case "":
            // Il menu Condividi a volte non passa l'estensione: un Excel è uno zip, il resto se è testo.
            if eZip(dati) { return .success(Preparato(nome: base + ".xlsx", tipo: tipoExcel)) }
            return eTesto(dati) ? .success(Preparato(nome: base + ".txt", tipo: "text/plain")) : .failure(.formato)
        default:
            return .failure(.formato)
        }
    }

    /// Un nome adatto all'intestazione del multipart: senza virgolette, a capo, barre, e di lunghezza ragionevole.
    static func pulisciNome(_ testo: String) -> String {
        let pulito = String(testo.filter { $0 != "\"" && $0 != "\\" && $0 != "/" && !$0.isNewline && $0 != "\r" })
            .trimmingCharacters(in: .whitespaces)
        let corto = String(pulito.prefix(80))
        return corto.isEmpty ? "rose" : corto
    }
}
