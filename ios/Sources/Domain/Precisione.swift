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
        private enum Chiavi: String, CodingKey { case giornate, meglioConsigliata, meglioTua, pari, punti, mediaConsigliata, mediaTua }
        init(giornate: Int? = nil, meglioConsigliata: Int? = nil, meglioTua: Int? = nil, pari: Int? = nil, punti: Double? = nil,
             mediaConsigliata: Double? = nil, mediaTua: Double? = nil) {
            self.giornate = giornate; self.meglioConsigliata = meglioConsigliata; self.meglioTua = meglioTua; self.pari = pari
            self.punti = punti; self.mediaConsigliata = mediaConsigliata; self.mediaTua = mediaTua
        }
        init(from decoder: Decoder) throws {
            let k = try decoder.container(keyedBy: Chiavi.self)   // non è un oggetto: la voce si scarta
            giornate = interoQP(k, .giornate); meglioConsigliata = interoQP(k, .meglioConsigliata); meglioTua = interoQP(k, .meglioTua)
            pari = interoQP(k, .pari); punti = numeroQP(k, .punti)
            mediaConsigliata = numeroQP(k, .mediaConsigliata); mediaTua = numeroQP(k, .mediaTua)
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
    }

    private enum Chiavi: String, CodingKey { case giornate, pochiDati, giornateMinime, fonti, fantavoto, gioca, confronto, squadra, perGiornata }

    init(giornate: Int? = nil, pochiDati: Bool? = nil, giornateMinime: Int? = nil, fonti: Fonti? = nil, fantavoto: Fantavoto? = nil,
         gioca: Gioca? = nil, confronto: Confronto? = nil, squadra: AffidabilitaDiario? = nil, perGiornata: [Giornata] = []) {
        self.giornate = giornate; self.pochiDati = pochiDati; self.giornateMinime = giornateMinime; self.fonti = fonti
        self.fantavoto = fantavoto; self.gioca = gioca; self.confronto = confronto; self.squadra = squadra; self.perGiornata = perGiornata
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
    }
}

