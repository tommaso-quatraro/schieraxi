import Foundation

// «Quanto ci abbiamo preso» (campo `precisione` di `GET /api/diario`, server `fanta/precisione.py`).
// Tutto facoltativo e tollerante: un numero mancante, nullo o di tipo strano vale «manca» e non rompe il Diario.
// Le frasi sono quelle della web (chiavi `diario.qp_*` di `fanta/web/testi.js`), copiate uguali.

/// Legge un numero senza far fallire niente: un tipo sbagliato o un numero non finito valgono «manca».
private func numeroQP<K: CodingKey>(_ c: KeyedDecodingContainer<K>, _ chiave: K) -> Double? {
    guard let v = (try? c.decodeIfPresent(Double.self, forKey: chiave)) ?? nil, v.isFinite else { return nil }
    return v
}

private func interoQP<K: CodingKey>(_ c: KeyedDecodingContainer<K>, _ chiave: K) -> Int? {
    numeroQP(c, chiave).map { Formato.intero($0) }
}

private func testoQP<K: CodingKey>(_ c: KeyedDecodingContainer<K>, _ chiave: K) -> String? {
    (try? c.decodeIfPresent(String.self, forKey: chiave)) ?? nil
}

private func boolQP<K: CodingKey>(_ c: KeyedDecodingContainer<K>, _ chiave: K) -> Bool? {
    (try? c.decodeIfPresent(Bool.self, forKey: chiave)) ?? nil
}

/// Un elenco che salta le voci illeggibili (con `Tollerante` di `Modelli.swift`) invece di far fallire tutto.
private func elencoQP<T: Decodable, K: CodingKey>(_ c: KeyedDecodingContainer<K>, _ chiave: K) -> [T] {
    ((try? c.decodeIfPresent([Tollerante<T>].self, forKey: chiave)) ?? nil)?.compactMap(\.valore) ?? []
}

struct PrecisioneDiario: Decodable, Equatable {
    var giornate: Int?
    var pochiDati: Bool?
    var giornateMinime: Int?
    var fonti: Fonti?
    var fantavoto: Fantavoto?
    var gioca: Gioca?
    var confronto: Confronto?
    /// Gli stessi numeri di `affidabilita` (punti della consigliata previsti contro fatti).
    var squadra: AffidabilitaDiario?
    var perGiornata: [Giornata] = []
    /// La riga su tutta la Serie A (registro delle giornate, #374). Facoltativa: server vecchio o registro vuoto = niente riga.
    var serieA: SerieA?

