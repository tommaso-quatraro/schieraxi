import UIKit
import XCTest
@testable import Schieraxi

/// Vision vero (nel simulatore) su screenshot INVENTATI disegnati qui, nello stile di «Dettaglio squadra» di Leghe:
/// testo, coordinate, colori dei pallini, due screenshot sovrapposti. Squadra, proprietario e calciatori inventati.
/// Stampa nel log quanti giocatori legge giusti.
final class RoseDaScreenshotVisionTests: XCTestCase {
    typealias Finto = RoseDaScreenshotTests.Finto

    static let rosa: [Finto] = [
        Finto("P", "Porticelli", "Genoa", 9, 7, 1),
        Finto("D", "N'Gorra", "Roma", 12, 20, 12),
        Finto("D", "Bianchi Al.", "Venezia", 5, 4, 1),
        Finto("D", "Edervan D.S.", "Atalanta", 14, 22, 18),
        Finto("C", "Soulèt", "Roma", 16, 30, 25),
        Finto("C", "Kavè M.", "Udinese", 7, 6, 2),
        Finto("C", "Nicolosi Cavaglia", "Parma", 6, 5, 1),
        Finto("C", "Zambi Angossa", "Napoli", 9, 13, 2),
        Finto("A", "Espinaldo F.P.", "Inter", 20, 45, 86),
        Finto("A", "Morenez Jo.", "Inter", 10, 12, 30),
        Finto("A", "Kolo Muaro", "Juventus", 19, 40, 152),
        Finto("A", "Milanovic-Savor V.", "Torino", 11, 12, 9),
    ]

    static func colore(_ ruolo: String) -> UIColor {
        switch ruolo {
        case "P": return UIColor(red: 0.95, green: 0.66, blue: 0.20, alpha: 1)
        case "D": return UIColor(red: 0.49, green: 0.70, blue: 0.26, alpha: 1)
        case "C": return UIColor(red: 0.16, green: 0.38, blue: 1.00, alpha: 1)
        default: return UIColor(red: 0.90, green: 0.22, blue: 0.21, alpha: 1)
        }
    }

    static func scrivi(_ testo: String, _ x: CGFloat, _ y: CGFloat, _ dimensione: CGFloat, _ colore: UIColor,
                       peso: UIFont.Weight = .regular, centrato: Bool = false) {
        let attributi: [NSAttributedString.Key: Any] = [.font: UIFont.systemFont(ofSize: dimensione, weight: peso), .foregroundColor: colore]
        let s = NSAttributedString(string: testo, attributes: attributi)
        let punto = centrato ? CGPoint(x: x - s.size().width / 2, y: y) : CGPoint(x: x, y: y)
        s.draw(at: punto)
    }

