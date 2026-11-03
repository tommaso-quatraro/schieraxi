import Foundation
import SwiftUI
import Testing
@testable import Schieraxi

/// Titoli delle pagine con il testo grande (issue #196). Il titolo grande della barra di iOS sta su una riga sola e con il
/// testo grande si tagliava («Avvisi e prome…», «Nuova stagi…», «Aggiorna le…»). Da `TitoloPagina.soglia` in su la barra
/// mostra il titolo piccolo e il titolo intero va in cima alla pagina (`TitoloNellaPagina`), dove va a capo.
/// A margine: in «Nuova stagione» l'icona di «Archivia e riparti» era verde e il testo rosso.
@Suite("Titoli delle pagine con il testo grande")
struct TitoloPaginaTests {

    @Test("Il titolo va nella pagina da XXL in su: fino a XL resta il titolo grande della barra")
    func soglia() {
        let nellaPagina = DynamicTypeSize.allCases.filter { TitoloPagina.nellaPagina($0) }
        #expect(nellaPagina == [.xxLarge, .xxxLarge, .accessibility1, .accessibility2, .accessibility3, .accessibility4, .accessibility5])
    }

    @Test("Nessuna pagina di Lega e Impostazioni ha il titolo grande della barra senza «titoloPagina» (si taglierebbe)")
    func nienteTitoloGrandeSenzaTitoloPagina() throws {
        var trovati: [String] = []
        for file in try Self.fileLega() {
            let righe = try Self.righe(file)
            for (i, riga) in righe.enumerated() where riga.contains(".navigationTitle(") {
                // titolo piccolo voluto (fogli, pagine di dettaglio): non si taglia
                let questaESeguente = righe[i...min(i + 1, righe.count - 1)].joined(separator: " ")
                if questaESeguente.contains("TitleDisplayMode(.inline)") { continue }
                if Self.eccezioni.contains(where: { riga.contains($0) }) { continue }
                trovati.append("\(file.lastPathComponent):\(i + 1)")
            }
        }
        #expect(trovati.isEmpty, "Titolo grande senza .titoloPagina(…): \(trovati)")
    }

    @Test("Ogni pagina con «titoloPagina» mostra anche il titolo nella pagina (TitoloNellaPagina)")
    func titoloAncheNellaPagina() throws {
        var mancanti: [String] = []
        var pagine = 0
        for file in try Self.fileLega() {
            let testo = try String(contentsOf: file, encoding: .utf8)
            let conTitolo = testo.components(separatedBy: ".titoloPagina(").count - 1
            guard conTitolo > 0 else { continue }
            pagine += conTitolo
            // PaginaMercato (LegaView) mostra le pagine di MercatoView: il titolo nella pagina sta lì.
            let contenuto = file.lastPathComponent == "LegaView.swift"
                ? Self.radice.appendingPathComponent("Sources/Presentation/Mercato/MercatoView.swift")
                : file
            let nellaPagina = try String(contentsOf: contenuto, encoding: .utf8).components(separatedBy: "TitoloNellaPagina()").count - 1
            if nellaPagina < conTitolo { mancanti.append("\(file.lastPathComponent): \(conTitolo) titoli, \(nellaPagina) nella pagina") }
        }
        #expect(pagine >= 12, "Le pagine di Lega e Impostazioni con il titolo grande sono almeno 12, trovate \(pagine)")
        #expect(mancanti.isEmpty, "Titolo che con il testo grande sparisce dalla pagina: \(mancanti)")
    }

    @Test("Pulsanti distruttivi nelle liste: icona e testo dello stesso rosso", arguments: [
        ("LegaPagine.swift", "Label(\"Archivia e riparti\""),
        ("RegoleEditor.swift", "Label(\"Togli la fascia\""),
    ])
    func distruttiviStessoColore(file: String, etichetta: String) throws {
        let righe = try Self.righe(Self.cartellaLega.appendingPathComponent(file))
        let riga = try #require(righe.first { $0.contains(etichetta) })
        #expect(riga.contains(".labelStyle(.distruttiva)"), "\(file): \(riga.trimmingCharacters(in: .whitespaces))")
    }

    // MARK: lettura dei sorgenti dal repository (il test gira nel checkout)

    /// Titoli grandi che restano nella barra: la radice delle schede Squadra e Altro (una parola, ed è l'elenco a sinistra
    /// sull'iPad) e il Diario (una parola corta: non si taglia).
    private static let eccezioni = [".navigationTitle(ambito.titolo)", ".navigationTitle(\"Diario\")"]

    /// La cartella `ios/` del repository.
    private static let radice = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()

    private static let cartellaLega = radice.appendingPathComponent("Sources/Presentation/Lega", isDirectory: true)

    private static func fileLega() throws -> [URL] {
        try FileManager.default.contentsOfDirectory(at: cartellaLega, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "swift" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    private static func righe(_ file: URL) throws -> [String] {
        try String(contentsOf: file, encoding: .utf8).components(separatedBy: .newlines)
    }
}
