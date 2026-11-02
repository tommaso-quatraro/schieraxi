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
    /// Le etichette della titolarità, a parole e senza numero (come la web): all'utente una sola percentuale, «gioca N%».
    static let nomiTitolarita: [String: (String, Etichetta.Gravita)] = [
        "titolare": ("Probabile titolare", .normale), "ballottaggio": ("In ballottaggio", .attenzione),
        "panchina": ("Probabile panchina", .attenzione), "improbabile": ("Improbabile", .grave), "fuori": ("Fuori", .grave),
    ]

    /// A giornata iniziata (`titolarita` vuota) lo stato della partita del giocatore (`stato_partita`).
    static let nomiStatoPartita: [String: (String, Etichetta.Gravita)] = [
        "da_giocare": ("Da giocare", .normale), "in_corso": ("Partita in corso", .normale), "fatto": ("Ha giocato", .normale),
        "senza_voto": ("Senza voto", .grave), "attesa_voti": ("Voto in arrivo", .normale), "rinviata": ("Rinviata", .attenzione),
    ]

    /// Come la web app: titolarità a parole (o, a giornata iniziata, lo stato della partita), diffida, dubbio e fino a due motivi utili.
    var etichette: [Etichetta] {
        var risultato: [Etichetta] = []
        if let t = titolarita, let (nome, gravita) = Self.nomiTitolarita[t] {
            risultato.append(Etichetta(testo: nome, gravita: gravita))
        } else if titolarita == nil, let s = statoPartita, let (nome, gravita) = Self.nomiStatoPartita[s] {
            risultato.append(Etichetta(testo: nome, gravita: gravita))
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
