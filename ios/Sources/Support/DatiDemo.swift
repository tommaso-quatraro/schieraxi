import Foundation

// Dati finti ma verosimili per la modalità demo (argomento di lancio `-DEMO`, vedi Demo.swift): una lega da 8 squadre,
// la mia rosa da 25, giornata 11 con partite, avvisi, mercato, scambi, regole, stato dei dati. Le date sono relative a "adesso":
// la prima partita è sempre tra qualche ora, così il conto alla rovescia di Oggi si vede anche se lo scatto è fatto un altro giorno.

extension FinteServer {
    /// Server della modalità demo (costruito una volta sola all'avvio).
    static let demo: FinteServer = FinteServer(risposte: DatiDemo.risposte(adesso: Date()), binari: { DemoImmagini.dati(per: $0) })

    /// Le fotografie delle fasi della giornata (`-DEMO_SCHERMATA oggi-in-corso` e `oggi-finita`): la stessa demo, con Oggi durante
    /// e dopo la giornata. Ognuna ha il suo indirizzo finto, così la copia salvata di Oggi non si mescola. Nil per le altre schermate.
    static func demoFase(_ schermata: String?) -> FinteServer? {
        let adesso = Date()
        var server = FinteServer.demo
        switch schermata ?? "" {
        case "oggi-in-corso":
            server.risposte["/api/oggi"] = DatiDemo.oggiInCorso(adesso: adesso)
            server.risposte["/api/live"] = DatiDemo.live(adesso: adesso, giornataInCorso: true)
            server.indirizzoFinto = "https://finto-giornata-in-corso.invalid"
        case "oggi-finita":
            server.risposte["/api/oggi"] = DatiDemo.oggiFinita(adesso: adesso)
            server.risposte["/api/live"] = "{\"in_corso\": 0, \"partite\": []}"
            server.indirizzoFinto = "https://finto-giornata-finita.invalid"
        case "formazione-chiusa":
            // la giornata chiusa (dopo la scadenza): la formazione salvata in sola lettura
            server.risposte["/api/formazione"] = DatiDemo.formazione(iniziata: true)
            server.risposte["/api/scelta"] = DatiDemo.sceltaSalvata(adesso: adesso)
            server.indirizzoFinto = "https://finto-formazione-chiusa.invalid"
        case "formazione-salvata":
            // la Formazione con la tua scelta già salvata (riga «La tua formazione è salvata (oggi alle …)»)
            server.risposte["/api/scelta"] = DatiDemo.sceltaSalvata(adesso: adesso)
            server.indirizzoFinto = "https://finto-scelta-salvata.invalid"
        case "oggi-rinvio":
            server.risposte["/api/oggi"] = DatiDemo.oggiRinvio(adesso: adesso)
            server.indirizzoFinto = "https://finto-partita-rinviata.invalid"
        case "oggi-finita-recupero":
            server.risposte["/api/oggi"] = DatiDemo.oggiFinita(adesso: adesso, recupero: true)
            server.risposte["/api/live"] = "{\"in_corso\": 0, \"partite\": []}"
            server.indirizzoFinto = "https://finto-recupero-da-giocare.invalid"
        default:
            return nil
        }
        return server
    }
}

private struct Calciatore {
    let id: Int
    let nome: String
    let ruolo: String
    let squadra: String
    var costo: Int = 0
    var quotazione: Int = 0
    var pVoto: Double = 0.85
    var punti: Double = 5.5
    var dubbio: Bool = false
    var diffidato: Bool = false
    var assente: Bool = false
}

/// Un calciatore con tutti i valori scritti a mano.
private func cal(_ id: Int, _ nome: String, _ ruolo: String, _ squadra: String, costo: Int, pVoto: Double, punti: Double,
                 dubbio: Bool = false, diffidato: Bool = false, assente: Bool = false) -> Calciatore {
    Calciatore(id: id, nome: nome, ruolo: ruolo, squadra: squadra, costo: costo, quotazione: 0, pVoto: pVoto, punti: punti,
               dubbio: dubbio, diffidato: diffidato, assente: assente)
}

/// Un calciatore di contorno: previsione ricavata dall'id, così non serve scriverla.
private func alt(_ id: Int, _ nome: String, _ ruolo: String, _ squadra: String) -> Calciatore {
    let punti = 4.6 + Double((id * 7) % 23) / 10.0
    let pVoto = 0.70 + Double((id * 3) % 27) / 100.0
    return Calciatore(id: id, nome: nome, ruolo: ruolo, squadra: squadra, costo: 4 + (id * 7) % 26, quotazione: 0, pVoto: pVoto, punti: punti)
}

private enum DatiDemo {
    static let nomeMia = "Schiera FC"
    static let altreSquadre = ["Real Madrink", "Atletico Divano", "Dinamo Pizza", "AC Pigra", "Inter Nos", "Borgo Rossi United",
                               "Gli Amici del Bar Sport Centrale"]
    static let giornata = 11
    static let giornate = [11, 12, 13, 14, 15]

    // MARK: - Calciatori

    /// La mia rosa (25): 3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti.
    static let miaRosa: [Calciatore] = [
        cal(101, "Ivo Sorvani", "P", "inter", costo: 12, pVoto: 0.98, punti: 6.1),
        cal(102, "Milo Magrenti", "P", "milan", costo: 22, pVoto: 0.97, punti: 5.8),
        cal(103, "Marcello Carsetti", "P", "atalanta", costo: 14, pVoto: 0.96, punti: 5.6),
        cal(104, "Alvise Bastrani", "D", "inter", costo: 28, pVoto: 0.96, punti: 6.4, diffidato: true),
        cal(105, "Fabio Dimarzi", "D", "inter", costo: 31, pVoto: 0.90, punti: 6.9),
        cal(106, "Glauco Brevisi", "D", "juventus", costo: 20, pVoto: 0.93, punti: 6.0),
        cal(107, "Aurelio Buonvicini", "D", "napoli", costo: 19, pVoto: 0.92, punti: 5.9),
        cal(108, "Gianni Di Corvara", "D", "napoli", costo: 17, pVoto: 0.94, punti: 6.2),
        cal(109, "Rolf Gostein", "D", "fiorentina", costo: 9, pVoto: 0.0, punti: 0.0, assente: true),
        cal(110, "Adriano Cambrisi", "D", "juventus", costo: 15, pVoto: 0.85, punti: 5.7),
        cal(111, "Ewan Ndolani", "D", "roma", costo: 8, pVoto: 0.78, punti: 5.2),
        cal(112, "Nestore Barlesi", "C", "inter", costo: 34, pVoto: 0.95, punti: 7.0),
        cal(113, "Hamit Çalvaroğlu", "C", "inter", costo: 36, pVoto: 0.93, punti: 7.2),
        cal(114, "Teo Kloosmeijer", "C", "juventus", costo: 21, pVoto: 0.88, punti: 6.3),
        cal(115, "Cesare Pulinski", "C", "milan", costo: 38, pVoto: 0.91, punti: 6.8),
        cal(116, "Stanko Lobrenka", "C", "napoli", costo: 10, pVoto: 0.90, punti: 5.6),
        cal(117, "Tarek Reimvaldt", "C", "milan", costo: 24, pVoto: 0.89, punti: 6.2),
        cal(118, "Nereo Fagiani", "C", "fiorentina", costo: 6, pVoto: 0.0, punti: 0.0, assente: true),
        cal(119, "Moussa Kerabo", "C", "roma", costo: 13, pVoto: 0.84, punti: 5.5),
        cal(120, "Leonel Marténi", "A", "inter", costo: 80, pVoto: 0.62, punti: 7.9, dubbio: true),
        cal(121, "Marvin Thorvan", "A", "inter", costo: 52, pVoto: 0.90, punti: 7.1),
        cal(122, "Adebayo Lorkman", "A", "atalanta", costo: 41, pVoto: 0.87, punti: 7.0),
        cal(123, "Renato Lemão", "A", "milan", costo: 45, pVoto: 0.88, punti: 6.9),
        cal(124, "Darko Vlasenić", "A", "juventus", costo: 33, pVoto: 0.65, punti: 5.4, dubbio: true),
        cal(125, "Mosè Kervan", "A", "fiorentina", costo: 18, pVoto: 0.82, punti: 5.8),
    ]

    /// Svincolati (non sono in nessuna squadra della lega).
    static let liberi: [Calciatore] = [
        cal(201, "Aldo Pinarotti", "A", "sassuolo", costo: 0, pVoto: 0.86, punti: 6.4),
        cal(202, "Marcello Polinardo", "C", "napoli", costo: 0, pVoto: 0.81, punti: 6.0),
        cal(203, "Mauro Retalli", "A", "genoa", costo: 0, pVoto: 0.90, punti: 6.9),
        cal(204, "Nenad Krslić", "A", "lecce", costo: 0, pVoto: 0.88, punti: 6.2),
        cal(205, "Marzio Zaviani", "C", "lazio", costo: 0, pVoto: 0.89, punti: 6.1),
        cal(206, "Aron Mercati", "P", "napoli", costo: 0, pVoto: 0.96, punti: 5.7),
        cal(207, "Manuel Brisciani", "C", "atalanta", costo: 0, pVoto: 0.83, punti: 5.6),
        cal(208, "Furio Gattoni", "D", "juventus", costo: 0, pVoto: 0.84, punti: 5.5),
        cal(209, "Pino Comurzi", "D", "fiorentina", costo: 0, pVoto: 0.88, punti: 5.4),
        cal(210, "Nando Rovalli", "C", "lazio", costo: 0, pVoto: 0.90, punti: 5.8),
        cal(211, "Egon Audrelli", "P", "cremonese", costo: 0, pVoto: 0.95, punti: 5.1),
        cal(212, "Ludovico Lucarni", "A", "udinese", costo: 0, pVoto: 0.79, punti: 5.9),
        cal(213, "Michele Gabbrosi", "D", "milan", costo: 0, pVoto: 0.66, punti: 5.0, dubbio: true),
        cal(214, "Aksel Sandemaker", "C", "milan", costo: 0, pVoto: 0.82, punti: 5.7),
        cal(215, "Gilberto Mancarini", "D", "roma", costo: 0, pVoto: 0.86, punti: 5.5),
    ]

