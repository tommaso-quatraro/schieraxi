import Foundation

/// Le parole della prova del modello in Stato dei dati («Quanto è affidabile il modello»).
enum ParoleAffidabilita {
    static let modello = "SchieraXI"
    static let fantamedia = "Da fantamedia"
    static let massimo = "Massimo possibile"
    static let nomeGrafico = "Grafico dei punti delle formazioni, giornata per giornata: SchieraXI, scelta da fantamedia e massimo possibile"

    static func giornate(_ righe: [RigaAffidabilita]) -> String? { nil }

    static func riga(_ r: RigaAffidabilita) -> String {
        "\(TempiLega.serieA(r.giornata)): SchieraXI \(r.puntiModello.map { Formato.decimali($0) } ?? "–"), "
            + "da fantamedia \(r.puntiFantamedia.map { Formato.decimali($0) } ?? "–"), "
            + "massimo possibile \(r.puntiPerfetta.map { Formato.decimali($0) } ?? "–")"
    }

    static func modelloBatteFantamedia(_ s: SintesiAffidabilita) -> Bool { false }
}
