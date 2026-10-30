import UIKit

/// Immagini finte per la modalità demo (foto dei giocatori, stemmi e maglie delle squadre): disegnate al volo, senza rete.
/// Servono a far vedere nelle fotografie del simulatore come appaiono foto e stemmi veri.
enum DemoImmagini {
    /// I giocatori della demo che hanno la «foto» (gli altri mostrano la maglietta della squadra).
    static let idConFoto: Set<Int> = [101, 104, 112, 113, 120, 121, 123, 203]
    /// Le squadre della demo con stemma e con maglia.
    static let conStemma: Set<String> = ["Schiera FC", "Real Madrink", "Atletico Divano", "Dinamo Pizza", "Gli Amici del Bar Sport Centrale"]
    static let conMaglia: Set<String> = ["Schiera FC", "Real Madrink"]

    /// I byte dell'immagine per un indirizzo del server (`/api/foto/101`, `/api/squadre/immagine?...`), o nil se non ce n'è.
    static func dati(per percorso: String) -> Data? {
        if percorso.hasPrefix("/api/foto/"), let id = Int(percorso.dropFirst("/api/foto/".count)), idConFoto.contains(id) {
            return foto(id)
        }
        if percorso.hasPrefix("/api/squadre/immagine"), let componenti = URLComponents(string: "https://demo.invalid" + percorso) {
            let valori = Dictionary(uniqueKeysWithValues: (componenti.queryItems ?? []).compactMap { v in v.value.map { (v.name, $0) } })
            guard let nome = valori["squadra"], let tipo = valori["tipo"] else { return nil }
            if tipo == "stemma", conStemma.contains(nome) { return stemma(nome) }
            if tipo == "maglia", conMaglia.contains(nome) { return maglia(nome) }
        }
        return nil
    }

    private static func tinta(_ testo: String, luminosita: CGFloat = 0.55) -> UIColor {
        var h: UInt32 = 2166136261
        for b in testo.utf8 { h = (h ^ UInt32(b)) &* 16777619 }
        return UIColor(hue: CGFloat(h % 360) / 360, saturation: 0.62, brightness: luminosita + 0.2, alpha: 1)
    }

    private static func disegna(lato: CGFloat, trasparente: Bool, _ cosa: (CGContext, CGRect) -> Void) -> Data? {
        let formato = UIGraphicsImageRendererFormat.default()
        formato.scale = 1
        formato.opaque = !trasparente
        let rect = CGRect(x: 0, y: 0, width: lato, height: lato)
        return UIGraphicsImageRenderer(size: rect.size, format: formato).pngData { contesto in cosa(contesto.cgContext, rect) }
    }

    /// Mezzo busto stilizzato SENZA sfondo (PNG trasparente), come i ritagli che manda il server: volto e spalle, sempre la stessa inquadratura.
    static func foto(_ id: Int) -> Data? {
        disegna(lato: 240, trasparente: true) { c, r in
            // spalle e maglia
            tinta("maglia\(id)").setFill()
            c.fillEllipse(in: CGRect(x: 20, y: 150, width: 200, height: 160))
            // collo e testa
            let pelle = UIColor(hue: 0.07, saturation: 0.35, brightness: id % 3 == 0 ? 0.55 : 0.85, alpha: 1)
            pelle.setFill()
            c.fill(CGRect(x: 100, y: 120, width: 40, height: 50))
            c.fillEllipse(in: CGRect(x: 72, y: 40, width: 96, height: 110))
            // capelli
            UIColor(white: id % 2 == 0 ? 0.12 : 0.35, alpha: 1).setFill()
            c.fillEllipse(in: CGRect(x: 70, y: 32, width: 100, height: 56))
        }
    }

    /// Scudetto con le iniziali della squadra.
    static func stemma(_ nome: String) -> Data? {
        disegna(lato: 256, trasparente: true) { c, r in
            let scudo = UIBezierPath()
            scudo.move(to: CGPoint(x: 40, y: 20))
            scudo.addLine(to: CGPoint(x: 216, y: 20))
            scudo.addLine(to: CGPoint(x: 216, y: 120))
            scudo.addCurve(to: CGPoint(x: 128, y: 240), controlPoint1: CGPoint(x: 216, y: 180), controlPoint2: CGPoint(x: 170, y: 220))
            scudo.addCurve(to: CGPoint(x: 40, y: 120), controlPoint1: CGPoint(x: 86, y: 220), controlPoint2: CGPoint(x: 40, y: 180))
            scudo.close()
            tinta(nome).setFill()
            scudo.fill()
            UIColor.white.setStroke()
            scudo.lineWidth = 10
            scudo.stroke()
            let iniziali = nome.split(separator: " ").prefix(2).compactMap { $0.first }.map(String.init).joined().uppercased()
            let attributi: [NSAttributedString.Key: Any] = [.font: UIFont.systemFont(ofSize: 86, weight: .heavy), .foregroundColor: UIColor.white]
            let misura = (iniziali as NSString).size(withAttributes: attributi)
            (iniziali as NSString).draw(at: CGPoint(x: r.midX - misura.width / 2, y: 88), withAttributes: attributi)
        }
    }

    /// Maglietta a righe nei colori della squadra.
    static func maglia(_ nome: String) -> Data? {
        disegna(lato: 256, trasparente: true) { c, r in
            let p = UIBezierPath()
            func punto(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * 6.4, y: y * 6.4) }
            p.move(to: punto(13, 6))
            p.addLine(to: punto(5, 11)); p.addLine(to: punto(8, 18)); p.addLine(to: punto(12, 16)); p.addLine(to: punto(12, 34))
            p.addLine(to: punto(28, 34)); p.addLine(to: punto(28, 16)); p.addLine(to: punto(32, 18)); p.addLine(to: punto(35, 11))
            p.addLine(to: punto(27, 6))
            p.addCurve(to: punto(13, 6), controlPoint1: punto(25, 9), controlPoint2: punto(15, 9))
            p.close()
            c.saveGState()
            p.addClip()
            let a = tinta(nome), b = UIColor.white
            for i in 0..<8 {
                (i % 2 == 0 ? a : b).setFill()
                c.fill(CGRect(x: r.minX + CGFloat(i) * 32, y: 0, width: 32, height: 256))
            }
            c.restoreGState()
            UIColor.black.withAlphaComponent(0.35).setStroke()
            p.lineWidth = 4
            p.stroke()
        }
    }
}