    /// Calciatori delle altre squadre della lega.
    static let altri: [Calciatore] = [
        alt(301, "Walter Falcherini", "P", "lecce"), alt(302, "Massimo Silverni", "P", "udinese"),
        alt(303, "Mirco Di Gradella", "P", "juventus"), alt(304, "Enea Caprisi", "P", "cagliari"),
        alt(305, "Nelson Morlani", "D", "atalanta"), alt(306, "Massimo Darvini", "D", "inter"),
        alt(307, "Leone Pellari", "D", "lazio"), alt(308, "Duilio Calbresi", "D", "bologna"),
        alt(309, "Stijn Beekmans", "D", "bologna"), alt(310, "Mauro Gilbaro", "D", "lazio"),
        alt(311, "Patrizio Mazzorchi", "D", "napoli"), alt(312, "Livio Spinarola", "D", "napoli"),
        alt(313, "Mats de Valk", "C", "atalanta"), alt(314, "Edvanson", "C", "atalanta"),
        alt(315, "Walden McKerrin", "C", "juventus"), alt(316, "Mauro Locardi", "C", "juventus"),
        alt(317, "Mathis Guermadi", "C", "lazio"), alt(318, "Dino Cavaldi", "C", "lazio"),
        alt(319, "Lyle Fernshaw", "C", "bologna"), alt(320, "Reto Fraunler", "C", "bologna"),
        alt(321, "Sandy McTarran", "C", "napoli"), alt(322, "Koen De Vlaam", "C", "napoli"),
        alt(323, "Matías Sorlé", "C", "roma"), alt(324, "Lamberto Pelozzi", "C", "roma"),
        alt(325, "Kaan Yurdız", "A", "juventus"), alt(326, "Joel Davenant", "A", "juventus"),
        alt(327, "Rolando Lumbaku", "A", "napoli"), alt(328, "Pablo Dobrala", "A", "roma"),
        alt(329, "Artur Dovrenko", "A", "roma"), alt(330, "Santiago Castrel", "A", "bologna"),
        alt(331, "Nils Pazor", "A", "como"), alt(332, "Pelayo", "A", "lazio"),
        alt(333, "Giacomo Scalmana", "A", "atalanta"), alt(334, "Alvar Hrafnsson", "A", "fiorentina"),
        alt(335, "Rune Højvang", "A", "napoli"), alt(336, "Lorenzo Verdi", "A", "roma"),
    ]

    static var tutti: [Calciatore] { miaRosa + liberi + altri }

    static func calciatore(_ id: Int) -> Calciatore {
        tutti.first { $0.id == id } ?? miaRosa[0]
    }

    /// Rosa di un'altra squadra (indice 0...6): 3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti, ruotando la scelta.
    static func rosaAltra(_ k: Int) -> [Calciatore] {
        func prendi(_ ruolo: String, _ n: Int) -> [Calciatore] {
            let lista = altri.filter { $0.ruolo == ruolo }
            return (0..<n).map { lista[($0 + k * 2) % lista.count] }
        }
        return prendi("P", 3) + prendi("D", 8) + prendi("C", 8) + prendi("A", 6)
    }

    static func proprietario(_ id: Int) -> String? {
        if miaRosa.contains(where: { $0.id == id }) { return nomeMia }
        if id >= 300 { return altreSquadre[id % altreSquadre.count] }
        return nil
    }

    // MARK: - Partite

    static let incontri: [(casa: String, trasferta: String)] = [
        ("inter", "roma"), ("milan", "juventus"), ("napoli", "atalanta"), ("lazio", "fiorentina"), ("bologna", "torino"),
        ("genoa", "como"), ("udinese", "parma"), ("cagliari", "verona"), ("lecce", "sassuolo"), ("pisa", "cremonese"),
    ]

    /// Dal più forte al più debole (serve per la difficoltà del calendario).
    static let forza = ["inter", "napoli", "milan", "juventus", "atalanta", "roma", "bologna", "lazio", "fiorentina", "como",
                        "torino", "udinese", "genoa", "parma", "cagliari", "verona", "lecce", "sassuolo", "pisa", "cremonese"]

    static func avversario(di squadra: String) -> (nome: String, inCasa: Bool)? {
        for i in incontri {
            if i.casa == squadra { return (i.trasferta, true) }
            if i.trasferta == squadra { return (i.casa, false) }
        }
        return nil
    }

    // MARK: - Date

    /// Il calcio d'inizio cade su un quarto d'ora (18:00, 18:15...), come le partite vere: mai «18:57».
    static func quartoDOra(_ data: Date) -> Date {
        let quarto = 15.0 * 60
        return Date(timeIntervalSinceReferenceDate: (data.timeIntervalSinceReferenceDate / quarto).rounded(.up) * quarto)
    }

    static func formatta(_ data: Date, _ formato: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = formato
        return f.string(from: data)
    }

    // MARK: - JSON

    static func json(_ oggetto: Any) -> String {
        let dati = (try? JSONSerialization.data(withJSONObject: oggetto, options: [.sortedKeys])) ?? Data("{}".utf8)
        return String(decoding: dati, as: UTF8.self)
    }

    /// Un giocatore come lo manda il server per formazioni, classifiche e avvisi.
    static func giocatore(_ p: Calciatore, conAvversario: Bool = true, conProprietario: Bool = false) -> [String: Any] {
        var d: [String: Any] = [
            "id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra,
            "p_voto": p.assente ? 0.0 : p.pVoto,
            "punti_attesi": p.assente ? 0.0 : p.punti,
            "gol_attesi": golAttesi(p),
            "assist_attesi": assistAttesi(p),
        ]
        d["fv_atteso"] = p.assente ? 0.0 : p.punti + 0.6 + (p.ruolo == "A" ? 0.5 : 0)
        d["voto_atteso"] = 5.9 + (p.punti - 5.0) / 8.0
        d["porta_inviolata"] = p.ruolo == "P" ? 0.34 : 0.0
        d["p_gol"] = min(0.6, golAttesi(p) * 0.85)
        d["p_assist"] = min(0.4, assistAttesi(p) * 0.9)
        d["p_giallo"] = 0.11
        d["p_rosso"] = 0.01
        d["quota_titolare"] = p.assente ? 0.0 : p.pVoto
        d["indice"] = p.assente ? 0 : min(100, max(1, Int(((p.punti - 4.6) / 3.4 * 100).rounded())))
        d["difficolta"] = difficolta(di: p.squadra)
        d["gol_squadra"] = 1.8
        d["gol_avversario"] = 1.2
        d["data_partita"] = formatta(quartoDOra(riferimento.addingTimeInterval(7 * 3600)), "yyyy-MM-dd HH:mm")
        // titolarità: come nelle probabili formazioni
        if p.assente {
            d["titolarita"] = "fuori"; d["stato"] = "infortunato"; d["percentuale"] = 0.0; d["motivi"] = ["infortunato"]
        } else if p.dubbio {
            // in dubbio: la probabilità delle probabili è la stessa di «gioca N%» (una sola percentuale, coerente ovunque).
            // Come il server: il motivo della titolarità e l'etichetta pronta «In dubbio · gioca N%» (`fanta/etichette.py`).
            d["titolarita"] = "ballottaggio"; d["stato"] = "titolare"; d["percentuale"] = (p.pVoto * 100).rounded(); d["motivi"] = ["titolare in ballottaggio"]
            d["etichetta"] = ["codice": "in_dubbio", "testo": DubbioRiassunto.inDubbio(p.pVoto), "tono": "attenzione"]
        } else if p.pVoto < 0.75 {
            d["titolarita"] = "improbabile"; d["stato"] = "panchina"; d["percentuale"] = (p.pVoto * 100).rounded(); d["motivi"] = ["parte dalla panchina"]
        } else {
            d["titolarita"] = "titolare"; d["stato"] = "titolare"; d["percentuale"] = 90.0; d["motivi"] = ["titolare"]
        }
        d["quotazione"] = quotazione(p)
        if conAvversario, let a = avversario(di: p.squadra) {
            d["avversario"] = a.nome
            d["in_casa"] = a.inCasa
        }
        if p.dubbio { d["dubbio"] = true }
        if p.diffidato { d["diffidato"] = true }
        if p.assente { d["assente"] = true }
        if conProprietario, let o = proprietario(p.id) { d["proprietario"] = o }
        if !p.assente { perche(p, in: &d) }
        return d
    }

    /// «Perché questo numero» come lo manda il server (`perche_numero`, `fv_atteso_medio_ruolo`): stesse frasi del server,
    /// effetti in fantavoti rispetto al giocatore medio del ruolo, al massimo tre motivi.
    static func perche(_ p: Calciatore, in d: inout [String: Any]) {
        let fv = p.punti + 0.6 + (p.ruolo == "A" ? 0.5 : 0)
        let medio = ["P": 6.0, "D": 6.1, "C": 6.4, "A": 7.0][p.ruolo] ?? 6.3
        let casa = avversario(di: p.squadra)?.inCasa ?? true
        let partita = Double(3 - difficolta(di: p.squadra)) * 0.15
        let resto = fv - medio - partita
        let arrotonda: (Double) -> Double = { ($0 * 100).rounded() / 100 }
        var numerici: [(String, String, Double)] = [
            ("partita", partita > 0 ? (casa ? "partita favorevole in casa" : "partita favorevole in trasferta")
                                    : (casa ? "partita difficile in casa" : "partita difficile in trasferta"), partita),
            ("voti", resto > 0 ? "voti sopra la media del ruolo" : "voti sotto la media del ruolo", resto * 0.4),
        ]
        if p.ruolo == "P" {
            numerici.append(("porta", resto > 0 ? "buone chance di porta inviolata (34%)" : "poche chance di porta inviolata (34%)", resto * 0.6))
        } else {
            let pGol = Int((min(0.6, golAttesi(p) * 0.85) * 100).rounded())
            numerici.append(("gol", resto > 0 ? "segna più della media del ruolo (\(pGol)% di segnare)" : "segna meno della media del ruolo", resto * 0.6))
        }
        var motivi: [[String: Any]] = []
        if p.dubbio {
            motivi.append(["chiave": "gioca", "testo": "gioca il \(Int((p.pVoto * 100).rounded()))%: dubbio", "effetto": NSNull()])
        } else if p.pVoto < 0.8 {
            let pct = Int((p.pVoto * 100).rounded())
            motivi.append(["chiave": "gioca", "testo": "gioca il \(pct)%: " + (p.pVoto < 0.5 ? "probabile panchina" : "dubbio"), "effetto": NSNull()])
        }
        let scelti = numerici.filter { abs($0.2) >= 0.08 }.sorted { abs($0.2) > abs($1.2) }.prefix(3 - motivi.count)
        motivi += scelti.map { t -> [String: Any] in ["chiave": t.0, "testo": t.1, "effetto": arrotonda(t.2)] }
        d["perche_numero"] = motivi
        d["fv_atteso_medio_ruolo"] = medio
    }

