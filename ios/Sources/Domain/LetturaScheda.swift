import Foundation

/// Cosa scrive la scheda del giocatore, una sola come la web (#616, `htmlScheda` e `riempiScheda` di app.js). Logica pura con le
/// frasi del catalogo comune e i numeri del server (`SchedaGiocatoreComeLaWebTests`); il disegno è in `Presentation/Mercato/`.
enum LetturaScheda {
    /// `stato_partita` a partita finita (`PARTITA_FINITA` di app.js).
    static let statiFinita: Set<String> = ["attesa_voti", "fatto", "senza_voto"]
    /// Un valore che manca, come `num` e `quando` della web.
    static let senzaValore = "–"

    // MARK: intestazione

    /// «Attaccante · Genoa»: il ruolo per intero (`ruolo.A_1`, come `NOME_RUOLO_1` della web) e il club. Un ruolo sconosciuto si
    /// scrive com'è; senza club solo il ruolo.
    static func ruoloEClub(ruolo: String, club: String?) -> String {
        let nome: String
        switch ruolo {
        case "P": nome = Catalogo.Ruolo.p1
        case "D": nome = Catalogo.Ruolo.d1
        case "C": nome = Catalogo.Ruolo.c1
        case "A": nome = Catalogo.Ruolo.a1
        default: nome = ruolo
        }
        let squadra = (club ?? "").trimmingCharacters(in: .whitespaces)
        return squadra.isEmpty ? nome : "\(nome) · \(squadra)"
    }

    /// «In casa contro Como · sab 31 20:45» o «In trasferta contro Hellas Verona · …» (`formazione.partita_casa`,
    /// `formazione.partita_fuori`), senza la giornata: la scheda si apre dalla Formazione di quella giornata. «oggi» e «ieri» si
    /// contano da `adesso` (l'ora dell'app, `Orologio`); senza data «–», come `quando` della web. nil senza avversario.
    static func partita(_ g: Giocatore, adesso: Date) -> String? {
        guard let avversario = g.avversario?.trimmingCharacters(in: .whitespaces), !avversario.isEmpty else { return nil }
        let nome = avversario.capitalized
        let quando = Quando.data(g.dataPartita) == nil ? senzaValore : Quando.leggibile(g.dataPartita, adesso: adesso)
        return g.inCasa == true
            ? Catalogo.Formazione.partitaCasa(avv: nome, quando: quando)
            : Catalogo.Formazione.partitaFuori(avv: nome, quando: quando)
    }

    // MARK: le cifre

    /// La cifra grande.
    enum Prima: Equatable {
        /// Prima della partita (e a partita in corso): il fantavoto atteso «se gioca»; nil = «–».
        case atteso(Double?)
        /// A partita finita con il voto: il fantavoto preso.
        case preso(Double)
        /// A partita finita senza voto: lo stato della partita («Senza voto», «Voto in arrivo»).
        case stato(String)
    }

    /// La cifra accanto.
    enum Accanto: Equatable {
        /// Prima della partita: «gioca N%» (colorato sotto l'80%) e lo stato a parole, se c'è.
        case gioca(percento: Int, livello: SogliaGioca.Livello, parola: ParolaStato?)
        /// A partita in corso: lo stato della partita al posto di «gioca N%».
        case stato(String)
    }

    enum Cifre: Equatable {
        /// Senza previsione per la giornata: `mercato.nessuna_previsione_per`.
        case nessunaPrevisione
        case cifre(Prima, accanto: Accanto?)
    }

