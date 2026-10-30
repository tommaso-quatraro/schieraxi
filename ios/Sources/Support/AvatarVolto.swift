import SwiftUI

// Il volto illustrato di un calciatore (specifica: docs/AVATAR.md del repository web). Gli indici delle parti vengono da
// `GeneratoreVolto` (uguali su web, iOS e Android); qui c'è il disegno su una griglia 100 x 100, dal fondo verso l'alto.

/// Una forma da disegnare sulla griglia 100 x 100.
struct ElementoVolto {
    var path: Path
    var riempimento: Color?
    var opacita = 1.0
    var bordo: Color?
    var larghezza = 0.0
    /// Ritagliato dentro l'ellisse del viso (barba) con questi semiassi.
    var ritaglio: (rx: Double, ry: Double)?
    /// Rotazione in gradi attorno a un punto (il cerotto).
    var rotazione: (gradi: Double, cx: Double, cy: Double)?
}

enum DisegnoVolto {
    private static func colore(_ c: RGB8) -> Color {
        Color(red: Double(c.r) / 255, green: Double(c.g) / 255, blue: Double(c.b) / 255)
    }

    private static func cerchio(_ cx: Double, _ cy: Double, _ r: Double) -> Path { ellisse(cx, cy, r, r) }
    private static func ellisse(_ cx: Double, _ cy: Double, _ rx: Double, _ ry: Double) -> Path {
        Path(ellipseIn: CGRect(x: cx - rx, y: cy - ry, width: 2 * rx, height: 2 * ry))
    }
    private static func rettangolo(_ x: Double, _ y: Double, _ w: Double, _ h: Double, _ r: Double) -> Path {
        Path(roundedRect: CGRect(x: x, y: y, width: w, height: h), cornerSize: CGSize(width: r, height: r))
    }
    private static func pieno(_ p: Path, _ c: Color, _ opacita: Double = 1) -> ElementoVolto {
        ElementoVolto(path: p, riempimento: c, opacita: opacita)
    }
    private static func linea(_ d: String, _ c: Color, _ larghezza: Double) -> ElementoVolto {
        ElementoVolto(path: PercorsoSVG.path(d), riempimento: nil, bordo: c, larghezza: larghezza)
    }

    private static let capCorto = "M30.5 43C29.5 26 40 19 50 19S70.5 26 69.5 43C67 36 62 33.5 50 33.5S33 36 30.5 43Z"
    private static let rasata = "M32.5 40C32.5 28 41 22 50 22S67.5 28 67.5 40C65 35 59 32 50 32S35 35 32.5 40Z"
    private static let barbaPiena = "M30 40H33Q35 50 42 51.5Q50 49.5 58 51.5Q65 50 67 40H70V70H30Z"
    private static let barbaCorta = "M30 44H33.5Q35 56 44 57.5H56Q65 56 66.5 44H70V70H30Z"

