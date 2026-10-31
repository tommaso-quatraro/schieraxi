import SwiftUI

// Il volto illustrato di un calciatore, versione 3 (specifica: docs/AVATAR.md del repository web). Gli indici delle parti vengono da
// `GeneratoreVolto` (uguali su web, iOS e Android); qui c'è il disegno su una griglia 100 x 100, dal fondo verso l'alto.

/// Come si riempie una forma: un colore pieno o una sfumatura lineare (punti nella griglia 100 x 100).
enum RiempimentoVolto {
    case colore(Color)
    case sfumatura(Gradient, CGPoint, CGPoint)
}

/// Una forma da disegnare sulla griglia 100 x 100.
struct ElementoVolto {
    var path: Path
    var riempimento: RiempimentoVolto?
    var opacita = 1.0
    var bordo: Color?
    var larghezza = 0.0
    /// Ritagliato dentro questa forma (viso, maglia, cerchio di sfondo).
    var ritaglio: Path?
    /// Testo (il numero sulla maglia) al posto della forma: centro (50, 94), grassetto, nel colore del riempimento.
    var testo: String?
}

enum DisegnoVolto {
    private static func colore(_ c: RGB8) -> Color {
        Color(red: Double(c.r) / 255, green: Double(c.g) / 255, blue: Double(c.b) / 255)
    }

    private static func cerchio(_ cx: Double, _ cy: Double, _ r: Double) -> Path { ellisse(cx, cy, r, r) }
    private static func ellisse(_ cx: Double, _ cy: Double, _ rx: Double, _ ry: Double) -> Path {
        Path(ellipseIn: CGRect(x: cx - rx, y: cy - ry, width: 2 * rx, height: 2 * ry))
    }
    private static func rettangolo(_ x: Double, _ y: Double, _ w: Double, _ h: Double, _ r: Double = 0) -> Path {
        Path(roundedRect: CGRect(x: x, y: y, width: w, height: h), cornerSize: CGSize(width: r, height: r))
    }
    private static func pieno(_ p: Path, _ c: Color, _ opacita: Double = 1) -> ElementoVolto {
        ElementoVolto(path: p, riempimento: .colore(c), opacita: opacita)
    }
    private static func linea(_ d: String, _ c: Color, _ larghezza: Double) -> ElementoVolto {
        ElementoVolto(path: PercorsoSVG.path(d), riempimento: nil, bordo: c, larghezza: larghezza)
    }
    /// Come l'attributo SVG `rotate(gradi cx cy)`.
    private static func ruotato(_ p: Path, _ gradi: Double, _ cx: Double, _ cy: Double) -> Path {
        let t = CGAffineTransform(translationX: cx, y: cy).rotated(by: gradi * .pi / 180).translatedBy(x: -cx, y: -cy)
        return p.applying(t)
    }
    private static func ritagliato(_ e: ElementoVolto, in forma: Path) -> ElementoVolto {
        var r = e
        r.ritaglio = forma
        return r
    }

    private static let capCorto = "M30.5 43C29.5 26 40 19 50 19S70.5 26 69.5 43C67 36 62 33.5 50 33.5S33 36 30.5 43Z"
    private static let rasata = "M32.5 40C32.5 28 41 22 50 22S67.5 28 67.5 40C65 35 59 32 50 32S35 35 32.5 40Z"
    private static let barbaPiena = "M30 40H33Q35 50 42 51.5Q50 49.5 58 51.5Q65 50 67 40H70V70H30Z"
    private static let barbaCorta = "M30 44H33.5Q35 56 44 57.5H56Q65 56 66.5 44H70V70H30Z"
    /// Le due forme delle spalle (normali, larghe).
    private static let spalle = ["M10 100C12 84 28 77 50 77S88 84 90 100Z", "M5 100C8 85 26 77 50 77S92 85 95 100Z"]

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

    /// Il motivo dello sfondo (colori della squadra, forme neutre: mai uno stemma), ritagliato nel cerchio.
    private static func motivo(_ n: Int, _ c2: Color) -> [ElementoVolto] {
        let cerchioSfondo = cerchio(50, 50, 50)
        let el: [ElementoVolto]
        switch n {
        case 1:
            el = [6.0, 28, 50, 72].map { y in pieno(ruotato(rettangolo(-20, y, 140, 9), 35, 50, 50), c2, 0.14) }
        case 2:
            el = [45.0, 34, 23].map { r in ElementoVolto(path: cerchio(50, 50, r), riempimento: nil, bordo: c2.opacity(0.16), larghezza: 3) }
        case 3:
            el = [pieno(PercorsoSVG.path("M50 5L83 15V46Q83 70 50 91Q17 70 17 46V15Z"), c2, 0.14)]
        case 4:
            let raggio = PercorsoSVG.path("M50 50L43 -20H57Z")
            el = (0..<8).map { i in pieno(ruotato(raggio, Double(i) * 45, 50, 50), c2, 0.11) }
        default:
            el = []
        }
        return el.map { ritagliato($0, in: cerchioSfondo) }
    }

