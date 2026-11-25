import Foundation

// Importazione delle rose in due passi (piano «Ingresso facile» del server; contratto in `docs/API.md`, «Anteprima delle rose»):
// 1) `POST /api/rose/anteprima` (o `/anteprima/file`) legge il testo o il file SENZA salvare e dice, giocatore per giocatore,
//    chi è riconosciuto, chi è da controllare (con le alternative) e chi non è stato trovato;
// 2) l'utente sceglie i dubbi e la sua squadra; «Conferma e salva» manda lo stesso contenuto a `/api/rose/testo` (o `/file`)
//    con `correzioni`, `mia_squadra` e If-Match = l'ETag dell'anteprima.
// Qui solo modelli tolleranti e logica pura (provata in `AnteprimaRoseTests`); la schermata è `ImportaRoseView`.

/// Come il server ha capito un giocatore.
enum StatoAnteprima: String, Equatable {
    case sicuro
    case daControllare = "da_controllare"
    case nonTrovato = "non_trovato"

    /// Uno stato che l'app non conosce (server più nuovo) si mostra da controllare: meglio un dubbio in più che uno in meno.
    init(server: String?) {
        self = StatoAnteprima(rawValue: server ?? "") ?? .daControllare
    }
}

/// Un elenco che salta gli elementi illeggibili invece di far fallire tutta la risposta.
private struct Scarta: Decodable {
    init(from decoder: Decoder) throws {}
}

private extension KeyedDecodingContainer {
    func elenco<T: Decodable>(_ tipo: T.Type, _ chiave: Key) -> [T] {
        guard var c = try? nestedUnkeyedContainer(forKey: chiave) else { return [] }
        var fuori: [T] = []
        while !c.isAtEnd {
            if let v = try? c.decode(T.self) { fuori.append(v) } else if (try? c.decode(Scarta.self)) == nil { break }
        }
        return fuori
    }

    func valore<T: Decodable>(_ tipo: T.Type, _ chiave: Key) -> T? {
        (try? decodeIfPresent(T.self, forKey: chiave)) ?? nil
    }

    /// Un numero che può arrivare intero o con la virgola.
    func numero(_ chiave: Key) -> Double? {
        if let d = valore(Double.self, chiave) { return d }
        return valore(Int.self, chiave).map(Double.init)
    }
}

/// Un giocatore del listone proposto per un dubbio (o trovato con la ricerca).
struct CandidatoAnteprima: Decodable, Hashable, Identifiable {
    let id: Int
    let nome: String
    let ruolo: String?
    let squadra: String?

    init(id: Int, nome: String, ruolo: String?, squadra: String?) {
        self.id = id; self.nome = nome; self.ruolo = ruolo; self.squadra = squadra
    }

    init(_ g: GiocatoreBreve) {
        self.init(id: g.id, nome: g.nome, ruolo: g.ruolo, squadra: g.squadra)
    }
}

/// Un giocatore così come l'ha letto l'anteprima.
struct GiocatoreAnteprima: Decodable, Equatable {
    /// Il nome come scritto nel file: con la `riga` (o da solo, con un server di prima) è la chiave delle `correzioni`.
    var testo: String
    /// La posizione del giocatore nella sua squadra come l'ha letta il server (da 0): due omonimi possono avere lo stesso
    /// `testo`, la riga li distingue (#662, #716). Nil con un server di prima.
    var riga: Int?
    var stato: StatoAnteprima
    var metodo: String?
    /// Il giocatore proposto (nil se nessuno).
    var id: Int?
    var nome: String?
    var ruolo: String?
    var squadra: String?
    var costo: Double?
    var avviso: String?
    var alternative: [CandidatoAnteprima]

    init(testo: String, riga: Int? = nil, stato: StatoAnteprima, metodo: String? = nil, id: Int? = nil, nome: String? = nil,
         ruolo: String? = nil, squadra: String? = nil, costo: Double? = nil, avviso: String? = nil, alternative: [CandidatoAnteprima] = []) {
        self.testo = testo; self.riga = riga; self.stato = stato; self.metodo = metodo; self.id = id; self.nome = nome
        self.ruolo = ruolo; self.squadra = squadra; self.costo = costo; self.avviso = avviso; self.alternative = alternative
    }

    /// Chi è nella sua squadra: la riga o, con un server di prima, il nome come scritto. Diverso per ogni dubbio di una squadra
    /// (`AnteprimaLogica.dubbi`): è l'identità nell'elenco e, con il nome della squadra, la chiave delle scelte.
    var chiaveInSquadra: String { riga.map { "\u{1}\($0)" } ?? testo }

