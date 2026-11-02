import XCTest
@testable import Schieraxi

/// Il repository è pubblico: dati demo, anteprime, fixture, test e documenti usano solo nomi di giocatori INVENTATI.
/// Questo test cerca i cognomi più evidenti di calciatori veri (scritti a pezzi, così il file non li contiene per intero)
/// e fallisce se ne trova uno. Se serve un nome nuovo, inventalo: non copiarlo dalla realtà.
final class NomiRealiTests: XCTestCase {
    private let pezzi: [[String]] = [
        ["Som", "mer"], ["Maig", "nan"], ["Carne", "secchi"], ["Bas", "toni"], ["Di", "marco"], ["Bre", "mer"],
        ["Gos", "ens"], ["Camb", "iaso"], ["Ndi", "cka"], ["Calha", "noglu"], ["Koop", "meiners"], ["Puli", "sic"],
        ["Lobo", "tka"], ["Reijn", "ders"], ["Lau", "taro"], ["Mart", "inez"], ["Thu", "ram"], ["Look", "man"],
        ["Vlaho", "vic"], ["Pina", "monti"], ["Poli", "tano"], ["Rete", "gui"], ["Krsto", "vic"], ["Zacca", "gni"], ["Brescia", "nini"],
        ["Comu", "zzo"], ["Aude", "ro"], ["Saele", "maekers"], ["Guen", "douzi"], ["Cata", "ldi"], ["Freu", "ler"], ["McTo", "minay"],
        ["De Bru", "yne"], ["Luka", "ku"], ["Dyb", "ala"], ["Dov", "byk"], ["Scam", "acca"], ["Gudmun", "dsson"], ["Kvara", "tskhelia"],
        ["Ziel", "inski"], ["Zan", "iolo"], ["Terra", "cciano"], ["Mkhit", "aryan"], ["Orso", "lini"], ["Dum", "fries"], ["Cris", "tante"],
        ["Angu", "issa"], ["Castel", "lanos"], ["Djim", "siti"], ["Rrah", "mani"], ["Pasa", "lic"], ["Pobe", "ga"], ["Spina", "zzola"],
        ["Mazz", "occhi"], ["Beu", "kema"],
    ]

    private var cognomi: [String] { pezzi.map { $0.joined() } }

    private func piega(_ testo: String) -> String {
        testo.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "it_IT"))
    }

    func testNeiFileDelRepositoryNonCiSonoNomiDiCalciatoriVeri() throws {
        // I file stanno accanto ai test sul Mac di GitHub; se non si trovano (altro ambiente) il test non dice niente.
        let radice = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let estensioni: Set<String> = ["swift", "json", "md", "yml", "csv", "txt", "plist"]
        let cercati = cognomi.map { piega($0) }
        var trovati: [String] = []
        for nome in ["Sources", "WidgetSources", "AnteprimaWidget", "Tests", "docs", "scripts", ".github"] {
            guard let elenco = FileManager.default.enumerator(at: radice.appendingPathComponent(nome, isDirectory: true),
                                                              includingPropertiesForKeys: nil) else { continue }
            for caso in elenco {
                guard let url = caso as? URL, estensioni.contains(url.pathExtension),
                      let testo = try? String(contentsOf: url, encoding: .utf8) else { continue }
                let pieno = piega(testo)
                for c in cercati where pieno.contains(c) { trovati.append("\(url.lastPathComponent): \(c.prefix(2))...") }
            }
        }
        for nome in ["README.md", "CLAUDE.md", "MAPPA.md"] {
            guard let testo = try? String(contentsOf: radice.appendingPathComponent(nome), encoding: .utf8) else { continue }
            let pieno = piega(testo)
            for c in cercati where pieno.contains(c) { trovati.append("\(nome): \(c.prefix(2))...") }
        }
        XCTAssertTrue(trovati.isEmpty, "Nomi di calciatori veri trovati (inventane di nuovi): \(trovati)")
    }
}
