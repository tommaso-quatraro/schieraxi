import Foundation

/// Le tre fasi della giornata in Oggi (campo `fase` di `GET /api/oggi`, contratto «fasi della giornata» nel repository del server).
enum FaseGiornata: String {
    /// La formazione si può ancora cambiare: Oggi come sempre (consigli, «Da controllare», migliori).
    case prima
    /// Scadenza passata, partite in corso o da giocare: punti fatti finora, niente consigli su chi schierare.
    case inCorso = "in_corso"
    /// La giornata di prima è finita da poco: riepilogo e prossima giornata.
    case finita
}

extension Oggi {
    /// Fase mancante (server vecchio) o sconosciuta = `prima`: il comportamento di sempre.
    var faseGiornata: FaseGiornata { FaseGiornata(rawValue: fase?.valore ?? "") ?? .prima }

    /// «Da controllare», migliori, indisponibili e diffidati: solo finché la formazione si può cambiare.
    var conConsigli: Bool { faseGiornata == .prima }

    /// Il blocco della giornata in corso (solo nella sua fase).
    var giornataInCorso: GiornataInCorso? { faseGiornata == .inCorso ? inCorso?.valore : nil }
    /// Il riepilogo della giornata finita (solo nella sua fase).
    var riepilogoGiornata: RiepilogoGiornata? { faseGiornata == .finita ? riepilogo?.valore : nil }
    /// La prossima giornata da preparare (solo nella fase `finita`).
    var prossimaGiornata: ProssimaGiornata? { faseGiornata == .finita ? prossima?.valore : nil }

    /// Quante partite in ogni stato: dal blocco `in_corso` se c'è, altrimenti dagli stati delle partite del turno. Nil se non si sa.
    var contoPartite: ContoPartite? {
        if let c = giornataInCorso?.partite, c.totale > 0 { return c }
        let stati = (partite ?? []).compactMap(\.stato)
        guard !stati.isEmpty else { return nil }
        func quante(_ s: String) -> Int { stati.filter { $0 == s }.count }
        let c = ContoPartite(inCorso: quante("in_corso"), finite: quante("finita"), daGiocare: quante("da_giocare"), rinviate: quante("rinviata"))
        return c.totale > 0 ? c : nil
    }
}

