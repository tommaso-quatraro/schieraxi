import XCTest
@testable import Schieraxi

/// Dopo la rinomina in SchieraXI i vecchi nomi non devono ricomparire nel codice (piano di rinomina, punto 9).
/// I vecchi nomi sono scritti a pezzi, così questo file non li contiene.
final class NomeVecchioTests: XCTestCase {
    private let vecchio1 = "fanta" + "claude"
    private let vecchio2 = "und" + "ici"
    private let vecchio3 = "titolar" + "xi"

    func testICopieDeiNomiVecchiNonSiLeggonoPiu() {
        let corpo = #"{"formato": "NOME", "versione": 1, "file": {"dati/osservati.json": [1]}}"#
        for formato in [vecchio1 + "-backup", vecchio2 + "-backup", vecchio3 + "-backup", "altro-backup"] {
            let dati = Data(corpo.replacingOccurrences(of: "NOME", with: formato).utf8)
            guard case .failure(let errore) = FileBackup.controlla(dati) else { return XCTFail("\(formato): deve rifiutare") }
            XCTAssertEqual(errore, .nonEUnBackup)
        }
        let giusto = Data(corpo.replacingOccurrences(of: "NOME", with: "schieraxi-backup").utf8)
        if case .failure(let e) = FileBackup.controlla(giusto) { XCTFail("schieraxi-backup: \(e)") }
    }

    func testNelCodiceNonCiSonoIVecchiNomi() throws {
        // I sorgenti stanno accanto ai test sul Mac di GitHub; se non si trovano (altro ambiente) il test non dice niente.
        let radice = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        var trovati: [String] = []
        for nome in ["Sources", "WidgetSources", "AnteprimaWidget"] {
            guard let elenco = FileManager.default.enumerator(at: radice.appendingPathComponent(nome, isDirectory: true), includingPropertiesForKeys: nil) else { continue }
            for caso in elenco {
                guard let url = caso as? URL, url.pathExtension == "swift",
                      let testo = try? String(contentsOf: url, encoding: .utf8) else { continue }
                if testo.lowercased().contains(vecchio1) || testo.lowercased().contains(vecchio3) { trovati.append(url.lastPathComponent) }
                // «Schiera SchieraXI» è l'etichetta per VoiceOver del titolo: l'unico posto in cui il nome vecchio resta, a voce.
                if testo.replacingOccurrences(of: "Schiera Und" + "ici", with: "").contains("Und" + "ici") { trovati.append(url.lastPathComponent) }
            }
        }
        XCTAssertTrue(trovati.isEmpty, "Nomi vecchi trovati in: \(trovati)")
    }
}
