import Foundation

// Il fantavoto atteso: il numero firma di SchieraXI. Qui le frasi (pure, provate dai test) di «Perché questo numero»
// e di «Quanto ci abbiamo preso» del Diario. Parole come nella web app; niente parole da scommessa.

/// Le parole del fantavoto atteso, uguali in ogni schermata.
enum FantavotoAtteso {
    static let nome = "Fantavoto atteso"
    static let definizione = "Il fantavoto atteso è quello che SchieraXI si aspetta da questo giocatore in questa partita, se gioca, con le regole della tua lega."

    /// «+1,1» o «−0,4» (con il vero segno meno), in fantavoti o punti. Sotto 0,05 due cifre, per non scrivere «+0,0».
    static func conSegno(_ valore: Double) -> String {
        let cifre = abs(valore) < 0.05 && valore != 0 ? 2 : 1
        return (valore < 0 ? "−" : "+") + Formato.decimali(abs(valore), cifre: cifre)
    }

    /// La stessa cosa a parole, per VoiceOver: «più 1,1», «meno 0,4».
    static func conSegnoVoce(_ valore: Double) -> String {
        let cifre = abs(valore) < 0.05 && valore != 0 ? 2 : 1
        return (valore < 0 ? "meno " : "più ") + Formato.decimali(abs(valore), cifre: cifre)
    }
}

/// «Perché questo numero»: al massimo tre motivi del fantavoto atteso, come li manda il server (`perche_numero`),
/// e il riferimento (il giocatore medio del ruolo). nil = server vecchio o niente da dire: il riquadro non si mostra.
struct PercheNumero: Equatable {
    enum Verso: Equatable {
        /// Alza il numero rispetto al giocatore medio del ruolo.
        case su
        /// Lo abbassa.
        case giu
        /// «gioca N%»: non cambia il fantavoto «se gioca», ma va detto (cambia i punti attesi).
        case avviso
        /// Un motivo senza numero che non è «gioca» (server più nuovo o dato strano).
        case neutro
    }

    struct Riga: Equatable, Identifiable {
        let id: Int
        let chiave: String
        /// La frase del server con la prima lettera maiuscola.
        let testo: String
        /// «+1,1», «−0,4»; nil senza numero.
        let effetto: String?
        let verso: Verso
        /// Frase completa per VoiceOver.
        let voce: String
    }

    static let titolo = "Perché questo numero"
    static let massimoMotivi = 3

    let righe: [Riga]
    /// Il riferimento: «Un giocatore medio del suo ruolo ha 6,2…».
    let nota: String

    init?(motivi: [MotivoNumero]?, mediaRuolo: Double?) {
        guard let motivi else { return nil }
        let media = mediaRuolo.flatMap { $0.isFinite ? $0 : nil }
        var righe: [Riga] = []
        for m in motivi {
            guard righe.count < Self.massimoMotivi else { break }
            let testo = (m.testo ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !testo.isEmpty else { continue }
            let chiave = m.chiave ?? "altro"
            let frase = testo.prefix(1).uppercased() + testo.dropFirst()
            let effetto = m.effetto.flatMap { $0.isFinite ? $0 : nil }
            let verso: Verso
            let voce: String
            if let e = effetto {
                verso = e < 0 ? .giu : .su
                voce = "\(FantavotoAtteso.conSegnoVoce(e)): \(testo)"
            } else {
                verso = chiave == "gioca" ? .avviso : .neutro
                voce = chiave == "gioca" ? "Attenzione: \(testo)" : frase
            }
            righe.append(Riga(id: righe.count, chiave: chiave, testo: frase, effetto: effetto.map(FantavotoAtteso.conSegno), verso: verso, voce: voce))
        }
        if righe.isEmpty && media == nil { return nil }
        self.righe = righe
        if righe.isEmpty, let media {
            nota = "Nessun motivo spicca: il numero è vicino a quello di un giocatore medio del suo ruolo, che ha \(Formato.punti(media))."
        } else if let media {
            nota = "Un giocatore medio del suo ruolo ha \(Formato.punti(media)). Il resto sono differenze piccole."
        } else {
            nota = "I numeri sono le differenze rispetto a un giocatore medio del suo ruolo."
        }
    }

    init?(_ g: Giocatore) {
        // Un assente non ha un fantavoto atteso da spiegare.
        guard g.assente != true else { return nil }
        self.init(motivi: g.motiviNumero, mediaRuolo: g.mediaRuolo)
    }
}

// MARK: - Diario: quanto ci abbiamo preso

/// Il riquadro «Quanto ci abbiamo preso» del Diario: punti attesi della consigliata contro quelli fatti, e l'affidabilità
/// dichiarata. Si mostra anche quando va male. nil = server vecchio o nessuna giornata: il riquadro non c'è.
struct TestoAffidabilita: Equatable {
    static let titolo = "Quanto ci abbiamo preso"
    static let intro = "I punti attesi della formazione consigliata contro quelli fatti davvero, giornata per giornata. Lo mostriamo anche quando va male."