    /// Il momento di riferimento della demo (per le date delle partite nelle schede).
    static var riferimento = Date()

    /// Difficoltà della prossima partita (1 facile ... 5 dura): dipende dalla forza dell'avversario.
    static func difficolta(di squadra: String) -> Int {
        guard let a = avversario(di: squadra), let i = forza.firstIndex(of: a.nome) else { return 3 }
        return 1 + Int((Double(forza.count - 1 - i) / Double(forza.count - 1) * 4.0).rounded())
    }

    static func golAttesi(_ p: Calciatore) -> Double {
        if p.assente { return 0 }
        switch p.ruolo {
        case "A": return p.punti / 15.0
        case "C": return p.punti / 35.0
        case "D": return p.punti / 80.0
        default: return 0
        }
    }

    static func assistAttesi(_ p: Calciatore) -> Double {
        if p.assente || p.ruolo == "P" { return 0 }
        return p.punti / 45.0
    }

    static func quotazione(_ p: Calciatore) -> Int {
        p.quotazione > 0 ? p.quotazione : 3 + Int(p.punti * 2.0) + (p.id % 5)
    }

    /// Giocatore breve (scambi e mercato).
    static func breve(_ id: Int) -> [String: Any] {
        let p = calciatore(id)
        return ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra, "quotazione": quotazione(p)]
    }

    static func rigaRosa(_ p: Calciatore) -> [String: Any] {
        ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra, "squadra_slug": p.squadra,
         "costo": p.costo > 0 ? p.costo : 4 + p.id % 20, "quotazione": quotazione(p), "previsione": giocatore(p)]
    }

    static func schedaGiocatore(_ p: Calciatore) -> [String: Any] {
        let presenze: Int = 7 + p.id % 4
        let media: Double = 5.7 + p.punti / 12.0
        let q: Int = quotazione(p)
        var gol: Int = p.id % 2
        if p.ruolo == "A" { gol = 3 + p.id % 4 }
        if p.ruolo == "C" { gol = 1 + p.id % 3 }
        let assist: Int = p.ruolo == "P" ? 0 : p.id % 4
        let espulsioni: Int = p.id % 11 == 0 ? 1 : 0

        var anagrafica: [String: Any] = ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra.uppercased(), "squadra_slug": p.squadra]
        anagrafica["quotazione"] = q
        anagrafica["quotazione_iniziale"] = q - 1
        anagrafica["fvm"] = q * 3 / 2

        var stagione: [String: Any] = ["presenze": presenze, "con_voto": presenze - 1, "giornate_giocate_serie_a": 10,
                                       "gol_subiti": p.ruolo == "P" ? 9 : 0, "rig_segnati": 0, "rig_parati": p.ruolo == "P" ? 1 : 0]
        stagione["media_voto"] = media
        stagione["fantamedia"] = media + p.punti / 25.0
        stagione["gol"] = gol
        stagione["assist"] = assist
        stagione["ammonizioni"] = p.id % 3
        stagione["espulsioni"] = espulsioni

        var d: [String: Any] = [:]
        d["calciatore"] = anagrafica
        d["stagione"] = stagione
        var previsione = giocatore(p)
        previsione["giornata"] = giornata
        d["previsione"] = previsione
        d["voti"] = voti(p)
        d["avanzate"] = ["minuti": 560 + p.id % 200, "xg": 3.4 + Double(p.id % 5) * 0.7, "xa": 1.2 + Double(p.id % 3) * 0.4, "tiri": 22 + p.id % 9,
                         "passaggi_chiave": 9 + p.id % 7, "rigori_calciati": p.id % 4 == 0 ? 2 : 0, "punizioni": p.id % 5 == 0 ? 3 : 0,
                         "per_90": ["xg": 0.52, "xa": 0.18, "tiri": 3.1],
                         "stagioni_precedenti": [["stagione": "2025-26", "minuti": 2400, "gol": 11, "xg": 10.2, "assist": 4, "xa": 3.6]]] as [String: Any]
        d["rendimento"] = ["sovra_rendimento": p.id % 2 == 0 ? 0.42 : -0.38, "gol_meno_xg": p.id % 2 == 0 ? 0.9 : -1.1, "assist_meno_xa": 0.2] as [String: Any]
        if let o = proprietario(p.id) { d["proprietario"] = o }
        return d
    }

    /// Voti e fantavoti delle ultime giornate: qualcuna senza voto (partita saltata), per vedere anche i «sv» nel grafico.
    static func voti(_ p: Calciatore) -> [[String: Any]] {
        var elenco: [[String: Any]] = []
        for (k, g) in [3, 4, 5, 6, 7, 8, 9, 10].enumerated() {
            if (p.id + k) % 7 == 0 { elenco.append(["giornata": g]); continue }
            let voto = 5.5 + Double((p.id * (k + 3)) % 15) / 10.0
            let bonus = p.ruolo == "A" && (p.id + k) % 3 == 0 ? 3.0 : (k % 4 == 0 ? 1.0 : 0.0)
            elenco.append(["giornata": g, "voto": voto, "fv": voto + bonus - (k % 5 == 0 ? 0.5 : 0), "gol": bonus >= 3 ? 1 : 0, "assist": 0])
        }
        return elenco
    }

    // MARK: - Formazione

    struct Modulo {
        let nome: String
        let titolari: [Int]
    }

    static let moduli: [Modulo] = [
        Modulo(nome: "3-4-3", titolari: [101, 104, 106, 107, 112, 113, 114, 115, 120, 121, 122]),
        Modulo(nome: "4-3-3", titolari: [101, 104, 105, 106, 107, 112, 113, 115, 120, 121, 122]),
        Modulo(nome: "3-5-2", titolari: [101, 104, 106, 107, 112, 113, 114, 115, 116, 120, 121]),
    ]

    /// La panchina (7): un portiere e i sei migliori disponibili tra gli altri.
    static func panchina(per titolari: [Int]) -> [Int] {
        let fuori = miaRosa.filter { !titolari.contains($0.id) && !$0.assente }
        var scelti: [Calciatore] = []
        if let portiere = fuori.first(where: { $0.ruolo == "P" }) { scelti.append(portiere) }
        let resto: [Calciatore] = fuori.filter { $0.ruolo != "P" }.sorted { $0.punti > $1.punti }
        scelti.append(contentsOf: resto.prefix(6))
        return scelti.map { $0.id }
    }

    static func punteggio(_ ids: [Int]) -> Double {
        ids.reduce(0.0) { $0 + calciatore($1).punti }
    }

    /// La fascia dei punti attesi, come la manda il server: da circa -8 a +8,5 attorno ai punti attesi, 8 volte su 10.
    static func fascia(_ attesi: Double, indicativo: Bool = true) -> [String: Any] {
        ["basso": attesi - 8, "alto": attesi + 8.5, "confidenza": 0.8, "indicativo": indicativo]
    }

    static func formazione(iniziata: Bool = false) -> String {
        let base = moduli[0]
        let ids = base.titolari
        let bench = panchina(per: ids)
        let titolari = ids.map { giocatore(calciatore($0)) }
        let panchinaJSON = bench.map { giocatore(calciatore($0)) }
        // gli stili come li manda il server (nomi e descrizioni di LIVELLI_RISCHIO): Sicura, Equilibrata (consigliata), Rischiosa
        var livelli: [[String: Any]] = []
        for r in [-1, 0, 1] {
            let nome = StileFormazione.nomi[r] ?? ""
            let extra = Double(r) * 0.6
            var elenco: [[String: Any]] = []
            for m in moduli {
                elenco.append(["modulo": m.nome, "punteggio_atteso": punteggio(m.titolari) + extra,
                               "titolari": m.titolari, "panchina": panchina(per: m.titolari),
                               "dev": 4.2, "intervallo": fascia(punteggio(m.titolari) + extra)])
            }
            livelli.append(["rischio": r, "stile": r, "nome": nome, "descrizione": StileFormazione.descrizione(r),
                            "modulo": base.nome, "punteggio_atteso": punteggio(ids) + extra, "moduli": elenco,
                            "intervallo": fascia(punteggio(ids) + extra)])
        }
        var schede: [String: Any] = [:]
        for p in miaRosa { schede[String(p.id)] = giocatore(p) }
        return json([
            "squadra": nomeMia, "giornata": giornata, "giornata_lega": giornata - 3, "modulo": base.nome, "punteggio_atteso": punteggio(ids),
            "con_probabili": false, "titolari": titolari, "panchina": panchinaJSON, "livelli": livelli, "schede": schede, "stile_consigliato": 0,
            "dev": 4.2, "intervallo": fascia(punteggio(ids)), "iniziata": iniziata,
        ])
    }

    /// La scelta salvata della giornata (gli undici del primo modulo), salvata un'ora fa (ora italiana, come il server).
    static func sceltaSalvata(adesso: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return json(["titolari": moduli[0].titolari, "modulo": moduli[0].nome, "salvata": f.string(from: adesso.addingTimeInterval(-3600)),
                     "tipo": "manuale"])
    }

    static func valutazione() -> String {
        let ids = moduli[0].titolari
        let punti = punteggio(ids)
        return json(["modulo": "3-4-3", "punteggio_atteso": punti - 1.2, "dev": 3.1, "intervallo": fascia(punti - 1.2), "panchina": panchina(per: ids),
                     "differenza": -1.2, "consigliata": punti])
    }

    // MARK: - Oggi

    static func oggi(adesso: Date) -> String { json(oggiDati(adesso: adesso)) }

    static func oggiDati(adesso: Date) -> [String: Any] {
        let inizio = quartoDOra(adesso.addingTimeInterval(7 * 3600))
        let ids = moduli[0].titolari
        // minuti di distanza dalla prima partita
        let scarti: [Double] = [0, 135, 1260, 1395, 1530, 1650, 2700, 2835, 2835, 2970]
        var partite: [[String: Any]] = []
        for (i, m) in incontri.enumerated() {
            partite.append(["data": formatta(inizio.addingTimeInterval(scarti[i] * 60), "yyyy-MM-dd HH:mm"),
                            "casa": m.casa, "trasferta": m.trasferta, "giocata": false])
        }
        let avvisi: [[String: Any]] = [
            ["id": 120, "nome": "Leonel Marténi", "ruolo": "A", "squadra": "inter", "tipo": "dubbio", "p_voto": 0.62,
             "nota": "Affaticamento muscolare, si decide all'ultimo", "in_formazione": true],
            ["id": 104, "nome": "Alvise Bastrani", "ruolo": "D", "squadra": "inter", "tipo": "diffidato",
             "nota": "Un'ammonizione alla squalifica", "in_formazione": true],
            ["id": 109, "nome": "Rolf Gostein", "ruolo": "D", "squadra": "fiorentina", "tipo": "squalificato",
             "nota": "Una giornata", "in_formazione": false],
            ["id": 118, "nome": "Nereo Fagiani", "ruolo": "C", "squadra": "fiorentina", "tipo": "infortunato",
             "nota": "Lesione al polpaccio, rientro a dicembre", "in_formazione": false],
            ["id": 124, "nome": "Darko Vlasenić", "ruolo": "A", "squadra": "juventus", "tipo": "dubbio", "p_voto": 0.65,
             "nota": "Botta alla caviglia", "in_formazione": false],
        ]
        let migliori = ids.map { calciatore($0) }.sorted { $0.punti > $1.punti }.prefix(5).map { giocatore($0) }
        var mieiTitolari: [String: [[String: Any]]] = [:]
        for id in ids {
            let c = calciatore(id)
            mieiTitolari[c.squadra, default: []].append(["id": c.id, "nome": c.nome, "ruolo": c.ruolo])
        }
        return [
            "miei_titolari": mieiTitolari, "fase": "prima",
            "giornata": giornata, "inizio": formatta(inizio, "yyyy-MM-dd HH:mm"),
            "scadenza": formatta(inizio.addingTimeInterval(-30 * 60), "yyyy-MM-dd HH:mm"), "minuti_scadenza": 30, "giornata_lega": giornata - 3,
            "iniziata": false, "con_probabili": true,
            "probabili": ["aggiornate_il": "2026-11-08 09:05", "minuti_fa": 480, "eta": "8 ore fa", "testo": "Probabili aggiornate alle 09:05",
                          "vecchie": true, "avviso": "Le probabili hanno 8 ore: ricontrolla prima del fischio."],
            "formazione": ["modulo": "3-4-3", "punteggio_atteso": punteggio(ids), "squadra": nomeMia,
                           "dev": 4.2, "intervallo": fascia(punteggio(ids)), "tua_scelta": true],
            "avvisi": avvisi, "migliori": migliori, "partite": partite,
            "da_fare": [voceDubbio, voceSvincolato, voceRoseVecchie, voceDiario, voceBackup],
        ]
    }

    // MARK: - «Da fare» come lo scrive il server
    // Testi e pulsanti sono quelli di `fanta/frasi.py` (chiavi `dafare.*`), riempiti con i dati della demo;
    // `DemoDaFareTests` li confronta con il catalogo del server.

    /// Marténi, titolare con il 62% di giocare (`pVoto` della demo): il miglior ricambio libero del ruolo è Lemão.
    static var voceDubbio: [String: Any] {
        ["id": "dubbio-120", "tipo": "dubbio", "testo": "Leonel Marténi è in dubbio (62% di giocare). Meglio Renato Lemão.", "priorita": 1,
         "azione": "Sostituisci", "destinazione": ["scheda": "formazione", "sezione": "formazione", "link": "schieraxi://formazione"]]
    }

    /// Il primo cambio di `mercato()`: Retalli (libero) al posto di Vlasenić, 3,4 punti in più.
    static var voceSvincolato: [String: Any] {
        ["id": "svincolato-203", "tipo": "svincolato",
         "testo": "Mauro Retalli (libero) al posto di Darko Vlasenić: circa 3,4 punti in più.", "priorita": 2,
         "azione": "Vedi", "destinazione": ["sezione": "mercato", "link": "schieraxi://mercato"]]
    }

    /// Rose ferme da 5 giorni dopo una giornata giocata.
    static var voceRoseVecchie: [String: Any] {
        ["id": "rose", "tipo": "rose", "testo": "Le rose non sono aggiornate da 5 giorni e nel frattempo si è giocata una giornata.",
         "priorita": 2, "azione": "Aggiorna le rose", "destinazione": ["sezione": "lega", "link": "schieraxi://lega"]]
    }

    /// L'ultima giornata finita: il server la numera per la lega (la 7, la testata dice «Giornata 8 di lega»), mentre `id`,
    /// `giornata` e `destinazione.giornata` sono i numeri della Serie A (la 10), come in `_diario` di `fanta/da_fare.py`.
    static var voceDiario: [String: Any] {
        let serieA = giornata - 1
        let lega = (giornata - 3) - 1
        return ["id": "diario:\(serieA)", "tipo": "diario", "testo": "La giornata \(lega) è finita: dimmi se hai schierato la consigliata.",
                "priorita": 3, "azione": "Ho schierato la consigliata",
                "destinazione": ["scheda": "lega", "sezione": "diario", "link": "schieraxi://lega/diario", "giornata": serieA] as [String: Any],
                "giornata": serieA]
    }

    /// Una voce che il server non manda più: l'app la nasconde (la copia di sicurezza non si fa dall'app). Resta per provarlo.
    static var voceBackup: [String: Any] {
        ["id": "backup", "tipo": "backup", "testo": "Fai una copia di sicurezza dei tuoi dati", "priorita": 3,
         "azione": "Apri", "destinazione": ["sezione": "lega", "link": "schieraxi://lega"]]
    }

    // MARK: - Oggi durante e dopo la giornata (fotografie `oggi-in-corso` e `oggi-finita`)

    /// Fase `in_corso`: scadenza passata da un'ora; Inter-Roma finita con i voti, Milan-Juventus e Lazio-Fiorentina in corso,
    /// il resto da giocare. Un cambio già fatto (Bastrani senza voto, entra Dimarzi) e due probabili.
    static func oggiInCorso(adesso: Date) -> String {
        var o = oggiDati(adesso: adesso)
        let minuti: [Double] = [-130, -45, 150, -20, 240, 1290, 1425, 1560, 2700, 2835]
        let stati = ["finita", "in_corso", "da_giocare", "in_corso", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "da_giocare"]
        func data(_ m: Double) -> String { formatta(adesso.addingTimeInterval(m * 60), "yyyy-MM-dd HH:mm") }
        o["partite"] = incontri.enumerated().map { i, m in
            ["data": data(minuti[i]), "casa": m.casa, "trasferta": m.trasferta, "giocata": i == 0, "stato": stati[i]] as [String: Any]
        }
        o["fase"] = "in_corso"
        o["iniziata"] = true
        o["inizio"] = data(-130)
        o["scadenza"] = data(-160)
        o["da_fare"] = [[String: Any]]()
        // stato di ogni giocatore: (id, titolare, a punteggio, stato, fantavoto)
        let righe: [(Int, Bool, Bool, String, Double?)] = [
            (101, true, true, "fatto", 5.0), (104, true, false, "senza_voto", nil), (106, true, true, "in_corso", nil),
            (107, true, false, "da_giocare", nil), (112, true, true, "fatto", 8.0), (113, true, true, "fatto", 9.5),
            (114, true, true, "in_corso", nil), (115, true, true, "in_corso", nil), (120, true, false, "senza_voto", nil),
            (121, true, true, "fatto", 10.0), (122, true, true, "da_giocare", nil),
            (102, false, false, "in_corso", nil), (105, false, true, "fatto", 6.5), (123, false, true, "in_corso", nil),
            (108, false, false, "da_giocare", nil), (117, false, false, "in_corso", nil), (125, false, false, "in_corso", nil),
            (110, false, true, "in_corso", nil),
        ]
        let giocatori: [[String: Any]] = righe.map { r in
            let c = calciatore(r.0)
            let i = incontri.firstIndex { $0.casa == c.squadra || $0.trasferta == c.squadra } ?? 0
            return ["id": c.id, "nome": c.nome, "ruolo": c.ruolo, "squadra": c.squadra, "titolare": r.1, "a_punteggio": r.2,
                    "stato": r.3, "fantavoto": r.4.map { $0 as Any } ?? NSNull(), "data": data(minuti[i])]
        }
        func persona(_ id: Int) -> [String: Any] { let c = calciatore(id); return ["id": c.id, "nome": c.nome, "ruolo": c.ruolo] }
        o["in_corso"] = [
            "giornata": giornata, "giornata_lega": giornata - 3, "formazione_di": "tua",
            "punti_fatti": 39.0, "punti_attesi_restanti": 38.7, "punti_previsti": 77.7, "modificatore": NSNull(), "ancora_da_giocare": 6,
            "giocatori": giocatori,
            "sostituzioni": [
                ["esce": persona(104), "entra": persona(105), "certa": true, "motivo": "senza_voto"],
                ["esce": persona(120), "entra": persona(123), "certa": false, "motivo": "senza_voto"],
                ["esce": persona(107), "entra": persona(110), "certa": false, "motivo": "fuori"],
            ],
            "partite": ["in_corso": 2, "finite": 1, "da_giocare": 7, "rinviate": 0],
        ] as [String: Any]
        return json(o)
    }

    /// Fase `finita`: la giornata 11 è finita ieri, Oggi parla già della 12 (si chiude fra 4 giorni, probabili non ancora uscite).
    // MARK: - Partite rinviate (fotografie `oggi-rinvio` e `oggi-finita-recupero`)

    /// La scelta «per questa giornata» della demo: la lega aspetta il recupero.
    static func sceltaRinvio(giornata g: Int, partite: [[String: Any]] = [], miei: [[String: Any]] = []) -> [String: Any] {
        ["stagione": "2026-27", "giornata": g, "giornata_lega": g - 3, "modo": "aspetta", "valore": NSNull(), "predefinito": "aspetta",
         "eccezione": false, "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6, "partite": partite, "miei": miei]
    }

    /// Oggi prima della scadenza con l'ultima partita del turno rinviata a fine mese: il riquadro «Partita rinviata».
    static func oggiRinvio(adesso: Date) -> String {
        var o = oggiDati(adesso: adesso)
        var partite = (o["partite"] as? [[String: Any]]) ?? []
        guard let ultima = incontri.last, !partite.isEmpty else { return json(o) }
        let recupero = formatta(adesso.addingTimeInterval(20 * 86_400), "yyyy-MM-dd HH:mm")
        partite[partite.count - 1]["data"] = recupero
        partite[partite.count - 1]["stato"] = "rinviata"
        o["partite"] = partite
        let miei = moduli[0].titolari.map { calciatore($0) }.filter { [ultima.casa, ultima.trasferta].contains($0.squadra) }
            .map { ["id": $0.id, "nome": $0.nome, "ruolo": $0.ruolo, "squadra": $0.squadra] as [String: Any] }
        o["rinvio"] = sceltaRinvio(giornata: giornata, partite: [["casa": ultima.casa, "trasferta": ultima.trasferta, "data": recupero]],
                                   miei: miei)
        return json(o)
    }

    static func oggiFinita(adesso: Date, recupero: Bool = false) -> String {
        var o = oggiDati(adesso: adesso)
        let scadenza = adesso.addingTimeInterval(4 * 86_400)
        func data(_ d: Date) -> String { formatta(d, "yyyy-MM-dd HH:mm") }
        let scarti: [Double] = [0, 135, 1260, 1395, 1530, 1650, 2700, 2835, 2835, 2970]
        o["partite"] = incontri.enumerated().map { i, m in
            ["data": data(scadenza.addingTimeInterval(1800 + scarti[i] * 60)), "casa": m.casa, "trasferta": m.trasferta, "giocata": false,
             "stato": "da_giocare"] as [String: Any]
        }
        o["fase"] = "finita"
        o["giornata"] = giornata + 1
        o["giornata_lega"] = giornata - 2
        o["inizio"] = data(scadenza.addingTimeInterval(1800))
        o["scadenza"] = data(scadenza)
        o["con_probabili"] = false
        o["probabili"] = NSNull()
        o["da_fare"] = [voceSvincolato]
        o["riepilogo"] = [
            "giornata": giornata, "giornata_lega": giornata - 3, "formazione_di": "tua", "nel_diario": true,
            "punti_fatti": 74.5, "punti_attesi": 71.2, "intervallo": fascia(71.2, indicativo: false),
            "consigliata": ["punti_fatti": 78.0, "punti_attesi": 73.7],
        ] as [String: Any]
        if recupero, let ultima = incontri.last {
            // la giornata è finita ma una partita aspetta il recupero: i punti possono ancora cambiare e si può decidere diversamente
            let partita: [String: Any] = ["casa": ultima.casa, "trasferta": ultima.trasferta, "data": data(adesso.addingTimeInterval(18 * 86_400))]
            o["riepilogo"] = (o["riepilogo"] as? [String: Any] ?? [:]).merging(
                ["nel_diario": false, "consigliata": NSNull(), "recuperi": [partita], "rinvio": sceltaRinvio(giornata: giornata)]) { _, nuovo in nuovo }
        }
        o["prossima"] = [
            "giornata": giornata + 1, "giornata_lega": giornata - 2, "scadenza": data(scadenza),
            "prepara_da": data(scadenza.addingTimeInterval(-72 * 3600)), "con_probabili": false,
        ] as [String: Any]
        return json(o)
    }

    // MARK: - Risultati in diretta

    /// Alcune partite in corso, una finita e il resto da giocare: la scheda «Partite del turno» di Oggi si vede viva.
    /// `giornataInCorso`: le partite come nella fotografia `oggi-in-corso` (Inter-Roma finita, Napoli-Atalanta ancora da giocare).
    static func live(adesso: Date, giornataInCorso: Bool = false) -> String {
        func ev(_ tipo: String, _ minuto: String, _ squadra: String, _ chi: String, _ assist: String? = nil) -> [String: Any] {
            var e: [String: Any] = ["tipo": tipo, "minuto": minuto, "squadra": squadra, "chi": chi]
            if let assist { e["assist"] = assist }
            return e
        }
        var partite: [[String: Any]] = []
        for (i, m) in incontri.enumerated() {
            var p: [String: Any] = ["casa": m.casa, "trasferta": m.trasferta, "stato": "da_giocare",
                                    "data": formatta(adesso.addingTimeInterval(Double(i + 1) * 3600), "yyyy-MM-dd HH:mm")]
            switch i {
            case 0:
                p["stato"] = "secondo_tempo"; p["minuto"] = "63'"; p["gol_casa"] = 2; p["gol_trasferta"] = 1
                p["eventi"] = [ev("gol", "12'", "casa", "Thorvan", "Barlesi"), ev("gol", "38'", "trasferta", "Dobrala"), ev("giallo", "44'", "casa", "Bastrani"),
                               ev("rigore", "55'", "casa", "Calvaroglu"), ev("rigore_sbagliato", "58'", "trasferta", "Dobrala"),
                               ev("rosso", "61'", "trasferta", "Cristoni")]
            case 1:
                p["stato"] = "intervallo"; p["gol_casa"] = 0; p["gol_trasferta"] = 0
                p["eventi"] = [ev("giallo", "30'", "trasferta", "Locardi")]
            case 2:
                p["stato"] = "finita"; p["gol_casa"] = 3; p["gol_trasferta"] = 1
                p["eventi"] = [ev("gol", "9'", "casa", "Lumbaku", "Polinardo"), ev("autogol", "40'", "casa", "Djorsati"), ev("giallo", "52'", "casa", "Rrapaj"),
                               ev("rosso", "71'", "trasferta", "De Valk"), ev("gol", "80'", "trasferta", "Retalli", "Pasenic"),
                               ev("gol", "88'", "casa", "McTarran", "Angrassa"), ev("doppio_giallo", "90'+2'", "casa", "Lobrenka")]
            case 3:
                p["stato"] = "primo_tempo"; p["minuto"] = "27'"; p["gol_casa"] = 1; p["gol_trasferta"] = 1
                p["eventi"] = [ev("gol", "11'", "casa", "Castelvera"), ev("gol", "25'", "trasferta", "Hrafnsson")]
            default: break
            }
            if giornataInCorso && i == 0 { p["stato"] = "finita"; p["minuto"] = nil }
            if giornataInCorso && i == 2 {
                p = ["casa": m.casa, "trasferta": m.trasferta, "stato": "da_giocare",
                     "data": formatta(adesso.addingTimeInterval(150 * 60), "yyyy-MM-dd HH:mm")]
            }
            partite.append(p)
        }
        return json(["aggiornato_il": formatta(adesso, "yyyy-MM-dd HH:mm:ss"), "fonte": "espn", "in_corso": 3, "partite": partite])
    }

    // MARK: - Mercato

    static func mercato() -> String {
        let cambi: [(Int, Int, Double, Double?)] = [
            (124, 203, 3.4, 11), (119, 205, 1.9, 6), (118, 210, 2.2, 3), (109, 215, 2.6, 4), (110, 209, 1.2, 5), (103, 206, 0.8, nil),
        ]
        var proposte: [[String: Any]] = []
        for (esce, entra, guadagno, rimborso) in cambi {
            var d: [String: Any] = ["esce": breve(esce), "entra": breve(entra), "guadagno": guadagno,
                                    "breve": guadagno * 0.4, "fattibile": true, "crediti_dopo": 12.0 + (rimborso ?? 0)]
            if let rimborso { d["rimborso"] = rimborso }
            proposte.append(d)
        }
        return json(["squadra": nomeMia, "svincolati": 118, "crediti_residui": 12, "proposte": proposte])
    }

    static func classifica() -> String {
        let ordinati = liberi.sorted { $0.punti > $1.punti }
        return json(["giornata": giornata, "giocatori": ordinati.map { giocatore($0) }])
    }

    static func osservati() -> String {
        var elenco: [[String: Any]] = []
        for id in [203, 205, 321, 328, 214] {
            var p = calciatore(id)
            if id == 328 { p.assente = true }
            elenco.append(giocatore(p, conProprietario: true))
        }
        return json(["giornata": giornata, "giocatori": elenco])
    }

    static func calendario() -> String {
        var squadre: [[String: Any]] = []
        for (i, nome) in forza.enumerated() {
            var partite: [[String: Any]] = []
            var somma = 0.0
            for (k, g) in giornate.enumerated() {
                var j = (i * 7 + g * 3 + 5) % forza.count
                if j == i { j = (j + 1) % forza.count }
                let difficolta = 1.0 + Double(forza.count - 1 - j) / 4.75
                somma += difficolta
                partite.append(["giornata": g, "avversario": forza[j], "in_casa": (i + k) % 2 == 0, "difficolta": difficolta.rounded()])
            }
            squadre.append(["squadra": nome, "media": somma / Double(giornate.count), "partite": partite])
        }
        squadre.sort { (($0["media"] as? Double) ?? 0) < (($1["media"] as? Double) ?? 0) }
        return json(["giornate": giornate, "squadre": Array(squadre.prefix(12))])
    }

    // MARK: - Scambi

    static func proposta(altra: String, dai: [Int], ricevi: [Int], mio: Double, loro: Double) -> [String: Any] {
        let n = Double(giornate.count)
        let mioPer = giornate.enumerated().map { (mio / n) + (Double($0.offset % 2) - 0.5) * 0.2 }
        let loroPer = giornate.enumerated().map { (loro / n) + (Double($0.offset % 3) - 1.0) * 0.1 }
        return ["mia": nomeMia, "altra": altra, "do": dai.map { breve($0) }, "ricevo": ricevi.map { breve($0) },
                "guadagno_mio": mio, "guadagno_loro": loro, "per_giornata_mio": mioPer, "per_giornata_loro": loroPer,
                "breve_mio": mio * 0.5, "breve_loro": loro * 0.5, "giornate": giornate]
    }

    static func scambi() -> String {
        let proposte: [[String: Any]] = [
            proposta(altra: "Real Madrink", dai: [124], ricevi: [327], mio: 2.4, loro: 1.1),
            proposta(altra: "Gli Amici del Bar Sport Centrale", dai: [110, 119], ricevi: [321, 308], mio: 3.1, loro: 0.6),
            proposta(altra: "Dinamo Pizza", dai: [116], ricevi: [322], mio: 1.8, loro: 0.9),
            proposta(altra: "Atletico Divano", dai: [125], ricevi: [336], mio: 1.2, loro: 1.0),
            proposta(altra: "Borgo Rossi United", dai: [111], ricevi: [312], mio: 0.7, loro: 0.4),
        ]
        return json(["giornate": giornate, "proposte": proposte])
    }

    static func analisi() -> String {
        var p = proposta(altra: "Real Madrink", dai: [124], ricevi: [327], mio: 2.4, loro: 1.1)
        // l'analisi completa (scambi N contro M con conguaglio): rose valide, crediti, valore e giudizio
        p["completo"] = true
        p["valido"] = true
        p["problemi"] = [String]()
        p["rose"] = ["mio": ["squadra": nomeMia, "valida": true, "problemi": [String](), "modulo": "3-4-3"],
                     "loro": ["squadra": "Real Madrink", "valida": true, "problemi": [String](), "modulo": "4-3-3"]]
        p["valore_rosa"] = ["mio": ["prima": 64.5, "dopo": 66.9, "variazione": 2.4, "percentuale": 3.7],
                            "loro": ["prima": 61.0, "dopo": 62.1, "variazione": 1.1, "percentuale": 1.8]]
        p["panchina"] = ["mio": ["prima": 8.0, "dopo": 8.3, "variazione": 0.3], "loro": ["prima": 7.5, "dopo": 7.4, "variazione": -0.1]]
        p["conguaglio"] = ["crediti": 5, "valido": true, "residui": ["mio": 12, "loro": 30], "dopo": ["mio": 17, "loro": 25],
                           "chi_paga": "loro", "tasso_mio": 0.12, "tasso_loro": 0.1, "valore_mio": 0.6, "valore_loro": -0.5]
        p["netto_mio"] = 3.0
        p["netto_loro"] = 0.6
        p["giudizio"] = ["chi": "entrambi", "testo": "Conviene a tutti e due: proponilo.", "soglia": 0.5,
                         "spiegazione": ["Per te la formazione migliore passa da 64,5 a 66,9 punti attesi.",
                                         "Con 5 crediti ricevuti il netto per te è +3,0."]]
        return json(p)
    }

    // MARK: - Lega

    static func squadre() -> String {
        let crediti = [12, 41, 7, 25, 0, 63, 18, 30]
        func immagini(_ nome: String) -> [String: Any] {
            ["stemma": DemoImmagini.conStemma.contains(nome), "maglia": DemoImmagini.conMaglia.contains(nome)]
        }
        var elenco: [[String: Any]] = [["nome": nomeMia, "mia": true, "giocatori": 25, "crediti_residui": crediti[0], "immagini": immagini(nomeMia)]]
        for (i, nome) in altreSquadre.enumerated() {
            elenco.append(["nome": nome, "mia": false, "giocatori": 25, "crediti_residui": crediti[i + 1], "immagini": immagini(nome)])
        }
        return json(elenco)
    }

    static func rosa(_ nome: String, _ giocatori: [Calciatore], mia: Bool) -> String {
        json(["nome": nome, "mia": mia, "crediti_residui": mia ? 12 : 30, "aggiornato": "2026-10-26T19:19:33",
              "giocatori": giocatori.map { rigaRosa($0) }, "avvisi": mia ? ["Schiera FC: Rolf Gostein e Nereo Fagiani sono indisponibili"] : [String]()])
    }

    static func stato(adesso: Date) -> String {
        json(["stagione": "2026-27", "prossima_giornata": giornata, "mia_squadra": nomeMia, "rose_importate": true, "versione": "1.9",
              "ultimo_aggiornamento": formatta(adesso.addingTimeInterval(-2 * 3600), "yyyy-MM-dd'T'HH:mm:ss")])
    }

    static func statoDati(adesso: Date) -> String {
        func quando(_ ore: Double) -> String { formatta(adesso.addingTimeInterval(-ore * 3600), "yyyy-MM-dd'T'HH:mm:ss") }
        return json([
            "stagione": "2026-27", "calciatori": 612, "voti": 2431, "coppe_fino": "2026-12-10", "foto": 8,
            "probabili": [["giornata": giornata, "giocatori": 539, "rilevato": quando(2)]],
            "calibrazione": ["giornate": 3, "gruppi": [
                ["gruppo": "Titolare 90-100%", "n": 142, "osservato": 0.93, "previsto": 0.95, "indicativo": false],
                ["gruppo": "Titolare 70-89%", "n": 61, "osservato": 0.78, "previsto": 0.8, "indicativo": false],
                ["gruppo": "Panchina 20-49%", "n": 12, "osservato": 0.25, "previsto": 0.31, "indicativo": true],
            ]],
            "partite": ["totali": 380, "giocate": 100],
            "aggiornamenti": [
                ["cosa": "listone e quotazioni", "quando": quando(30), "errori": [String]()],
                ["cosa": "probabili formazioni", "quando": quando(2), "errori": ["Una fonte non ha risposto: usata la copia delle 08:10"]],
                ["cosa": "voti e statistiche", "quando": quando(52), "errori": [String]()],
                ["cosa": "calendario e coppe europee", "quando": quando(100), "errori": [String]()],
            ],
        ])
    }

    static func regole() -> String {
        json([
            "nome_lega": "Lega degli amici", "fonte_voto": "redazione",
            "bonus": ["gol": ["P": 3.0, "D": 3.0, "C": 3.0, "A": 3.0], "rigore_segnato": 3.0, "assist": 1.0, "rigore_parato": 3.0,
                      "rigore_sbagliato": -3.0, "autogol": -2.0, "gol_subito_portiere": -1.0, "portiere_imbattuto": 1.0,
                      "ammonizione": -0.5, "espulsione": -1.0, "mvp": 0.0],
            "rosa": ["P": 3, "D": 8, "C": 8, "A": 6], "crediti_iniziali": 500, "rimborso_svincolo": 0.5,
            "scadenza_minuti": 30, "prima_giornata_lega": 4, "aggiornamenti_vicino_scadenza": true,
            "partite_rinviate": "aspetta", "voto_ufficio_rinviate": 6, "rinvii_giornate": [String: Any](),
            "moduli": ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"],
            "panchina": ["numero": 11, "tipo": "per_ruolo", "max_sostituzioni": 5, "cambio_modulo": false,
                         "posti": ["P": 2, "D": 3, "C": 3, "A": 3]],
            "modificatore_difesa": ["attivo": true, "min_difensori": 4,
                                    "soglie": [[6, 1], [6.25, 1.5], [6.5, 2], [6.75, 2.5], [7, 3], [7.25, 3.5]]],
            "voto_senza_sostituto": NSNull(), "fattore_campo": 0.0, "soglia_primo_gol": 66.0, "ampiezza_fascia_gol": 6.0,
        ])
    }

    static func riconosci() -> String {
        json(["modifiche": [
            ["chiave": "bonus.assist", "etichetta": "Assist", "valore": 1.0, "riga": "Assist: +1 punto"],
            ["chiave": "bonus.ammonizione", "etichetta": "Ammonizione", "valore": -0.5, "riga": "Ammonizione: -0.5"],
            ["chiave": "panchina.numero", "etichetta": "Giocatori in panchina", "valore": 7, "riga": "Panchina: 7 giocatori"],
            ["chiave": "moduli", "etichetta": "Moduli ammessi", "valore": ["3-4-3", "4-3-3", "4-4-2"], "riga": "Moduli: 3-4-3, 4-3-3, 4-4-2"],
        ] as [[String: Any]], "non_riconosciute": ["Il bonus per il rigore parato vale 3 punti, tranne in coppa"]])
    }

    static func novita() -> String {
        json([
            ["versione": "1.9", "data": "2026-10-20", "titolo": "Scambi più veloci",
             "voci": ["Gli scambi 2 contro 2 si calcolano in metà tempo.", "Il calendario mostra la difficoltà per cinque giornate.",
                      "Corretto il conteggio dei crediti dopo uno svincolo."]],
            ["versione": "1.8", "data": "2026-10-05", "titolo": "Copia di sicurezza e icona",
             "voci": ["La copia di sicurezza notturna comprende anche le chiavi degli avvisi.", "Nuova icona dell'app."]],
            ["versione": "1.7", "data": "2026-09-21", "titolo": "Probabili formazioni",
             "voci": ["Le probabili formazioni arrivano da due fonti.", "Avviso quando un titolare diventa dubbio."]],
        ])
    }

    static func avvisi() -> String {
        json(["impostazioni": ["cambi": true, "promemoria_60": true, "promemoria_15": false, "riepilogo": true, "copertura": true, "app_nativa": true,
                              "silenzio": false, "silenzio_da": 23, "silenzio_a": 23, "avviso_prima": 60],
              "canale": true, "dispositivi": 2, "ore_tranquille_spente": true])
    }

    /// Diario delle giornate: le quattro giornate finite prima di quella di Oggi (la 4, 5, 6 e 7 della lega, Serie A 7-10),
    /// due con la tua formazione e due senza. Ogni voce porta `giornata_lega`, come le manda il server.
    static func diario() -> String {
        // la lega parte dalla giornata 4 di Serie A (`prima_giornata_lega` delle regole della demo), come in Oggi: Serie A 11 = giornata 8
        func lega(_ serieA: Int) -> Int { serieA - 3 }
        // Gli id seguono il nome (non la posizione), così due formazioni con un nome diverso risultano davvero diverse.
        let anagrafe = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Calvaroglu", "Leonel", "Thorvan", "Pulinski", "Lemao", "Kloosmeijer", "Dunfrey", "Orsetti", "Mkhedrian", "Zelawski"]
        let ruoliDi = ["Sorvani": "P", "Bastrani": "D", "Dimarzi": "D", "Dunfrey": "D", "Leonel": "A", "Thorvan": "A", "Lemao": "A", "Pulinski": "A", "Orsetti": "A"]
        func titolari(_ nomi: [String]) -> [[String: Any]] {
            nomi.map { ["id": 9000 + (anagrafe.firstIndex(of: $0) ?? 99), "nome": $0, "ruolo": ruoliDi[$0] ?? "C"] }
        }
        let base = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Calvaroglu", "Leonel", "Thorvan", "Pulinski", "Lemao", "Kloosmeijer", "Dunfrey"]
        let altra = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Calvaroglu", "Leonel", "Thorvan", "Pulinski", "Lemao", "Kloosmeijer", "Orsetti"]
        let altra2 = ["Sorvani", "Bastrani", "Dimarzi", "Barlesi", "Mkhedrian", "Leonel", "Thorvan", "Pulinski", "Lemao", "Zelawski", "Orsetti"]
        func istantanea(_ g: Int, _ modulo: String, _ nomi: [String], atteso: Double, ora: String) -> [String: Any] {
            ["giornata": g, "modulo": modulo, "titolari": titolari(nomi), "panchina": titolari(["Mkhedrian", "Zelawski", "Orsetti"]),
             "atteso": atteso, "stile": "Equilibrato", "calcolata": ora]
        }
        // «Quanto ci abbiamo preso»: punti attesi e fatti della consigliata (le stesse voci qui sotto), con la fascia.
        func avf(_ atteso: Double, _ fatti: Double) -> [String: Any] {
            let f = fascia(atteso)
            let basso = f["basso"] as? Double ?? atteso, alto = f["alto"] as? Double ?? atteso
            return ["riferimento": "consigliata", "atteso": atteso, "fatti": fatti, "scarto": ((fatti - atteso) * 10).rounded() / 10,
                    "nella_fascia": basso <= fatti && fatti <= alto, "intervallo": ["basso": basso, "alto": alto]]
        }
        let affidabilita: [String: Any] = [
            "giornate": 4, "scarto_medio": 3.4, "errore_medio": -0.4, "punti_medi_attesi": 67.4, "punti_medi_fatti": 67.0,
            "dentro_fascia": 4, "con_fascia": 4, "percentuale_dentro": 100, "fascia_dichiarata": 80, "pochi_dati": true,
            "giornate_minime": 8, "giudizio": "pochi_dati",
        ]
        // «Quanto ci abbiamo preso» (forma nuova): numeri onesti anche quando vanno male (qui «gioca» è troppo ottimista).
        let precisione: [String: Any] = [
            "giornate": 4, "pochi_dati": true, "giornate_minime": 8, "fonti": ["mostrati": 3, "ricostruiti": 1],
            "fantavoto": ["errore_medio": 1.4, "scostamento": -0.4, "entro_un_punto": 58, "voti": 41],
            "gioca": ["giocatori": 52, "principale": 1, "fonte": "mostrati", "giornate": 3, "gruppi": [
                ["da": 40, "a": 70, "giocatori": 9, "pochi": true, "detto": 55, "giocato": 44],
                ["da": 90, "a": 100, "giocatori": 43, "pochi": false, "detto": 96, "giocato": 83],
            ]],
            "confronto": ["giornate": 2, "meglio_consigliata": 2, "meglio_tua": 0, "pari": 0, "punti": 12.0,
                          "media_consigliata": 67.5, "media_tua": 61.5],
            "squadra": affidabilita,
            "per_giornata": [
                ["stagione": "2026-27", "giornata": 7, "giornata_lega": lega(7), "fonte": "ricostruiti", "errore_fantavoto": 1.6, "voti": 10,
                 "attesi": 65.0, "fatti": 60.5, "tua": NSNull(), "differenza": NSNull()],
                ["stagione": "2026-27", "giornata": 8, "giornata_lega": lega(8), "fonte": "mostrati", "errore_fantavoto": 1.2, "voti": 11,
                 "attesi": 67.0, "fatti": 64.0, "tua": 59.5, "differenza": 4.5],
                ["stagione": "2026-27", "giornata": 9, "giornata_lega": lega(9), "fonte": "mostrati", "errore_fantavoto": 1.5, "voti": 10,
                 "attesi": 68.5, "fatti": 71.0, "tua": 63.5, "differenza": 7.5],
                ["stagione": "2026-27", "giornata": 10, "giornata_lega": lega(10), "fonte": "mostrati", "errore_fantavoto": 1.3, "voti": 10,
                 "attesi": 69.0, "fatti": 72.5, "tua": NSNull(), "differenza": NSNull()],
            ],
        ]
        return json([
            "affidabilita": affidabilita,
            "precisione": precisione,
            "giornate": [
                ["stagione": "2026-27", "giornata": 10, "giornata_lega": lega(10), "atteso_vs_fatto": avf(69.0, 72.5),
                 "consigliata": ["modulo": "3-4-3", "atteso": 69.0, "reale": 72.5, "intervallo": fascia(69.0), "titolari": titolari(base)],
                 "istantanea": istantanea(10, "3-4-3", base, atteso: 69.0, ora: "2026-10-31T10:05:00")],
                ["stagione": "2026-27", "giornata": 9, "giornata_lega": lega(9), "atteso_vs_fatto": avf(68.5, 71.0),
                 "consigliata": ["modulo": "3-4-3", "atteso": 68.5, "reale": 71.0, "intervallo": fascia(68.5), "titolari": titolari(base)],
                 "istantanea": istantanea(9, "3-4-3", base, atteso: 68.5, ora: "2026-10-24T09:40:00"),
                 "schierata": ["modulo": "3-5-2", "atteso": 66.0, "reale": 63.5, "intervallo": fascia(66.0), "titolari": titolari(altra)]],
                ["stagione": "2026-27", "giornata": 8, "giornata_lega": lega(8), "atteso_vs_fatto": avf(67.0, 64.0),
                 "consigliata": ["modulo": "3-4-3", "atteso": 67.0, "reale": 64.0, "intervallo": fascia(67.0), "titolari": titolari(base)],
                 "istantanea": istantanea(8, "3-4-3", base, atteso: 67.0, ora: "2026-10-17T11:20:00"),
                 "schierata": ["modulo": "3-4-3", "atteso": 66.0, "reale": 59.5, "intervallo": fascia(66.0), "titolari": titolari(altra2)]],
                ["stagione": "2026-27", "giornata": 7, "giornata_lega": lega(7), "atteso_vs_fatto": avf(65.0, 60.5),
                 "consigliata": ["modulo": "4-3-3", "atteso": 65.0, "reale": 60.5, "intervallo": fascia(65.0), "titolari": titolari(base)]],
            ],
            // come `sintesi` di fanta/diario.py: le giornate 9 e 8 di Serie A, le due con la tua formazione
            "sintesi": ["giornate": 2, "punti_schierata": 61.5, "punti_consigliata": 67.5, "attesi_schierata": 66.0,
                        "meglio_tua": 0, "meglio_consigliata": 2],
            // come `scelte_tue` di fanta/diario.py, dalle stesse voci: le giornate 9 e 8 di Serie A, le sole con la tua formazione
            // (undici diversi da quelli consigliati); 2 giornate sono sotto le 8 che servono, quindi «pochi dati»
            "scelte_tue": ["giornate": 2, "meglio_tua": 0, "meglio_consigliata": 2, "pari": 0, "punti_differenza": -12.0,
                           "percentuale_tua": 0, "pochi_dati": true,
                           "per_giornata": [
                               ["stagione": "2026-27", "giornata": 9, "giornata_lega": lega(9), "hai_scelto": ["Orsetti"], "consigliava": ["Dunfrey"],
                                "punti_tua": 63.5, "punti_consigliata": 71.0, "differenza": -7.5, "esito": "consigliata"],
                               ["stagione": "2026-27", "giornata": 8, "giornata_lega": lega(8), "hai_scelto": ["Mkhedrian", "Zelawski", "Orsetti"],
                                "consigliava": ["Calvaroglu", "Kloosmeijer", "Dunfrey"],
                                "punti_tua": 59.5, "punti_consigliata": 64.0, "differenza": -4.5, "esito": "consigliata"],
                           ]],
        ])
    }

    /// Un backup piccolo ma valido, per provare «Scarica il backup» in demo.
    static func backup() -> String {
        json(["formato": "schieraxi-backup", "versione": 1, "creato": "2026-10-30T09:00:00",
              "file": ["dati/osservati.json": [9001, 9002]]])
    }

    // MARK: - Confronto, prova del modello, movimenti, stagione

    static func confronto(_ a: Calciatore, _ b: Calciatore) -> String {
        let consigliato = a.punti >= b.punti ? a : b
        let fattori: [[String: Any]] = [
            ["chiave": "giocare", "etichetta": "Probabilità di giocare", "a": a.pVoto, "b": b.pVoto, "effetto": (a.pVoto - b.pVoto) * 4.0, "percentuale": true],
            ["chiave": "voto", "etichetta": "Voto in pagella atteso", "a": 6.1, "b": 6.0, "effetto": 0.12, "percentuale": false],
            ["chiave": "gol", "etichetta": "Gol attesi", "a": golAttesi(a), "b": golAttesi(b), "effetto": (golAttesi(a) - golAttesi(b)) * 3.0, "percentuale": false],
            ["chiave": "assist", "etichetta": "Assist attesi", "a": assistAttesi(a), "b": assistAttesi(b), "effetto": (assistAttesi(a) - assistAttesi(b)) * 1.2, "percentuale": false],
            ["chiave": "rigori", "etichetta": "Rigori", "a": 0.0, "b": 0.0, "effetto": 0.0, "percentuale": false],
            ["chiave": "altro", "etichetta": "Cartellini e altro", "a": -0.09, "b": -0.12, "effetto": 0.03, "percentuale": false],
        ]
        return json(["giornata": giornata, "giocatori": [giocatore(a), giocatore(b)], "consigliato": consigliato.id, "margine": abs(a.punti - b.punti),
                     "fattori": fattori,
                     "perche": "\(consigliato.nome) ha più probabilità di giocare e un avversario più abbordabile.",
                     "formazione": ["modulo": "3-4-3", "posto_a": "titolare", "posto_b": "panchina", "attuale": NSNull(), "invertita": NSNull(), "differenza": NSNull(),
                                    "testo": "\(a.nome) è titolare nel 3-4-3, \(b.nome) è in panchina: schierando \(consigliato.nome) la formazione guadagna circa \(Formato.punti(abs(a.punti - b.punti))) punti attesi."]])
    }

    static func affidabilita() -> String {
        var righe: [[String: Any]] = []
        for g in 1...8 {
            let base = 64.0 + Double((g * 7) % 9)
            righe.append(["stagione": "2026-27", "giornata": g, "errore_modello": 1.4 + Double(g % 3) * 0.2, "errore_fantamedia": 1.7 + Double(g % 4) * 0.15,
                          "punti_modello": base + 3, "punti_fantamedia": base, "punti_perfetta": base + 9, "n": 200])
        }
        return json(["calcolato": "2026-10-28T00:38:07", "ultima": "2026-27/8", "righe": righe,
                     "sintesi": ["giornate": 8, "errore_modello": 1.6, "errore_fantamedia": 1.82, "punti_modello": 71.7, "punti_fantamedia": 70.6, "punti_perfetta": 77.8]])
    }

    static func movimenti() -> String {
        func g(_ id: Int, _ nome: String, _ ruolo: String, _ squadra: String) -> [String: Any] { ["id": id, "nome": nome, "ruolo": ruolo, "squadra": squadra, "costo": 10] }
        return json([
            ["quando": "2026-10-26T19:19:33",
             "scambi": [["squadre": ["Real Madrink", "Dinamo Pizza"], "da_a": [g(325, "Kaan Yurdız", "A", "juventus")], "da_b": [g(321, "Sandy McTarran", "C", "napoli")]]],
             "svincolati_presi": [["squadra": "AC Pigra", "giocatori": [g(204, "Nenad Krslić", "A", "lecce")]]],
             "tagliati": [["squadra": "Inter Nos", "giocatori": [g(215, "Gilberto Mancarini", "D", "roma")]]],
             "crediti": [["squadra": "AC Pigra", "prima": 30, "dopo": 22]],
             "testo": "Scambio Real Madrink / Dinamo Pizza: Kaan Yurdız ⇄ Sandy McTarran"] as [String: Any],
            ["quando": "2026-10-19T08:02:10",
             "scambi": [[String: Any]](), "svincolati_presi": [["squadra": "Schiera FC", "giocatori": [g(113, "Hamit Çalvaroğlu", "C", "inter")]]],
             "tagliati": [[String: Any]](), "crediti": [[String: Any]](), "testo": "Schiera FC prende dagli svincolati: Hamit Çalvaroğlu"] as [String: Any],
        ] as [[String: Any]])
    }

    static func stagione() -> String {
        let nuova = Demo.schermata == "lega-stagione"
        return json(["corrente": nuova ? "2027-28" : "2026-27", "rose": "2026-27", "nuova": nuova])
    }

    static func offerta() -> String {
        json(["con": "Real Madrink", "do": ["Darko Vlasenić"], "ricevo": ["Rolando Lumbaku"], "ambigui": [String](),
              "analisi": proposta(altra: "Real Madrink", dai: [124], ricevi: [327], mio: 2.4, loro: 1.1)
                  .merging(["reparti": ["mio": ["P": 0.0, "D": 0.0, "C": 0.0, "A": 6.2], "loro": ["P": 0.0, "D": 0.0, "C": 1.1, "A": -2.0]],
                            "percentuale_mio": 1.4, "quotazione_do": 14, "quotazione_ricevo": 18]) { $1 }])
    }

    static func importa() -> String {
        json(["squadre_importate": ["Real Madrink", "Dinamo Pizza"], "totale_squadre": 8, "avvisi": ["Dinamo Pizza: 24 giocatori invece di 25"],
              "mia_squadra": nomeMia, "riepilogo": "Scambio Real Madrink / Dinamo Pizza: Kaan Yurdız ⇄ Sandy McTarran",
              "differenze": [
                "prima_importazione": false, "nessuna_differenza": false,
                "scambi": [["squadre": ["Real Madrink", "Dinamo Pizza"], "da_a": [["id": 325, "nome": "Kaan Yurdız", "ruolo": "A", "squadra": "juventus", "costo": 33]],
                            "da_b": [["id": 321, "nome": "Sandy McTarran", "ruolo": "C", "squadra": "napoli", "costo": 25]]]],
                "svincolati_presi": [["squadra": "AC Pigra", "giocatori": [["id": 204, "nome": "Nenad Krslić", "ruolo": "A", "squadra": "lecce", "costo": 5]]]],
                "tagliati": [[String: Any]](), "crediti": [["squadra": "AC Pigra", "prima": 30, "dopo": 22]],
                "testo": "Scambio Real Madrink / Dinamo Pizza"] as [String: Any]])
    }

    // MARK: - Tutte le risposte

    static func risposte(adesso: Date) -> [String: String] {
        let centrocampisti: [Calciatore] = Array(altri.filter { $0.ruolo == "C" }.prefix(3))
        let trovati: [Calciatore] = liberi + centrocampisti
        var r: [String: String] = [
            // account (con il server di sempre non servono: «me» dice che non c'è nessun accesso)
            "/api/account/me": "{\"multiutente\": false, \"utente\": {\"id\": 0, \"nome_utente\": \"locale\", \"ruolo\": \"amministratore\", \"creato\": \"\"}}",
            "/api/account/accedi": "{\"multiutente\": true, \"utente\": {\"id\": 7, \"nome_utente\": \"mister.rossi\", \"ruolo\": \"utente\", \"creato\": \"2026-10-29\"}, \"token\": \"token-demo\"}",
            "/api/account/registra": "{\"multiutente\": true, \"utente\": {\"id\": 7, \"nome_utente\": \"mister.rossi\", \"ruolo\": \"utente\", \"creato\": \"2026-10-29\"}, \"token\": \"token-demo\", \"codice_recupero\": \"K7M2P-XQ4NH-W8RTV\"}",
            "/api/account/codice-recupero": "{\"codice_recupero\": \"H3N8D-R5WQA-C9XEJ\"}",
            "/api/account/recupero": "{\"ok\": true, \"codice_recupero\": \"H3N8D-R5WQA-C9XEJ\"}",
            "/api/stato": stato(adesso: adesso),
            "/api/stato-dati": statoDati(adesso: adesso),
            "/api/squadre": squadre(),
            "/api/rosa": rosa(nomeMia, miaRosa, mia: true),
            "/api/scambi/proposte": scambi(),
            "/api/scambi/analizza": analisi(),
            "/api/mercato": mercato(),
            "/api/classifica": classifica(),
            "/api/calendario": calendario(),
            "/api/osservati": osservati(),
            "/api/giocatori": json(trovati.map { breve($0.id) }),
            "/api/formazione/testo": "Giornata \(giornata) - 3-4-3 (\(Formato.punti(punteggio(moduli[0].titolari))) punti attesi)",
            "/api/formazione/valuta": valutazione(),
            "/api/scelta": "null",   // nessuna scelta salvata: si vede la consigliata
            "/api/formazione": formazione(),
            "/api/primo-avvio": json(["primo_avvio": NSNull(), "passi": ["server", "accesso", "rose", "squadra", "stemma", "pwa", "widget", "avvisi"]]),
            "/api/oggi": oggi(adesso: adesso),
            "/api/live": live(adesso: adesso),
            "/api/regole": regole(),
            "/api/avvisi": avvisi(),
            "/api/diario": diario(),
            "/api/backup": backup(),
            "/api/novita": novita(),
            "/api/foto-disponibili": json(["ids": Array(DemoImmagini.idConFoto).sorted()]),
            "/api/affidabilita": affidabilita(),
            "/api/movimenti": movimenti(),
            "/api/stagione": stagione(),
            "/api/scambi/da-testo": offerta(),
            "/api/regole/riconosci": riconosci(),
            "/api/rose/testo": importa(),
            "/api/rose/file": importa(),
            "/api/rose/anteprima": DemoAnteprimaRose.json,   // anche /api/rose/anteprima/file
            "/api/aggiorna": json(["avviato": true, "in_corso": false, "righe": [String](), "errori": [String]()]),
            "/api/confronto": confronto(calciatore(120), calciatore(123)),
        ]
        riferimento = adesso
        r["/api/rosa?squadra=" + IndirizzoServer.codifica(nomeMia)] = rosa(nomeMia, miaRosa, mia: true)
        for (k, nome) in altreSquadre.enumerated() {
            r["/api/rosa?squadra=" + IndirizzoServer.codifica(nome)] = rosa(nome, rosaAltra(k), mia: false)
        }
        // ogni scheda ha il suo indirizzo (id a tre cifre: nessun indirizzo è l'inizio di un altro)
        for p in tutti { r["/api/giocatore/\(p.id)"] = json(schedaGiocatore(p)) }
        r["/api/giocatore/"] = json(schedaGiocatore(calciatore(203)))
        return r
    }
}
