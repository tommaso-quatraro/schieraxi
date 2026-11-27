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
        let quando = Quando.leggibileSeData(g.dataPartita, adesso: adesso) ?? senzaValore
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
        /// A partita in corso: lo stato della partita al posto di «gioca N%»; accanto al voto d'ufficio «Voto d'ufficio».
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
        if let esito {
            // accanto al voto d'ufficio la sua parola («Voto d'ufficio», #895), come `esito.parola || esito.testo` della web
            accanto = finita ? nil : .stato(esito.parola ?? testoEsito)
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

    /// «Perché questo numero» dentro la scheda: niente a partita finita, e mai il motivo «gioca» (#923, come `htmlScheda` della
    /// web): prima della partita «gioca N%» sta accanto al numero con la parola dello stato, e la riga «gioca il 62%: dubbio» lo
    /// diceva una seconda volta; a partita cominciata non serve più. nil con un server che non manda i motivi.
    /// Un infortunato o uno squalificato ha dal server il solo motivo «gioca» («infortunato: non gioca», fanta/perche.py): tolto
    /// quello, il riquadro direbbe «Nessun motivo spicca…», falso. Allora niente riquadro: lo stato si legge accanto al numero
    /// (revisione della #945, come `htmlScheda`).
    static func perche(_ g: Giocatore) -> PercheNumero? {
        guard !statiFinita.contains(g.statoPartita ?? ""), g.assente != true else { return nil }
        let motivi = g.motiviNumero?.filter { $0.chiave != "gioca" }
        let nonGiocano: Set<String> = ["infortunato", "squalificato"]
        let stati: [String] = [g.stato, ParolaStato(g)?.codice].compactMap { $0 }
        let nonGioca = stati.contains { nonGiocano.contains($0) }
        if nonGioca, motivi?.isEmpty == true { return nil }
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

    /// «Dati fino al 9/11.»: fin dove arrivano i numeri della fonte delle statistiche avanzate (`avanzate.dati_fino_al`, #862), per
    /// «Gol e assist rispetto alle occasioni» e «Statistiche avanzate»; si scrive una volta sola, in fondo al secondo blocco (#911),
    /// come `finoAl` di `riempiScheda` della web (il giorno scritto come `giornoMese`). nil se il server non manda il giorno o non è
    /// una data.
    static func datiFinoAl(_ avanzate: StatisticheAvanzate?) -> String? {
        ParoleRegistro.giornoMese(avanzate?.datiFinoAl).map { Catalogo.Mercato.datiFinoAl(data: $0) }
    }

    /// «Gol e assist rispetto alle occasioni»: sta segnando più di quanto crea (cala), il contrario (si sblocca) o è in linea.
    enum Tendenza: String {
        case cala, sblocca
        case inLinea = "in_linea"
    }

    /// La tendenza del rendimento come la decide il server (`rendimento.tendenza`, 27/11/2026); un server di prima non la manda (o un
    /// codice che non conosciamo): allora la soglia di prima, 0,3 punti a partita sul numero mostrato, come `riempiScheda` della web.
    /// nil senza numero né codice.
    static func tendenza(_ r: Rendimento) -> Tendenza? {
        if let codice = r.tendenza, let t = Tendenza(rawValue: codice) { return t }
        guard let sovra = r.sovraRendimento, sovra.isFinite else { return nil }
        return sovra > 0.3 ? .cala : sovra < -0.3 ? .sblocca : .inLinea
    }

    /// La frase che spiega la tendenza: quella del server (`rendimento.testo`) o, da un server di prima, quella del catalogo.
    static func fraseRendimento(_ r: Rendimento) -> String? {
        if let testo = r.testo, !testo.isEmpty { return testo }
        switch tendenza(r) {
        case .cala: return Catalogo.Mercato.rendCala
        case .sblocca: return Catalogo.Mercato.rendSblocca
        case .inLinea: return Catalogo.Mercato.rendLinea
        case nil: return nil
        }
    }

    /// La tessera «gol (N rig.)»: gol e rigori segnati già sommati dal server (`stagione.gol_con_rigori`); da un server di prima la
    /// somma, come prima.
    static func golConRigori(_ st: StagioneGiocatore) -> Double {
        st.golConRigori ?? (st.gol ?? 0) + (st.rigSegnati ?? 0)
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
