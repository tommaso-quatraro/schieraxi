import Foundation

/// «Le tue scelte» del Diario (`scelte_tue` dentro `GET /api/diario`): quante volte i tuoi undici hanno fatto più punti
/// di quelli consigliati. Tutti i campi sono opzionali: un server più vecchio non manda il blocco e la scheda sparisce.
struct ScelteTue: Decodable {
    let giornate: Int?
    let meglioTua: Int?
    let meglioConsigliata: Int?
    let pari: Int?
    let puntiDifferenza: Double?
    let percentualeTua: Double?
    let pochiDati: Bool?
    let perGiornata: [SceltaGiornata]?
}

struct SceltaGiornata: Decodable, Identifiable {
    let stagione: String?
    let giornata: Int?
    let haiScelto: [String]?
    let consigliava: [String]?
    let puntiTua: Double?
    let puntiConsigliata: Double?
    let differenza: Double?
    /// `tua`, `consigliata` o `pari`; un valore nuovo che l'app non conosce si tratta come «pari».
    let esito: String?

    var id: String { "\(stagione ?? "")-\(giornata ?? 0)" }
}

/// I testi della scheda, in un posto solo (si provano nei test, VoiceOver legge le stesse frasi).
struct ScelteTueTesto: Equatable {
    /// Sotto questo numero di giornate il server dice «pochi dati».
    static let giornateMinime = 8

    let giornate: Int
    let tua: Int
    let consigliata: Int
    let pari: Int
    let pochiDati: Bool
    let percentuale: Int?
    let puntiDifferenza: Double
    let righe: [RigaScelta]

    struct RigaScelta: Equatable, Identifiable {
        let id: String
        let titolo: String
        let frase: String
        let punti: String
        let esito: Esito
    }

    enum Esito: Equatable { case tua, consigliata, pari }

    /// `nil` se il blocco manca o non ci sono giornate con scelte diverse: la scheda allora non si mostra.
    init?(_ s: ScelteTue?) {
        guard let s, let n = s.giornate, n > 0 else { return nil }
        giornate = n
        let t = max(0, s.meglioTua ?? 0)
        tua = t
        consigliata = max(0, s.meglioConsigliata ?? 0)
        pari = max(0, s.pari ?? 0)
        pochiDati = s.pochiDati ?? (n < Self.giornateMinime)
        percentuale = s.percentualeTua.map { Int($0.rounded()) } ?? Int((Double(t) * 100 / Double(n)).rounded())
        puntiDifferenza = s.puntiDifferenza ?? 0
        righe = (s.perGiornata ?? []).map(Self.riga)
    }

    private static func riga(_ g: SceltaGiornata) -> RigaScelta {
        let esito: Esito = g.esito == "tua" ? .tua : g.esito == "consigliata" ? .consigliata : .pari
        var frase = "Hai messo \(elenco(g.haiScelto)) al posto di \(elenco(g.consigliava))."
        if (g.haiScelto ?? []).isEmpty || (g.consigliava ?? []).isEmpty { frase = "undici diversi da quelli consigliati." }
        let t = Formato.punti(g.puntiTua), c = Formato.punti(g.puntiConsigliata)
        let verdetto = esito == .tua ? "Meglio tu" : esito == .consigliata ? "Meglio il consiglio" : "Pari"
        return RigaScelta(id: g.id, titolo: "Giornata \(g.giornata ?? 0)", frase: frase,
                          punti: "\(verdetto): tu \(t), consiglio \(c)", esito: esito)
    }

    private static func elenco(_ nomi: [String]?) -> String {
        let n = (nomi ?? []).filter { !$0.isEmpty }
        switch n.count {
        case 0: return "–"
        case 1: return n[0]
        default: return n.dropLast().joined(separator: ", ") + " e " + n[n.count - 1]
        }
    }

    static func volte(_ n: Int) -> String { Formato.plurale(n, "volta", "volte") }

    /// Il numero grande: «5 su 9».
    var numeroGrande: String { "\(tua) su \(giornate)" }

    var sottotitolo: String {
        "\(tua == 1 ? "volta" : "volte") in cui i tuoi undici hanno fatto più punti del consiglio, in \(Formato.giornate(giornate)) con scelte diverse"
    }

    /// «+4,5 punti rispetto al consiglio» o «gli stessi punti del consiglio».
    var frasePunti: String {
        let d = (puntiDifferenza * 10).rounded() / 10
        if d == 0 { return "In totale, gli stessi punti del consiglio." }
        let unita = abs(d) == 1 ? "punto" : "punti"
        let segno = Formato.conSegno(d).replacingOccurrences(of: "-", with: "−")
        return d > 0 ? "In totale \(segno) \(unita) rispetto al consiglio: ci hai guadagnato."
                     : "In totale \(segno) \(unita) rispetto al consiglio: ci hai perso."
    }

    var fraseCommento: String {
        if pochiDati { return "Ancora pochi dati: servono almeno \(Self.giornateMinime) giornate con scelte diverse per dire chi ha ragione più spesso." }
        return percentuale.map { "Hai avuto ragione nel \($0)% delle giornate." } ?? ""
    }

    /// La frase che legge VoiceOver per tutto il riepilogo.
    var voceRiepilogo: String {
        "Le tue scelte. In \(Formato.giornate(giornate)) con undici diversi dal consiglio: meglio tu \(Self.volte(tua)), meglio il consiglio \(Self.volte(consigliata)), pari \(Self.volte(pari)). \(frasePunti) \(fraseCommento)"
    }
}