    /// «8/10»: in quante giornate i punti sono caduti nella fascia prevista (nil se non c'erano fasce).
    let dentro: String?
    /// «4,2»: di quanti punti ci sbagliamo in media.
    let scarto: String?
    /// «67,0 / 67,4»: punti medi fatti e previsti.
    let media: String?
    /// «Su 10 giornate i punti fatti sono caduti nella fascia prevista 8 volte, l'80% (dichiarato: 8 volte su 10).»
    let riga: String?
    /// «In media i punti fatti sono stati 1,5 punti in meno di quelli previsti.»
    let verso: String?
    /// Il giudizio in una frase (pochi dati, in linea, peggio o meglio del previsto).
    let giudizio: String?
    /// true se il periodo è andato peggio o meglio del previsto: la frase va evidenziata.
    let fuoriLinea: Bool
    let pochiDati: Bool

    init?(_ a: AffidabilitaDiario?) {
        guard let a, let n = a.giornate, n > 0 else { return nil }
        let minime = a.giornateMinime ?? 8
        let pochi = a.giudizio == "pochi_dati" || a.pochiDati == true || (a.giudizio == nil && n < minime)
        pochiDati = pochi
        let dichiarate = Formato.intero((a.fasciaDichiarata ?? 80) / 10)

        if let k = a.dentroFascia, let c = a.conFascia, c > 0 {
            dentro = "\(k)/\(c)"
            let quota = a.percentualeDentro.map { ", " + Self.percentualeConArticolo(Formato.intero($0)) } ?? ""
            riga = "Su \(Formato.giornate(c)) i punti fatti sono caduti nella fascia prevista \(Formato.plurale(k, "volta", "volte"))"
                + (c > 1 ? quota : "") + " (dichiarato: \(dichiarate) volte su 10)."
        } else {
            dentro = nil
            riga = "Su \(Formato.giornate(n)) non c'era ancora la fascia prevista."
        }
        scarto = a.scartoMedio.map { Formato.punti($0) }
        if let f = a.puntiMediFatti, let p = a.puntiMediAttesi {
            media = "\(Formato.punti(f)) / \(Formato.punti(p))"
        } else {
            media = nil
        }
        if let e = a.erroreMedio {
            if abs(e) < 0.05 {
                verso = "In media i punti fatti e quelli previsti coincidono."
            } else {
                let quanti = Formato.punti(abs(e))
                verso = "In media i punti fatti sono stati \(quanti) punti" + (e > 0 ? " in più" : " in meno") + " di quelli previsti."
            }
        } else {
            verso = nil
        }
        switch a.giudizio {
        case "sotto_le_attese":
            giudizio = "Questo periodo è andato peggio del previsto: i punti veri sono stati spesso sotto la fascia."
            fuoriLinea = true
        case "sopra_le_attese":
            giudizio = "Questo periodo è andato meglio del previsto: i punti veri sono stati spesso sopra la fascia."
            fuoriLinea = true
        case "in_linea":
            giudizio = pochi ? Self.frasePochi(minime) : "È in linea con quello che dichiariamo."
            fuoriLinea = false
        default:
            giudizio = pochi ? Self.frasePochi(minime) : nil
            fuoriLinea = false
        }
    }