    /// Su tutta la Serie A (`serie_a`): il testo lo scrive il server (`fanta/precisione.py`, `serie_a`), uguale a quello della web.
    struct SerieA: Decodable, Equatable {
        /// Giornate misurate del registro (al massimo le ultime 8).
        var giornate: Int?
        var giornateMinime: Int?
        /// Giornate che mancano ai numeri: 0 = la riga ha i numeri, altrimenti dice «servono ancora N giornate».
        var mancano: Int?
        var testo: String?
        private enum Chiavi: String, CodingKey { case giornate, giornateMinime, mancano, testo }
        init(giornate: Int? = nil, giornateMinime: Int? = nil, mancano: Int? = nil, testo: String? = nil) {
            self.giornate = giornate; self.giornateMinime = giornateMinime; self.mancano = mancano; self.testo = testo
        }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: niente riga
            giornate = interoQP(k, .giornate); giornateMinime = interoQP(k, .giornateMinime)
            mancano = interoQP(k, .mancano); testo = testoQP(k, .testo)
        }
    }

    struct Fonti: Decodable, Equatable {
        var mostrati: Int?
        var ricostruiti: Int?
        private enum Chiavi: String, CodingKey { case mostrati, ricostruiti }
        init(mostrati: Int? = nil, ricostruiti: Int? = nil) { self.mostrati = mostrati; self.ricostruiti = ricostruiti }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: la voce si scarta
            mostrati = interoQP(k, .mostrati); ricostruiti = interoQP(k, .ricostruiti)
        }
    }

    struct Fantavoto: Decodable, Equatable {
        var erroreMedio: Double?
        var scostamento: Double?
        /// Percentuale (0-100) dei voti entro un punto dal fantavoto atteso.
        var entroUnPunto: Double?
        var voti: Int?
        private enum Chiavi: String, CodingKey { case erroreMedio, scostamento, entroUnPunto, voti }
        init(erroreMedio: Double? = nil, scostamento: Double? = nil, entroUnPunto: Double? = nil, voti: Int? = nil) {
            self.erroreMedio = erroreMedio; self.scostamento = scostamento; self.entroUnPunto = entroUnPunto; self.voti = voti
        }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: la voce si scarta
            erroreMedio = numeroQP(k, .erroreMedio); scostamento = numeroQP(k, .scostamento)
            entroUnPunto = numeroQP(k, .entroUnPunto); voti = interoQP(k, .voti)
        }
    }

    struct Fascia: Decodable, Equatable {
        var da: Int?
        var a: Int?
        var giocatori: Int?
        var pochi: Bool?
        /// Probabilità detta in media, in percento intero.
        var detto: Int?
        /// Quota che ha preso voto davvero, in percento intero.
        var giocato: Int?
        private enum Chiavi: String, CodingKey { case da, a, giocatori, pochi, detto, giocato }
        init(da: Int? = nil, a: Int? = nil, giocatori: Int? = nil, pochi: Bool? = nil, detto: Int? = nil, giocato: Int? = nil) {
            self.da = da; self.a = a; self.giocatori = giocatori; self.pochi = pochi; self.detto = detto; self.giocato = giocato
        }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: la voce si scarta
            da = interoQP(k, .da); a = interoQP(k, .a); giocatori = interoQP(k, .giocatori)
            pochi = boolQP(k, .pochi); detto = interoQP(k, .detto); giocato = interoQP(k, .giocato)
        }
    }

    struct Gioca: Decodable, Equatable {
        var giocatori: Int?
        var gruppi: [Fascia] = []
        /// Indice in `gruppi` della fascia da mettere in evidenza.
        var principale: Int?
        /// «mostrati» (numeri visti davvero, probabili comprese) o «ricostruiti» (senza le probabili).
        var fonte: String?
        var giornate: Int?
        private enum Chiavi: String, CodingKey { case giocatori, gruppi, principale, fonte, giornate }
        init(giocatori: Int? = nil, gruppi: [Fascia] = [], principale: Int? = nil, fonte: String? = nil, giornate: Int? = nil) {
            self.giocatori = giocatori; self.gruppi = gruppi; self.principale = principale; self.fonte = fonte; self.giornate = giornate
        }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: la voce si scarta
            giocatori = interoQP(k, .giocatori); gruppi = elencoQP(k, .gruppi); principale = interoQP(k, .principale)
            fonte = testoQP(k, .fonte); giornate = interoQP(k, .giornate)
        }

        /// La fascia principale, se l'indice è valido.
        var fasciaPrincipale: Fascia? {
            guard let i = principale, gruppi.indices.contains(i) else { return nil }
            return gruppi[i]
        }
    }

    struct Confronto: Decodable, Equatable {
        var giornate: Int?
        var meglioConsigliata: Int?
        var meglioTua: Int?
        var pari: Int?
        /// Somma di (consigliata − tua): positivo = seguendo sempre la consigliata avresti fatto più punti.
        var punti: Double?
        var mediaConsigliata: Double?
        var mediaTua: Double?
        /// La frase del server sulle giornate senza verdetto (#614), la stessa di «Le tue scelte»: dopo i numeri, o al loro posto
        /// se non ci sono giornate da confrontare. Null o assente (server di prima) = niente da dire.
        var nota: String?
        private enum Chiavi: String, CodingKey { case giornate, meglioConsigliata, meglioTua, pari, punti, mediaConsigliata, mediaTua, nota }
        init(giornate: Int? = nil, meglioConsigliata: Int? = nil, meglioTua: Int? = nil, pari: Int? = nil, punti: Double? = nil,
             mediaConsigliata: Double? = nil, mediaTua: Double? = nil, nota: String? = nil) {
            self.giornate = giornate; self.meglioConsigliata = meglioConsigliata; self.meglioTua = meglioTua; self.pari = pari
            self.punti = punti; self.mediaConsigliata = mediaConsigliata; self.mediaTua = mediaTua; self.nota = nota
        }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: la voce si scarta
            giornate = interoQP(k, .giornate); meglioConsigliata = interoQP(k, .meglioConsigliata); meglioTua = interoQP(k, .meglioTua)
            pari = interoQP(k, .pari); punti = numeroQP(k, .punti)
            mediaConsigliata = numeroQP(k, .mediaConsigliata); mediaTua = numeroQP(k, .mediaTua); nota = testoQP(k, .nota)
        }
    }

    struct Giornata: Decodable, Equatable {
        var stagione: String?
        var giornata: Int?
        var giornataLega: Int?
        var fonte: String?
        var erroreFantavoto: Double?
        var voti: Int?
        var attesi: Double?
        var fatti: Double?
        var tua: Double?
        var differenza: Double?
        private enum Chiavi: String, CodingKey { case stagione, giornata, giornataLega, fonte, erroreFantavoto, voti, attesi, fatti, tua, differenza }
        init(stagione: String? = nil, giornata: Int? = nil, giornataLega: Int? = nil, fonte: String? = nil, erroreFantavoto: Double? = nil,
             voti: Int? = nil, attesi: Double? = nil, fatti: Double? = nil, tua: Double? = nil, differenza: Double? = nil) {
            self.stagione = stagione; self.giornata = giornata; self.giornataLega = giornataLega; self.fonte = fonte
            self.erroreFantavoto = erroreFantavoto; self.voti = voti; self.attesi = attesi; self.fatti = fatti; self.tua = tua; self.differenza = differenza
        }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: la voce si scarta
            stagione = testoQP(k, .stagione); giornata = interoQP(k, .giornata); giornataLega = interoQP(k, .giornataLega)
            fonte = testoQP(k, .fonte); erroreFantavoto = numeroQP(k, .erroreFantavoto); voti = interoQP(k, .voti)
            attesi = numeroQP(k, .attesi); fatti = numeroQP(k, .fatti); tua = numeroQP(k, .tua); differenza = numeroQP(k, .differenza)
        }

        /// Il numero da mostrare: quello della lega se c'è (come la web).
        var numero: Int? { giornataLega ?? giornata }

        /// La giornata con i due numeri (#299); nil senza il numero di Serie A.
        var nomeGiornata: NomeGiornata? { giornata.map { NomeGiornata(serieA: $0, lega: giornataLega) } }
    }

    private enum Chiavi: String, CodingKey {
        case giornate, pochiDati, giornateMinime, fonti, fantavoto, gioca, confronto, squadra, perGiornata, serieA
    }

    init(giornate: Int? = nil, pochiDati: Bool? = nil, giornateMinime: Int? = nil, fonti: Fonti? = nil, fantavoto: Fantavoto? = nil,
         gioca: Gioca? = nil, confronto: Confronto? = nil, squadra: AffidabilitaDiario? = nil, perGiornata: [Giornata] = [],
         serieA: SerieA? = nil) {
        self.giornate = giornate; self.pochiDati = pochiDati; self.giornateMinime = giornateMinime; self.fonti = fonti
        self.fantavoto = fantavoto; self.gioca = gioca; self.confronto = confronto; self.squadra = squadra; self.perGiornata = perGiornata
        self.serieA = serieA
    }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        giornate = interoQP(k, .giornate)
        pochiDati = boolQP(k, .pochiDati)
        giornateMinime = interoQP(k, .giornateMinime)
        fonti = (try? k.decodeIfPresent(Fonti.self, forKey: .fonti)) ?? nil
        fantavoto = (try? k.decodeIfPresent(Fantavoto.self, forKey: .fantavoto)) ?? nil
        gioca = (try? k.decodeIfPresent(Gioca.self, forKey: .gioca)) ?? nil
        confronto = (try? k.decodeIfPresent(Confronto.self, forKey: .confronto)) ?? nil
        squadra = (try? k.decodeIfPresent(AffidabilitaDiario.self, forKey: .squadra)) ?? nil
        perGiornata = elencoQP(k, .perGiornata)
        serieA = (try? k.decodeIfPresent(SerieA.self, forKey: .serieA)) ?? nil
    }
}

