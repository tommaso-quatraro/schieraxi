import Foundation

/// Logica pura delle partite in diretta (Oggi > Partite del turno): quando chiedere di nuovo al server, cosa mostrare.
enum DirettaLogica {
    /// Ogni quanti secondi chiedere mentre una partita è in gioco o sta per iniziare (30-60 s da contratto).
    static let passo: TimeInterval = 45
    /// Da quanto prima del calcio d'inizio si comincia a chiedere.
    static let anticipo: TimeInterval = 10 * 60
    /// Dopo quanto dall'inizio, senza notizie di fine, si smette di aspettare una partita.
    static let durataMassima: TimeInterval = 130 * 60
    /// Oltre questa distanza dalla prossima partita non si programma nessun controllo.
    static let orizzonte: TimeInterval = 12 * 3600

    /// Dopo quanti secondi chiedere di nuovo, o nil se non serve (nessuna partita in corso né in arrivo).
    /// Considera sia le partite dal vivo sia quelle del turno non ancora giocate (se la fonte dal vivo non le ha ancora viste).
    static func attesa(live: LiveWidget?, turno: [Partita], adesso: Date) -> TimeInterval? {
        let dalVivo = live?.partite ?? []
        if (live?.inCorso ?? 0) > 0 || dalVivo.contains(where: \.inGioco) { return passo }

        var inizi: [Date] = []
        for p in dalVivo where !p.finita && p.stato != "rinviata" {
            if let q = p.quando { inizi.append(q) }
        }
        let viste = Set(dalVivo.map { coppia($0.casa, $0.trasferta) })
        for p in turno where p.giocata != true && !viste.contains(coppia(p.casa, p.trasferta)) {
            if let q = Quando.data(p.data) { inizi.append(q) }
        }
        // Le partite già iniziate da poco (e non finite) contano: la fonte potrebbe non averle ancora segnate.
        let rilevanti = inizi.filter { adesso.timeIntervalSince($0) < durataMassima }
        guard let prossimo = rilevanti.min() else { return nil }
        let manca = prossimo.timeIntervalSince(adesso) - anticipo
        if manca <= 0 { return passo }
        if manca > orizzonte { return nil }
        return min(manca, 1800)
    }

    static func coppia(_ casa: String?, _ trasferta: String?) -> String {
        MieiTitolari.chiave(casa ?? "") + "|" + MieiTitolari.chiave(trasferta ?? "")
    }

    /// La partita dal vivo che corrisponde a una del turno (casa e trasferta).
    static func dalVivo(_ live: LiveWidget?, per p: Partita) -> PartitaLive? {
        let c = coppia(p.casa, p.trasferta)
        return live?.partite?.first { coppia($0.casa, $0.trasferta) == c }
    }

    /// Le partite del turno, più quelle in corso fuori turno (recuperi) che il server dal vivo conosce.
    static func conRecuperi(_ turno: [Partita], live: LiveWidget?) -> [Partita] {
        let presenti = Set(turno.map { coppia($0.casa, $0.trasferta) })
        let extra: [Partita] = (live?.partite ?? []).compactMap { l in
            guard l.inGioco, let c = l.casa, let t = l.trasferta, !presenti.contains(coppia(c, t)) else { return nil }
            return Partita(data: l.data, casa: c, trasferta: t, giocata: false)
        }
        return turno + extra
    }

    /// true se il punteggio è salito (un gol appena segnato): serve al lampo lieve. Il primo dato non conta.
    static func golSegnato(prima: PartitaLive?, dopo: PartitaLive?) -> Bool {
        guard let prima, let dopo, prima.golCasa != nil, prima.golTrasferta != nil else { return false }
        return (dopo.golCasa ?? 0) > (prima.golCasa ?? 0) || (dopo.golTrasferta ?? 0) > (prima.golTrasferta ?? 0)
    }

    // MARK: testi

    /// «34'» diventa «34», «90'+3'» diventa «90 più 3» (per VoiceOver).
    static func minutoParlato(_ minuto: String?) -> String? {
        guard let m = minuto, !m.isEmpty else { return nil }
        return m.replacingOccurrences(of: "'", with: "").replacingOccurrences(of: "+", with: " più ")
    }

    static func descrizione(_ e: EventoLive) -> String {
        let chi = e.chi ?? ""
        let quando = minutoParlato(e.minuto).map { " al minuto \($0)" } ?? ""
        switch e.tipo ?? "" {
        case "gol": return "Gol di \(chi)\(quando)" + (e.assistPulito.map { ", assist di \($0)" } ?? "")
        case "rigore": return "Gol su rigore di \(chi)\(quando)"
        case "autogol": return "Autogol di \(chi)\(quando)"
        case "rosso": return "Espulso \(chi)\(quando)"
        case _ where e.tipoVisibile == .rosso: return "Espulso per doppia ammonizione \(chi)\(quando)"
        case _ where e.tipoVisibile == .rigoreFallito: return "Rigore non segnato di \(chi)\(quando)"
        default: return "\(chi)\(quando)".trimmingCharacters(in: .whitespaces)
        }
    }

    /// Frase per VoiceOver: «Inter 1, Roma 0, al 34. Gol di Thuram al minuto 10. Giocano i tuoi titolari Giocatore 089, Giocatore 004».
    static func frase(casa: String, trasferta: String, live: PartitaLive?, ora: String?, titolari: [MioTitolare]) -> String {
        let a = casa.capitalized, b = trasferta.capitalized
        var testo: String
        if let l = live, l.golCasa != nil, l.golTrasferta != nil {
            testo = "\(a) \(l.golCasa ?? 0), \(b) \(l.golTrasferta ?? 0)"
            switch l.stato ?? "" {
            case "intervallo": testo += ", intervallo"
            case "finita": testo += ", finita"
            case "rinviata": testo += ", rinviata"
            case "sospesa": testo += ", sospesa"
            case "da_giocare", "": break
            default: if let m = minutoParlato(l.minuto) { testo += ", al minuto \(m)" } else { testo += ", in corso" }
            }
        } else if live?.stato == "rinviata" {
            testo = "\(a) contro \(b), rinviata"
        } else {
            testo = "\(a) contro \(b)" + (ora.map { ", alle \($0)" } ?? "")
        }
        for e in EventiPartita.visibili(live?.eventi) { testo += ". " + descrizione(e) }
        if !titolari.isEmpty {
            testo += ". Giocano \(titolari.count == 1 ? "il tuo titolare" : "i tuoi titolari") "
                + titolari.map(\.nome).joined(separator: ", ")
        }
        return testo
    }

    /// «Aggiornato alle 15:20» dalla data del server, o nil.
    static func aggiornatoAlle(_ live: LiveWidget?) -> String? {
        guard let d = Quando.data(live?.aggiornatoIl) else { return nil }
        return "Aggiornato alle \(Quando.ora(d))"
    }

    /// La riga della fonte, sempre sotto le partite dal vivo.
    static func nota(fonte: String?) -> String? {
        switch fonte {
        case "espn": return "Risultati in diretta: fonte ESPN, uso personale."
        case "fantacalcio": return "Risultati: fonte Fantacalcio.it, senza il minuto di gioco."
        default: return nil
        }
    }
}