    /// Tutti gli elementi del volto, dal fondo (ordine di disegno della sezione 9 della specifica). Lo sfondo (cerchio con sfumatura)
    /// è a parte: vedi `sfondo(c1:c2:)`. `numero` (1-99) è facoltativo: fuori dall'intervallo non si disegna.
    static func elementi(id: Int, portiere: Bool, c1: RGB8, c2: RGB8, tratti: TrattiVolto? = nil, numero: Int? = nil) -> [ElementoVolto] {
        let v = GeneratoreVolto.estrai(id: id, tratti: tratti)
        let pelleRGB = RGB8(GeneratoreVolto.pelli[v.pelle])
        let pelle = colore(pelleRGB), ombra = colore(pelleRGB.scuri(0.14)), segno = colore(pelleRGB.scuri(0.22))
        let capRGB = RGB8(GeneratoreVolto.capelli[v.colore])
        let cap = colore(capRGB), capScuro = colore(capRGB.scuri(0.3))
        let (rx, ry) = GeneratoreVolto.forme[v.forma]
        let (ox, oy) = GeneratoreVolto.orecchie[v.orecchie]
        let mag = colore(portiere ? RGB8("#8d99a8") : c1)
        let col = colore(portiere ? RGB8("#1f2937") : c2)
        let squadra2 = colore(c2)
        let boccaRGB = v.pelle >= 4 ? pelleRGB.misce(RGB8("#f0b8a8"), 0.55) : pelleRGB.scuri(0.45)
        let bocca = colore(boccaRGB)
        let occhioScuro = colore(RGB8("#1d1d22"))
        let (dietro, davanti) = capelli(v.acconciatura, cap, capScuro)
        let viso = ellisse(50, 42, rx, ry)
        let sagoma = PercorsoSVG.path(spalle[v.spalle])
        let ep = v.espressione

        var e: [ElementoVolto] = motivo(v.sfondo, squadra2)
        e.append(contentsOf: dietro)
        // collo, ombra sul collo, spalle (con il disegno della maglia ritagliato dentro) e loro sfumatura
        e.append(pieno(rettangolo(42, 58, 16, 26, 6), ombra))
        e.append(pieno(rettangolo(42, 58, 16, 12, 6), .black, 0.16))
        e.append(pieno(sagoma, mag))
        if !portiere {
            var disegno: [ElementoVolto] = []
            switch v.maglia {
            case 1:
                disegno = [18.0, 34, 50, 66, 82].map { x in pieno(rettangolo(x - 4, 76, 8, 26), squadra2, 0.3) }
            case 2:
                disegno = [pieno(rettangolo(0, 88, 100, 5.5), squadra2, 0.65)]
            case 3:
                disegno = [pieno(PercorsoSVG.path("M0 100C0 96 5 91 12.5 89L24 91.5C22.5 94 21.5 97 21 100ZM100 100C100 96 95 91 87.5 89L76 91.5C77.5 94 78.5 97 79 100Z"), squadra2, 0.55)]
            default:
                break
            }
            e.append(contentsOf: disegno.map { ritagliato($0, in: sagoma) })
        }
        e.append(ElementoVolto(path: sagoma, riempimento: .sfumatura(Gradient(colors: [Color.white.opacity(0.12), Color.black.opacity(0.24)]),
                                                                     CGPoint(x: 50, y: 77), CGPoint(x: 50, y: 100))))
        // colletto
        switch v.colletto {
        case 1:
            e.append(pieno(PercorsoSVG.path("M41 77L50 90L59 77Z"), ombra))
            e.append(linea("M38 77.2L50 92.5L62 77.2", col, 2.4))
        case 2:
            e.append(pieno(PercorsoSVG.path("M41 77Q50 85 59 77Z"), ombra))
            e.append(pieno(PercorsoSVG.path("M39 77.5Q50 85 61 77.5L58.5 75.6Q50 80.6 41.5 75.6Z"), col))
            e.append(linea("M50 81.5V87", col, 1.3))
            e.append(pieno(cerchio(50, 84, 0.8), mag))
        default:
            e.append(pieno(PercorsoSVG.path("M41 77Q50 87 59 77Z"), ombra))
            e.append(pieno(PercorsoSVG.path("M37 77.5Q50 92 63 77.5L59 76.5Q50 85 41 76.5Z"), col))
        }
        if let n = numero, (1...99).contains(n) {
            e.append(ElementoVolto(path: Path(), riempimento: .colore(col), testo: "\(n)"))
        }
        if portiere {
            for x in [18.0, 66.0] {
                e.append(ElementoVolto(path: rettangolo(x, 81, 16, 18, 6), riempimento: .colore(colore(RGB8("#d4f34a"))), bordo: colore(RGB8("#1f2937")), larghezza: 1.2))
                e.append(linea("M\(x + 5.3) 87V93M\(x + 10.7) 87V93", colore(RGB8("#1f2937")), 1))
            }
        }
        // orecchie, viso e sua sfumatura (luce a sinistra, ombra a destra), ombre e guance dentro il viso
        e.append(pieno(ellisse(50 - rx, 44, ox, oy), pelle))
        e.append(pieno(ellisse(50 + rx, 44, ox, oy), pelle))
        e.append(pieno(viso, pelle))
        let sfumaturaViso = Gradient(stops: [
            .init(color: Color.white.opacity(0.13), location: 0),
            .init(color: Color.white.opacity(0), location: 0.45),
            .init(color: Color.black.opacity(0.2), location: 1),
        ])
        e.append(ElementoVolto(path: viso, riempimento: .sfumatura(sfumaturaViso, CGPoint(x: 50 - rx, y: 42), CGPoint(x: 50 + rx, y: 42))))
        e.append(ritagliato(pieno(ellisse(50, 35, 26, 6), .black, 0.1), in: viso))
        e.append(ritagliato(pieno(ellisse(50, 66, rx + 2, 9), .black, 0.09), in: viso))
        if v.guance == 1 {
            let rosa = colore(RGB8("#e8667a"))
            e.append(ritagliato(pieno(ellisse(36.8, 50.5, 4.3, 2.6), rosa, 0.24), in: viso))
            e.append(ritagliato(pieno(ellisse(63.2, 50.5, 4.3, 2.6), rosa, 0.24), in: viso))
        }
        // barba: ritagliata nel viso
        if v.barba == 1 {
            e.append(ritagliato(pieno(PercorsoSVG.path("M30 44Q50 56 70 44V70H30Z"), cap, 0.25), in: viso))
        } else if v.barba == 2 || v.barba == 3 {
            e.append(ritagliato(pieno(PercorsoSVG.path(v.barba == 3 ? barbaPiena : barbaCorta), cap), in: viso))
            e.append(ritagliato(pieno(v.barba == 3 ? ellisse(50, 57.5, 8, 4) : ellisse(50, 57.5, 7.5, 3.6), pelle), in: viso))
        }
        // rughe e naso
        if v.rughe == 1 {
            e.append(linea("M41 52.5Q39.2 56.5 41.4 59.5M59 52.5Q60.8 56.5 58.6 59.5", segno.opacity(0.6), 0.9))
        }
        switch v.naso {
        case 1:
            e.append(linea("M48 51.6Q50 53.6 52 51.6", segno, 1.5))
            e.append(pieno(cerchio(47.6, 51.4, 0.8), segno))
            e.append(pieno(cerchio(52.4, 51.4, 0.8), segno))
        case 2:
            e.append(linea("M50.5 44.5V51.2Q48.6 52.4 46.8 51.6", segno, 1.5))
        default:
            e.append(linea("M49.5 46.5Q47.5 51.5 51 52", segno, 1.6))
        }
        // occhi (l'espressione 3 li chiude tutti e due, la 4 solo il destro)
        func occhioChiuso(_ x: Double) { e.append(linea("M\(x - 3) 43.6Q\(x) 40.4 \(x + 3) 43.6", occhioScuro, 1.8)) }
        func occhioAperto(_ x: Double) {
            if v.pelle >= 5, v.occhi < 2 { e.append(pieno(ellisse(x, 43, 3.1, 2.1), colore(RGB8("#f3ede4")))) }
            switch v.occhi {
            case 0: e.append(pieno(cerchio(x, 43, 1.9), occhioScuro))
            case 1: e.append(pieno(ellisse(x, 43, 2.6, 1.5), occhioScuro))
            default:
                e.append(pieno(ellisse(x, 43, 3.3, 2.4), .white))
                e.append(pieno(cerchio(x, 43, 1.6), colore(RGB8("#2a1d14"))))
            }
        }
        if ep == 3 {
            occhioChiuso(42.5); occhioChiuso(57.5)
        } else if ep == 4 {
            occhioAperto(42.5); occhioChiuso(57.5)
        } else {
            occhioAperto(42.5); occhioAperto(57.5)
        }
        // sopracciglia
        let sopracciglia: (String, Double)
        if ep == 2 {
            sopracciglia = ("M37.5 38.6L47 36.6M53 36.6L62.5 38.6", 2.8)
        } else if ep == 3 {
            sopracciglia = ("M37.5 36Q42 33.5 47 35.5M53 35.5Q58 33.5 62.5 36", 2.2)
        } else {
            let tutte: [(String, Double)] = [("M37.5 37.5H47M53 37.5H62.5", 2.2), ("M37.5 37.5H47M53 37.5H62.5", 3.4), ("M37.5 36.5L47 38.5M53 38.5L62.5 36.5", 2.4)]
            sopracciglia = tutte[v.sopracciglia]
        }
        e.append(linea(sopracciglia.0, colore(capRGB.scuri(0.2)), sopracciglia.1))
        // bocca (l'espressione, se non è quella normale, prende il posto della bocca estratta)
        func boccaNormale(_ n: Int) {
            switch n {
            case 0: e.append(linea("M44.5 57.5H55.5", bocca, 2))
            case 1: e.append(linea("M44 56Q50 61 56 56", bocca, 2))
            case 2: e.append(linea("M45.5 58H54.5", bocca, 2.4))
            default:
                e.append(ElementoVolto(path: PercorsoSVG.path("M44 56Q50 63.5 56 56Z"), riempimento: .colore(.white), bordo: bocca, larghezza: 1.6))
            }
        }
        switch ep {
        case 1:
            e.append(ElementoVolto(path: PercorsoSVG.path("M42.5 55.5Q50 65.5 57.5 55.5Z"), riempimento: .colore(.white), bordo: bocca, larghezza: 1.6))
        case 2:
            e.append(linea("M46 58.5H54", bocca, 2.4))
        case 3:
            e.append(ElementoVolto(path: ellisse(50, 59, 5, 5.6), riempimento: .colore(colore(RGB8("#3b1219"))), bordo: bocca, larghezza: 1.4))
            e.append(pieno(ellisse(50, 62, 3.1, 1.9), colore(RGB8("#e0707a"))))
        case 4:
            boccaNormale(1)
        default:
            boccaNormale(v.bocca)
        }
        if v.barba == 4 {
            e.append(pieno(PercorsoSVG.path("M42 54.5Q46 51.5 50 54Q54 51.5 58 54.5Q54 57.2 50 55.6Q46 57.2 42 54.5Z"), cap))
        }
        if v.accessorio == 3 {
            let bordo = colore(RGB8("#c9b48e"))
            e.append(ElementoVolto(path: ruotato(rettangolo(59, 50, 9, 4, 1.2), -20, 63.5, 52), riempimento: .colore(colore(RGB8("#f1e3c8"))), bordo: bordo, larghezza: 0.6))
            e.append(pieno(ruotato(cerchio(62, 52, 0.5), -20, 63.5, 52), bordo))
            e.append(pieno(ruotato(cerchio(65, 52, 0.5), -20, 63.5, 52), bordo))
        }
        e.append(contentsOf: davanti)
        // ritocchi dei capelli (non su rasata, calvo, cresta bassa)
        if v.ritocco > 0, !GeneratoreVolto.senzaRitocchi.contains(v.acconciatura) {
            if v.ritocco == 1 {
                e.append(linea("M38 26Q44 22 51 21.5M53 22.5Q58.5 22.5 63 26.5", colore(capRGB.misce(RGB8("#ffffff"), 0.3)).opacity(0.6), 1.4))
            } else {
                e.append(pieno(PercorsoSVG.path("M30.5 43C29.5 36 30.5 30 33 27L36 30C34 34 33.5 38 34 43ZM69.5 43C70.5 36 69.5 30 67 27L64 30C66 34 66.5 38 66 43Z"), capScuro, 0.5))
            }
        }
        if v.accessorio == 1 {
            e.append(ElementoVolto(path: PercorsoSVG.path("M31 33Q50 27 69 33V37Q50 31 31 37Z"), riempimento: .colore(squadra2), bordo: colore(c2.scuri(0.35)), larghezza: 0.8))
        }
        if v.accessorio == 2 {
            e.append(ElementoVolto(path: cerchio(50 - rx, 50.5, 1.9), riempimento: .colore(colore(RGB8("#e9c24a"))), bordo: colore(RGB8("#a8841c")), larghezza: 0.6))
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

/// Il volto illustrato nel suo cerchio (sfondo con i colori della squadra e il suo motivo, maglia, volto). Si disegna con un `Canvas`:
/// vettoriale, nessuna foto, nessuna richiesta di rete. Quadrato, di qualunque dimensione; i colori sono quelli dell'illustrazione e
/// valgono uguali nel tema chiaro e scuro. Per VoiceOver è nascosto: il nome sta già nella riga.
struct AvatarVolto: View {
    let id: Int
    var squadra: String?
    var portiere = false
    /// Tratti grossolani del giocatore (colore e famiglia dei capelli, barba); senza, il volto viene tutto dal codice.
    var tratti: TrattiVolto? = nil
    /// Numero di maglia (1-99), facoltativo: se manca non si disegna.
    var numero: Int? = nil

    var body: some View {
        let (c1, c2) = DisegnoVolto.coloriSquadra(squadra)
        let elementi = Self.elementiInMemoria(id: id, portiere: portiere, squadra: squadra, tratti: tratti, numero: numero, c1: c1, c2: c2)
        let (g1, g2) = DisegnoVolto.sfondo(c1: c1, c2: c2)
        Canvas { ctx, dimensione in
            let k = Double(min(dimensione.width, dimensione.height)) / 100
            ctx.scaleBy(x: k, y: k)
            let cerchio = Path(ellipseIn: CGRect(x: 0, y: 0, width: 100, height: 100))
            ctx.fill(cerchio, with: .linearGradient(Gradient(colors: [g1, g2]), startPoint: .zero, endPoint: CGPoint(x: 100, y: 100)))
            for el in elementi {
                if let r = el.ritaglio {
                    ctx.drawLayer { strato in
                        strato.clip(to: r)
                        Self.disegna(el, in: &strato)
                    }
                } else {
                    Self.disegna(el, in: &ctx)
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .clipShape(Circle())
        .accessibilityHidden(true)
    }

    private static func disegna(_ el: ElementoVolto, in ctx: inout GraphicsContext) {
        if let t = el.testo {
            if case .colore(let c)? = el.riempimento {
                ctx.draw(Text(t).font(.system(size: 9, weight: .heavy)).foregroundStyle(c), at: CGPoint(x: 50, y: 94.2), anchor: .center)
            }
            return
        }
        switch el.riempimento {
        case .colore(let c)?: ctx.fill(el.path, with: .color(c.opacity(el.opacita)))
        case .sfumatura(let g, let da, let a)?: ctx.fill(el.path, with: .linearGradient(g, startPoint: da, endPoint: a))
        case nil: break
        }
        if let b = el.bordo {
            ctx.stroke(el.path, with: .color(b), style: StrokeStyle(lineWidth: el.larghezza, lineCap: .round, lineJoin: .round))
        }
    }

    // Gli elementi di un volto non cambiano mai: si costruiscono una volta sola per id, ruolo, squadra, tratti e numero
    // (liste con tante righe: poi costa solo il passaggio sul Canvas).
    private static let memoria: NSCache<NSString, ContenitoreElementi> = {
        let m = NSCache<NSString, ContenitoreElementi>()
        m.countLimit = 3000
        return m
    }()
    private final class ContenitoreElementi {
        let elementi: [ElementoVolto]
        init(_ e: [ElementoVolto]) { elementi = e }
    }

    private static func elementiInMemoria(id: Int, portiere: Bool, squadra: String?, tratti: TrattiVolto?, numero: Int?, c1: RGB8, c2: RGB8) -> [ElementoVolto] {
        let chiave = "\(id)|\(portiere ? "P" : "-")|\((squadra ?? "").lowercased())|\(tratti?.chiave ?? "")|\(numero ?? 0)" as NSString
        if let trovato = memoria.object(forKey: chiave) { return trovato.elementi }
        let nuovi = DisegnoVolto.elementi(id: id, portiere: portiere, c1: c1, c2: c2, tratti: tratti, numero: numero)
        memoria.setObject(ContenitoreElementi(nuovi), forKey: chiave)
        return nuovi
    }
}