    private enum Chiavi: String, CodingKey { case testo, riga, stato, metodo, id, nome, ruolo, squadra, costo, avviso, alternative }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        let nome = k.valore(String.self, .nome)
        // senza `testo` non si può correggere: si ripiega sul nome (il server lo manda sempre)
        testo = k.valore(String.self, .testo) ?? nome ?? ""
        riga = k.valore(Int.self, .riga)
        stato = StatoAnteprima(server: k.valore(String.self, .stato))
        metodo = k.valore(String.self, .metodo)
        id = k.valore(Int.self, .id)
        self.nome = nome
        ruolo = k.valore(String.self, .ruolo)
        squadra = k.valore(String.self, .squadra)
        costo = k.numero(.costo)
        avviso = k.valore(String.self, .avviso)
        alternative = k.elenco(CandidatoAnteprima.self, .alternative)
    }
}

/// Una squadra letta dall'anteprima, con i conteggi.
struct SquadraAnteprima: Decodable, Identifiable, Equatable {
    var nome: String
    var nuova: Bool
    var creditiResidui: Double?
    var sicuri: Int
    var daControllare: Int
    var nonTrovati: Int
    var totale: Int
    var attesi: Int?
    var mancano: [String: Int]
    var inPiu: [String: Int]
    var senzaRuolo: Int
    var avvisi: [String]
    var giocatori: [GiocatoreAnteprima]
    var id: String { nome }

    init(nome: String, nuova: Bool = false, creditiResidui: Double? = nil, totale: Int? = nil, attesi: Int? = nil,
         mancano: [String: Int] = [:], inPiu: [String: Int] = [:], senzaRuolo: Int = 0, avvisi: [String] = [],
         giocatori: [GiocatoreAnteprima]) {
        self.nome = nome; self.nuova = nuova; self.creditiResidui = creditiResidui
        sicuri = giocatori.filter { $0.stato == .sicuro }.count
        daControllare = giocatori.filter { $0.stato == .daControllare }.count
        nonTrovati = giocatori.filter { $0.stato == .nonTrovato }.count
        self.totale = totale ?? giocatori.count; self.attesi = attesi; self.mancano = mancano; self.inPiu = inPiu
        self.senzaRuolo = senzaRuolo; self.avvisi = avvisi; self.giocatori = giocatori
    }

    private enum Chiavi: String, CodingKey {
        case nome, nuova, creditiResidui, sicuri, daControllare, nonTrovati, totale, attesi, mancano, inPiu, senzaRuolo, avvisi, giocatori
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        nome = k.valore(String.self, .nome) ?? ""
        nuova = k.valore(Bool.self, .nuova) ?? false
        creditiResidui = k.numero(.creditiResidui)
        giocatori = k.elenco(GiocatoreAnteprima.self, .giocatori)
        sicuri = k.valore(Int.self, .sicuri) ?? giocatori.filter { $0.stato == .sicuro }.count
        daControllare = k.valore(Int.self, .daControllare) ?? giocatori.filter { $0.stato == .daControllare }.count
        nonTrovati = k.valore(Int.self, .nonTrovati) ?? giocatori.filter { $0.stato == .nonTrovato }.count
        totale = k.valore(Int.self, .totale) ?? giocatori.count
        attesi = k.valore(Int.self, .attesi)
        mancano = k.valore([String: Int].self, .mancano) ?? [:]
        inPiu = k.valore([String: Int].self, .inPiu) ?? [:]
        senzaRuolo = k.valore(Int.self, .senzaRuolo) ?? 0
        avvisi = k.valore([String].self, .avvisi) ?? []
    }
}

/// La risposta dell'anteprima.
struct AnteprimaRose: Decodable {
    var squadre: [SquadraAnteprima]
    var avvisi: [String]
    /// La squadra dell'utente suggerita dal server (quella già scelta, o l'unica letta).
    var miaSquadra: String?
    var totaleSquadre: Int?
    var sicuri: Int
    var daControllare: Int
    var nonTrovati: Int
    var differenze: Differenze?
    var riepilogo: String?

    init(squadre: [SquadraAnteprima], avvisi: [String] = [], miaSquadra: String? = nil, totaleSquadre: Int? = nil,
         differenze: Differenze? = nil, riepilogo: String? = nil) {
        self.squadre = squadre; self.avvisi = avvisi; self.miaSquadra = miaSquadra; self.totaleSquadre = totaleSquadre
        sicuri = squadre.reduce(0) { $0 + $1.sicuri }
        daControllare = squadre.reduce(0) { $0 + $1.daControllare }
        nonTrovati = squadre.reduce(0) { $0 + $1.nonTrovati }
        self.differenze = differenze; self.riepilogo = riepilogo
    }

