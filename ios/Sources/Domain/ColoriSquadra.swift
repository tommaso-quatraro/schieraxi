import Foundation

// MARK: - Colori delle squadre (per la maglia di chi non ha la foto)

/// Colore principale e secondario (esadecimali RRGGBB) delle squadre di Serie A, come nella web app.
enum ColoriSquadra {
    static let tabella: [String: (String, String)] = [
        "atalanta": ("1e71b8", "111827"), "bologna": ("a21c26", "1a2f5a"), "cagliari": ("a51e36", "0b2a52"), "como": ("1b5fa8", "f3f4f6"),
        "fiorentina": ("6b2f9a", "f3f4f6"), "frosinone": ("f2d200", "1a56a6"), "genoa": ("b3202a", "0a2a52"), "inter": ("0a58a8", "111827"),
        "juventus": ("f3f4f6", "111827"), "lazio": ("8fc4ea", "f3f4f6"), "lecce": ("d8232a", "f2d200"), "milan": ("d11f2f", "111827"),
        "monza": ("d11f2f", "f3f4f6"), "napoli": ("3d8fd1", "f3f4f6"), "parma": ("f2f2f2", "f2c200"), "roma": ("8b1c2e", "f2a900"),
        "sassuolo": ("1f8a4c", "111827"), "torino": ("7a1f2a", "f3f4f6"), "udinese": ("f3f4f6", "111827"), "venezia": ("0b3d2e", "f08a1a"),
        "verona": ("1a3a8a", "f2d200"), "cremonese": ("b3202a", "8b95a1"), "pisa": ("0b2a52", "111827"), "sampdoria": ("1b5fa8", "f3f4f6"),
        "palermo": ("f4a6c0", "111827"), "spezia": ("f3f4f6", "111827"),
    ]

    /// I due colori della squadra (grigi se la squadra non è nell'elenco o manca). Gli «slug» sono minuscoli (`inter`); le sigle del
    /// server in maiuscolo (`INT`) non corrispondono e restano grigie.
    static func esadecimali(_ squadra: String?) -> (String, String) {
        guard let s = squadra?.lowercased(), let colori = tabella[s] else { return ("6b7280", "e5e7eb") }
        return colori
    }

    /// Sigla di tre lettere della squadra (`inter` → `INT`).
    static let sigle: [String: String] = [
        "atalanta": "ATA", "bologna": "BOL", "cagliari": "CAG", "como": "COM", "fiorentina": "FIO", "frosinone": "FRO", "genoa": "GEN",
        "inter": "INT", "juventus": "JUV", "lazio": "LAZ", "lecce": "LEC", "milan": "MIL", "monza": "MON", "napoli": "NAP", "parma": "PAR",
        "roma": "ROM", "sassuolo": "SAS", "torino": "TOR", "udinese": "UDI", "venezia": "VEN", "verona": "VER", "cremonese": "CRE",
        "pisa": "PIS", "sampdoria": "SAM", "palermo": "PAL", "spezia": "SPE",
    ]

    static func sigla(_ squadra: String?) -> String {
        guard let s = squadra, !s.isEmpty else { return "" }
        return sigle[s.lowercased()] ?? String(s.prefix(3)).uppercased()
    }
}
