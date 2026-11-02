import Foundation

// Le rose dagli screenshot di «Dettaglio squadra» dell'app Leghe Fantacalcio (dal telefono il testo delle rose non si copia).
// Il testo lo legge Vision sul telefono (`Data/LetturaScreenshot.swift`); qui c'è solo la logica, senza interfaccia e senza
// Vision, così si prova con parole inventate: righe ricostruite dalle coordinate, nome della squadra dall'intestazione, più
// screenshot della stessa squadra uniti senza doppioni, e il testo da mandare all'anteprima del server come se fosse incollato.
// Le immagini non escono dal telefono: al server va solo il testo.

/// Una parola letta: testo e riquadro misurati in LARGHEZZE dell'immagine (x e y divisi per la larghezza), origine in alto a sinistra.
struct ParolaLetta: Equatable, Sendable {
    var testo: String
    var x: Double
    var y: Double
    var larghezza: Double
    var altezza: Double

    var maxX: Double { x + larghezza }
    var maxY: Double { y + altezza }
    var medioX: Double { x + larghezza / 2 }
    var medioY: Double { y + altezza / 2 }
}

/// Uno screenshot letto: le parole, altezza/larghezza dell'immagine e, per ogni fascia orizzontale dall'alto in basso, il ruolo
/// dato dal colore del pallino a sinistra (P giallo, D verde, C blu, A rosso; nil = nessun pallino in quella fascia).
struct PaginaScreenshot: Equatable, Sendable {
    var parole: [ParolaLetta]
    var proporzione: Double
    var strisciaRuoli: [String?] = []
}

/// Un giocatore letto da uno screenshot.
struct RigaScreenshot: Equatable, Sendable {
    var nome: String
    var club: String?
    var ruolo: String?
    var quotazione: Int?
    var fvm: Int?
    /// Valore d'acquisto (il prezzo pagato all'asta).
    var costo: Int?
    /// Riga tagliata in cima o in fondo allo screenshot (manca la squadra di Serie A o qualche numero).
    var parziale: Bool = false
}

/// Quello che si legge da uno screenshot.
struct LetturaPagina: Equatable, Sendable {
    var squadra: String?
    var crediti: Int?
    var righe: [RigaScreenshot]
    /// Righe di cui si legge solo la squadra di Serie A (il nome no): si dice all'utente.
    var illeggibili: Int = 0
}

/// Una fantasquadra ricostruita da uno o più screenshot.
struct SquadraScreenshot: Equatable, Sendable {
    var nome: String
    var crediti: Int?
    var righe: [RigaScreenshot]
    var illeggibili: Int = 0
    var foto: Int = 1
}

enum RoseDaScreenshot {
    /// Squadre di Serie A degli ultimi anni, come le scrive Leghe: servono solo a correggere una lettura sbagliata di poco
    /// («Caqliari» → «Cagliari») e a riconoscere la squadra di una riga tagliata. Una squadra che non c'è resta come letta.
    static let squadreSerieA = [
        "Atalanta", "Bologna", "Cagliari", "Como", "Cremonese", "Fiorentina", "Genoa", "Verona", "Inter", "Juventus",
        "Lazio", "Lecce", "Milan", "Napoli", "Parma", "Pisa", "Roma", "Sassuolo", "Torino", "Udinese", "Empoli", "Monza",
        "Venezia", "Frosinone", "Salernitana", "Sampdoria", "Spezia", "Benevento", "Crotone", "Palermo", "Bari", "Brescia",
    ]
    /// Dove stanno le colonne «Q. att.», «FVMp» e «V. Acq.» (centro, in larghezze) se l'intestazione non si legge.
    static let colonneTipiche: [Double] = [0.629, 0.766, 0.902]
    static let ruoli = ["P", "D", "C", "A"]

    // MARK: testo