    /// «il 50%», ma «l'80%», «l'8%», «l'11%», «l'1%» (i numeri che si leggono con una vocale davanti).
    static func percentualeConArticolo(_ p: Int) -> String {
        let vocale = String(p).hasPrefix("8") || p == 1 || p == 11
        return (vocale ? "l'" : "il ") + "\(p)%"
    }

    static func frasePochi(_ minime: Int) -> String {
        "Ancora pochi dati: servono almeno \(Formato.giornate(minime)) per dire quanto ci prendiamo."
    }
}

/// Una giornata nel grafico e nell'elenco di «Quanto ci abbiamo preso».
struct PuntoAttesoFatto: Identifiable, Equatable {
    let giornata: Int
    let atteso: Double
    let fatti: Double
    let basso: Double?
    let alto: Double?
    /// nil se la fascia non c'era.
    let dentro: Bool?
    var id: Int { giornata }

    /// Fatti meno attesi: positivo = meglio del previsto.
    var scarto: Double { fatti - atteso }

    /// «Previsti tra 61,0 e 77,5: dentro la fascia», «…: sotto la fascia (−4,0)»; senza fascia «Previsti 69,0, fatti 72,5 (+3,5)».
    var frase: String {
        if let basso, let alto, let dentro {
            let tra = "Previsti tra \(Formato.punti(basso)) e \(Formato.punti(alto))"
            if dentro { return tra + ": dentro la fascia" }
            if fatti < basso { return tra + ": sotto la fascia (\(FantavotoAtteso.conSegno(fatti - basso)))" }
            return tra + ": sopra la fascia (\(FantavotoAtteso.conSegno(fatti - alto)))"
        }
        return "Previsti \(Formato.punti(atteso)), fatti \(Formato.punti(fatti)) (\(FantavotoAtteso.conSegno(scarto)))"
    }

    /// Frase completa per VoiceOver.
    var voce: String {
        var t = "Giornata \(giornata): attesi \(Formato.punti(atteso)) punti, fatti \(Formato.punti(fatti))"
        if let basso, let alto, let dentro {
            t += ", fascia prevista tra \(Formato.punti(basso)) e \(Formato.punti(alto)), " + (dentro ? "dentro" : "fuori")
        }
        return t
    }

    init(giornata: Int, atteso: Double, fatti: Double, basso: Double? = nil, alto: Double? = nil, dentro: Bool? = nil) {
        self.giornata = giornata; self.atteso = atteso; self.fatti = fatti
        self.basso = basso; self.alto = alto; self.dentro = dentro
    }

    init?(giornata: Int?, _ r: AttesoVsFatto?) {
        guard let giornata, let r, let atteso = r.atteso, let fatti = r.fatti else { return nil }
        let fascia = r.intervallo?.valido == true ? r.intervallo : nil
        self.init(giornata: giornata, atteso: atteso, fatti: fatti, basso: fascia?.basso, alto: fascia?.alto,
                  dentro: fascia == nil ? nil : r.nellaFascia)
    }

    /// Le giornate della stagione più recente del Diario, dalla prima all'ultima, al massimo le ultime `massimo`.
    static func elenco(_ voci: [VoceDiario], massimo: Int = 12) -> [PuntoAttesoFatto] {
        let stagione = voci.first(where: { $0.attesoVsFatto != nil })?.stagione
        var visti = Set<Int>()
        let punti = voci
            .filter { $0.stagione == stagione }
            .compactMap { PuntoAttesoFatto(giornata: $0.giornata, $0.attesoVsFatto) }
            .filter { visti.insert($0.giornata).inserted }
            .sorted { $0.giornata < $1.giornata }
        return Array(punti.suffix(max(massimo, 1)))
    }
}
