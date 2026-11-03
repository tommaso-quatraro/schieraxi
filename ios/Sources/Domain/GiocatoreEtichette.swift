import Foundation

/// Una piccola etichetta sotto il nome di un giocatore («Probabile titolare», «In ballottaggio», «Diffidato», «Infortunato»).
/// Solo parole: l'unica percentuale sul giocare è «gioca N%» (come la web app, dal 2/11/2026).
struct Etichetta: Equatable, Hashable {
    enum Gravita: Equatable, Hashable {
        case normale, attenzione, grave
    }

    let testo: String
    let gravita: Gravita
}

extension Giocatore {
    /// Le etichette della titolarità, come la web app (`tit.*` in testi.js).
    static let nomiTitolarita: [String: (String, Etichetta.Gravita)] = [
        "titolare": ("Probabile titolare", .normale), "ballottaggio": ("In ballottaggio", .attenzione),
        "panchina": ("Probabile panchina", .attenzione), "improbabile": ("Improbabile", .grave), "fuori": ("Fuori", .grave),
    ]

    /// A giornata iniziata il server toglie `titolarita` e manda `stato_partita`: lo stato vero al posto delle probabili.
    static let nomiStatoPartita: [String: (String, Etichetta.Gravita)] = [
        "fatto": ("Ha giocato", .normale), "senza_voto": ("Senza voto", .attenzione), "attesa_voti": ("Voto in arrivo", .normale),
        "in_corso": ("Partita in corso", .normale), "da_giocare": ("Da giocare", .normale), "rinviata": ("Rinviata", .attenzione),
    ]

    /// Come la web app: titolarità a parole (o lo stato della partita), diffida, dubbio e fino a due motivi utili del server
    /// (senza quelli con una percentuale).
    var etichette: [Etichetta] {
        var risultato: [Etichetta] = []
        if titolarita == nil, let s = statoPartita, let (nome, gravita) = Self.nomiStatoPartita[s] {
            risultato.append(Etichetta(testo: nome, gravita: gravita))
        } else if let t = titolarita, let (nome, gravita) = Self.nomiTitolarita[t] {
            risultato.append(Etichetta(testo: nome, gravita: gravita))
        }
        if diffidato == true { risultato.append(Etichetta(testo: "Diffidato", gravita: .attenzione)) }
        let utili = (motivi ?? []).filter { m in
            let minuscolo = m.lowercased()
            return !(minuscolo.hasPrefix("titolare") || minuscolo.hasPrefix("parte dalla panchina")
                     || minuscolo.hasPrefix("partita favorevole") || minuscolo.hasPrefix("partita difficile"))
                && m.range(of: #"\d\s*%"#, options: .regularExpression) == nil
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

// TODO(#189): da scrivere dopo i test.
extension Avviso {
    var descrizione: String { tipo ?? "" }
    var gravita: Etichetta.Gravita { .normale }
}
