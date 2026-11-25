import Foundation

/// SCHELETRO per vedere fallire i test (#889): la versione vera arriva nel commit dopo.
struct AnteprimaRegolamento: Equatable, Sendable {
    struct Valore: Equatable, Sendable, Identifiable {
        let id: Int
        let testo: String
        let motivo: String?
        let daRiga: String?
    }

    let riconosciuti: [Valore]
    let nonApplicati: [Valore]

    var vuota: Bool { riconosciuti.isEmpty }
    var siApplica: Bool { !riconosciuti.isEmpty }

    init(_ esito: RiconoscimentoRegole) {
        riconosciuti = esito.modifiche.enumerated().map {
            Valore(id: $0.offset, testo: "\($0.element.etichetta): \(RegoleLogica.descrivi($0.element.valore))", motivo: nil,
                   daRiga: $0.element.riga.map { Catalogo.Regole.daRiga(r: $0) })
        }
        nonApplicati = []
    }

    static func valore(chiave: String, _ v: JSONValue) -> String {
        RegoleLogica.descrivi(v)
    }
}
