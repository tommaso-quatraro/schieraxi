import Foundation

// La lega inventata della demo: UNA fonte per l'app (`DatiDemo.swift`: modalità `-DEMO`, «Prova con dati di esempio» e foto
// dell'app) e per i widget (`LegaDemo.widget`, mostrato dalla galleria `AnteprimaWidget` nelle foto dei widget). Così widget e
// app dicono le stesse cose: stessi nomi con gli accenti, stessa percentuale di chi è in dubbio, stessa scadenza, stesse giornate
// del Diario (#192, provato in `DemoWidgetComeAppTests`). Nomi, squadre e numeri INVENTATI; le date sono relative ad «adesso».
// Solo Foundation: il file si compila anche nella galleria dei widget (target `AnteprimaWidget` in `project.yml`).

/// Un calciatore della lega inventata.
struct CalciatoreDemo {
    let id: Int
    let nome: String
    let ruolo: String
    let squadra: String
    var costo: Int = 0
    var quotazione: Int = 0
    var pVoto: Double = 0.85
    /// Il rendimento scritto a mano: da qui vengono fantavoto atteso, punti attesi, indice, quotazione, gol e assist attesi.
    var punti: Double = 5.5
    var dubbio: Bool = false
    var diffidato: Bool = false
    var assente: Bool = false

    /// Il voto in pagella atteso (`voto_atteso`).
    var votoAtteso: Double { 5.9 + (punti - 5.0) / 8.0 }

    /// Il fantavoto atteso (`fv_atteso`): lo stesso numero nella Formazione dell'app e accanto ai titolari del widget (#240).
    var fvAtteso: Double { assente ? 0 : punti + 0.6 + (ruolo == "A" ? 0.5 : 0) }

    /// Lo stato delle probabili formazioni (`stato`): infortunato, titolare (anche in dubbio) o panchina.
    var statoProbabili: String {
        if assente { return "infortunato" }
        return dubbio || pVoto >= 0.75 ? "titolare" : "panchina"
    }

    /// La percentuale delle probabili (`percentuale`): il server la manda ancora, ma app e widget mostrano solo `p_voto`.
    var percentualeProbabili: Double {
        if assente { return 0 }
        return dubbio || pVoto < 0.75 ? (pVoto * 100).rounded() : 90
    }

    /// I punti attesi (`punti_attesi`) come li conta il server: probabilità di giocare per fantavoto atteso se gioca, a due
    /// decimali (#246). Così le barre del confronto sommano la differenza tra due giocatori.
    var puntiAttesi: Double { assente ? 0 : (pVoto * fvAtteso * 100).rounded() / 100 }

    /// I gol attesi (`gol_attesi`) e gli assist attesi (`assist_attesi`), dal rendimento e dal ruolo.
    var golAttesi: Double {
        if assente { return 0 }
        switch ruolo {
        case "A": return punti / 15.0
        case "C": return punti / 35.0
        case "D": return punti / 80.0
        default: return 0
        }
    }

    var assistAttesi: Double { assente || ruolo == "P" ? 0 : punti / 45.0 }
}

/// Un calciatore con tutti i valori scritti a mano.
private func cal(_ id: Int, _ nome: String, _ ruolo: String, _ squadra: String, costo: Int, pVoto: Double, punti: Double,
                 dubbio: Bool = false, diffidato: Bool = false, assente: Bool = false) -> CalciatoreDemo {
    CalciatoreDemo(id: id, nome: nome, ruolo: ruolo, squadra: squadra, costo: costo, quotazione: 0, pVoto: pVoto, punti: punti,
                   dubbio: dubbio, diffidato: diffidato, assente: assente)
}