//// I testi pronti di «Quanto ci abbiamo preso» (i «Dettagli» della pagina Giornate, come `dettagliPrecisione` della web): i numeri con
/// una frase, l'andamento e le note. Le frasi vengono dal catalogo comune (`diario.qp_*`). `nil` se il campo manca o non ci sono
/// giornate (la parte non si mostra).
struct TestoPrecisione: Equatable {
    struct Voce: Equatable {
        /// Il numero grande («1,3», «8 su 10», «–» se manca).
        let numero: String
        let etichetta: String
        let frase: String
        /// Un giudizio a parte (solo «gioca»): «Qui siamo stati troppo ottimisti.»
        var giudizio: String? = nil
        /// true = il numero va evidenziato come attenzione (abbiamo sbagliato in eccesso).
        var attenzione = false
        /// Le righe delle fasce di «gioca N%» (solo «gioca»).
        var fasce: [String] = []

        /// La frase intera per VoiceOver.
        var voce: String {
            let n: String = numero == "–" ? "non ancora disponibile" : numero
            let inizio: String = etichetta.prefix(1).uppercased() + String(etichetta.dropFirst())
            var parti: [String] = ["\(inizio): \(n).", frase]
            if let giudizio { parti.append(giudizio) }
            return parti.joined(separator: " ")
        }
    }

