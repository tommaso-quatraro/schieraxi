import Foundation

/// La formazione scritta a parole, da copiare o mandare nel gruppo (Leghe non permette di incollarla: si inserisce a mano).
enum TestoFormazione {
    /// «Giornata 9 · 4-3-3», una riga per reparto («P: Giocatore 094»), poi «Panchina: 1) Giocatore 007, 2) ...».
    static func crea(giornata: Int, giornataLega: Int? = nil, modulo: String, titolari: [Giocatore], panchina: [Giocatore]) -> String {
        var righe = ["\(TempiLega.etichetta(serieA: giornata, lega: giornataLega)) · \(modulo)"]
        for ruolo in ["P", "D", "C", "A"] {
            righe.append("\(ruolo): " + titolari.filter { $0.ruolo == ruolo }.map(\.nome).joined(separator: ", "))
        }
        if !panchina.isEmpty {
            righe.append("Panchina: " + panchina.enumerated().map { "\($0.offset + 1)) \($0.element.nome)" }.joined(separator: ", "))
        }
        return righe.joined(separator: "\n")
    }
}

/// I «ballottaggi»: per un titolare non sicuro, i due della rosa dello stesso ruolo che gli stanno più vicini.
enum Ballottaggio {
    struct Alternativa: Identifiable, Equatable {
        let giocatore: Giocatore
        /// Punti attesi di quello in più (o in meno) rispetto al titolare incerto.
        let differenza: Double
        var id: Int { giocatore.id }
        /// Meno di 0,4 punti di distanza: quasi pari.
        var quasiPari: Bool { abs(differenza) < 0.4 }

        static func == (a: Alternativa, b: Alternativa) -> Bool { a.giocatore.id == b.giocatore.id && a.differenza == b.differenza }
    }

    /// Vuoto per i titolari sicuri (e per chi non ha una titolarità indicata).
    static func alternative(per g: Giocatore, rosa: [Giocatore], titolari: [Giocatore]) -> [Alternativa] {
        guard let t = g.titolarita, t != "titolare" else { return [] }
        let dentro = Set(titolari.map(\.id))
        return rosa
            .filter { $0.ruolo == g.ruolo && !dentro.contains($0.id) && ($0.pVoto ?? 0) >= 0.2 }
            .sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
            .prefix(2)
            .map { Alternativa(giocatore: $0, differenza: ($0.puntiAttesi ?? 0) - (g.puntiAttesi ?? 0)) }
    }
}
