import Foundation

/// Le regole di contorno degli scambi (stesse della web app): bozza del messaggio, giudizio, squadre più propense ad accettare.
enum ScambiLogica {
    /// Sotto questa soglia (punti attesi in stagione) uno scambio «cambia poco». Come fanta/scambi.py.
    static let soglia = 0.5

    private static func nomi(_ lista: [GiocatoreBreve]) -> String { lista.map(\.nome).joined(separator: " e ") }

    /// Il messaggio da mandare all'altro allenatore.
    static func bozza(_ s: PropostaScambio) -> String {
        let quasiUguale = abs(s.guadagnoMio - s.guadagnoLoro) < 1
        let conti = quasiUguale
            ? "più o meno uguale"
            : "tu \(Formato.conSegno(s.guadagnoLoro)) punti attesi in stagione, io \(Formato.conSegno(s.guadagnoMio))"
        return "Ciao! Ti propongo uno scambio: io ti do \(nomi(s.`do`)), tu mi dai \(nomi(s.ricevo)). "
            + "Secondo i miei calcoli conviene a tutti e due (\(conti)). Che ne dici?"
    }

    /// Giudizio su un'offerta ricevuta.
    static func giudizioOfferta(_ s: PropostaScambio) -> String {
        if s.guadagnoMio >= soglia {
            return s.guadagnoLoro >= soglia ? "Conviene a tutti e due: accettalo." : "Ti conviene: accettalo (a loro un po' meno)."
        }
        return s.guadagnoMio > -soglia ? "Cambia poco: decidi tu." : "Non ti conviene: rifiuta o chiedi di più."
    }

    /// Giudizio su uno scambio analizzato a mano.
    static func giudizioAnalisi(_ s: PropostaScambio) -> String {
        if s.guadagnoMio >= soglia && s.guadagnoLoro >= soglia { return "Conviene a tutti e due: proponilo." }
        if s.guadagnoMio >= soglia { return "Conviene a te ma non a loro: difficile che accettino." }
        return s.guadagnoMio > -soglia ? "Cambia poco: non vale la pena." : "Non ti conviene."
    }

    /// Una squadra che guadagna dagli scambi proposti, e il reparto che ne beneficia di più.
    struct SquadraPropensa: Equatable, Identifiable {
        let nome: String
        let scambi: Int
        let media: Double
        /// Il reparto («A», «C»...) e di quanti punti percentuali migliora.
        let reparto: String?
        let miglioramento: Double?
        var id: String { nome }
    }

    /// Le (al massimo quattro) squadre che guadagnano di più dagli scambi proposti: sono le più propense ad accettare.
    /// Con meno di due squadre non serve una classifica.
    static func squadrePropense(_ proposte: [PropostaScambio]) -> [SquadraPropensa] {
        var per: [String: (n: Int, somma: Double, reparti: [String: Double])] = [:]
        var ordine: [String] = []
        for s in proposte {
            if per[s.altra] == nil { ordine.append(s.altra) }
            var x = per[s.altra] ?? (0, 0, [:])
            x.n += 1
            x.somma += s.guadagnoLoro
            for (r, v) in s.reparti?.loro ?? [:] { x.reparti[r] = max(x.reparti[r] ?? -99, v) }
            per[s.altra] = x
        }
        let elenco: [SquadraPropensa] = ordine.compactMap { nome in
            guard let x = per[nome] else { return nil }
            let migliore = x.reparti.max { $0.value < $1.value }
            return SquadraPropensa(nome: nome, scambi: x.n, media: x.somma / Double(x.n), reparto: migliore?.key, miglioramento: migliore?.value)
        }
        .sorted { $0.media > $1.media }
        let primi = Array(elenco.prefix(4))
        return primi.count < 2 ? [] : primi
    }
}

/// Gli scambi analizzati, ricordati su questo telefono (gli ultimi 20): come l'archivio della web app.
struct VoceArchivioScambi: Codable, Identifiable, Equatable {
    let quando: Date
    let con: String
    let dai: [String]
    let ricevo: [String]
    let mio: Double
    let loro: Double
    let percentuale: Double?
    var id: String { chiave }
    var chiave: String { "\(con)|\(dai.joined(separator: ","))|\(ricevo.joined(separator: ","))" }
}

enum ArchivioScambi {
    private static let chiaveMemoria = "archivioScambi"
    static let massimo = 20

    static func leggi(_ memoria: UserDefaults = .standard) -> [VoceArchivioScambi] {
        guard let dati = memoria.data(forKey: chiaveMemoria) else { return [] }
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return (try? d.decode([VoceArchivioScambi].self, from: dati)) ?? []
    }

    /// Aggiunge lo scambio in cima (se c'era già lo stesso, lo sposta in cima) e tiene gli ultimi 20.
    @discardableResult
    static func registra(_ s: PropostaScambio, quando: Date = Date(), _ memoria: UserDefaults = .standard) -> [VoceArchivioScambi] {
        let voce = VoceArchivioScambi(quando: quando, con: s.altra, dai: s.`do`.map(\.nome), ricevo: s.ricevo.map(\.nome),
                                      mio: s.guadagnoMio, loro: s.guadagnoLoro, percentuale: s.percentualeMio)
        let nuovo = Array(([voce] + leggi(memoria).filter { $0.chiave != voce.chiave }).prefix(massimo))
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        if let dati = try? e.encode(nuovo) { memoria.set(dati, forKey: chiaveMemoria) }
        return nuovo
    }

    static func svuota(_ memoria: UserDefaults = .standard) {
        memoria.removeObject(forKey: chiaveMemoria)
    }
}