    /// Capelli: (dietro, davanti) per l'acconciatura `n`, con colore `c` e colore scuro dei dettagli `s`.
    private static func capelli(_ n: Int, _ c: Color, _ s: Color) -> ([ElementoVolto], [ElementoVolto]) {
        func cerchi(_ lista: [(Double, Double, Double)]) -> [ElementoVolto] { lista.map { pieno(cerchio($0.0, $0.1, $0.2), c) } }
        switch n {
        case 0: return ([], [pieno(PercorsoSVG.path(rasata), c, 0.8)])
        case 1: return ([], [pieno(PercorsoSVG.path(capCorto), c)])
        case 2:
            return (cerchi([(32, 38, 6.5), (68, 38, 6.5), (36, 28, 8), (50, 22, 9), (64, 28, 8)]),
                    [pieno(PercorsoSVG.path(capCorto), c)] + cerchi([(37, 33, 3.6), (44, 32, 3.6), (51, 32, 3.6), (58, 32, 3.6), (64, 33, 3.6)]))
        case 3: return ([pieno(cerchio(50, 33, 26), c)], [pieno(PercorsoSVG.path(capCorto), c)])
        case 4:
            return ([pieno(PercorsoSVG.path("M29 38C27 22 38 17 50 17S73 22 71 38L74 70Q74 80 66 82H34Q26 80 26 70Z"), c)],
                    [pieno(PercorsoSVG.path("M31 44C30 27 40 19 50 19S70 27 69 44C67 37 62 31 54 30C46 35 38 36 31 44Z"), c)])
        case 5: return ([pieno(cerchio(50, 14, 7.5), c)], [pieno(PercorsoSVG.path(capCorto), c)])
        case 6:
            return ([], [pieno(PercorsoSVG.path("M30.5 43C29 26 40 19 50 19S70 26 69.5 40C66 33 58 30 44 33C38 35 34 38 30.5 43Z"), c),
                         linea("M44 32.4Q41 27 40 22", s, 1.2)])
        case 7:
            return ([], [pieno(PercorsoSVG.path(rasata), c, 0.4),
                         pieno(PercorsoSVG.path("M43.5 31C43 22 46 16 50 16S57 22 56.5 31C54 29.5 46 29.5 43.5 31Z"), c)])
        case 8:
            return ([pieno(ellisse(50, 36, 22, 21), c)] + cerchi([(28, 52, 7), (72, 52, 7), (26, 62, 5.5), (74, 62, 5.5)]),
                    [pieno(PercorsoSVG.path("M30.5 43C29 26 40 19 50 19S71 26 69.5 43C68 38 66 34 61 33C58 36 54 31 50 33C46 36 42 31 39 33C34 34 32 38 30.5 43Z"), c)])
        case 10:
            return ([], [pieno(PercorsoSVG.path("M30.5 41C29.5 25 40 18.5 50 18.5S70.5 25 69.5 41C67 33 60 28 50 28S33 33 30.5 41Z"), c),
                         linea("M40 29Q42 22 46 19.5M50 28V19.5M60 29Q58 22 54 19.5", s, 1)])
        case 11:
            return ([], [pieno(PercorsoSVG.path("M30.5 43C29.5 26 40 19 50 19S70.5 26 69.5 43L67 33Q63 34.5 59 33Q54 35 50 33Q45 35 41 33Q37 34.5 33 33Z"), c)])
        default: return ([], [])   // 9 calvo
        }
    }

