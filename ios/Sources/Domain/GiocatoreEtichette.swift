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

    /// Come la web app (`etichetteGiocatore` di `app.js`): prima l'etichetta pronta del server, se c'è; altrimenti la titolarità a
    /// parole (o lo stato della partita) e il dubbio come lo scrive il server («In dubbio · gioca 62%»). Poi la diffida e fino a due
    /// motivi utili del server: senza quelli con una percentuale e, con l'etichetta pronta, senza infortunio, squalifica e
    /// convocazione (li dice già lei).
    var etichette: [Etichetta] {
        var risultato: [Etichetta] = []
        let pronta = etichetta?.testoPronto
        if let e = etichetta, let testo = pronta {
            risultato.append(Etichetta(testo: testo, gravita: e.gravita))
        } else if titolarita == nil, let s = statoPartita, let (nome, gravita) = Self.nomiStatoPartita[s] {
            risultato.append(Etichetta(testo: nome, gravita: gravita))
        } else {
            if let t = titolarita, let (nome, gravita) = Self.nomiTitolarita[t] {
                risultato.append(Etichetta(testo: nome, gravita: gravita))
            }
            // Server senza etichetta: il dubbio con le parole del server (`in_dubbio` di `fanta/etichette.py`); dopo «Fuori» no.
            if dubbio == true, titolarita != "fuori" {
                risultato.append(Etichetta(testo: DubbioRiassunto.inDubbio(pVoto), gravita: .attenzione))
            }
        }
        if diffidato == true { risultato.append(Etichetta(testo: "Diffidato", gravita: .attenzione)) }
        let utili = (motivi ?? []).filter { m in
            let minuscolo = m.lowercased()
            return !(minuscolo.hasPrefix("titolare") || minuscolo.hasPrefix("parte dalla panchina")
                     || minuscolo.hasPrefix("partita favorevole") || minuscolo.hasPrefix("partita difficile"))
                && m.range(of: #"\d\s*%"#, options: .regularExpression) == nil
                && !(pronta != nil && Self.motivoDiStato(minuscolo))
        }
        for m in utili.prefix(2) {
            let minuscolo = m.lowercased()
            let grave = ["infortunat", "squalificat", "dubbio", "non tra"].contains { minuscolo.contains($0) }
            risultato.append(Etichetta(testo: m.primaMaiuscola, gravita: grave ? .grave : .normale))
        }
        return risultato
    }

    /// I motivi che ripetono lo stato (`motivo.infortunato`, `motivo.squalificato`, `motivo.non_convocato` di `fanta/frasi.py`),
    /// come `motivoDiStato` della web.
    private static func motivoDiStato(_ minuscolo: String) -> Bool {
        ["infortunato", "squalificato", "non tra i convocati"].contains { minuscolo.hasPrefix($0) }
    }
}

extension Avviso.EtichettaPronta {
    /// Il testo del server senza spazi ai bordi; nil se manca o è vuoto (allora vale «niente etichetta»).
    var testoPronto: String? {
        guard let t = testo?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else { return nil }
        return t
    }

    /// Il colore dal tono del server (`fanta/etichette.py`): negativo grave, attenzione arancio; positivo, neutro o un tono nuovo
    /// normale, come `classeTono` della web.
    var gravita: Etichetta.Gravita {
        switch tono {
        case "negativo": return .grave
        case "attenzione": return .attenzione
        default: return .normale
        }
    }
}

extension Avviso {
    /// La riga di un avviso di Oggi come la web: il testo del server se c'è, altrimenti le stesse parole («In dubbio · gioca 55%»
    /// di `oggi.dubbio`, «Infortunato», «Squalificato», «Diffidato»).
    var descrizione: String {
        if let t = etichetta?.testoPronto { return t }
        switch tipo {
        case "infortunato": return "Infortunato"
        case "squalificato": return "Squalificato"
        case "dubbio": return DubbioRiassunto.inDubbio(pVoto)
        case "diffidato": return "Diffidato"
        default: return (tipo ?? "").primaMaiuscola
        }
    }

    /// Il colore del pallino: dal tono del server se c'è l'etichetta, altrimenti dal tipo (assenze gravi, dubbio da guardare).
    var gravita: Etichetta.Gravita {
        if let e = etichetta, e.testoPronto != nil { return e.gravita }
        switch tipo {
        case "infortunato", "squalificato": return .grave
        case "dubbio": return .attenzione
        default: return .normale
        }
    }
}