    private enum Chiavi: String, CodingKey {
        case squadre, avvisi, miaSquadra, totaleSquadre, sicuri, daControllare, nonTrovati, differenze, riepilogo
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        squadre = k.elenco(SquadraAnteprima.self, .squadre).filter { !$0.nome.isEmpty }
        avvisi = k.valore([String].self, .avvisi) ?? []
        miaSquadra = k.valore(String.self, .miaSquadra)
        totaleSquadre = k.valore(Int.self, .totaleSquadre)
        sicuri = k.valore(Int.self, .sicuri) ?? squadre.reduce(0) { $0 + $1.sicuri }
        daControllare = k.valore(Int.self, .daControllare) ?? squadre.reduce(0) { $0 + $1.daControllare }
        nonTrovati = k.valore(Int.self, .nonTrovati) ?? squadre.reduce(0) { $0 + $1.nonTrovati }
        differenze = k.valore(Differenze.self, .differenze)
        riepilogo = k.valore(String.self, .riepilogo)
    }
}

/// Cosa ha deciso l'utente per un dubbio.
enum SceltaDubbio: Hashable {
    /// Nessuna scelta: si salva come l'ha capito il server (per un «non trovato»: resta senza codice).
    case lascia
    /// Il giocatore giusto del listone.
    case giocatore(Int)
    /// Togliere la riga dalla rosa.
    case togli
}

/// Una scelta da mandare con l'importazione: `id` nil = togli la riga; `riga` (quella dell'anteprima) fa valere la scelta solo
/// per quella riga. Chiavi identiche a quelle del server.
struct CorrezioneRosa: Encodable, Equatable {
    let squadra: String
    let testo: String
    let id: Int?
    let riga: Int?

    init(squadra: String, testo: String, id: Int?, riga: Int? = nil) {
        self.squadra = squadra; self.testo = testo; self.id = id; self.riga = riga
    }

    private enum CodingKeys: String, CodingKey { case squadra, testo, id, riga }

    /// `id` si manda sempre, anche `null` (vuol dire «togli»): la codifica automatica lo ometterebbe. `riga` solo se l'anteprima
    /// l'ha data: un server di prima non la conosce.
    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(squadra, forKey: .squadra)
        try c.encode(testo, forKey: .testo)
        if let id { try c.encode(id, forKey: .id) } else { try c.encodeNil(forKey: .id) }
        try c.encodeIfPresent(riga, forKey: .riga)
    }
}

/// Il corpo dell'anteprima da testo.
struct RichiestaAnteprimaRose: Encodable {
    let testo: String
    let sostituisci_tutto: Bool
}

enum AnteprimaLogica {
    /// La chiave di un dubbio, come `arChiave` della web: squadra e riga, così due omonimi scritti uguali nella stessa rosa si
    /// scelgono uno per uno (#716). Con un server di prima, senza `riga`, squadra e nome come scritto.
    static func chiave(_ squadra: String, _ g: GiocatoreAnteprima) -> String { chiave(squadra, g.chiaveInSquadra) }

    /// La chiave per nome come scritto (lo stesso nome in due squadre sono due dubbi diversi).
    static func chiave(_ squadra: String, _ testo: String) -> String { squadra + "\u{0}" + testo }

    /// La scelta di partenza: la proposta del server per un «da controllare», altrimenti nessuna.
    static func iniziale(_ g: GiocatoreAnteprima) -> SceltaDubbio {
        if g.stato == .daControllare, let id = g.id { return .giocatore(id) }
        return .lascia
    }

    static func scelta(_ g: GiocatoreAnteprima, squadra: String, scelte: [String: SceltaDubbio]) -> SceltaDubbio {
        scelte[chiave(squadra, g)] ?? iniziale(g)
    }

    /// Le correzioni da mandare: una per ogni dubbio deciso, con la sua `riga` (come `arCorrezioni` della web app). Con un
    /// server di prima una per nome, senza riga: lui la applica a tutte le righe con quel nome.
    static func correzioni(_ squadre: [SquadraAnteprima], scelte: [String: SceltaDubbio]) -> [CorrezioneRosa] {
        var fuori: [CorrezioneRosa] = []
        var viste = Set<String>()
        for s in squadre {
            for g in s.giocatori where g.stato != .sicuro {
                guard viste.insert(chiave(s.nome, g)).inserted else { continue }
                switch scelta(g, squadra: s.nome, scelte: scelte) {
                case .giocatore(let id): fuori.append(CorrezioneRosa(squadra: s.nome, testo: g.testo, id: id, riga: g.riga))
                case .togli: fuori.append(CorrezioneRosa(squadra: s.nome, testo: g.testo, id: nil, riga: g.riga))
                case .lascia: break
                }
            }
        }
        return fuori
    }

