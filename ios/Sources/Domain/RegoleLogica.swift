import Foundation

// Modifica delle regole della lega: il JSON del server si legge e si scrive con «percorsi» (`bonus.gol.D`), senza perdere nessun campo.

extension JSONValue {
    /// Il valore al percorso indicato (`["bonus", "gol", "D"]`), se c'è.
    func valore(_ percorso: [String]) -> JSONValue? {
        guard let primo = percorso.first else { return self }
        guard case .oggetto(let d) = self, let figlio = d[primo] else { return nil }
        return figlio.valore(Array(percorso.dropFirst()))
    }

    /// Scrive un valore al percorso indicato; le parti mancanti del percorso si creano.
    mutating func imposta(_ percorso: [String], _ nuovo: JSONValue) {
        guard let primo = percorso.first else { self = nuovo; return }
        var d: [String: JSONValue] = [:]
        if case .oggetto(let esistente) = self { d = esistente }
        var figlio = d[primo] ?? .nullo
        figlio.imposta(Array(percorso.dropFirst()), nuovo)
        d[primo] = figlio
        self = .oggetto(d)
    }

    /// Comodità con il percorso scritto «a punti»: `valore("bonus.gol.D")`.
    func valore(_ percorso: String) -> JSONValue? { valore(percorso.split(separator: ".").map(String.init)) }
    mutating func imposta(_ percorso: String, _ nuovo: JSONValue) { imposta(percorso.split(separator: ".").map(String.init), nuovo) }

    var numero: Double? {
        switch self {
        case .intero(let n): return Double(n)
        case .decimale(let d): return d
        default: return nil
        }
    }

    var booleano: Bool? {
        if case .booleano(let b) = self { return b }
        return nil
    }

    var testo: String? {
        if case .testo(let t) = self { return t }
        return nil
    }

    var elenco: [JSONValue]? {
        if case .lista(let l) = self { return l }
        return nil
    }

    /// Un numero come lo scrive Python: intero se è intero («500»), decimale altrimenti («0.5»).
    static func numero(_ valore: Double) -> JSONValue {
        valore == valore.rounded() && abs(valore) < 1e12 ? .intero(Int(valore)) : .decimale(valore)
    }
}

enum RegoleLogica {
    /// Tutti i moduli tra cui scegliere (più quelli già nelle regole).
    static let tuttiIModuli = ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1", "3-6-1", "4-2-4", "5-2-3", "3-3-4", "4-6-0"]

    /// Una fascia del modificatore difesa: dalla media di portiere e tre difensori in su vale `bonus` punti.
    struct Fascia: Equatable, Identifiable {
        var media: Double
        var bonus: Double
        let id: UUID
        init(media: Double, bonus: Double, id: UUID = UUID()) {
            self.media = media
            self.bonus = bonus
            self.id = id
        }
        static func == (a: Fascia, b: Fascia) -> Bool { a.media == b.media && a.bonus == b.bonus }
    }

    static func fasce(_ regole: JSONValue) -> [Fascia] {
        (regole.valore("modificatore_difesa.soglie")?.elenco ?? []).compactMap { riga in
            guard let c = riga.elenco, c.count == 2, let m = c[0].numero, let b = c[1].numero else { return nil }
            return Fascia(media: m, bonus: b)
        }
        .sorted { $0.media < $1.media }
    }

    static func scriviFasce(_ fasce: [Fascia], in regole: inout JSONValue) {
        let righe = fasce.sorted { $0.media < $1.media }.map { JSONValue.lista([.numero($0.media), .numero($0.bonus)]) }
        regole.imposta("modificatore_difesa.soglie", .lista(righe))
    }

    /// Bonus del modificatore difesa per una media: l'ultima fascia raggiunta (come fa il calcolo della formazione).
    static func bonusDifesa(media: Double, fasce: [Fascia]) -> Double {
        fasce.sorted { $0.media < $1.media }.filter { media >= $0.media }.last?.bonus ?? 0
    }

    /// Il valore dopo un tocco su + (`su`) o − di una riga delle regole, dentro i limiti.
    static func passoSuccessivo(_ valore: Double, passo: Double, su: Bool, minimo: Double, massimo: Double) -> Double {
        min(massimo, max(minimo, valore + (su ? passo : -passo)))
    }

    /// Media di portiere e tre difensori: la somma dei quattro voti divisa per 4.
    static func mediaDifesa(_ voti: [Double]) -> Double {
        voti.isEmpty ? 0 : voti.reduce(0, +) / Double(voti.count)
    }

