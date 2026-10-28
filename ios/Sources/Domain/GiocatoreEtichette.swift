import Foundation

/// Una piccola etichetta sotto il nome di un giocatore («Titolare 85%», «Ballottaggio», «Diffidato», «infortunato»).
struct Etichetta: Equatable, Hashable {
    enum Gravita: Equatable, Hashable {
        case normale, attenzione, grave
    }

    let testo: String
    let gravita: Gravita
}

extension Giocatore {
    /// Come la web app: titolarità con la percentuale, diffida, dubbio e fino a due motivi utili del server.
    var etichette: [Etichetta] {
        var risultato: [Etichetta] = []
        let nomi: [String: (String, Etichetta.Gravita)] = [
            "titolare": ("Titolare", .normale), "ballottaggio": ("Ballottaggio", .attenzione), "panchina": ("Panchina", .attenzione),
            "improbabile": ("Improbabile", .grave), "fuori": ("Fuori", .grave),
        ]
        if let t = titolarita, let (nome, gravita) = nomi[t] {
            var testo = nome
            if stato == "titolare", let p = percentuale, t != "fuori" { testo += " \(Formato.intero(p.rounded()))%" }
            risultato.append(Etichetta(testo: testo, gravita: gravita))
        }
        if diffidato == true { risultato.append(Etichetta(testo: "Diffidato", gravita: .attenzione)) }
        let utili = (motivi ?? []).filter { m in
            let minuscolo = m.lowercased()
            return !(minuscolo.hasPrefix("titolare") || minuscolo.hasPrefix("parte dalla panchina")
                     || minuscolo.hasPrefix("partita favorevole") || minuscolo.hasPrefix("partita difficile"))
        }
        for m in utili.prefix(2) {
            let minuscolo = m.lowercased()
            let grave = ["infortunat", "squalificat", "dubbio", "non tra"].contains { minuscolo.contains($0) }
            risultato.append(Etichetta(testo: m.primaMaiuscola, gravita: grave ? .grave : .normale))
        }
        // Un dubbio che il server non ha spiegato con un motivo si mostra comunque.
        if dubbio == true, !risultato.contains(where: { $0.testo.lowercased().contains("dubbio") }) {
            risultato.append(Etichetta(testo: "In dubbio", gravita: .attenzione))
        }
        return risultato
    }
}
