import Foundation

// Avatar illustrati di SchieraXI, versione 1. Specifica: docs/AVATAR.md del repository dell'app web (implementazione di riferimento
// `fanta/web/avatar.js`). Stesso codice calciatore = stesso volto su web, iOS e Android: qui si riproducono gli STESSI indici
// (numeri casuali mulberry32 e pesi) e gli stessi colori derivati. Il disegno è in `AvatarVolto.swift`.

/// Gli indici di ogni parte del volto, nell'ordine fisso della specifica.
struct IndiciVolto: Equatable, Sendable {
    var pelle = 0, forma = 0, acconciatura = 0, colore = 0, barba = 0
    var sopracciglia = 0, occhi = 0, bocca = 0, accessorio = 0, orecchie = 0

    var elenco: [Int] { [pelle, forma, acconciatura, colore, barba, sopracciglia, occhi, bocca, accessorio, orecchie] }
}

/// Un colore a tre canali interi, con l'aritmetica della specifica (stessi arrotondamenti ovunque).
struct RGB8: Equatable, Sendable {
    let r: Int, g: Int, b: Int

    /// Da «#rrggbb» o «rrggbb»; un testo non valido dà grigio.
    init(_ esadecimale: String) {
        var testo = esadecimale
        if testo.hasPrefix("#") { testo.removeFirst() }
        var n: UInt64 = 0
        if testo.count == 6, Scanner(string: testo).scanHexInt64(&n) {
            r = Int((n >> 16) & 0xff); g = Int((n >> 8) & 0xff); b = Int(n & 0xff)
        } else {
            r = 0x6b; g = 0x72; b = 0x80
        }
    }

    init(r: Int, g: Int, b: Int) { self.r = r; self.g = g; self.b = b }

    var esadecimale: String { String(format: "#%02x%02x%02x", r, g, b) }

    /// `scuri(c, k)`: ogni canale `floor(canale * (1 - k) + 0.5)`.
    func scuri(_ k: Double) -> RGB8 {
        func f(_ c: Int) -> Int { Int((Double(c) * (1 - k) + 0.5).rounded(.down)) }
        return RGB8(r: f(r), g: f(g), b: f(b))
    }

    /// `misce(a, b, t)`: ogni canale `floor(a*(1-t) + b*t + 0.5)`.
    func misce(_ altro: RGB8, _ t: Double) -> RGB8 {
        func f(_ a: Int, _ b: Int) -> Int { Int((Double(a) * (1 - t) + Double(b) * t + 0.5).rounded(.down)) }
        return RGB8(r: f(r, altro.r), g: f(g, altro.g), b: f(b, altro.b))
    }

    /// Luminanza WCAG.
    var luminanza: Double {
        func lineare(_ c: Int) -> Double {
            let x = Double(c) / 255
            return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4)
        }
        return 0.2126 * lineare(r) + 0.7152 * lineare(g) + 0.0722 * lineare(b)
    }
}

enum GeneratoreVolto {
    static let versione = 1
    private static let sale: UInt32 = 0xA5C1D1CE

    /// Pesi (interi, somma 100) di ogni parte, nell'ordine di estrazione.
    static let pesiPelle = [20, 26, 24, 12, 8, 6, 4]
    static let pesiForma = [50, 25, 25]
    static let pesiAcconciatura = [10, 16, 8, 5, 7, 6, 12, 7, 8, 5, 9, 7]
    static let pesiColore = [24, 22, 18, 10, 8, 6, 4, 8]
    static let pesiBarba = [40, 20, 16, 14, 10]
    static let pesiSopracciglia = [40, 30, 30]
    static let pesiOcchi = [40, 30, 30]
    static let pesiBocca = [30, 35, 20, 15]
    static let pesiAccessorio = [78, 8, 8, 6]
    static let pesiOrecchie = [70, 30]