    /// I dubbi di una squadra, uno per riga (con un server di prima uno per nome): prima quelli da controllare, poi i non trovati.
    static func dubbi(_ s: SquadraAnteprima) -> [GiocatoreAnteprima] {
        var visti = Set<String>()
        let ordinati = s.giocatori.filter { $0.stato == .daControllare } + s.giocatori.filter { $0.stato == .nonTrovato }
        return ordinati.filter { visti.insert($0.chiaveInSquadra).inserted }
    }

    /// Le opzioni del menu di un dubbio: le alternative del server più quella trovata con la ricerca (se non c'è già).
    static func opzioni(_ g: GiocatoreAnteprima, trovato: CandidatoAnteprima?) -> [CandidatoAnteprima] {
        var elenco = g.alternative
        if let trovato, !elenco.contains(where: { $0.id == trovato.id }) { elenco.append(trovato) }
        return elenco
    }

    private static let ordineRuoli = ["P", "D", "C", "A"]
    private static let nomiRuolo: [String: (String, String)] = [
        "P": ("portiere", "portieri"), "D": ("difensore", "difensori"), "C": ("centrocampista", "centrocampisti"), "A": ("attaccante", "attaccanti"),
    ]

    static func ruolo(_ r: String?, _ n: Int = 1) -> String {
        guard let r, let nomi = nomiRuolo[r.uppercased()] else { return r ?? "" }
        return n == 1 ? nomi.0 : nomi.1
    }

    /// I problemi di una rosa a parole: «Manca 1 portiere», «Mancano 2 difensori», «1 attaccante in più», «1 giocatore senza ruolo».
    static func problemi(_ s: SquadraAnteprima) -> [String] {
        var fuori: [String] = []
        for r in ordineRuoli + s.mancano.keys.filter({ !ordineRuoli.contains($0) }).sorted() {
            guard let n = s.mancano[r], n > 0 else { continue }
            fuori.append("\(n == 1 ? "Manca" : "Mancano") \(n) \(ruolo(r, n))")
        }
        for r in ordineRuoli + s.inPiu.keys.filter({ !ordineRuoli.contains($0) }).sorted() {
            guard let n = s.inPiu[r], n > 0 else { continue }
            fuori.append("\(n) \(ruolo(r, n)) in più")
        }
        if s.senzaRuolo > 0 { fuori.append("\(Formato.giocatori(s.senzaRuolo)) senza ruolo") }
        return fuori
    }

    /// «25 giocatori · 12 crediti» oppure «23 giocatori su 25 · 1 credito».
    static func conteggio(_ s: SquadraAnteprima) -> String {
        var parti: [String] = []
        if let attesi = s.attesi, attesi != s.totale {
            parti.append("\(Formato.giocatori(s.totale)) su \(attesi)")
        } else {
            parti.append(Formato.giocatori(s.totale))
        }
        if let c = s.creditiResidui { parti.append(Formato.crediti(Formato.intero(c))) }
        return parti.joined(separator: " · ")
    }

    /// «8 squadre: 196 giocatori riconosciuti, 3 da controllare, 1 non trovato. Sistema i dubbi qui sotto, poi conferma.»
    /// Si rifà dopo ogni scelta, come `arRiassuntoScelte` della web (#808): un dubbio deciso dall'utente (un giocatore scelto o
    /// «Toglilo dalla rosa») non è più da controllare né «non trovato», e chi è stato scelto conta tra i riconosciuti. La proposta
    /// del server non toccata e «Scegli chi è» / «Lascialo così per ora» restano dubbi.
    static func riassunto(_ r: AnteprimaRose, scelte: [String: SceltaDubbio] = [:]) -> String {
        var sistemati = 0, decisiDaControllare = 0, decisiNonTrovati = 0
        for s in r.squadre {
            for g in s.giocatori where g.stato != .sicuro {
                guard let scelta = scelte[chiave(s.nome, g)] else { continue }
                switch scelta {
                case .giocatore: sistemati += 1
                case .togli: break
                case .lascia: continue
                }
                if g.stato == .nonTrovato { decisiNonTrovati += 1 } else { decisiDaControllare += 1 }
            }
        }
        let sicuri = r.sicuri + sistemati
        let daControllare = max(0, r.daControllare - decisiDaControllare)
        let nonTrovati = max(0, r.nonTrovati - decisiNonTrovati)
        let squadre = Formato.plurale(r.squadre.count, "squadra", "squadre")
        var parti = ["\(Formato.giocatori(sicuri)) \(sicuri == 1 ? "riconosciuto" : "riconosciuti")"]
        if daControllare > 0 { parti.append("\(daControllare) da controllare") }
        if nonTrovati > 0 { parti.append("\(nonTrovati) \(nonTrovati == 1 ? "non trovato" : "non trovati")") }
        let invito = daControllare + nonTrovati > 0 ? " Sistema i dubbi qui sotto, poi conferma." : ""
        return "\(squadre): \(parti.joined(separator: ", "))." + invito
    }