/// I testi delle fasi della giornata, in un posto solo (e provati in `FasiGiornataTests`).
enum TestiFase {
    private static let giornoEOra: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "EEE HH:mm"
        return f
    }()

    /// «1 punto», «2,5 punti» (sempre positivo: il segno lo dice la frase).
    static func punti(_ valore: Double) -> String {
        let t = Formato.punti(abs(valore))
        return t == "1,0" ? "1 punto" : "\(t) punti"
    }

    // MARK: partite

    /// «2 in corso · 3 finite · 5 da giocare» (le voci a zero non si scrivono). Nil se non c'è nessuna partita.
    static func partite(_ c: ContoPartite) -> String? {
        var voci: [String] = []
        if c.inCorso > 0 { voci.append("\(c.inCorso) in corso") }
        if c.finite > 0 { voci.append("\(c.finite) \(c.finite == 1 ? "finita" : "finite")") }
        if c.daGiocare > 0 { voci.append("\(c.daGiocare) da giocare") }
        if c.rinviate > 0 { voci.append("\(c.rinviate) \(c.rinviate == 1 ? "rinviata" : "rinviate")") }
        return voci.isEmpty ? nil : voci.joined(separator: " · ")
    }

    /// La stessa cosa per VoiceOver, in una frase: «Partite: 2 in corso, 3 finite, 5 da giocare».
    static func partiteVoce(_ c: ContoPartite) -> String? {
        partite(c).map { "Partite: " + $0.replacingOccurrences(of: " · ", with: ", ") }
    }

    // MARK: giornata in corso

    /// Il fantavoto: una cifra decimale, due se servono (6,25).
    static func fantavoto(_ v: Double) -> String {
        let decimi = v * 10
        return Formato.decimali(v, cifre: abs(decimi - decimi.rounded()) < 0.001 ? 1 : 2)
    }

    /// Cosa scrivere a destra del giocatore: il fantavoto, oppure lo stato o l'ora della partita.
    static func valore(_ g: GiocatoreInCorso) -> String {
        switch g.stato {
        case "fatto": return g.fantavoto.map(fantavoto) ?? "—"
        case "senza_voto": return "Senza voto"
        case "attesa_voti": return "Aspetta il voto"
        case "in_corso": return "In campo"
        case "rinviata": return "Rinviata"
        case "da_giocare": return Quando.data(g.data).map { giornoEOra.string(from: $0) } ?? "Da giocare"
        default: return "—"
        }
    }

    /// Lo stato del giocatore detto a voce: «fantavoto 7,5», «gioca sabato 8 novembre alle 15:00»...
    static func valoreVoce(_ g: GiocatoreInCorso) -> String {
        switch g.stato {
        case "fatto": return g.fantavoto.map { "fantavoto \(fantavoto($0))" } ?? "ha giocato"
        case "senza_voto": return "senza voto"
        case "attesa_voti": return "partita finita, aspetta il voto"
        case "in_corso": return "in campo adesso"
        case "rinviata": return "partita rinviata"
        case "da_giocare":
            if let d = Quando.data(g.data) { return "gioca \(Quando.giorno(d)) alle \(Quando.ora(d))" }
            return "deve ancora giocare"
        default: return "stato non disponibile"
        }
    }

    /// «Mancano i voti di 4 giocatori»; nil se il numero non c'è.
    static func ancora(_ n: Int?) -> String? {
        guard let n, n >= 0 else { return nil }
        switch n {
        case 0: return "Hanno tutti il voto."
        case 1: return "Manca il voto di 1 giocatore."
        default: return "Mancano i voti di \(n) giocatori."
        }
    }

    /// Di chi è la formazione che conta.
    static func formazioneDi(_ di: String?) -> String {
        di == "tua" ? "Con la tua formazione" : "Con la formazione consigliata: non avevi salvato una tua scelta"
    }

    /// «Modificatore della difesa: +1,0, già contato»; nil se non c'è.
    static func modificatore(_ m: Double?) -> String? {
        guard let m, m.isFinite else { return nil }
        return "Modificatore della difesa: \(Formato.conSegno(m)), già contato"
    }

    /// Perché scatta un cambio, in parole semplici.
    static func motivo(_ m: String?) -> String? {
        switch m {
        case "senza_voto": return "Non ha preso il voto"
        case "fuori": return "Infortunato o squalificato"
        case "rinviata": return "Partita rinviata"
        default: return nil
        }
    }

    /// «Esce Marténi, entra Lemão» o «Esce Marténi: nessun sostituto in panchina».
    static func cambio(_ c: CambioPanchina) -> String {
        let esce = c.esce?.nome ?? "un titolare"
        guard let entra = c.entra?.nome, !entra.isEmpty else { return "Esce \(esce): nessun sostituto in panchina" }
        return "Esce \(esce), entra \(entra)"
    }

    static func etichettaCambio(_ c: CambioPanchina) -> String { c.certa ? "Già fatto" : "Probabile" }

    // MARK: giornata finita

    /// «Giornata 8 di lega (Serie A 11)»; nil se il numero manca.
    static func giornata(serieA: Int?, lega: Int?) -> String? {
        serieA.map { TempiLega.etichetta(serieA: $0, lega: lega) }
    }

    /// «3,5 punti più del previsto», «2,0 punti meno del previsto», «Proprio come previsto».
    static func scarto(fatti: Double?, attesi: Double?) -> String? {
        guard let fatti, let attesi, fatti.isFinite, attesi.isFinite else { return nil }
        let d = fatti - attesi
        if abs(d) < 0.05 { return "Proprio come previsto" }
        return "\(punti(d)) \(d > 0 ? "più" : "meno") del previsto"
    }

    /// «Dentro la fascia prevista (tra 63 e 80)» o «Fuori dalla fascia prevista (...)»; nil senza fascia.
    static func fascia(_ r: RiepilogoGiornata) -> String? {
        guard let i = r.intervallo, i.valido, let basso = i.basso, let alto = i.alto, let fatti = r.puntiFatti else { return nil }
        let dentro = basso <= fatti && fatti <= alto
        return "\(dentro ? "Dentro la" : "Fuori dalla") fascia prevista (tra \(Formato.intero(basso)) e \(Formato.intero(alto)))"
    }

    /// Il confronto con la consigliata: solo se hai schierato una formazione tua e il Diario ha i punti della consigliata.
    static func confronto(_ r: RiepilogoGiornata) -> String? {
        guard r.formazioneDi == "tua", let mia = r.puntiFatti, let cons = r.consigliata?.puntiFatti, mia.isFinite, cons.isFinite else { return nil }
        let d = cons - mia
        let base = "Con la consigliata avresti fatto \(Formato.punti(cons)) punti"
        if abs(d) < 0.05 { return base + ": gli stessi." }
        return d > 0 ? base + ": \(punti(d)) in più." : base + ": hai fatto meglio tu di \(punti(d))."
    }

    /// Detto quando il Diario non ha ancora calcolato la giornata.
    static func notaDiario(_ r: RiepilogoGiornata) -> String? {
        r.nelDiario ? nil : "Il confronto con la formazione consigliata arriva nel Diario quando la giornata è calcolata."
    }

    // MARK: prossima giornata

    /// Da quando preparare la prossima formazione.
    static func prossima(_ p: ProssimaGiornata, adesso: Date = Date()) -> String {
        if p.conProbabili { return "Le probabili formazioni ci sono già: puoi preparare la formazione." }
        if let da = Quando.data(p.preparaDa), da > adesso.addingTimeInterval(60) {
            return "Prepara la formazione da \(Quando.giorno(da)) alle \(Quando.ora(da)): di solito le probabili escono allora."
        }
        return "Puoi già preparare la formazione."
    }

    /// «Si chiude sab 8 nov, 14:30»; nil senza scadenza.
    static func scadenza(_ p: ProssimaGiornata) -> String? {
        guard Quando.data(p.scadenza) != nil else { return nil }
        return "Si chiude \(Quando.leggibile(p.scadenza))"
    }
}
