import SwiftUI

/// Legge i percorsi nel formato SVG (`M10 100C12 84 28 77 50 77S88 84 90 100Z`) usati dagli avatar illustrati.
/// Comandi assoluti: M L H V C S Q Z. Numeri anche con decimali e segno; coordinate ripetute dopo un comando valgono come
/// una nuova istanza dello stesso comando (dopo M diventano L), come in SVG.
enum PercorsoSVG {
    private enum Pezzo {
        case comando(Character)
        case numero(Double)
    }

    private static func pezzi(_ testo: String) -> [Pezzo] {
        var risultato: [Pezzo] = []
        var corrente = ""
        func chiudi() {
            if !corrente.isEmpty, let n = Double(corrente) { risultato.append(.numero(n)) }
            corrente = ""
        }
        for c in testo {
            if c.isLetter {
                chiudi()
                risultato.append(.comando(c))
            } else if c == "-" {
                chiudi()
                corrente = "-"
            } else if c == "." {
                // un secondo punto comincia un nuovo numero («.5.5»)
                if corrente.contains(".") { chiudi() }
                corrente.append(c)
            } else if c.isNumber {
                corrente.append(c)
            } else {
                chiudi()   // spazi e virgole
            }
        }
        chiudi()
        return risultato
    }

    static func path(_ d: String) -> Path {
        var p = Path()
        var corrente = CGPoint.zero
        var inizio = CGPoint.zero
        var ultimoControllo: CGPoint?
        var comando: Character = "M"
        var numeri: [Double] = []

        func quanti(_ c: Character) -> Int {
            switch c {
            case "M", "L": return 2
            case "H", "V": return 1
            case "C": return 6
            case "S", "Q": return 4
            default: return 0
            }
        }

        func esegui(_ c: Character, _ n: [Double]) {
            switch c {
            case "M":
                corrente = CGPoint(x: n[0], y: n[1]); inizio = corrente
                p.move(to: corrente); ultimoControllo = nil
            case "L":
                corrente = CGPoint(x: n[0], y: n[1]); p.addLine(to: corrente); ultimoControllo = nil
            case "H":
                corrente = CGPoint(x: n[0], y: corrente.y); p.addLine(to: corrente); ultimoControllo = nil
            case "V":
                corrente = CGPoint(x: corrente.x, y: n[0]); p.addLine(to: corrente); ultimoControllo = nil
            case "C":
                let c2 = CGPoint(x: n[2], y: n[3])
                p.addCurve(to: CGPoint(x: n[4], y: n[5]), control1: CGPoint(x: n[0], y: n[1]), control2: c2)
                corrente = CGPoint(x: n[4], y: n[5]); ultimoControllo = c2
            case "S":
                // il primo controllo è il riflesso dell'ultimo secondo controllo (se il comando prima era C o S)
                let c1 = ultimoControllo.map { CGPoint(x: 2 * corrente.x - $0.x, y: 2 * corrente.y - $0.y) } ?? corrente
                let c2 = CGPoint(x: n[0], y: n[1])
                p.addCurve(to: CGPoint(x: n[2], y: n[3]), control1: c1, control2: c2)
                corrente = CGPoint(x: n[2], y: n[3]); ultimoControllo = c2
            case "Q":
                p.addQuadCurve(to: CGPoint(x: n[2], y: n[3]), control: CGPoint(x: n[0], y: n[1]))
                corrente = CGPoint(x: n[2], y: n[3]); ultimoControllo = nil
            default: break
            }
        }

        for pezzo in pezzi(d) {
            switch pezzo {
            case .numero(let n):
                numeri.append(n)
                // si esegue appena il gruppo è completo (serve per «S» che dipende dal comando precedente)
                let k = quanti(comando)
                if k > 0, numeri.count == k {
                    esegui(comando, numeri)
                    numeri.removeAll()
                    if comando == "M" { comando = "L" }
                }
            case .comando(let c):
                numeri.removeAll()
                if c == "Z" || c == "z" {
                    p.closeSubpath()
                    corrente = inizio
                    ultimoControllo = nil
                    comando = "Z"
                } else {
                    comando = Character(c.uppercased())
                }
            }
        }
        return p
    }
}
