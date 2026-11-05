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
    /// Il numero di Serie A: identifica la giornata.
    let giornata: Int?
    /// Il numero della giornata nella lega (facoltativo: `null` fuori dalla stagione in corso, assente nei server vecchi).
    let giornataLega: Int?
    let haiScelto: [String]?
    let consigliava: [String]?
    let puntiTua: Double?
    let puntiConsigliata: Double?
    let differenza: Double?
    /// `tua`, `consigliata` o `pari`; un valore nuovo che l'app non conosce si tratta come «pari».
    let esito: String?

    var id: String { "\(stagione ?? "")-\(giornata ?? 0)" }

    /// «Giornata 6 · 9ª di Serie A», come la web e le voci del Diario (#299); senza numero della lega «9ª giornata di Serie A».
    var titolo: String { giornata.map { TempiLega.etichetta(serieA: $0, lega: giornataLega) } ?? "Giornata" }

    private enum Chiavi: String, CodingKey {
        case stagione, giornata, giornataLega, haiScelto, consigliava, puntiTua, puntiConsigliata, differenza, esito
    }

    /// Tollerante come `VoceDiario`: un campo in un formato che l'app non conosce vale «assente» e non fa sparire il Diario.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: Chiavi.self)
        stagione = try? c.decodeIfPresent(String.self, forKey: .stagione)
        giornata = try? c.decodeIfPresent(Int.self, forKey: .giornata)
        giornataLega = try? c.decodeIfPresent(Int.self, forKey: .giornataLega)
        haiScelto = try? c.decodeIfPresent([String].self, forKey: .haiScelto)
        consigliava = try? c.decodeIfPresent([String].self, forKey: .consigliava)
        puntiTua = try? c.decodeIfPresent(Double.self, forKey: .puntiTua)
        puntiConsigliata = try? c.decodeIfPresent(Double.self, forKey: .puntiConsigliata)
        differenza = try? c.decodeIfPresent(Double.self, forKey: .differenza)
        esito = try? c.decodeIfPresent(String.self, forKey: .esito)
    }
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
        /// Il titolo come lo legge VoiceOver: «Giornata 6, 9ª di Serie A» (#299).
        var voceTitolo: String? = nil
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
        if (g.haiScelto ?? []).isEmpty || (g.consigliava ?? []).isEmpty { frase = "Hai scelto undici diversi da quelli consigliati." }
        let t = Formato.punti(g.puntiTua), c = Formato.punti(g.puntiConsigliata)
        let verdetto = esito == .tua ? "Meglio tu" : esito == .consigliata ? "Meglio il consiglio" : "Pari"
        return RigaScelta(id: g.id, titolo: g.titolo, frase: frase,
                          punti: "\(verdetto): tu \(t), consiglio \(c)", esito: esito,
                          voceTitolo: g.giornata.map { NomeGiornata(serieA: $0, lega: g.giornataLega).voce })
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