    /// Una barra del grafico: errore medio del fantavoto atteso in una giornata.
    struct Barra: Equatable, Identifiable {
        let id: Int
        let etichetta: String
        let errore: Double
        /// La giornata con i due numeri, per VoiceOver (#299). Nil se il server non manda il numero di Serie A.
        var nome: NomeGiornata? = nil
        var valore: String { Formato.punti(errore) }
        /// «Giornata 8, 11ª di Serie A»: la giornata della barra come la legge VoiceOver.
        var voceGiornata: String { nome?.voce ?? "Giornata \(etichetta)" }
        var voce: String { "\(voceGiornata): errore medio \(valore) punti" }
    }

    static let titolo = Catalogo.Diario.afTitolo
    static let intro = Catalogo.Diario.qpIntro
    static let titoloGrafico = Catalogo.Diario.qpGraficoAria
    static let legendaGrafico = Catalogo.Diario.qpGraficoLeg
    static let andamento = Catalogo.Diario.qpAndamento
    static let tutteLeFasce = Catalogo.Diario.qpGiocaTutte

    /// «Calcolato su N giornate, dalla giornata X alla Y.»
    let calcolatoSu: String
    /// L'avviso «ancora pochi dati» (nil se i dati bastano).
    let pochi: String?
    let fantavoto: Voce
    let gioca: Voce
    /// «La consigliata contro la tua»: solo se una giornata ha la consigliata mostrata prima della scadenza (`conConfronto`) e il
    /// server conta almeno una giornata con un verdetto, come la web. Nil altrimenti.
    let confronto: Voce?
    let squadra: Voce
    /// Le ultime 12 giornate con l'errore del fantavoto (il grafico si mostra solo con almeno 2).
    let barre: [Barra]
    /// Le righe dell'andamento, dalla più recente: l'errore e i punti della consigliata (quanto ha fatto la tua lo dice la riga di
    /// ogni giornata).
    let righe: [String]
    /// La nota sulle giornate con i numeri ricostruiti (nil se nessuna).
    let notaRicostruiti: String?
    /// La riga su tutta la Serie A, sotto i numeri: la frase del server così com'è (nil = niente riga).
    let serieA: String?
    /// La frase del server sulle giornate con la tua formazione che non hanno un verdetto (`confronto.nota`, #614), in fondo e
    /// così com'è, come la web; nil se non c'è.
    let nota: String?

    // MARK: aiuti uguali alla web

    /// `v()` della web: una cifra decimale con la virgola, «–» se manca.
    private static func v(_ x: Double?) -> String { Formato.punti(x) }
    /// `suDieci()` della web: una percentuale in «volte su 10», arrotondata.
    static func suDieci(_ percento: Double?) -> Int { Formato.intero((percento ?? 0) / 10) }

    /// «al 75%», ma «all'84%», «all'8%», «all'11%» e «all'1%»: davanti a una vocale l'articolo si apostrofa.
    static func alPercento(_ n: Int) -> String {
        let testo = String(n)
        let vocale = testo.hasPrefix("8") || n == 1 || n == 11 || (testo.hasPrefix("11") && testo.count == 4)
        return (vocale ? "all'" : "al ") + testo + "%"
    }
    /// La giornata dentro «Calcolato su…»: «Giornata 8 · 11ª di Serie A»; con un server senza numero di Serie A «giornata 8».
    private static func nomeInFrase(_ g: PrecisioneDiario.Giornata) -> String? {
        g.nomeGiornata?.intero ?? g.numero.map { "giornata \($0)" }
    }