    /// Tutti gli elementi del volto, dal fondo. Lo sfondo (cerchio con sfumatura) è a parte: vedi `sfondo(c1:c2:)`.
    static func elementi(id: Int, portiere: Bool, c1: RGB8, c2: RGB8) -> [ElementoVolto] {
        let v = GeneratoreVolto.estrai(id: id)
        let pelleRGB = RGB8(GeneratoreVolto.pelli[v.pelle])
        let pelle = colore(pelleRGB), ombra = colore(pelleRGB.scuri(0.14))
        let capRGB = RGB8(GeneratoreVolto.capelli[v.colore])
        let cap = colore(capRGB), capScuro = colore(capRGB.scuri(0.3))
        let (rx, ry) = GeneratoreVolto.forme[v.forma]
        let (ox, oy) = GeneratoreVolto.orecchie[v.orecchie]
        let mag = portiere ? RGB8("#8d99a8") : c1
        let col = portiere ? RGB8("#1f2937") : c2
        let boccaRGB = v.pelle >= 4 ? pelleRGB.misce(RGB8("#f0b8a8"), 0.55) : pelleRGB.scuri(0.45)
        let (dietro, davanti) = capelli(v.acconciatura, cap, capScuro)

        var e: [ElementoVolto] = dietro
        e.append(pieno(rettangolo(42, 58, 16, 26, 6), ombra))
        e.append(pieno(PercorsoSVG.path("M10 100C12 84 28 77 50 77S88 84 90 100Z"), colore(mag)))
        e.append(pieno(PercorsoSVG.path("M41 77Q50 87 59 77Z"), ombra))
        e.append(pieno(PercorsoSVG.path("M37 77.5Q50 92 63 77.5L59 76.5Q50 85 41 76.5Z"), colore(col)))
        if portiere {
            for x in [18.0, 66.0] {
                e.append(ElementoVolto(path: rettangolo(x, 81, 16, 18, 6), riempimento: colore(RGB8("#d4f34a")), bordo: colore(RGB8("#1f2937")), larghezza: 1.2))
                e.append(linea("M\(x + 5.3) 87V93M\(x + 10.7) 87V93", colore(RGB8("#1f2937")), 1))
            }
        }
        e.append(pieno(ellisse(50 - rx, 44, ox, oy), pelle))
        e.append(pieno(ellisse(50 + rx, 44, ox, oy), pelle))
        e.append(pieno(ellisse(50, 42, rx, ry), pelle))
        // barba: ritagliata nel viso
        let dentro: (rx: Double, ry: Double) = (rx, ry)
        if v.barba == 1 {
            var b = pieno(PercorsoSVG.path("M30 44Q50 56 70 44V70H30Z"), cap, 0.25)
            b.ritaglio = dentro
            e.append(b)
        } else if v.barba == 2 || v.barba == 3 {
            var b = pieno(PercorsoSVG.path(v.barba == 3 ? barbaPiena : barbaCorta), cap)
            b.ritaglio = dentro
            var libera = pieno(v.barba == 3 ? ellisse(50, 57.5, 8, 4) : ellisse(50, 57.5, 7.5, 3.6), pelle)
            libera.ritaglio = dentro
            e.append(b)
            e.append(libera)
        }
        // naso, occhi, sopracciglia, bocca
        e.append(linea("M49.5 46.5Q47.5 51.5 51 52", colore(pelleRGB.scuri(0.22)), 1.6))
        let occhioScuro = colore(RGB8("#1d1d22"))
        for x in [42.5, 57.5] {
            if v.pelle >= 5, v.occhi < 2 { e.append(pieno(ellisse(x, 43, 3.1, 2.1), colore(RGB8("#f3ede4")))) }
            switch v.occhi {
            case 0: e.append(pieno(cerchio(x, 43, 1.9), occhioScuro))
            case 1: e.append(pieno(ellisse(x, 43, 2.6, 1.5), occhioScuro))
            default:
                e.append(pieno(ellisse(x, 43, 3.3, 2.4), .white))
                e.append(pieno(cerchio(x, 43, 1.6), colore(RGB8("#2a1d14"))))
            }
        }
        let sopracciglia: [(String, Double)] = [("M37.5 37.5H47M53 37.5H62.5", 2.2), ("M37.5 37.5H47M53 37.5H62.5", 3.4), ("M37.5 36.5L47 38.5M53 38.5L62.5 36.5", 2.4)]
        e.append(linea(sopracciglia[v.sopracciglia].0, colore(capRGB.scuri(0.2)), sopracciglia[v.sopracciglia].1))
        let bocca = colore(boccaRGB)
        switch v.bocca {
        case 0: e.append(linea("M44.5 57.5H55.5", bocca, 2))
        case 1: e.append(linea("M44 56Q50 61 56 56", bocca, 2))
        case 2: e.append(linea("M45.5 58H54.5", bocca, 2.4))
        default:
            e.append(ElementoVolto(path: PercorsoSVG.path("M44 56Q50 63.5 56 56Z"), riempimento: .white, bordo: bocca, larghezza: 1.6))
        }
        if v.barba == 4 {
            e.append(pieno(PercorsoSVG.path("M42 54.5Q46 51.5 50 54Q54 51.5 58 54.5Q54 57.2 50 55.6Q46 57.2 42 54.5Z"), cap))
        }
        if v.accessorio == 3 {
            let bordo = colore(RGB8("#c9b48e"))
            var cerotto = ElementoVolto(path: rettangolo(59, 50, 9, 4, 1.2), riempimento: colore(RGB8("#f1e3c8")), bordo: bordo, larghezza: 0.6)
            cerotto.rotazione = (-20, 63.5, 52)
            var p1 = pieno(cerchio(62, 52, 0.5), bordo), p2 = pieno(cerchio(65, 52, 0.5), bordo)
            p1.rotazione = (-20, 63.5, 52)
            p2.rotazione = (-20, 63.5, 52)
            e.append(contentsOf: [cerotto, p1, p2])
        }
        e.append(contentsOf: davanti)
        if v.accessorio == 1 {
            e.append(ElementoVolto(path: PercorsoSVG.path("M31 33Q50 27 69 33V37Q50 31 31 37Z"), riempimento: colore(c2), bordo: colore(c2.scuri(0.35)), larghezza: 0.8))
        }
        if v.accessorio == 2 {
            e.append(ElementoVolto(path: cerchio(50 - rx, 50.5, 1.9), riempimento: colore(RGB8("#e9c24a")), bordo: colore(RGB8("#a8841c")), larghezza: 0.6))
        }
        return e
    }