/// Un calciatore di contorno: previsione ricavata dall'id, così non serve scriverla.
private func alt(_ id: Int, _ nome: String, _ ruolo: String, _ squadra: String) -> CalciatoreDemo {
    let punti = 4.6 + Double((id * 7) % 23) / 10.0
    let pVoto = 0.70 + Double((id * 3) % 27) / 100.0
    return CalciatoreDemo(id: id, nome: nome, ruolo: ruolo, squadra: squadra, costo: 4 + (id * 7) % 26, quotazione: 0, pVoto: pVoto, punti: punti)
}

enum LegaDemo {
    /// La fase della giornata, come `fase` di `/api/oggi`.
    enum Fase: String { case prima, inCorso = "in_corso", finita }

    // MARK: - Lega

    static let nomeMia = "Schiera FC"
    static let altreSquadre = ["Real Madrink", "Atletico Divano", "Dinamo Pizza", "AC Pigra", "Inter Nos", "Borgo Rossi United",
                               "Gli Amici del Bar Sport Centrale"]
    static let stagioneInCorso = "2026-27"
    /// La giornata di Serie A da giocare e il suo numero nella lega (la lega parte dalla giornata 4 di Serie A).
    static let giornata = 11
    static let giornataLega = giornata - 3
    static let creditiResidui = 12
    /// Quanto restituisce uno svincolo, in parte del prezzo pagato (`rimborso_svincolo` delle regole della demo).
    static let rimborsoSvincolo = 0.5
    /// La formazione della giornata è quella salvata da te (`tua_scelta` di Oggi e del widget).
    static let tuaScelta = true

    // MARK: - Calciatori

