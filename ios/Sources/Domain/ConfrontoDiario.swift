import Foundation

/// I testi e le righe del confronto nel Diario: «Cosa consigliava SchieraXI» accanto a «Cosa hai schierato».
/// Logica pura, provata nei test; la vista usa solo queste frasi (VoiceOver legge le stesse).
struct ConfrontoDiario: Equatable {
    struct Riga: Equatable, Identifiable {
        let id: Int
        let ruolo: String
        let nome: String
        /// Non c'è nell'altra formazione.
        let diverso: Bool

        /// Per VoiceOver: il ruolo per esteso e, se serve, la differenza.
        var voce: String { "\(ConfrontoDiario.ruoloEsteso(ruolo)) \(nome)" + (diverso ? ", diverso dall'altra formazione" : "") }
    }

    let giornata: Int?
    /// «Cosa consigliava SchieraXI (3-4-3)» oppure, se non registrata, «Ricostruita oggi (3-4-3)».
    let titoloConsigliata: String
    /// «Calcolata il 31 ott, 10:05 · Prudente», oppure l'avviso «Consigliata non registrata…».
    let sottoConsigliata: String
    let registrata: Bool
    let consigliata: [Riga]
    let panchina: String?
    /// `nil` se non hai dichiarato nessuna formazione per la giornata.
    let titoloSchierata: String?
    let schierata: [Riga]?
    /// «Hai cambiato 2: A e B al posto di C e D.» / «Hai schierato gli stessi 11 consigliati.»; `nil` se non hai schierato nulla.
    let fraseCambi: String?
    let cambiati: Int

    init?(_ v: VoceDiario) {
        let ist = v.istantanea
        let titolariIst = ist?.titolari ?? []
        let usaIstantanea = !titolariIst.isEmpty
        let base: [TitolareDiario] = usaIstantanea ? titolariIst : (v.consigliata?.titolari ?? [])
        guard !base.isEmpty else { return nil }
        giornata = v.giornata
        registrata = usaIstantanea
        let modulo = (usaIstantanea ? ist?.modulo : v.consigliata?.modulo) ?? "–"
        titoloConsigliata = usaIstantanea ? "Cosa consigliava SchieraXI (\(modulo))" : "Ricostruita oggi (\(modulo))"
        if usaIstantanea {
            var pezzi: [String] = []
            if let q = Self.quando(ist?.calcolata) { pezzi.append("Calcolata il \(q)") }
            if let stile = ist?.stile, !stile.isEmpty { pezzi.append(stile) }
            sottoConsigliata = pezzi.joined(separator: " · ")
        } else {
            sottoConsigliata = "Consigliata non registrata: qui c'è quella che SchieraXI rifà oggi con i dati di allora."
        }
        let p = (usaIstantanea ? ist?.panchina : nil) ?? []
        panchina = p.isEmpty ? nil : "Panchina: " + p.compactMap(\.nome).joined(separator: ", ")

        let tue = v.schierata?.titolari ?? []
        let chiaviCons = Set(base.compactMap(Self.chiave)), chiaviTue = Set(tue.compactMap(Self.chiave))
        func righe(_ l: [TitolareDiario], contro altre: Set<String>?) -> [Riga] {
            let ordinate = l.enumerated().sorted { a, b in
                let ra = Self.ordineRuolo(a.element.ruolo), rb = Self.ordineRuolo(b.element.ruolo)
                return ra == rb ? a.offset < b.offset : ra < rb
            }
            return ordinate.map { i, t in
                Riga(id: i, ruolo: t.ruolo ?? "", nome: t.nome ?? "–", diverso: Self.chiave(t).map { k in altre.map { !$0.contains(k) } ?? false } ?? false)
            }
        }
        if v.schierata != nil, !tue.isEmpty {
            consigliata = righe(base, contro: chiaviTue)
            let rTue = righe(tue, contro: chiaviCons)
            schierata = rTue
            let m = v.schierata?.modulo ?? "–"
            titoloSchierata = v.schierata?.tipo == "consigliata" ? "Cosa hai schierato: la consigliata (\(m))" : "Cosa hai schierato (\(m))"
            let dentro = rTue.filter(\.diverso).map(\.nome)
            let fuori = consigliata.filter(\.diverso).map(\.nome)
            cambiati = max(dentro.count, fuori.count)
            if cambiati == 0 {
                fraseCambi = "Hai schierato gli stessi 11 consigliati."
            } else {
                fraseCambi = "Hai cambiato \(cambiati): \(Self.elenco(dentro)) al posto di \(Self.elenco(fuori))."
            }
        } else {
            consigliata = righe(base, contro: nil)
            schierata = nil
            titoloSchierata = nil
            fraseCambi = nil
            cambiati = 0
        }
    }

    /// Chi non ha id si riconosce dal nome; chi non ha né l'uno né l'altro non si confronta.
    private static func chiave(_ t: TitolareDiario) -> String? {
        if let id = t.id { return "id\(id)" }
        if let n = t.nome, !n.isEmpty { return "n" + n.lowercased() }
        return nil
    }

    private static func ordineRuolo(_ r: String?) -> Int { ["P": 0, "D": 1, "C": 2, "A": 3][r ?? ""] ?? 9 }

    static func ruoloEsteso(_ r: String) -> String {
        ["P": "portiere", "D": "difensore", "C": "centrocampista", "A": "attaccante"][r] ?? r
    }

    /// «A», «A e B», «A, B e C».
    static func elenco(_ nomi: [String]) -> String {
        switch nomi.count {
        case 0: return "–"
        case 1: return nomi[0]
        default: return nomi.dropLast().joined(separator: ", ") + " e " + nomi[nomi.count - 1]
        }
    }

    private static func quando(_ testo: String?) -> String? {
        guard let testo, !testo.isEmpty else { return nil }
        guard let d = Quando.data(testo.replacingOccurrences(of: "T", with: " ")) else { return nil }
        return Quando.leggibile(d)
    }

    /// La frase che legge VoiceOver per la colonna della consigliata (la frase dei cambi è un elemento a parte).
    var voceConfronto: String {
        var f = "\(titoloConsigliata). \(sottoConsigliata) "
        f += consigliata.map(\.voce).joined(separator: ". ") + ". "
        if let p = panchina { f += p + ". " }
        return f
    }
}
