import Foundation

// Il calendario della demo (`/api/calendario`), come `calendario` di fanta/gestione.py: le prossime cinque giornate di ogni squadra
// di Serie A, a coppie (in ogni giornata ogni squadra ha un avversario solo, che a sua volta ha lei, una in casa e l'altra fuori).
// La prima giornata sono le partite di Oggi (`incontri`), le altre girano con il metodo del cerchio, così nessuna partita si ripete
// (#303). La difficoltà della prima giornata è quella delle schede dei giocatori, come sul server.

extension LegaDemo {
    /// Le giornate di Serie A del calendario e degli scambi: quella di Oggi e le quattro dopo.
    static let giornateProssime = Array(giornata..<(giornata + 5))

    /// Le squadre di Serie A dalla più forte alla più debole (serve per la difficoltà delle partite).
    static let forza = ["inter", "napoli", "milan", "juventus", "atalanta", "roma", "bologna", "lazio", "fiorentina", "como",
                        "torino", "udinese", "genoa", "parma", "cagliari", "verona", "lecce", "sassuolo", "pisa", "cremonese"]

    /// Quanto è dura una partita contro `avversario`, da 1 (facile) a 5 (dura): dipende dalla sua forza.
    static func difficolta(contro avversario: String) -> Int {
        guard let i = forza.firstIndex(of: avversario) else { return 3 }
        return 1 + Int((Double(forza.count - 1 - i) / Double(forza.count - 1) * 4.0).rounded())
    }

    /// La difficoltà della partita di Oggi di una squadra: la stessa nelle schede dei giocatori e nel calendario.
    static func difficolta(di squadra: String) -> Int {
        guard let a = avversario(di: squadra) else { return 3 }
        return difficolta(contro: a.nome)
    }

    /// Gli incontri di una giornata di Serie A. Quella di Oggi è `incontri`; ogni giornata dopo tiene ferma la prima squadra e fa
    /// girare le altre di un posto (metodo del cerchio: in diciannove giornate due squadre non si incontrano due volte), con casa
    /// e trasferta che si scambiano da una giornata all'altra.
    static func incontriDellaGiornata(_ g: Int) -> [(casa: String, trasferta: String)] {
        let giro = g - giornata
        guard giro > 0 else { return incontri }
        // il cerchio: le squadre di casa in ordine, poi quelle in trasferta al contrario (oggi il posto i gioca con il posto 19 - i)
        let cerchio = incontri.map { $0.casa } + incontri.reversed().map { $0.trasferta }
        guard let fermo = cerchio.first else { return incontri }
        let resto = Array(cerchio.dropFirst())
        let girati = [fermo] + resto.indices.map { j in resto[((j - giro) % resto.count + resto.count) % resto.count] }
        let n = girati.count
        return (0..<n / 2).map { i -> (casa: String, trasferta: String) in
            let a = girati[i], b = girati[n - 1 - i]
            return giro % 2 == 1 ? (casa: b, trasferta: a) : (casa: a, trasferta: b)
        }
    }

    /// Il calendario come lo manda il server: per ogni squadra le partite delle prossime giornate (avversario, in casa o fuori,
    /// difficoltà, data), dalla squadra con il calendario più morbido. Le giornate dopo quella di Oggi cadono una settimana dopo
    /// l'altra, agli stessi orari.
    static func calendario(adesso: Date) -> [String: Any] {
        let ore = orari(adesso: adesso)
        let roma = oraItaliana
        var partite: [String: [[String: Any]]] = [:]
        for (k, g) in giornateProssime.enumerated() {
            for (i, m) in incontriDellaGiornata(g).enumerated() {
                var data: Any = NSNull()
                if i < ore.count, let quando = roma.date(byAdding: .day, value: 7 * k, to: ore[i]) {
                    data = formatta(quando, "yyyy-MM-dd HH:mm")
                }
                partite[m.casa, default: []].append(["giornata": g, "avversario": m.trasferta, "in_casa": true,
                                                     "difficolta": difficolta(contro: m.trasferta), "data": data])
                partite[m.trasferta, default: []].append(["giornata": g, "avversario": m.casa, "in_casa": false,
                                                          "difficolta": difficolta(contro: m.casa), "data": data])
            }
        }
        let squadre: [(squadra: String, media: Double, partite: [[String: Any]])] = partite.map { squadra, elenco in
            let somma = elenco.reduce(0) { $0 + (($1["difficolta"] as? Int) ?? 3) }
            return (squadra: squadra, media: (Double(somma) / Double(max(1, elenco.count)) * 100).rounded() / 100, partite: elenco)
        }
        let ordinate = squadre.sorted { ($0.media, $0.squadra) < ($1.media, $1.squadra) }
        return ["giornate": giornateProssime,
                "squadre": ordinate.map { ["squadra": $0.squadra, "media": $0.media, "partite": $0.partite] as [String: Any] }]
    }
}