    /// La mia rosa (25): 3 portieri, 8 difensori, 8 centrocampisti, 6 attaccanti.
    static let miaRosa: [CalciatoreDemo] = [
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
    static let liberi: [CalciatoreDemo] = [
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
    static let altri: [CalciatoreDemo] = [
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

    static var tutti: [CalciatoreDemo] { miaRosa + liberi + altri }

    static func calciatore(_ id: Int) -> CalciatoreDemo {
        tutti.first { $0.id == id } ?? miaRosa[0]
    }

    static func quotazione(_ p: CalciatoreDemo) -> Int {
        p.quotazione > 0 ? p.quotazione : 3 + Int(p.punti * 2.0) + (p.id % 5)
    }

    /// Il prezzo pagato all'asta (`costo` della rosa).
    static func costo(_ p: CalciatoreDemo) -> Int {
        p.costo > 0 ? p.costo : 4 + p.id % 20
    }

    /// Il rimborso di uno svincolo, come il server: la quota delle regole del prezzo pagato, arrotondata come `round` di Python
    /// (a metà si va al pari: 16,5 → 16).
    static func rimborso(_ p: CalciatoreDemo) -> Int {
        Int((Double(costo(p)) * rimborsoSvincolo).rounded(.toNearestOrEven))
    }

    /// Chi tira i rigori nella mia rosa (il server lo ricava da `rigori_attesi`): Çalvaroğlu, che nelle partite in diretta ne segna uno.
    static let rigoristi: Set<Int> = [113]

    /// I giocatori seguiti (Squadra > Seguiti), nell'ordine: gli stessi nell'app e nei widget. Marténi è il primo perché la
    /// galleria dei widget lo mostra nel widget «Giocatore seguito» (`AnteprimaWidget/DatiGalleria.swift`, #246).
    static let idOsservati = [120, 203, 205, 321, 328, 214]

    /// Un seguito com'è adesso: Dobrala (328) è infortunato.
    static func osservato(_ id: Int) -> CalciatoreDemo {
        var p = calciatore(id)
        if id == 328 { p.assente = true }
        return p
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

    /// La panchina (7): un portiere e i sei migliori disponibili tra gli altri (per rendimento).
    static func panchina(per titolari: [Int]) -> [Int] {
        let fuori = miaRosa.filter { !titolari.contains($0.id) && !$0.assente }
        var scelti: [CalciatoreDemo] = []
        if let portiere = fuori.first(where: { $0.ruolo == "P" }) { scelti.append(portiere) }
        let resto: [CalciatoreDemo] = fuori.filter { $0.ruolo != "P" }.sorted { $0.punti > $1.punti }
        scelti.append(contentsOf: resto.prefix(6))
        return scelti.map { $0.id }
    }

    /// I punti attesi di una formazione: la somma di quelli dei titolari.
    static func punteggio(_ ids: [Int]) -> Double {
        ids.reduce(0.0) { $0 + calciatore($1).puntiAttesi }
    }

    /// La fascia dei punti attesi, come la manda il server: da circa -8 a +8,5 attorno ai punti attesi, 8 volte su 10.
    static func fascia(_ attesi: Double, indicativo: Bool = true) -> [String: Any] {
        ["basso": attesi - 8, "alto": attesi + 8.5, "confidenza": 0.8, "indicativo": indicativo]
    }

    // MARK: - Partite e date

    static let incontri: [(casa: String, trasferta: String)] = [
        ("inter", "roma"), ("milan", "juventus"), ("napoli", "atalanta"), ("lazio", "fiorentina"), ("bologna", "torino"),
        ("genoa", "como"), ("udinese", "parma"), ("cagliari", "verona"), ("lecce", "sassuolo"), ("pisa", "cremonese"),
    ]

    static func avversario(di squadra: String) -> (nome: String, inCasa: Bool)? {
        for i in incontri {
            if i.casa == squadra { return (i.trasferta, true) }
            if i.trasferta == squadra { return (i.casa, false) }
        }
        return nil
    }

    /// Il calcio d'inizio della partita di una squadra (`data_partita`), lo stesso delle partite di Oggi; nil se non gioca.
    static func dataPartita(di squadra: String, adesso: Date, fase: Fase = .prima) -> String? {
        guard let i = incontri.firstIndex(where: { $0.casa == squadra || $0.trasferta == squadra }) else { return nil }
        let ore = orari(adesso: adesso, fase: fase)
        return i < ore.count ? formatta(ore[i], "yyyy-MM-dd HH:mm") : nil
    }

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

    static func json(_ oggetto: Any) -> String {
        let dati = (try? JSONSerialization.data(withJSONObject: oggetto, options: [.sortedKeys])) ?? Data("{}".utf8)
        return String(decoding: dati, as: UTF8.self)
    }

    /// La formazione si chiude mezz'ora prima della prima partita (le regole della demo).
    static let minutiScadenza = 30
    /// Dalla prima partita, i minuti del calcio d'inizio di ogni incontro (dalla sera del primo giorno a due giorni dopo).
    static let scarti: [Double] = [0, 135, 1260, 1395, 1530, 1650, 2700, 2835, 2835, 2970]
    /// A giornata in corso, i minuti da adesso del calcio d'inizio di ogni incontro: Inter-Roma finita, Milan-Juventus
    /// all'intervallo, Lazio-Fiorentina nel primo tempo, il resto da giocare.
    static let minutiInCorso: [Double] = [-130, -45, 150, -30, 240, 1290, 1425, 1560, 2700, 2835]

    /// La prima partita del turno: fra circa sette ore (prima della scadenza), iniziata da poco più di due ore (giornata in
    /// corso), fra quattro giorni (giornata finita: è già la prossima).
    static func inizio(adesso: Date, fase: Fase = .prima) -> Date {
        switch fase {
        case .prima: return quartoDOra(adesso.addingTimeInterval(7 * 3600))
        case .inCorso: return adesso.addingTimeInterval((minutiInCorso.min() ?? 0) * 60)
        case .finita: return adesso.addingTimeInterval(4 * 86_400 + Double(minutiScadenza) * 60)
        }
    }

    static func scadenza(adesso: Date, fase: Fase = .prima) -> Date {
        inizio(adesso: adesso, fase: fase).addingTimeInterval(-Double(minutiScadenza) * 60)
    }

    /// Il calcio d'inizio di ogni incontro (nell'ordine di `incontri`).
    static func orari(adesso: Date, fase: Fase = .prima) -> [Date] {
        if fase == .inCorso { return minutiInCorso.map { adesso.addingTimeInterval($0 * 60) } }
        let primo = inizio(adesso: adesso, fase: fase)
        return scarti.map { primo.addingTimeInterval($0 * 60) }
    }

    /// L'ultimo aggiornamento dei dati: due ore fa.
    static func ultimoAggiornamento(adesso: Date) -> String {
        formatta(adesso.addingTimeInterval(-2 * 3600), "yyyy-MM-dd'T'HH:mm:ss")
    }

    // MARK: - Avvisi, giornata in corso e finita

    /// Gli avvisi di Oggi: chi è in dubbio (con `p_voto`), diffidato, squalificato o infortunato; `in_formazione` se è titolare.
    static func avvisiOggi() -> [[String: Any]] {
        func avviso(_ id: Int, _ tipo: String, _ nota: String) -> [String: Any] {
            let p = calciatore(id)
            var a: [String: Any] = ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra, "tipo": tipo, "nota": nota,
                                    "in_formazione": moduli[0].titolari.contains(id)]
            if tipo == "dubbio" { a["p_voto"] = p.pVoto }
            return a
        }
        return [
            avviso(120, "dubbio", "Affaticamento muscolare, si decide all'ultimo"),
            avviso(104, "diffidato", "Un'ammonizione alla squalifica"),
            avviso(109, "squalificato", "Una giornata"),
            avviso(118, "infortunato", "Lesione al polpaccio, rientro a dicembre"),
            avviso(124, "dubbio", "Botta alla caviglia"),
        ]
    }

    /// Il blocco `in_corso` di Oggi a giornata in corso: punti fatti, previsti, giocatore per giocatore e i cambi dalla panchina.
    /// Un cambio già fatto (Bastrani senza voto, entra Dimarzi) e due probabili.
    static func bloccoInCorso(adesso: Date) -> [String: Any] {
        let ore = orari(adesso: adesso, fase: .inCorso)
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
                    "stato": r.3, "fantavoto": r.4.map { $0 as Any } ?? NSNull(), "data": formatta(ore[i], "yyyy-MM-dd HH:mm")]
        }
        func persona(_ id: Int) -> [String: Any] { let c = calciatore(id); return ["id": c.id, "nome": c.nome, "ruolo": c.ruolo] }
        return [
            "giornata": giornata, "giornata_lega": giornataLega, "formazione_di": "tua",
            "punti_fatti": 39.0, "punti_attesi_restanti": 38.7, "punti_previsti": 77.7, "modificatore": NSNull(), "ancora_da_giocare": 6,
            "giocatori": giocatori,
            "sostituzioni": [
                ["esce": persona(104), "entra": persona(105), "certa": true, "motivo": "senza_voto"],
                ["esce": persona(120), "entra": persona(123), "certa": false, "motivo": "senza_voto"],
                ["esce": persona(107), "entra": persona(110), "certa": false, "motivo": "fuori"],
            ],
            "partite": ["in_corso": 2, "finite": 1, "da_giocare": 7, "rinviate": 0],
        ]
    }

    /// Il blocco `riepilogo` a giornata finita: la giornata appena chiusa, la tua formazione contro la consigliata.
    static func riepilogoFinita() -> [String: Any] {
        ["giornata": giornata, "giornata_lega": giornataLega, "formazione_di": "tua", "nel_diario": true,
         "punti_fatti": 74.5, "punti_attesi": 71.2, "intervallo": fascia(71.2, indicativo: false),
         "consigliata": ["punti_fatti": 78.0, "punti_attesi": 73.7]]
    }

    /// Il blocco `prossima` a giornata finita: la prossima giornata si chiude fra quattro giorni, probabili non ancora uscite.
    static func prossimaDopoFinita(adesso: Date) -> [String: Any] {
        let s = scadenza(adesso: adesso, fase: .finita)
        return ["giornata": giornata + 1, "giornata_lega": giornataLega + 1, "scadenza": formatta(s, "yyyy-MM-dd HH:mm"),
                "prepara_da": formatta(s.addingTimeInterval(-72 * 3600), "yyyy-MM-dd HH:mm"), "con_probabili": false]
    }

    // MARK: - Diario, scambio e svincolo

    /// Punti attesi e fatti di una formazione in una giornata finita.
    struct EsitoGiornata {
        let modulo: String
        let atteso: Double
        let fatti: Double
    }

    /// Una giornata finita (numero di Serie A): la consigliata e, se l'avevi schierata, la tua formazione.
    struct GiornataFinita {
        let serieA: Int
        let consigliata: EsitoGiornata
        let schierata: EsitoGiornata?
    }

    /// Le giornate finite, dalla più recente (Serie A 10-7, cioè 7-4 della lega): il Diario dell'app e «Attesi e fatti» dei
    /// widget, che come il server prendono la tua formazione se c'era, altrimenti la consigliata.
    static let giornateFinite: [GiornataFinita] = [
        GiornataFinita(serieA: 10, consigliata: EsitoGiornata(modulo: "3-4-3", atteso: 69.0, fatti: 72.5), schierata: nil),
        GiornataFinita(serieA: 9, consigliata: EsitoGiornata(modulo: "3-4-3", atteso: 68.5, fatti: 71.0),
                       schierata: EsitoGiornata(modulo: "3-5-2", atteso: 66.0, fatti: 63.5)),
        GiornataFinita(serieA: 8, consigliata: EsitoGiornata(modulo: "3-4-3", atteso: 67.0, fatti: 64.0),
                       schierata: EsitoGiornata(modulo: "3-4-3", atteso: 66.0, fatti: 59.5)),
        GiornataFinita(serieA: 7, consigliata: EsitoGiornata(modulo: "4-3-3", atteso: 65.0, fatti: 60.5), schierata: nil),
    ]

    /// Il miglior scambio (il primo di Scambi): con chi, chi dai, chi ricevi, quanto guadagnate tu e loro.
    static let scambioMigliore = (altra: "Real Madrink", dai: [124], ricevi: [327], mio: 2.4, loro: 1.1)

    /// Il miglior svincolo (il primo dei Cambi consigliati): chi esce, chi entra, quanto guadagni. Rimborso e crediti dopo si
    /// contano dal prezzo pagato (`rimborso`) e dalla quotazione di chi entra, come il server.
    static let svincoloMigliore = (esce: 124, entra: 203, guadagno: 3.4)

    // MARK: - Partite in diretta

    /// Le partite in diretta (`GET /api/live` e `live` del widget) nella fase della giornata. Prima della scadenza tutte da giocare,
    /// con gli orari di Oggi: nessuna partita può essere in corso prima che la formazione si chiuda. A giornata in corso Inter-Roma
    /// finita, Milan-Juventus all'intervallo e Lazio-Fiorentina nel primo tempo. A giornata finita nessuna.
    static func liveDemo(adesso: Date, fase: Fase) -> [String: Any] {
        guard fase != .finita else { return ["in_corso": 0, "partite": [[String: Any]]()] }
        func ev(_ tipo: String, _ minuto: String, _ squadra: String, _ chi: String, _ assist: String? = nil) -> [String: Any] {
            var e: [String: Any] = ["tipo": tipo, "minuto": minuto, "squadra": squadra, "chi": chi]
            if let assist { e["assist"] = assist }
            return e
        }
        let ore = orari(adesso: adesso, fase: fase)
        var partite: [[String: Any]] = []
        for (i, m) in incontri.enumerated() {
            var p: [String: Any] = ["casa": m.casa, "trasferta": m.trasferta, "stato": "da_giocare",
                                    "data": formatta(ore[i], "yyyy-MM-dd HH:mm")]
            if fase == .inCorso {
                switch i {
                case 0:
                    p["stato"] = "finita"; p["gol_casa"] = 2; p["gol_trasferta"] = 1
                    p["eventi"] = [ev("gol", "12'", "casa", "Thorvan", "Barlesi"), ev("gol", "38'", "trasferta", "Dovrenko"),
                                   ev("giallo", "44'", "casa", "Darvini"), ev("rigore", "55'", "casa", "Çalvaroğlu"),
                                   ev("rigore_sbagliato", "58'", "trasferta", "Dovrenko"), ev("rosso", "61'", "trasferta", "Cristoni")]
                case 1:
                    p["stato"] = "intervallo"; p["gol_casa"] = 0; p["gol_trasferta"] = 0
                    p["eventi"] = [ev("giallo", "30'", "trasferta", "Locardi")]
                case 3:
                    p["stato"] = "primo_tempo"; p["minuto"] = "27'"; p["gol_casa"] = 1; p["gol_trasferta"] = 1
                    p["eventi"] = [ev("gol", "11'", "casa", "Castelvera"), ev("gol", "25'", "trasferta", "Hrafnsson")]
                default: break
                }
            }
            partite.append(p)
        }
        return ["aggiornato_il": formatta(adesso, "yyyy-MM-dd HH:mm:ss"), "fonte": "espn", "in_corso": fase == .inCorso ? 2 : 0,
                "partite": partite]
    }

    // MARK: - Widget

    /// Il riassunto dei widget (`GET /api/widget`) nella forma del server (`fanta/widget.py`), dagli stessi dati delle risposte
    /// dell'app. `parziali`: un server che non ha ancora scambio, svincolo e Diario (li elenca in `mancano`).
    static func widget(adesso: Date, fase: Fase = .prima, parziali: Bool = false) -> Data {
        let ids = moduli[0].titolari
        let attesi = punteggio(ids)
        func breve(_ p: CalciatoreDemo) -> [String: Any] { ["id": p.id, "nome": p.nome, "ruolo": p.ruolo, "squadra": p.squadra] }
        func conQuotazione(_ id: Int) -> [String: Any] {
            let p = calciatore(id)
            return breve(p).merging(["quotazione": quotazione(p)]) { _, nuovo in nuovo }
        }
        /// Un giocatore con la sua prossima partita e lo stato delle probabili (rosa e seguiti).
        func conPartita(_ p: CalciatoreDemo) -> [String: Any] {
            var d = breve(p)
            if let a = avversario(di: p.squadra) { d["avversario"] = a.nome; d["in_casa"] = a.inCasa }
            if let data = dataPartita(di: p.squadra, adesso: adesso, fase: fase) { d["data_partita"] = data }
            d["stato"] = p.statoProbabili
            d["percentuale"] = p.percentualeProbabili
            d["punti_attesi"] = p.puntiAttesi
            return d
        }
        // la rosa come il server: con «gioca N%» (`p_voto`), chi è nella formazione e chi tira i rigori, in ordine di partita
        func ordine(_ d: [String: Any]) -> (String, String) { (d["data_partita"] as? String ?? "~", d["nome"] as? String ?? "") }
        let rosa: [[String: Any]] = miaRosa.map { p -> [String: Any] in
            var d = conPartita(p)
            d["p_voto"] = p.assente ? 0.0 : p.pVoto
            d["dubbio"] = p.dubbio
            d["diffidato"] = p.diffidato
            d["titolare"] = ids.contains(p.id)
            d["rigorista"] = rigoristi.contains(p.id)
            return d
        }.sorted { ordine($0) < ordine($1) }
        // i seguiti come il server (#226, #239): «In dubbio · gioca N%» (`dubbio`, `p_voto`) e il fantavoto atteso dell'app
        let osservati: [[String: Any]] = idOsservati.map { id -> [String: Any] in
            let p = osservato(id)
            var d = conPartita(p)
            d["voto_atteso"] = p.votoAtteso
            d["fv_atteso"] = p.fvAtteso
            d["p_voto"] = p.assente ? 0.0 : p.pVoto
            d["dubbio"] = p.dubbio
            return d
        }
        let titolari: [[String: Any]] = ids.map { id -> [String: Any] in
            let p = calciatore(id)
            return breve(p).merging(["punti_attesi": p.puntiAttesi, "p_voto": p.pVoto] as [String: Any]) { _, nuovo in nuovo }
        }
        var formazione: [String: Any] = ["modulo": moduli[0].nome, "punti_attesi": attesi, "intervallo": fascia(attesi),
                                         "titolari": titolari, "panchina": panchina(per: ids)]
        if tuaScelta {
            formazione["tua_scelta"] = true
            formazione["consigliata"] = ["modulo": moduli[0].nome, "punti_attesi": attesi] as [String: Any]
        }
        let primaPartita = formatta(inizio(adesso: adesso, fase: fase), "yyyy-MM-dd HH:mm")
        let scadenzaFase = scadenza(adesso: adesso, fase: fase)
        let oreMancanti = (scadenzaFase.timeIntervalSince(adesso) / 360).rounded() / 10
        let diffidati = miaRosa.filter { $0.diffidato }.map { $0.id }
        let rigoristiInRosa = miaRosa.filter { rigoristi.contains($0.id) }.map { $0.id }
        var w: [String: Any] = [
            "giornata": giornata, "giornata_lega": giornataLega, "fase": fase.rawValue,
            "prima_partita": primaPartita, "scadenza": formatta(scadenzaFase, "yyyy-MM-dd HH:mm"), "ore_mancanti": oreMancanti,
            "iniziata": fase == .inCorso, "con_probabili": fase != .finita,
            "squadra": nomeMia, "crediti_residui": creditiResidui, "formazione": formazione,
            "avvisi": avvisiOggi(), "rosa": rosa, "squalificati": [Int](), "diffidati": diffidati, "rigoristi": rigoristiInRosa,
            "osservati": osservati, "dati": ["ultimo_aggiornamento": ultimoAggiornamento(adesso: adesso)],
            "live": liveDemo(adesso: adesso, fase: fase),
        ]
        switch fase {
        case .prima:
            break
        case .inCorso:
            // come il server: a giornata in corso il widget riceve solo i numeri, non giocatore per giocatore né i cambi
            w["in_corso"] = bloccoInCorso(adesso: adesso).filter { $0.key != "giocatori" && $0.key != "sostituzioni" }
        case .finita:
            // a giornata finita giornata e scadenza sono già quelle della prossima
            w["giornata"] = giornata + 1
            w["giornata_lega"] = giornataLega + 1
            w["riepilogo"] = riepilogoFinita()
            w["prossima"] = prossimaDopoFinita(adesso: adesso)
        }
        if parziali {
            w["diario"] = [[String: Any]]()
            w["mancano"] = ["scambio", "svincolato"]
        } else {
            w["diario"] = giornateFinite.map { g -> [String: Any] in
                let e = g.schierata ?? g.consigliata
                return ["giornata": g.serieA, "giornata_lega": g.serieA - (giornata - giornataLega), "stagione": stagioneInCorso,
                        "attesi": e.atteso, "fatti": e.fatti, "intervallo": fascia(e.atteso)]
            }
            let s = scambioMigliore
            w["scambio"] = ["mia": nomeMia, "altra": s.altra, "do": s.dai.map(conQuotazione), "ricevo": s.ricevi.map(conQuotazione),
                            "guadagno_mio": s.mio, "guadagno_loro": s.loro, "valido": true] as [String: Any]
            let v = svincoloMigliore
            w["svincolato"] = ["esce": breve(calciatore(v.esce)), "entra": conQuotazione(v.entra), "guadagno": v.guadagno,
                               "fattibile": true] as [String: Any]
        }
        return Data(json(w).utf8)
    }
}