    /// Applica ai campi i valori riconosciuti nel regolamento incollato: la chiave è già il percorso nel JSON delle regole
    /// (`bonus.assist`, `panchina.posti`, `moduli`...). Niente è salvato: lo fa l'utente con «Salva».
    static func applica(_ modifiche: [ModificaRegola], a regole: JSONValue) -> JSONValue {
        var nuove = regole
        for m in modifiche { nuove.imposta(m.chiave, m.valore) }
        return nuove
    }

    /// Controlla e sistema le regole prima di salvarle (come la web app). Lancia un errore con il motivo in italiano.
    static func preparaPerSalvataggio(_ regole: JSONValue) throws -> JSONValue {
        var r = regole
        guard let moduli = r.valore("moduli")?.elenco, !moduli.isEmpty else {
            throw ErroreRegole.messaggio("Scegli almeno un modulo.")
        }
        let medie = fasce(r).map(\.media)
        if Set(medie).count != medie.count {
            throw ErroreRegole.messaggio("Due fasce hanno la stessa media: toglierne una.")
        }
        // Con i posti fissi per ruolo il numero in panchina è la somma dei posti.
        if case .oggetto(let posti)? = r.valore("panchina.posti") {
            let totale = ["P", "D", "C", "A"].reduce(0.0) { $0 + (posti[$1]?.numero ?? 0) }
            r.imposta("panchina.numero", .numero(totale))
        }
        if let nome = r.valore("nome_lega")?.testo, nome.trimmingCharacters(in: .whitespaces).isEmpty {
            r.imposta("nome_lega", .testo("La mia lega"))
        }
        return r
    }

    /// Come si scrive un valore riconosciuto nel regolamento, per mostrarlo prima di applicarlo. I numeri negativi con il meno
    /// tipografico «−0,5», come il resto dell'app (`Formato.conSegno`, `CampiRegole.cifra`; prima «-0,5», #911).
    static func descrivi(_ v: JSONValue) -> String {
        switch v {
        case .booleano(let b): return b ? "sì" : "no"
        case .intero(let n): return n < 0 ? "\u{2212}\(n.magnitude)" : String(n)
        case .decimale(let d): return conMeno(d, cifre: decimaliRegola(d))
        case .testo(let t): return t
        case .nullo: return "—"
        case .lista(let l):
            // le fasce sono coppie [media, bonus]
            if l.allSatisfy({ $0.elenco?.count == 2 }) && !l.isEmpty {
                return l.compactMap { c -> String? in
                    guard let e = c.elenco, let m = e[0].numero, let b = e[1].numero else { return nil }
                    return "\(Formato.decimali(m, cifre: 2))→+\(Formato.decimali(b, cifre: 0))"
                }.joined(separator: " · ")
            }
            return l.map { descrivi($0) }.joined(separator: ", ")
        case .oggetto(let d):
            return d.keys.sorted().map { "\($0): \(descrivi(d[$0] ?? .nullo))" }.joined(separator: ", ")
        }
    }

    /// Un testo su una riga, per il nome della lega nel campo che va a capo (#923). Senza a capo resta com'è, anche con uno spazio in
    /// fondo, perché il nome si sta scrivendo. Con un a capo («Invio», un testo incollato) ogni riga perde gli spazi ai lati e le
    /// righe non vuote si uniscono con uno spazio solo: «Invio» dopo uno spazio non lascia «Lega  degli» (revisione della #945), e
    /// quello in fondo si toglie.
    static func suUnaRiga(_ testo: String) -> String {
        guard testo.contains(where: \.isNewline) else { return testo }
        return testo.split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }

    /// Quanti decimali scrivere per un valore delle regole: 0 per un intero, 1 per «0,5», 2 per «0,25» (oltre si arrotonda), come
    /// `decimaliRegola` della web (app.js).
    static func decimaliRegola(_ valore: Double) -> Int {
        valore == valore.rounded() ? 0 : (valore * 10 == (valore * 10).rounded() ? 1 : 2)
    }

    /// Un decimale con `cifre` cifre e, se è negativo, il meno tipografico davanti; senza segno se arrotondato vale zero («0,00»).
    /// La usano anche le righe con − e + dell'editor delle regole (`RigaStepper.testo`).
    static func conMeno(_ valore: Double, cifre: Int) -> String {
        let testo = Formato.decimali(abs(valore), cifre: cifre)
        guard valore < 0, testo.contains(where: { ("1"..."9").contains($0) }) else { return testo }
        return "\u{2212}" + testo
    }
}

enum ErroreRegole: LocalizedError {
    case messaggio(String)

    var errorDescription: String? {
        switch self {
        case .messaggio(let m): return m
        }
    }
}