    /// Gli avvisi di tutto il file: quelli di una sola squadra («Squadra: …») si vedono già nella sua scheda.
    static func avvisiGenerali(_ r: AnteprimaRose) -> [String] {
        let diSquadra = Set(r.squadre.flatMap { s in s.avvisi.map { "\(s.nome): \($0)" } })
        return r.avvisi.filter { !diSquadra.contains($0) }
    }

    /// Le squadre tra cui scegliere la propria, come `nomiMia` della web: quelle lette e, per prima, quella suggerita dal server se
    /// non è nel file (si aggiornano solo le rose degli altri: la propria resta com'era, #808).
    static func nomiMia(_ r: AnteprimaRose) -> [String] {
        let nomi = r.squadre.map(\.nome)
        guard let suggerita = r.miaSquadra, !suggerita.isEmpty, !nomi.contains(suggerita) else { return nomi }
        return [suggerita] + nomi
    }

    /// La squadra dell'utente da mostrare scelta: quella già decisa, altrimenti il suggerimento del server; vuota se non è tra quelle
    /// che si possono scegliere (`nomiMia`).
    static func mia(decisa: String?, _ r: AnteprimaRose) -> String {
        let candidata = decisa ?? r.miaSquadra ?? ""
        return nomiMia(r).contains(candidata) ? candidata : ""
    }

    /// Le differenze si mostrano solo se c'era già qualcosa e qualcosa cambia.
    static func mostraDifferenze(_ d: Differenze?) -> Bool {
        guard let d else { return false }
        return d.primaImportazione != true && d.nessunaDifferenza != true
    }

    /// «Nuova» accanto al nome della squadra solo se si aggiunge a rose già salvate, come la web (#873): alla prima importazione le
    /// squadre sono tutte nuove e l'etichetta su ognuna non dice niente. Senza differenze (server di prima) vale ciò che segna il server.
    static func mostraNuova(_ s: SquadraAnteprima, differenze: Differenze?) -> Bool {
        s.nuova && differenze?.primaImportazione != true
    }

    /// Una squadra senza dubbi sta in due righe, come la web (#873: al telefono dieci squadre erano quattro schermi): il nome e, da
    /// aprire, i conti con dentro i nomi dei riconosciuti. Con dei dubbi, o senza riconosciuti, i conti restano una riga a sé.
    static func contiNelRipiegato(_ s: SquadraAnteprima) -> Bool {
        dubbi(s).isEmpty && s.sicuri > 0
    }

    /// La squadra di Serie A per esteso: «juventus» o «JUV» → «Juventus»; se non la conosciamo, com'è.
    static func club(_ s: String?) -> String {
        guard let s, !s.isEmpty else { return "" }
        if ColoriSquadra.sigle[s.lowercased()] != nil { return s.lowercased().capitalized }
        if let intero = ColoriSquadra.sigle.first(where: { $0.value == s.uppercased() })?.key { return intero.capitalized }
        return s
    }

    /// «Ivo Sorvani · portiere · Inter».
    static func descrivi(_ c: CandidatoAnteprima) -> String {
        [c.nome, ruolo(c.ruolo), club(c.squadra)].filter { !$0.isEmpty }.joined(separator: " · ")
    }

    /// Il testo della scelta fatta, per il menu e per VoiceOver.
    static func testoScelta(_ scelta: SceltaDubbio, _ g: GiocatoreAnteprima, opzioni: [CandidatoAnteprima]) -> String {
        switch scelta {
        case .giocatore(let id): return opzioni.first { $0.id == id }.map(descrivi) ?? g.nome ?? "Giocatore scelto"
        case .togli: return "Toglilo dalla rosa"
        case .lascia: return g.stato == .nonTrovato ? "Lascialo così per ora" : "Scegli chi è"
        }
    }
}