    static let pelli = ["#f6d5bd", "#efc2a0", "#e0a97e", "#c98e5f", "#a56a43", "#7a4a2d", "#5a3722"]
    static let capelli = ["#17171b", "#3a2618", "#6a4328", "#a9793a", "#d9b45a", "#a8441f", "#9aa0a6", "#e8dcc0"]
    /// Semiassi (x, y) del viso, centro (50, 42).
    static let forme: [(Double, Double)] = [(18, 21), (20, 20), (16, 22)]
    static let orecchie: [(Double, Double)] = [(3.2, 4.6), (4.4, 6)]
    static let acconciatureCheCoprono = [3, 4, 8]   // afro, lunga, ondulata
    static let cresta = 7

    /// mulberry32 a 32 bit: ogni chiamata a `prossimo()` dà un numero in [0, 1).
    struct Mulberry32 {
        private var a: UInt32
        init(seme: UInt32) { a = seme }

        mutating func prossimo() -> Double {
            a = a &+ 0x6D2B79F5
            var t = a
            t = (t ^ (t >> 15)) &* (t | 1)
            t ^= t &+ ((t ^ (t >> 7)) &* (t | 61))
            return Double(t ^ (t >> 14)) / 4294967296
        }
    }

    /// Un id valido è un intero tra 0 e 4294967295; altrimenti si usa 0.
    static func idValido(_ id: Int) -> UInt32 {
        (0...4_294_967_295).contains(id) ? UInt32(id) : 0
    }

    static func seme(id: Int) -> UInt32 { (idValido(id) &* 0x9E3779B1) ^ sale }

    /// Scelta con pesi: `n = floor(estrazione * somma)`, poi si scorrono le parti sommando i pesi.
    static func scegli(_ generatore: inout Mulberry32, _ pesi: [Int]) -> Int {
        let totale = pesi.reduce(0, +)
        let n = Int((generatore.prossimo() * Double(totale)).rounded(.down))
        var somma = 0
        for (i, p) in pesi.enumerated() {
            somma += p
            if n < somma { return i }
        }
        return pesi.count - 1
    }

    /// Gli indici di ogni parte per un codice calciatore, con le due regole di coerenza.
    static func estrai(id: Int) -> IndiciVolto { coerenza(estraiGrezzo(id: id)) }

    /// Le due regole di coerenza (cambiano solo l'accessorio).
    static func coerenza(_ grezzo: IndiciVolto) -> IndiciVolto {
        var v = grezzo
        if v.accessorio == 2, acconciatureCheCoprono.contains(v.acconciatura) { v.accessorio = 0 }   // R1
        if v.accessorio == 1, v.acconciatura == cresta { v.accessorio = 0 }                           // R2
        return v
    }

    /// Le dieci estrazioni, nell'ordine fisso della specifica, prima delle regole di coerenza.
    static func estraiGrezzo(id: Int) -> IndiciVolto {
        var g = Mulberry32(seme: seme(id: id))
        var v = IndiciVolto()
        v.pelle = scegli(&g, pesiPelle)
        v.forma = scegli(&g, pesiForma)
        v.acconciatura = scegli(&g, pesiAcconciatura)
        v.colore = scegli(&g, pesiColore)
        v.barba = scegli(&g, pesiBarba)
        v.sopracciglia = scegli(&g, pesiSopracciglia)
        v.occhi = scegli(&g, pesiOcchi)
        v.bocca = scegli(&g, pesiBocca)
        v.accessorio = scegli(&g, pesiAccessorio)
        v.orecchie = scegli(&g, pesiOrecchie)
        return v
    }

    /// Lo sfondo: due colori (da in alto a sinistra a in basso a destra) dai colori della squadra.
    static func sfondo(c1: RGB8, c2: RGB8) -> (RGB8, RGB8) {
        let l = c1.luminanza
        let base: (RGB8, RGB8)
        if l > 0.25 { base = (c1.scuri(0.55), c1.scuri(0.3)) }
        else if l < 0.04 { base = (c1.misce(RGB8("#ffffff"), 0.3), c1.misce(RGB8("#ffffff"), 0.12)) }
        else { base = (c1.scuri(0.5), c1.scuri(0.25)) }
        return (base.0.misce(c2, 0.22), base.1)
    }
}
