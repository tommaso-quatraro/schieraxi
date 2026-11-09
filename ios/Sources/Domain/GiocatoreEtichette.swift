import Foundation

/// Una piccola etichetta sotto il nome di un giocatore («Probabile titolare», «In ballottaggio», «Diffidato», «Infortunato»).
/// Solo parole: l'unica percentuale sul giocare è «gioca N%» (come la web app, dal 2/11/2026).
struct Etichetta: Equatable, Hashable {
    /// Il colore della pillola, con i quattro toni del server (`tono` di `fanta/etichette.py`) e delle pillole della web
    /// (`CLASSE_TONO` di app.js): positivo verde, neutro grigio, attenzione arancio, negativo rosso.
    enum Tono: Equatable, Hashable {
        case positivo, neutro, attenzione, negativo

        /// Il tono scritto dal server; uno mancante o sconosciuto vale neutro, come `classeTono` della web.
        init(server: String?) {
            switch server {
            case "positivo": self = .positivo
            case "attenzione": self = .attenzione
            case "negativo": self = .negativo
            default: self = .neutro
            }
        }

        var gravita: Gravita {
            switch self {
            case .positivo, .neutro: return .normale
            case .attenzione: return .attenzione
            case .negativo: return .grave
            }
        }
    }

    /// Quanto conta l'etichetta, per chi distingue solo grave, attenzione e il resto (righe compatte, pallini di Oggi): positivo e
    /// neutro sono «normale».
    enum Gravita: Equatable, Hashable {
        case normale, attenzione, grave
    }

    let testo: String
    let tono: Tono
    var gravita: Gravita { tono.gravita }
}

extension Giocatore {
    /// Le etichette della titolarità, con le parole e i colori della web app (`tit.*` in testi.js, `TITOLARITA` in app.js).
    static let nomiTitolarita: [String: (String, Etichetta.Tono)] = [
        "titolare": ("Probabile titolare", .positivo), "ballottaggio": ("In ballottaggio", .attenzione),
        "panchina": ("Probabile panchina", .attenzione), "improbabile": ("Improbabile", .negativo), "fuori": ("Fuori", .negativo),
    ]

    /// A giornata iniziata il server toglie `titolarita` e manda `stato_partita`: lo stato vero al posto delle probabili
    /// (colori come `STATO_PARTITA` di app.js, parole `tit.st_*` del catalogo comune).
    static let nomiStatoPartita: [String: (String, Etichetta.Tono)] = [
        "fatto": (Catalogo.Tit.stFatto, .positivo), "senza_voto": (Catalogo.Tit.stSenzaVoto, .attenzione),
        "attesa_voti": (Catalogo.Tit.stAttesaVoti, .neutro), "in_corso": (Catalogo.Tit.stInCorso, .positivo),
        "da_giocare": (Catalogo.Tit.stDaGiocare, .neutro), "rinviata": (Catalogo.Tit.stRinviata, .attenzione),
    ]

    /// Come la web app (`etichetteGiocatore` di `app.js`): prima l'etichetta pronta del server, se c'è; altrimenti la titolarità a
    /// parole (o lo stato della partita) e il dubbio come lo scrive il server («In dubbio · gioca 62%»). Poi la diffida e fino a due
    /// motivi utili del server: senza quelli con una percentuale e, con l'etichetta pronta, senza infortunio, squalifica e
    /// convocazione (li dice già lei).
    var etichette: [Etichetta] {
        var risultato: [Etichetta] = []
        let pronta = etichetta?.testoPronto
        if let e = etichetta, let testo = pronta {
            risultato.append(Etichetta(testo: testo, tono: Etichetta.Tono(server: e.tono)))
        } else if titolarita == nil, let s = statoPartita, let (nome, tono) = Self.nomiStatoPartita[s] {
            risultato.append(Etichetta(testo: nome, tono: tono))
        } else {
            if let t = titolarita, let (nome, tono) = Self.nomiTitolarita[t] {
                risultato.append(Etichetta(testo: nome, tono: tono))
            }
            // Server senza etichetta: il dubbio con le parole del server (`in_dubbio` di `fanta/etichette.py`); dopo «Fuori» no.
            if dubbio == true, titolarita != "fuori" {
                risultato.append(Etichetta(testo: DubbioRiassunto.inDubbio(pVoto), tono: .attenzione))
            }
        }
        if diffidato == true { risultato.append(Etichetta(testo: "Diffidato", tono: .attenzione)) }
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
            risultato.append(Etichetta(testo: m.primaMaiuscola, tono: grave ? .negativo : .neutro))
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

    /// La gravità dal tono del server (`fanta/etichette.py`): negativo grave, attenzione arancio; positivo, neutro o un tono nuovo
    /// normale. Il colore della pillola invece distingue anche il positivo (`Etichetta.Tono`).
    var gravita: Etichetta.Gravita { Etichetta.Tono(server: tono).gravita }
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
