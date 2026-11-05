import Foundation
import SwiftUI
import Testing
import UIKit
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

    /// Comportamento vero, non solo i sorgenti: `.titoloPagina` deve passare il titolo a `TitoloNellaPagina` (ambiente).
    /// Si disegna con `ImageRenderer` dentro una colonna larga 320 punti (un iPhone stretto): `ImageRenderer` non disegna
    /// le `List` (sono di UIKit), quindi qui una `VStack`, che come la lista non dà spazio a un elemento vuoto.
    @MainActor
    @Test("Con il testo grande il titolo intero c'è e va a capo; con il testo normale non occupa spazio")
    func titoloNellaPaginaSiVede() {
        func altezza(_ dimensione: DynamicTypeSize) -> CGFloat {
            let vista = VStack(spacing: 0) { TitoloNellaPagina() }
                .titoloPagina("Avvisi e promemoria")
                .frame(width: 320)
                .dynamicTypeSize(dimensione)
            let disegno = ImageRenderer(content: vista)
            disegno.scale = 1
            return disegno.uiImage?.size.height ?? 0
        }
        // una riga sola dello stesso carattere, per dire «va a capo» senza numeri scritti a mano
        let riga = ImageRenderer(content: Text("Avvisi").font(.largeTitle.bold()).dynamicTypeSize(.accessibility1))
        riga.scale = 1
        let unaRiga = riga.uiImage?.size.height ?? 0

        #expect(altezza(.large) == 0, "testo normale: niente titolo nella pagina (resta quello grande della barra)")
        #expect(altezza(.xLarge) == 0)
        #expect(unaRiga > 0)
        #expect(altezza(.accessibility1) > unaRiga * 1.5, "testo grande: titolo intero su più righe, non tagliato")
        #expect(altezza(.accessibility5) > unaRiga * 1.5)
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

    /// Issue #276: la pagina di una squadra aveva il titolo piccolo della barra (`.inline`) con il nome della squadra, e con il
    /// testo grande si leggeva «Gli Amici del B…». Un titolo che viene dai dati può essere lungo quanto vuole: anche con la
    /// barra piccola passa da `.titoloPagina`, così con il testo grande il nome intero va a capo nella pagina.
    @Test("Nessuna pagina di Lega ha nella barra un titolo preso dai dati senza «titoloPagina» (nome della squadra, #276)")
    func titoliDaiDatiInteri() throws {
        var trovati: [String] = []
        for file in try Self.fileLega() {
            let righe = try Self.righe(file)
            for (i, riga) in righe.enumerated() {
                guard let inizio = riga.range(of: ".navigationTitle(") else { continue }
                // un testo scritto qui ha una lunghezza nota: lo controlla il test del titolo grande
                if riga[inizio.upperBound...].hasPrefix("\"") { continue }
                if Self.eccezioni.contains(where: { riga.contains($0) }) { continue }
                trovati.append("\(file.lastPathComponent):\(i + 1)")
            }
        }
        #expect(trovati.isEmpty, "Titolo preso dai dati senza .titoloPagina(…), con il testo grande si taglia: \(trovati)")
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