/// I testi pronti di «Quanto ci abbiamo preso»: quattro numeri con una frase, l'andamento e le note.
/// `nil` se il campo manca o non ci sono giornate (la sezione non si mostra).
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
        var valore: String { Formato.punti(errore) }
        var voce: String { "Giornata \(etichetta): errore medio \(valore) punti" }
    }

    static let titolo = "Quanto ci abbiamo preso"
    static let intro = "Le giornate finite confrontate con quello che SchieraXI si aspettava. Lo mostriamo anche quando va male."
    static let titoloGrafico = "Errore medio del fantavoto atteso, giornata per giornata"
    static let legendaGrafico = "Di quanto ha sbagliato in media il fantavoto atteso in ogni giornata: più bassa è la barra, meglio è."
    static let andamento = "Giornata per giornata"
    static let tutteLeFasce = "Tutte le fasce"

    /// «Calcolato su N giornate, dalla giornata X alla Y.»
    let calcolatoSu: String
    /// L'avviso «ancora pochi dati» (nil se i dati bastano).
    let pochi: String?
    let fantavoto: Voce
    let gioca: Voce
    let confronto: Voce
    let squadra: Voce
    /// Le ultime 12 giornate con l'errore del fantavoto (il grafico si mostra solo con almeno 2).
    let barre: [Barra]
    /// Le righe dell'andamento, dalla più recente.
    let righe: [String]
    /// La nota sulle giornate con i numeri ricostruiti (nil se nessuna).
    let notaRicostruiti: String?

    // MARK: aiuti uguali alla web

    /// `v()` della web: una cifra decimale con la virgola, «–» se manca.
    private static func v(_ x: Double?) -> String { Formato.punti(x) }
    /// `suDieci()` della web: una percentuale in «volte su 10», arrotondata.
    static func suDieci(_ percento: Double?) -> Int { Formato.intero((percento ?? 0) / 10) }
    /// Il plurale della web (`Intl.PluralRules` italiano): «one» solo per 1 esatto.
    private static func uno(_ x: Double) -> Bool { x == 1 }

    init?(_ p: PrecisioneDiario?) {
        guard let p, let n = p.giornate, n > 0 else { return nil }
        let v = Self.v

        // Calcolato su N giornate (con la prima e l'ultima, se ci sono)
        let pg = p.perGiornata
        let primo = pg.first?.numero, ultimo = pg.last?.numero
        if n == 1 {
            calcolatoSu = primo.map { "Calcolato su 1 giornata (la \($0))." } ?? "Calcolato su 1 giornata."
        } else if let primo, let ultimo {
            calcolatoSu = "Calcolato su \(n) giornate, dalla giornata \(primo) alla \(ultimo)."
        } else {
            calcolatoSu = "Calcolato su \(n) giornate."
        }
        pochi = p.pochiDati == true
            ? "Ancora pochi dati: servono almeno \(p.giornateMinime ?? 8) giornate perché questi numeri siano affidabili. Per ora possono cambiare molto."
            : nil

        let vuoto = "Ancora niente da confrontare."

        // 1. Fantavoto atteso dei tuoi giocatori
        if let fv = p.fantavoto {
            var frase = "In media il fantavoto atteso dei tuoi giocatori sbaglia di \(v(fv.erroreMedio)) punti; \(Self.suDieci(fv.entroUnPunto)) voti su 10 sono entro un punto."
            if let voti = fv.voti { frase += voti == 1 ? " Su 1 voto." : " Su \(voti) voti." }
            if let sc = fv.scostamento, abs(sc) >= 0.3 {
                frase += sc > 0 ? " In media hanno fatto \(v(sc)) in più del previsto." : " In media hanno fatto \(v(-sc)) in meno del previsto."
            }
            fantavoto = Voce(numero: v(fv.erroreMedio), etichetta: "punti di errore medio del fantavoto atteso", frase: frase)
        } else {
            fantavoto = Voce(numero: "–", etichetta: "punti di errore medio del fantavoto atteso", frase: vuoto)
        }

        // 2. «Gioca N%»: la fascia principale e, sotto, tutte
        let etiGioca = "hanno giocato davvero, quando diciamo che giocano"
        if let gi = p.gioca, let gp = gi.fasciaPrincipale {
            let detto = gp.detto ?? 0, giocato = gp.giocato ?? 0
            let k = Self.suDieci(Double(giocato))
            let frase = gi.fonte == "ricostruiti"
                ? "Con i dati disponibili prima di ogni giornata (senza le probabili formazioni), chi davamo al \(detto)% ha giocato \(k) volte su 10."
                : "Quando diciamo «gioca \(detto)%», ha giocato \(k) volte su 10."
            let ottimisti = giocato < detto - 10
            let giudizio: String? = ottimisti ? "Qui siamo stati troppo ottimisti." : giocato > detto + 10 ? "Qui siamo stati troppo prudenti." : nil
            let fasce = gi.gruppi.map { g -> String in
                let da = g.da ?? 0, a = g.a ?? 0
                let casi = (g.giocatori ?? 0) == 1 ? "1 caso" : "\(g.giocatori ?? 0) casi"
                return "Gioca \(da)-\(a >= 100 ? 100 : a - 1)%: dicevamo \(g.detto ?? 0)%, hanno giocato nel \(g.giocato ?? 0)% dei casi"
                    + " (\(casi)\(g.pochi == true ? ", pochi per dirlo" : ""))"
            }
            gioca = Voce(numero: "\(k) su 10", etichetta: etiGioca, frase: frase, giudizio: giudizio, attenzione: ottimisti, fasce: fasce)
        } else {
            gioca = Voce(numero: "–", etichetta: etiGioca, frase: vuoto)
        }

        // 3. Consigliata contro la tua
        let etiCf = "giornate in cui la consigliata ha fatto meglio della tua"
        if let cf = p.confronto, let g = cf.giornate, g > 0 {
            var frase = "Giornate in cui la consigliata ha fatto meglio della tua: \(cf.meglioConsigliata ?? 0) su \(g). Meglio la tua: \(cf.meglioTua ?? 0). Pari: \(cf.pari ?? 0)."
            if let punti = cf.punti {
                if punti == 0 {
                    frase += " In tutto, gli stessi punti."
                } else if punti > 0 {
                    frase += " Seguendo sempre la consigliata avresti fatto \(v(punti)) \(Self.uno(punti) ? "punto" : "punti") in più."
                } else {
                    frase += " Con le tue scelte hai fatto \(v(-punti)) \(Self.uno(-punti) ? "punto" : "punti") in più della consigliata."
                }
            }
            confronto = Voce(numero: "\(cf.meglioConsigliata ?? 0) su \(g)", etichetta: etiCf, frase: frase)
        } else {
            confronto = Voce(numero: "–", etichetta: etiCf,
                             frase: "Non sappiamo ancora cosa hai schierato: dillo qui sotto in ogni giornata, con «Ho schierato…».")
        }

        // 4. Punti della squadra (consigliata): previsti contro fatti
        let etiSq = "punti di scarto medio sulla squadra"
        if let sq = p.squadra {
            var frase = "Punti della consigliata: \(v(sq.puntiMediAttesi)) previsti e \(v(sq.puntiMediFatti)) fatti, in media."
            if let k = sq.dentroFascia, let tot = sq.conFascia ?? sq.giornate {
                let d = Formato.intero((sq.fasciaDichiarata ?? 80) / 10)
                frase += " Giornate dentro la fascia prevista: \(k) su \(tot) (puntiamo a \(d) su 10)."
            }
            squadra = Voce(numero: v(sq.scartoMedio), etichetta: etiSq, frase: frase)
        } else {
            squadra = Voce(numero: "–", etichetta: etiSq, frase: vuoto)
        }

        // Grafico: le ultime 12 giornate con l'errore del fantavoto atteso
        let conErrore = pg.filter { $0.erroreFantavoto != nil }.suffix(12)
        var viste: [String: Int] = [:]
        var elenco: [Barra] = []
        for g in conErrore {
            guard let e = g.erroreFantavoto else { continue }
            var etichetta = g.numero.map { String($0) } ?? "–"
            let volte = (viste[etichetta] ?? 0) + 1
            viste[etichetta] = volte
            if volte > 1 { etichetta += " (\(g.stagione ?? String(volte)))" }   // la stessa giornata di due stagioni: etichette diverse
            elenco.append(Barra(id: elenco.count, etichetta: etichetta, errore: e))
        }
        barre = elenco

        // Andamento, dalla più recente
        righe = pg.reversed().map { (g: PrecisioneDiario.Giornata) -> String in
            var r = "Giornata \(g.numero.map { String($0) } ?? "–") · "
            if let e = g.erroreFantavoto { r += "fantavoto: errore \(v(e)) · " }
            r += "squadra: \(v(g.attesi)) previsti, \(v(g.fatti)) fatti"
            if let tua = g.tua {
                let d = g.differenza ?? 0
                r += " · tua: \(v(tua)) (\(d > 0 ? "+" : d < 0 ? "−" : "")\(v(abs(d))))"
            }
            return r
        }

        let ric = p.fonti?.ricostruiti ?? 0
        if ric > 0 {
            notaRicostruiti = ric == 1
                ? "In 1 giornata su \(n) i numeri dei giocatori sono ricostruiti con i dati che c'erano prima: quelli mostrati allora non erano stati salvati."
                : "In \(ric) giornate su \(n) i numeri dei giocatori sono ricostruiti con i dati che c'erano prima: quelli mostrati allora non erano stati salvati."
        } else {
            notaRicostruiti = nil
        }
    }

    /// Le quattro voci nell'ordine della web.
    var voci: [Voce] { [fantavoto, gioca, confronto, squadra] }
}