    /// Le cifre in testa alla scheda, come `cifre-scheda` della web.
    static func cifre(_ g: Giocatore?) -> Cifre {
        guard let g else { return .nessunaPrevisione }
        let esito = g.esitoPartita
        let finita = statiFinita.contains(g.statoPartita ?? "")
        let testoEsito = esito?.testo ?? senzaValore
        let prima: Prima
        if let fv = esito?.fv {
            prima = .preso(fv)
        } else if finita {
            prima = .stato(testoEsito)
        } else {
            prima = .atteso(g.fvAtteso)
        }
        let accanto: Accanto?
        if esito != nil {
            accanto = finita ? nil : .stato(testoEsito)
        } else {
            accanto = .gioca(percento: Formato.percento(SogliaGioca.letta(g.pVoto)), livello: SogliaGioca.livello(g.pVoto),
                             parola: ParolaStato(g))
        }
        return .cifre(prima, accanto: accanto)
    }

    /// La nota delle probabili che spiega lo stato («contusione al ginocchio, in forte dubbio»), scritta com'è: solo con uno stato
    /// a parole e mai a partita cominciata (`notaStato` della web).
    static func nota(_ g: Giocatore) -> String? {
        guard g.esitoPartita == nil, ParolaStato(g) != nil else { return nil }
        let testo = (g.nota ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return testo.isEmpty ? nil : testo
    }

    /// «Perché questo numero» dentro la scheda: niente a partita finita; a partita cominciata senza il motivo «gioca» (non serve
    /// più). nil con un server che non manda i motivi.
    static func perche(_ g: Giocatore) -> PercheNumero? {
        guard !statiFinita.contains(g.statoPartita ?? ""), g.assente != true else { return nil }
        var motivi = g.motiviNumero
        if g.esitoPartita != nil { motivi = motivi?.filter { $0.chiave != "gioca" } }
        return PercheNumero(motivi: motivi, mediaRuolo: g.mediaRuolo)
    }

    // MARK: «Tutti i numeri»

    /// «Questa partita» solo prima della partita e per chi può giocare (né infortunato, né squalificato, né fuori).
    static func conQuestaPartita(_ g: Giocatore?) -> Bool {
        guard let g else { return false }
        return !EsitoPedina.statiIniziata.contains(g.statoPartita ?? "") && ParolaStato(g)?.nonGiocaDiSicuro != true
    }

    /// I motivi da mostrare in «Questa partita», come `motiviUtili(pr).filter(senzaPercentuale)` della web: via titolarità e
    /// partita, i primi due, poi via quelli con una percentuale (l'unica percentuale sul giocare è «gioca N%»).
    static func motiviPartita(_ g: Giocatore) -> [String] {
        let utili = (g.motivi ?? []).filter { m in
            !(m.hasPrefix("titolare") || m.hasPrefix("parte dalla panchina")
              || m.hasPrefix("partita favorevole") || m.hasPrefix("partita difficile"))
        }
        return utili.prefix(2).filter { $0.range(of: #"\d\s*%"#, options: .regularExpression) == nil }
    }

    /// «risultato atteso 2,1–1,0»: gol attesi della sua squadra, poi quelli dell'avversario (`mercato.gol_attesi`). Senza uno dei
    /// due numeri non si mostra.
    static func risultatoAtteso(_ g: Giocatore) -> String? {
        guard let a = g.golSquadra, let b = g.golAvversario, a.isFinite, b.isFinite else { return nil }
        return Catalogo.Mercato.golAttesi(a: Formato.decimali(a), b: Formato.decimali(b))
    }

    /// Per VoiceOver, con i nomi delle squadre: «Risultato atteso: Genoa 2,1, Como 1,0».
    static func voceRisultatoAtteso(_ g: Giocatore, squadra: String?) -> String? {
        guard let a = g.golSquadra, let b = g.golAvversario, a.isFinite, b.isFinite else { return nil }
        let mia = (squadra ?? g.squadra ?? "").capitalized
        let loro = (g.avversario ?? "").capitalized
        guard !mia.isEmpty, !loro.isEmpty else { return "Risultato atteso: \(Formato.decimali(a)) a \(Formato.decimali(b))" }
        return "Risultato atteso: \(mia) \(Formato.decimali(a)), \(loro) \(Formato.decimali(b))"
    }
}