    static func piega(_ s: String) -> String {
        s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "it_IT"))
    }

    /// Solo lettere e cifre, senza accenti e maiuscole: per confrontare due letture dello stesso nome.
    static func chiave(_ s: String) -> String {
        String(piega(s).filter { $0.isLetter || $0.isNumber })
    }

    static func distanza(_ a: String, _ b: String) -> Int {
        let x = Array(a), y = Array(b)
        if x.isEmpty { return y.count }
        if y.isEmpty { return x.count }
        var prima = Array(0...y.count)
        for i in 1...x.count {
            var ora = [i] + Array(repeating: 0, count: y.count)
            for j in 1...y.count {
                ora[j] = min(prima[j] + 1, ora[j - 1] + 1, prima[j - 1] + (x[i - 1] == y[j - 1] ? 0 : 1))
            }
            prima = ora
        }
        return prima[y.count]
    }

    /// La squadra di Serie A più vicina a quella letta (nil se nessuna è abbastanza vicina).
    static func squadraSerieA(_ letto: String) -> String? {
        let n = String(piega(letto).filter { $0.isLetter || $0 == " " }).trimmingCharacters(in: .whitespaces)
        guard !n.isEmpty else { return nil }
        var migliore: String?
        var minima = Int.max
        for s in squadreSerieA {
            let d = distanza(n, piega(s))
            if d < minima { minima = d; migliore = s }
        }
        return minima <= max(1, n.count / 4) ? migliore : nil
    }

    static func eNumero(_ s: String) -> Bool {
        let t = s.trimmingCharacters(in: .whitespaces)
        return !t.isEmpty && t.count <= 4 && t.allSatisfy { $0.isASCII && $0.isNumber }
    }

    static func haLettere(_ s: String) -> Bool { s.contains { $0.isLetter } }

    /// Il nome come va nel testo: spazi in ordine, niente segni sparsi ai bordi.
    static func pulisci(_ s: String) -> String {
        let spazi = s.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
        return spazi.trimmingCharacters(in: CharacterSet(charactersIn: " |•·-_\t\"")).replacingOccurrences(of: "\"", with: "'")
    }

    // MARK: righe di testo

    /// «9 7 1» letto come un pezzo solo: un numero per colonna, con la posizione stimata dai caratteri.
    static func dividiNumeri(_ p: ParolaLetta) -> [ParolaLetta] {
        let pezzi = p.testo.split(separator: " ", omittingEmptySubsequences: true)
        guard pezzi.count > 1, pezzi.allSatisfy({ eNumero(String($0)) }) else { return [p] }
        let totale = Double(max(p.testo.count, 1))
        var risultato: [ParolaLetta] = []
        var inizio = 0
        let caratteri = Array(p.testo)
        var i = 0
        while i < caratteri.count {
            if caratteri[i] == " " { i += 1; inizio = i; continue }
            var fine = i
            while fine < caratteri.count, caratteri[fine] != " " { fine += 1 }
            let x = p.x + p.larghezza * Double(inizio) / totale
            let w = p.larghezza * Double(fine - inizio) / totale
            risultato.append(ParolaLetta(testo: String(caratteri[inizio..<fine]), x: x, y: p.y, larghezza: w, altezza: p.altezza))
            i = fine
            inizio = fine
        }
        return risultato
    }

    /// Le parole vicine sulla stessa riga diventano una riga sola («Zambi», «Angossa» → «Zambi Angossa»; «V.», «Acq.» → «V. Acq.»);
    /// le colonne dei numeri, lontane, restano separate.
    static func linee(_ parole: [ParolaLetta]) -> [ParolaLetta] {
        let ordinate = parole.flatMap(dividiNumeri).filter { !$0.testo.trimmingCharacters(in: .whitespaces).isEmpty }
            .sorted { $0.x < $1.x }
        var gruppi: [[ParolaLetta]] = []
        for p in ordinate {
            if let i = gruppi.firstIndex(where: { g in
                guard let u = g.last else { return false }
                let piccola = min(u.altezza, p.altezza), grande = max(u.altezza, p.altezza)
                let spazio = p.x - u.maxX
                // altezze troppo diverse: una scritta della figurina accanto al nome, non la stessa riga
                return piccola > 0.6 * grande && abs(u.medioY - p.medioY) < 0.6 * piccola && spazio > -0.5 * grande && spazio < 1.0 * grande
            }) {
                gruppi[i].append(p)
            } else {
                gruppi.append([p])
            }
        }
        return gruppi.compactMap { g -> ParolaLetta? in
            guard let x = g.map(\.x).min(), let y = g.map(\.y).min(),
                  let maxX = g.map(\.maxX).max(), let maxY = g.map(\.maxY).max() else { return nil }
            return ParolaLetta(testo: g.map(\.testo).joined(separator: " "), x: x, y: y, larghezza: maxX - x, altezza: maxY - y)
        }
        .sorted { ($0.medioY, $0.x) < ($1.medioY, $1.x) }
    }

    // MARK: una pagina

    /// Legge uno screenshot. nil se non è il «Dettaglio squadra» di Leghe (manca l'intestazione «Calciatore» della tabella).
    static func leggi(_ pagina: PaginaScreenshot) -> LetturaPagina? {
        let righe = linee(pagina.parole)
        let piegate = righe.map { (piega($0.testo), $0) }
        guard let calciatore = piegate.first(where: { $0.0.contains("calciatore") })?.1 else { return nil }
        let dettaglio = piegate.first(where: { $0.0.contains("dettaglio") })?.1
        let schede = piegate.first(where: { $0.0.contains("calendario") && $0.1.medioY < calciatore.medioY })?.1
        let sopra = dettaglio?.maxY ?? 0
        let sotto = min(calciatore.y, schede?.y ?? .infinity)

        // Nome della squadra: la riga più grande tra «DETTAGLIO SQUADRA» e le schede, a destra degli stemmi
        // (sotto c'è il proprietario, più piccolo, che non serve; a destra «N CREDITI»).
        let candidati = piegate.filter { coppia in
            let (n, l) = coppia
            return l.medioY > sopra && l.medioY < sotto && l.x >= 0.28 && l.x <= 0.75 && haLettere(n)
                && !n.contains("crediti") && !n.contains("calendario") && !n.contains("dettaglio") && l != dettaglio
        }.map { $0.1 }
        var squadra: String?
        if let alta = candidati.map(\.altezza).max() {
            squadra = candidati.filter { $0.altezza >= 0.85 * alta }.min(by: { $0.medioY < $1.medioY }).map { pulisci($0.testo) }
        }
        var crediti: Int?
        if let etichetta = piegate.first(where: { $0.0.trimmingCharacters(in: .whitespaces) == "crediti" && $0.1.medioY < sotto })?.1 {
            crediti = righe.last(where: {
                eNumero($0.testo) && $0.x > 0.7 && $0.medioY > etichetta.y - 3 * etichetta.altezza && $0.medioY < etichetta.y
            }).flatMap { Int($0.testo.trimmingCharacters(in: .whitespaces)) }
        }

        // Colonne dei numeri dall'intestazione della tabella.
        let intestazione = righe.filter { abs($0.medioY - calciatore.medioY) < 1.5 * calciatore.altezza }
        func colonna(_ indice: Int, _ prova: (String) -> Bool) -> Double {
            intestazione.first(where: { prova(piega($0.testo)) })?.medioX ?? colonneTipiche[indice]
        }
        let colonne = [colonna(0) { $0.contains("att") || $0.hasPrefix("q") }, colonna(1) { $0.contains("fvm") },
                       colonna(2) { $0.contains("acq") }]
        let cima = intestazione.map(\.maxY).max() ?? calciatore.maxY

        let tabella = righe.filter { $0.y > cima - 0.005 }
        // a sinistra le figurine (con scritte piccole), poi nome e squadra, a destra i numeri
        let testi = tabella.filter { $0.x >= 0.19 && $0.x <= 0.45 && haLettere($0.testo) }
        let numeri = tabella.filter { eNumero($0.testo) && $0.x > 0.5 }
        let lettere = tabella.filter { ruoli.contains($0.testo.trimmingCharacters(in: .whitespaces).uppercased()) && $0.maxX < 0.12 }

        // nome sopra, squadra di Serie A subito sotto (tra una scheda e l'altra c'è molto più spazio)
        var coppie: [(ParolaLetta, ParolaLetta?)] = []
        var i = 0
        while i < testi.count {
            let a = testi[i]
            if i + 1 < testi.count, testi[i + 1].y - a.maxY < 1.5 * a.altezza, testi[i + 1].medioY > a.medioY {
                coppie.append((a, testi[i + 1]))
                i += 2
            } else {
                coppie.append((a, nil))
                i += 1
            }
        }
        let altezzeNomi = coppie.filter { $0.1 != nil }.map { $0.0.altezza }.sorted()
        let altezzaNome = altezzeNomi.isEmpty ? 0 : altezzeNomi[altezzeNomi.count / 2]

        var lette: [RigaScreenshot] = []
        var illeggibili = 0
        for (k, (nome, club)) in coppie.enumerated() {
            if club == nil, squadraSerieA(nome.testo) != nil, altezzaNome == 0 || nome.altezza < 0.85 * altezzaNome {
                // solo la squadra di Serie A: in cima è una riga tagliata (si vede in un altro screenshot), altrove il nome non si legge
                if k > 0 { illeggibili += 1 }
                continue
            }
            let centro = club.map { (nome.medioY + $0.medioY) / 2 } ?? (nome.medioY + nome.altezza)
            var valori: [Int?] = [nil, nil, nil]
            for n in numeri where abs(n.medioY - centro) < 1.6 * nome.altezza {
                guard let j = colonne.indices.min(by: { abs(colonne[$0] - n.medioX) < abs(colonne[$1] - n.medioX) }),
                      abs(colonne[j] - n.medioX) < 0.06 else { continue }
                valori[j] = Int(n.testo.trimmingCharacters(in: .whitespaces))
            }
            var ruolo = lettere.last(where: { $0.medioY > nome.y - 2 * nome.altezza && $0.medioY < nome.maxY })
                .map { $0.testo.trimmingCharacters(in: .whitespaces).uppercased() }
            if ruolo == nil {
                ruolo = ruoloDaStriscia(pagina.strisciaRuoli, da: (nome.medioY - 0.065) / pagina.proporzione,
                                        a: (nome.medioY - 0.005) / pagina.proporzione)
            }
            let parziale = club == nil || nome.y - cima < 0.3 * nome.altezza || valori[2] == nil
            let squadraA = club.map { squadraSerieA($0.testo) ?? pulisci($0.testo) }
            lette.append(RigaScreenshot(nome: pulisci(nome.testo), club: squadraA, ruolo: ruolo, quotazione: valori[0],
                                        fvm: valori[1], costo: valori[2], parziale: parziale))
        }
        return LetturaPagina(squadra: squadra, crediti: crediti, righe: lette, illeggibili: illeggibili)
    }

    /// Il ruolo più frequente nella striscia dei colori tra due altezze (in frazioni dell'altezza dell'immagine).
    static func ruoloDaStriscia(_ striscia: [String?], da: Double, a: Double) -> String? {
        guard !striscia.isEmpty, a > da else { return nil }
        let n = Double(striscia.count)
        let inizio = max(0, Int(da * n)), fine = min(striscia.count - 1, Int(a * n))
        guard inizio <= fine else { return nil }
        var conta: [String: Int] = [:]
        for r in striscia[inizio...fine] { if let r { conta[r, default: 0] += 1 } }
        guard let migliore = conta.max(by: { $0.value < $1.value }), migliore.value >= 2 else { return nil }
        return migliore.key
    }

    /// Il ruolo dal colore di un punto del pallino (componenti 0-1): P giallo/arancio, D verde, C blu, A rosso; grigi e bianchi nil.
    static func ruolo(rosso r: Double, verde g: Double, blu b: Double) -> String? {
        let massimo = max(r, g, b), minimo = min(r, g, b)
        guard massimo >= 0.35, massimo > 0, (massimo - minimo) / massimo >= 0.45 else { return nil }
        let delta = massimo - minimo
        var tinta: Double
        if massimo == r { tinta = 60 * ((g - b) / delta).truncatingRemainder(dividingBy: 6) }
        else if massimo == g { tinta = 60 * ((b - r) / delta + 2) }
        else { tinta = 60 * ((r - g) / delta + 4) }
        if tinta < 0 { tinta += 360 }
        switch tinta {
        case ..<18, 335...: return "A"
        case 25..<60: return "P"
        case 70..<165: return "D"
        case 200..<255: return "C"
        default: return nil
        }
    }

    // MARK: più screenshot

    /// Unisce gli screenshot: stessa squadra (anche letta con una lettera diversa) = stessa rosa; le righe ripetute scorrendo si
    /// tengono una volta sola, nella versione più completa. Righe in ordine di ruolo (P, D, C, A), come in Leghe.
    /// `esistenti`: i nomi delle squadre già salvate; un nome letto quasi uguale prende quello salvato.
    static func unisci(_ pagine: [LetturaPagina], esistenti: [String] = []) -> [SquadraScreenshot] {
        var squadre: [SquadraScreenshot] = []
        for p in pagine {
            let indice: Int
            if let nome = p.squadra.map({ nomeSalvato($0, esistenti: esistenti) }) {
                if let i = squadre.firstIndex(where: { simili($0.nome, nome) }) {
                    indice = i
                    squadre[i].foto += 1
                } else {
                    squadre.append(SquadraScreenshot(nome: nome, crediti: nil, righe: []))
                    indice = squadre.count - 1
                }
            } else if !squadre.isEmpty {
                indice = squadre.count - 1          // nome non letto: è il seguito dello screenshot di prima
                squadre[indice].foto += 1
            } else {
                squadre.append(SquadraScreenshot(nome: "Squadra senza nome", crediti: nil, righe: []))
                indice = 0
            }
            if squadre[indice].crediti == nil { squadre[indice].crediti = p.crediti }
            squadre[indice].illeggibili += p.illeggibili
            for riga in p.righe { aggiungi(riga, a: &squadre[indice].righe) }
        }
        for i in squadre.indices {
            riempiRuoli(&squadre[i].righe)
            squadre[i].righe = ordinaPerRuolo(squadre[i].righe)
        }
        return squadre
    }

    /// Due letture dello stesso nome di squadra: uguali, oppure diverse di poco («Pigiama» / «Pigiarna»); i nomi corti devono essere uguali.
    static func simili(_ a: String, _ b: String) -> Bool {
        let x = chiave(a), y = chiave(b)
        let corto = min(x.count, y.count)
        return x == y || distanza(x, y) <= (corto >= 10 ? 2 : corto >= 5 ? 1 : 0)
    }

    static func nomeSalvato(_ letto: String, esistenti: [String]) -> String {
        if let uguale = esistenti.first(where: { chiave($0) == chiave(letto) }) { return uguale }
        return esistenti.first(where: { simili($0, letto) }) ?? letto
    }

    private static func completezza(_ r: RigaScreenshot) -> Int {
        (r.parziale ? 0 : 8) + (r.club != nil ? 4 : 0) + (r.costo != nil ? 2 : 0) + (r.ruolo != nil ? 1 : 0)
    }

    /// Due letture dello stesso giocatore? Stesso nome; oppure, se una è tagliata, nome quasi uguale; oppure nome quasi uguale
    /// con stessa squadra e stessi numeri. «Rossi Al.» e «Rossi An.» con numeri diversi restano due giocatori.
    static func stessoGiocatore(_ a: RigaScreenshot, _ b: RigaScreenshot) -> Bool {
        let x = chiave(a.nome), y = chiave(b.nome)
        if x == y { return a.club == nil || b.club == nil || a.club == b.club }
        let d = distanza(x, y)
        if a.parziale || b.parziale {
            let prefisso = min(x.count, y.count) >= 4 && (x.hasPrefix(y) || y.hasPrefix(x))
            if d <= 1 || prefisso { return a.club == nil || b.club == nil || a.club == b.club }
        }
        return d <= 2 && a.club != nil && a.club == b.club && a.costo != nil && a.costo == b.costo && a.quotazione == b.quotazione
    }

    private static func aggiungi(_ riga: RigaScreenshot, a righe: inout [RigaScreenshot]) {
        guard let i = righe.firstIndex(where: { stessoGiocatore($0, riga) }) else {
            righe.append(riga)
            return
        }
        let vecchia = righe[i]
        if completezza(riga) > completezza(vecchia) {
            var nuova = riga
            nuova.ruolo = riga.ruolo ?? vecchia.ruolo
            nuova.club = riga.club ?? vecchia.club
            nuova.costo = riga.costo ?? vecchia.costo
            righe[i] = nuova
        } else {
            righe[i].ruolo = vecchia.ruolo ?? riga.ruolo
            righe[i].club = vecchia.club ?? riga.club
            righe[i].costo = vecchia.costo ?? riga.costo
        }
    }

    /// Ruolo mancante: in Leghe la rosa è in ordine P, D, C, A, quindi tra due giocatori dello stesso ruolo c'è quel ruolo,
    /// prima del primo portiere c'è un portiere e dopo l'ultimo attaccante un attaccante.
    static func riempiRuoli(_ righe: inout [RigaScreenshot]) {
        for i in righe.indices where righe[i].ruolo == nil {
            let prima = righe[..<i].last(where: { $0.ruolo != nil })?.ruolo
            let dopo = righe[(i + 1)...].first(where: { $0.ruolo != nil })?.ruolo
            if let prima, prima == dopo { righe[i].ruolo = prima }
            else if prima == nil, dopo == "P" { righe[i].ruolo = "P" }
            else if dopo == nil, prima == "A" { righe[i].ruolo = "A" }
        }
    }

    /// Ordine stabile per ruolo; chi non ha il ruolo resta dov'era rispetto agli altri senza ruolo, in fondo.
    static func ordinaPerRuolo(_ righe: [RigaScreenshot]) -> [RigaScreenshot] {
        righe.enumerated().sorted { a, b in
            let ra = a.element.ruolo.flatMap { ruoli.firstIndex(of: $0) } ?? ruoli.count
            let rb = b.element.ruolo.flatMap { ruoli.firstIndex(of: $0) } ?? ruoli.count
            return (ra, a.offset) < (rb, b.offset)
        }.map { $0.element }
    }

    // MARK: testo per il server

    /// Il testo da mandare all'anteprima, come se fosse incollato: colonne separate da tabulazioni, il nome della squadra su
    /// una riga, sotto un giocatore per riga «ruolo, nome, squadra di Serie A, prezzo», poi i crediti rimasti.
    static func testo(_ squadre: [SquadraScreenshot]) -> String {
        var righe = ["Ruolo\tCalciatore\tSquadra\tCosto"]
        for s in squadre where !s.righe.isEmpty {
            righe.append("")
            righe.append(pulisci(s.nome))
            for r in s.righe {
                righe.append([r.ruolo ?? "", pulisci(r.nome), r.club.map(pulisci) ?? "", r.costo.map(String.init) ?? ""].joined(separator: "\t"))
            }
            if let c = s.crediti { righe.append("Crediti residui\t\(c)") }
        }
        return righe.joined(separator: "\n") + "\n"
    }

    /// Cosa dire all'utente dopo la lettura (frasi brevi, una per problema).
    static func avvisi(_ squadre: [SquadraScreenshot], scartate: Int) -> [String] {
        var avvisi: [String] = []
        if scartate > 0 {
            avvisi.append(scartate == 1
                ? "1 foto non sembra la rosa di una squadra di Leghe: l'ho saltata."
                : "\(scartate) foto non sembrano la rosa di una squadra di Leghe: le ho saltate.")
        }
        for s in squadre {
            if s.illeggibili > 0 {
                avvisi.append(s.illeggibili == 1
                    ? "«\(s.nome)»: in 1 riga non leggo il nome. Controlla nell'anteprima chi manca."
                    : "«\(s.nome)»: in \(s.illeggibili) righe non leggo il nome. Controlla nell'anteprima chi manca.")
            }
            let senzaPrezzo = s.righe.filter { $0.costo == nil }.count
            if senzaPrezzo > 0 {
                avvisi.append("«\(s.nome)»: non leggo il prezzo di \(Formato.giocatori(senzaPrezzo)).")
            }
        }
        return avvisi
    }

    /// «Ho letto 2 squadre e 50 giocatori da 6 foto.»
    static func riassunto(_ squadre: [SquadraScreenshot]) -> String {
        let piene = squadre.filter { !$0.righe.isEmpty }
        let giocatori = piene.reduce(0) { $0 + $1.righe.count }
        let foto = piene.reduce(0) { $0 + $1.foto }
        return "Ho letto \(Formato.plurale(piene.count, "squadra", "squadre")) e \(Formato.giocatori(giocatori)) da \(Formato.plurale(foto, "foto", "foto"))."
    }
}