    /// Uno screenshot 1184 x 2576 px. `scorrimento`: quanti pixel la lista è salita sotto l'intestazione.
    static func screenshot(scorrimento: CGFloat) -> UIImage {
        let formato = UIGraphicsImageRendererFormat()
        formato.scale = 1
        formato.opaque = true
        return UIGraphicsImageRenderer(size: CGSize(width: 1184, height: 2576), format: formato).image { ctx in
            UIColor(red: 0.93, green: 0.94, blue: 0.96, alpha: 1).setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 1184, height: 2576))
            let scuro = UIColor(red: 0.10, green: 0.13, blue: 0.19, alpha: 1), grigio = UIColor(red: 0.35, green: 0.38, blue: 0.44, alpha: 1)
            for (k, g) in rosa.enumerated() {
                let cima = 808 + CGFloat(k) * 230 - scorrimento
                UIColor.white.setFill()
                UIBezierPath(roundedRect: CGRect(x: 24, y: cima, width: 1136, height: 205), cornerRadius: 26).fill()
                UIColor(red: 0.87, green: 0.89, blue: 0.92, alpha: 1).setFill()
                UIBezierPath(ovalIn: CGRect(x: 71, y: cima + 14, width: 176, height: 176)).fill()
                colore(g.ruolo).setFill()
                UIBezierPath(ovalIn: CGRect(x: 48, y: cima + 15, width: 46, height: 46)).fill()
                scrivi(g.ruolo, 71, cima + 20, 28, .white, peso: .bold, centrato: true)
                scrivi(g.nome, 272, cima + 46, 44, scuro, peso: .medium)
                scrivi(g.club, 272, cima + 112, 30, grigio)
                scrivi(String(g.q), 745, cima + 84, 34, grigio, centrato: true)
                scrivi(String(g.fvm), 907, cima + 84, 34, grigio, centrato: true)
                scrivi(String(g.costo), 1068, cima + 84, 34, UIColor(red: 0.18, green: 0.36, blue: 0.83, alpha: 1), centrato: true)
            }
            // intestazione fissa, sopra la lista che scorre
            UIColor(red: 0.24, green: 0.42, blue: 0.88, alpha: 1).setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: 1184, height: 590))
            UIColor.white.setFill()
            ctx.fill(CGRect(x: 0, y: 590, width: 1184, height: 118))
            UIColor(red: 0.93, green: 0.94, blue: 0.96, alpha: 1).setFill()
            ctx.fill(CGRect(x: 0, y: 708, width: 1184, height: 92))
            scrivi("10:54", 146, 70, 44, .white, peso: .semibold)
            scrivi("Lega Inventata", 159, 188, 44, .white, peso: .semibold)
            scrivi("DETTAGLIO SQUADRA", 158, 242, 32, .white)
            UIBezierPath(ovalIn: CGRect(x: 48, y: 355, width: 170, height: 170)).fill()
            scrivi("Atletico Pigiama", 396, 388, 46, .white, peso: .medium)
            scrivi("Gianni", 396, 458, 34, .white)
            scrivi("7", 1120, 388, 46, .white, peso: .medium)
            scrivi("CREDITI", 1002, 458, 34, .white)
            scrivi("Rosa", 250, 626, 44, scuro, peso: .medium)
            scrivi("Calendario e risultati", 674, 626, 44, grigio)
            scrivi("Calciatore", 48, 740, 30, scuro)
            scrivi("Q. att.", 745, 740, 30, scuro, centrato: true)
            scrivi("FVMp", 907, 740, 30, scuro, centrato: true)
            scrivi("V. Acq.", 1068, 740, 30, scuro, centrato: true)
        }
    }

    func testVisionLeggeDueScreenshotInventati() throws {
        var pagine: [LetturaPagina] = []
        for scorrimento: CGFloat in [0, 1100] {
            guard let immagine = Self.screenshot(scorrimento: scorrimento).cgImage else { return XCTFail("immagine non creata") }
            let pagina: PaginaScreenshot
            do {
                pagina = try LetturaScreenshot.leggi(immagine)
            } catch {
                return XCTFail("DIAGNOSI-TEMPORANEA Vision non disponibile: \(error)")
            }
            if pagina.parole.isEmpty { return XCTFail("DIAGNOSI-TEMPORANEA Vision non ha letto niente") }
            pagine += [RoseDaScreenshot.leggi(pagina)].compactMap { $0 }
        }
        XCTAssertEqual(pagine.count, 2, "entrambe riconosciute come rose di Leghe")
        let squadre = RoseDaScreenshot.unisci(pagine)
        let righe = squadre.first?.righe ?? []
        var giusti = 0
        var sbagliati: [String] = []
        for g in Self.rosa {
            if let r = righe.first(where: { $0.nome == g.nome }), r.ruolo == g.ruolo, r.costo == g.costo, r.club == g.club { giusti += 1 }
            else { sbagliati.append("\(g.nome) -> \(righe.first(where: { RoseDaScreenshot.simili($0.nome, g.nome) }).map { "\($0)" } ?? "assente")"); print("VISION, non giusto: \(g.nome) -> \(righe.first(where: { RoseDaScreenshot.simili($0.nome, g.nome) }).map { "\($0)" } ?? "assente")") }
        }
        print("VISION su screenshot inventati: \(giusti) giocatori giusti su \(Self.rosa.count) (righe lette \(righe.count), squadre \(squadre.map(\.nome)))")
        XCTFail("DIAGNOSI-TEMPORANEA VISION \(giusti)/\(Self.rosa.count) righe \(righe.count) squadre \(squadre.map(\.nome)) crediti \(String(describing: squadre.first?.crediti)) sbagliati \(sbagliati) parole \(pagine.map(\.righe.count))")
        XCTAssertEqual(squadre.map(\.nome), ["Atletico Pigiama"])
        XCTAssertEqual(squadre.first?.crediti, 7)
        XCTAssertEqual(righe.count, Self.rosa.count, "nessun doppione e nessuno perso")
        XCTAssertGreaterThanOrEqual(giusti, Self.rosa.count - 1, "nome, ruolo, squadra e prezzo")
    }
}