    /// Il plurale della web (`Intl.PluralRules` italiano): «one» solo per 1 esatto.
    private static func plurale(_ x: Double) -> Int { x == 1 ? 1 : 2 }

    /// `conConfronto`: c'è almeno una giornata con la consigliata mostrata prima della scadenza (la pagina Giornate lo chiede alle
    /// sue voci, `VoceDiario.conMostrata`). Senza, la voce del confronto non c'è: con il server di prima il confronto era con una
    /// formazione rifatta dopo.
    init?(_ p: PrecisioneDiario?, conConfronto: Bool = true) {
        guard let p, let n = p.giornate, n > 0 else { return nil }
        let v = Self.v

        // Calcolato su N giornate (con la prima e l'ultima, se ci sono), con i due numeri come la web (#299):
        // «dalla Giornata 4 · 7ª di Serie A alla Giornata 8 · 11ª di Serie A». Senza il numero di Serie A, quello che c'è.
        let pg = p.perGiornata
        let primo = pg.first.flatMap(Self.nomeInFrase), ultimo = pg.last.flatMap(Self.nomeInFrase)
        if let primo, let ultimo {
            // «(l'11ª giornata di Serie A)», «dall'8ª … all'11ª …»: l'apostrofo come la web (`elidiOrdinali`)
            calcolatoSu = TempiLega.elidiOrdinali(Catalogo.Diario.qpSu(n, a: ultimo, da: primo))
        } else {
            calcolatoSu = n == 1 ? "Calcolato su 1 giornata." : "Calcolato su \(n) giornate."
        }
        pochi = p.pochiDati == true ? Catalogo.Diario.qpPochi(n: String(p.giornateMinime ?? 8)) : nil

        let vuoto = Catalogo.Diario.qpFvVuoto

        // 1. Fantavoto atteso dei tuoi giocatori
        if let fv = p.fantavoto {
            var frase = Catalogo.Diario.qpFv(e: v(fv.erroreMedio), k: String(Self.suDieci(fv.entroUnPunto)))
            if let voti = fv.voti { frase += " " + Catalogo.Diario.qpFvVoti(voti) }
            if let sc = fv.scostamento, abs(sc) >= 0.3 {
                frase += " " + (sc > 0 ? Catalogo.Diario.qpFvPiu(e: v(sc)) : Catalogo.Diario.qpFvMeno(e: v(-sc)))
            }
            fantavoto = Voce(numero: v(fv.erroreMedio), etichetta: Catalogo.Diario.qpFvEti, frase: frase)
        } else {
            fantavoto = Voce(numero: "–", etichetta: Catalogo.Diario.qpFvEti, frase: vuoto)
        }

        // 2. «Gioca N%»: la fascia principale e, sotto, tutte
        if let gi = p.gioca, let gp = gi.fasciaPrincipale {
            let detto = gp.detto ?? 0, giocato = gp.giocato ?? 0
            let k = String(Self.suDieci(Double(giocato)))
            let frase = gi.fonte == "ricostruiti"
                ? Catalogo.Diario.qpGiocaRic(al: Self.alPercento(detto), k: k)
                : Catalogo.Diario.qpGioca(k: k, p: String(detto))
            let ottimisti = giocato < detto - 10
            let giudizio: String? = ottimisti ? Catalogo.Diario.qpGiocaOttimisti
                : giocato > detto + 10 ? Catalogo.Diario.qpGiocaPrudenti : nil
            let fasce = gi.gruppi.map { g -> String in
                let da = g.da ?? 0, a = g.a ?? 0
                let riga = Catalogo.Diario.qpGiocaFascia(a: String(a >= 100 ? 100 : a - 1), d: String(g.detto ?? 0), da: String(da),
                                                         g: String(g.giocato ?? 0))
                let casi = Catalogo.Diario.qpGiocatori(g.giocatori ?? 0)
                return riga + " (" + casi + (g.pochi == true ? ", " + Catalogo.Diario.qpPochiCasi : "") + ")"
            }
            gioca = Voce(numero: Catalogo.Diario.qpSuDieci(k: k), etichetta: Catalogo.Diario.qpGiocaEti, frase: frase,
                         giudizio: giudizio, attenzione: ottimisti, fasce: fasce)
        } else {
            gioca = Voce(numero: "–", etichetta: Catalogo.Diario.qpGiocaEti, frase: vuoto)
        }

        // 3. Consigliata contro la tua: solo con la consigliata mostrata in almeno una giornata e un verdetto, come la web
        if conConfronto, let cf = p.confronto, let g = cf.giornate, g > 0 {
            let k = String(cf.meglioConsigliata ?? 0), tot = String(g)
            var frase = Catalogo.Diario.qpCf(k: k, n: tot, pari: String(cf.pari ?? 0), tua: String(cf.meglioTua ?? 0))
            if let punti = cf.punti {
                if punti == 0 {
                    frase += " " + Catalogo.Diario.qpCfPari
                } else if punti > 0 {
                    frase += " " + Catalogo.Diario.qpCfPiu(Self.plurale(punti), e: v(punti))
                } else {
                    frase += " " + Catalogo.Diario.qpCfMeno(Self.plurale(-punti), e: v(-punti))
                }
            }
            confronto = Voce(numero: Catalogo.Diario.qpKSuN(k: k, n: tot), etichetta: Catalogo.Diario.qpCfEti, frase: frase)
        } else {
            confronto = nil
        }
        let notaCf = p.confronto?.nota?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        nota = notaCf.isEmpty ? nil : notaCf

        // 4. Punti della squadra (consigliata): previsti contro fatti
        if let sq = p.squadra {
            let frase = Catalogo.Diario.qpSq(a: v(sq.puntiMediAttesi), d: String(Formato.intero((sq.fasciaDichiarata ?? 80) / 10)),
                                             f: v(sq.puntiMediFatti), k: sq.dentroFascia.map { String($0) } ?? "–",
                                             n: (sq.conFascia ?? sq.giornate).map { String($0) } ?? "–")
            squadra = Voce(numero: v(sq.scartoMedio), etichetta: Catalogo.Diario.qpSqEti, frase: frase)
        } else {
            squadra = Voce(numero: "–", etichetta: Catalogo.Diario.qpSqEti, frase: vuoto)
        }

        // Grafico: le ultime 12 giornate con l'errore del fantavoto atteso
        let conErrore = pg.filter { $0.erroreFantavoto != nil }.suffix(12)
        var viste: [String: Int] = [:]
        var elenco: [Barra] = []
        for g in conErrore {
            guard let e = g.erroreFantavoto else { continue }
            // sotto la barra il numero della lega; senza (stagione passata) «G11», come `sottoBarra` della web
            var etichetta = g.giornataLega.map { String($0) } ?? g.giornata.map { "G\($0)" } ?? "–"
            let volte = (viste[etichetta] ?? 0) + 1
            viste[etichetta] = volte
            if volte > 1 { etichetta += " (\(g.stagione ?? String(volte)))" }   // la stessa giornata di due stagioni: etichette diverse
            elenco.append(Barra(id: elenco.count, etichetta: etichetta, errore: e, nome: g.nomeGiornata))
        }
        barre = elenco

        // Andamento, dalla più recente: l'errore e i punti della consigliata, come la web
        righe = pg.reversed().map { (g: PrecisioneDiario.Giornata) -> String in
            var r = (g.nomeGiornata?.intero ?? "Giornata \(g.numero.map { String($0) } ?? "–")") + " · "
            if let e = g.erroreFantavoto { r += Catalogo.Diario.qpRigaFv(e: v(e)) + " · " }
            return r + Catalogo.Diario.qpRigaSq(a: v(g.attesi), f: v(g.fatti))
        }

        // Su tutta la Serie A (#374): il testo del server, lo stesso che la web mostra in italiano
        let riga = p.serieA?.testo?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        serieA = riga.isEmpty ? nil : riga

        let ric = p.fonti?.ricostruiti ?? 0
        notaRicostruiti = ric > 0 ? Catalogo.Diario.qpRicostruiti(ric, t: String(n)) : nil
    }

    /// Le voci nell'ordine della web (quella del confronto solo se c'è).
    var voci: [Voce] { [fantavoto, gioca] + (confronto.map { [$0] } ?? []) + [squadra] }
}
