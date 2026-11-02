import CoreGraphics
import Foundation
import ImageIO
import Vision

/// Legge uno screenshot di Leghe SUL TELEFONO: testo con Vision (italiano, livello accurato) e colore dei pallini dei ruoli.
/// L'immagine non esce dal telefono; il risultato va a `RoseDaScreenshot` (logica pura, provata senza Vision).
enum LetturaScreenshot {
    enum Errore: LocalizedError {
        case immagineNonLeggibile
        var errorDescription: String? { "Non riesco ad aprire una delle foto. Scegli screenshot normali (PNG o JPEG)." }
    }

    /// Dove cercare i pallini dei ruoli: una striscia verticale a sinistra della figurina (in larghezze dell'immagine).
    static let strisciaDa = 0.02
    static let strisciaA = 0.085

    /// Da chiamare fuori dal thread principale (Vision è sincrono e ci mette qualche decimo di secondo per foto).
    static func leggi(_ dati: Data) throws -> PaginaScreenshot {
        guard let sorgente = CGImageSourceCreateWithData(dati as CFData, nil),
              let immagine = CGImageSourceCreateImageAtIndex(sorgente, 0, nil) else { throw Errore.immagineNonLeggibile }
        return try leggi(immagine)
    }

    static func leggi(_ immagine: CGImage) throws -> PaginaScreenshot {
        let larghezza = Double(immagine.width), altezza = Double(immagine.height)
        guard larghezza > 0, altezza > 0 else { throw Errore.immagineNonLeggibile }
        var parole = try riconosci(immagine)
        // Secondo passaggio sulla sola zona dei numeri: una cifra isolata («1») in uno screenshot intero a volte sfugge.
        // Si aggiungono solo i numeri che mancano.
        let x0 = Int(larghezza * 0.55), y0 = Int(altezza * 0.2)
        if let ritaglio = immagine.cropping(to: CGRect(x: x0, y: y0, width: immagine.width - x0, height: immagine.height - y0)),
           let numeri = try? riconosci(ritaglio) {
            let scala = Double(ritaglio.width) / larghezza
            for n in numeri where RoseDaScreenshot.eNumero(n.testo) {
                let p = ParolaLetta(testo: n.testo, x: Double(x0) / larghezza + n.x * scala, y: Double(y0) / larghezza + n.y * scala,
                                    larghezza: n.larghezza * scala, altezza: n.altezza * scala)
                let gia = parole.contains {
                    RoseDaScreenshot.eNumero($0.testo) && abs($0.medioY - p.medioY) < 0.6 * p.altezza && abs($0.medioX - p.medioX) < 0.03
                }
                if !gia { parole.append(p) }
            }
        }
        return PaginaScreenshot(parole: parole, proporzione: altezza / larghezza, strisciaRuoli: striscia(immagine))
    }

    /// Il testo di un'immagine, in parole con il loro riquadro (in larghezze di questa immagine).
    private static func riconosci(_ immagine: CGImage) throws -> [ParolaLetta] {
        let larghezza = Double(immagine.width), altezza = Double(immagine.height)
        guard larghezza > 0, altezza > 0 else { return [] }
        let richiesta = VNRecognizeTextRequest()
        richiesta.recognitionLevel = .accurate
        richiesta.recognitionLanguages = ["it-IT"]
        richiesta.usesLanguageCorrection = false        // i cognomi stranieri non vanno «corretti»
        richiesta.minimumTextHeight = Float(min(0.5, 12 / altezza))   // anche le scritte piccole (12 pixel)
        let gestore = VNImageRequestHandler(cgImage: immagine, orientation: .up, options: [:])
        try gestore.perform([richiesta])
        let proporzione = altezza / larghezza
        var parole: [ParolaLetta] = []
        for osservazione in richiesta.results ?? [] {
            guard let candidato = osservazione.topCandidates(1).first else { continue }
            parole += dividi(candidato, intera: osservazione.boundingBox, proporzione: proporzione)
        }
        return parole
    }

    /// Una riga di Vision divisa in parole, ognuna con il suo riquadro (così le colonne dei numeri restano separate).
    /// Se Vision non dà il riquadro di una parola, la riga resta intera.
    private static func dividi(_ testo: VNRecognizedText, intera: CGRect, proporzione: Double) -> [ParolaLetta] {
        let s = testo.string
        var parole: [ParolaLetta] = []
        var indice = s.startIndex
        while indice < s.endIndex {
            guard let inizio = s[indice...].firstIndex(where: { !$0.isWhitespace }) else { break }
            let fine = s[inizio...].firstIndex(where: { $0.isWhitespace }) ?? s.endIndex
            guard let riquadro = (try? testo.boundingBox(for: inizio..<fine))?.boundingBox else {
                return [parola(s, riquadro: intera, proporzione: proporzione)]
            }
            parole.append(parola(String(s[inizio..<fine]), riquadro: riquadro, proporzione: proporzione))
            indice = fine
        }
        return parole
    }

    /// Da coordinate di Vision (0-1, origine in basso a sinistra) a larghezze dell'immagine con origine in alto a sinistra.
    private static func parola(_ testo: String, riquadro r: CGRect, proporzione: Double) -> ParolaLetta {
        ParolaLetta(testo: testo, x: Double(r.minX), y: (1 - Double(r.maxY)) * proporzione,
                    larghezza: Double(r.width), altezza: Double(r.height) * proporzione)
    }

    /// Per ogni riga di pixel della striscia a sinistra: il ruolo del pallino, se ci sono almeno 3 punti di quel colore.
    static func striscia(_ immagine: CGImage) -> [String?] {
        let x0 = Int(Double(immagine.width) * strisciaDa)
        let larghezza = max(1, Int(Double(immagine.width) * strisciaA) - x0)
        let altezza = immagine.height
        let perRiga = larghezza * 4
        var pixel = [UInt8](repeating: 0, count: perRiga * altezza)
        let disegnato: Bool = pixel.withUnsafeMutableBytes { buffer in
            guard let contesto = CGContext(data: buffer.baseAddress, width: larghezza, height: altezza, bitsPerComponent: 8,
                                           bytesPerRow: perRiga, space: CGColorSpaceCreateDeviceRGB(),
                                           bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            // si disegna solo la striscia: l'immagine spostata a sinistra di x0
            contesto.draw(immagine, in: CGRect(x: -x0, y: 0, width: immagine.width, height: altezza))
            return true
        }
        guard disegnato else { return [] }
        var risultato: [String?] = []
        risultato.reserveCapacity(altezza)
        for riga in 0..<altezza {            // nel buffer la prima riga è quella in alto
            var conta: [String: Int] = [:]
            var x = 0
            while x < larghezza {
                let i = riga * perRiga + x * 4
                if let r = RoseDaScreenshot.ruolo(rosso: Double(pixel[i]) / 255, verde: Double(pixel[i + 1]) / 255,
                                                  blu: Double(pixel[i + 2]) / 255) {
                    conta[r, default: 0] += 1
                }
                x += 2
            }
            let migliore = conta.max(by: { $0.value < $1.value })
            risultato.append((migliore?.value ?? 0) >= 3 ? migliore?.key : nil)
        }
        return risultato
    }
}