    /// I due colori della sfumatura dello sfondo.
    static func sfondo(c1: RGB8, c2: RGB8) -> (Color, Color) {
        let (a, b) = GeneratoreVolto.sfondo(c1: c1, c2: c2)
        return (colore(a), colore(b))
    }

    /// I colori della squadra (slug come `inter`); grigi se manca o non si conosce.
    static func coloriSquadra(_ squadra: String?) -> (RGB8, RGB8) {
        let (a, b) = ColoriSquadra.esadecimali(squadra)
        return (RGB8(a), RGB8(b))
    }
}

/// Il volto illustrato nel suo cerchio (sfondo con i colori della squadra, maglia, volto). Si disegna con un `Canvas`: nessuna
/// foto, nessuna richiesta di rete. Quadrato, di qualunque dimensione. Per VoiceOver è nascosto: il nome sta già nella riga.
struct AvatarVolto: View {
    let id: Int
    var squadra: String?
    var portiere = false

    var body: some View {
        let (c1, c2) = DisegnoVolto.coloriSquadra(squadra)
        let elementi = Self.elementiInMemoria(id: id, portiere: portiere, squadra: squadra, c1: c1, c2: c2)
        let (g1, g2) = DisegnoVolto.sfondo(c1: c1, c2: c2)
        Canvas { ctx, dimensione in
            let k = Double(min(dimensione.width, dimensione.height)) / 100
            ctx.scaleBy(x: k, y: k)
            let cerchio = Path(ellipseIn: CGRect(x: 0, y: 0, width: 100, height: 100))
            ctx.fill(cerchio, with: .linearGradient(Gradient(colors: [g1, g2]), startPoint: .zero, endPoint: CGPoint(x: 100, y: 100)))
            for el in elementi {
                ctx.drawLayer { strato in
                    if let r = el.ritaglio { strato.clip(to: Path(ellipseIn: CGRect(x: 50 - r.rx, y: 42 - r.ry, width: 2 * r.rx, height: 2 * r.ry))) }
                    if let rot = el.rotazione {
                        strato.translateBy(x: rot.cx, y: rot.cy)
                        strato.rotate(by: .degrees(rot.gradi))
                        strato.translateBy(x: -rot.cx, y: -rot.cy)
                    }
                    if let f = el.riempimento { strato.fill(el.path, with: .color(f.opacity(el.opacita))) }
                    if let b = el.bordo {
                        strato.stroke(el.path, with: .color(b), style: StrokeStyle(lineWidth: el.larghezza, lineCap: .round, lineJoin: .round))
                    }
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .clipShape(Circle())
        .accessibilityHidden(true)
    }

    // Gli elementi di un volto non cambiano mai: si costruiscono una volta sola per id, ruolo e squadra (lista con tante righe).
    private static let memoria = NSCache<NSString, ContenitoreElementi>()
    private final class ContenitoreElementi {
        let elementi: [ElementoVolto]
        init(_ e: [ElementoVolto]) { elementi = e }
    }

    private static func elementiInMemoria(id: Int, portiere: Bool, squadra: String?, c1: RGB8, c2: RGB8) -> [ElementoVolto] {
        let chiave = "\(id)|\(portiere ? "P" : "-")|\((squadra ?? "").lowercased())" as NSString
        if let trovato = memoria.object(forKey: chiave) { return trovato.elementi }
        let nuovi = DisegnoVolto.elementi(id: id, portiere: portiere, c1: c1, c2: c2)
        memoria.setObject(ContenitoreElementi(nuovi), forKey: chiave)
        return nuovi
    }
}
