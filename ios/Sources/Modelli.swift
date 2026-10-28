import Foundation

// Le risposte del server (JSON con nomi_in_snake_case, convertiti da Api.get). Quasi tutto è opzionale: un campo mancante non deve rompere la schermata.

struct Stato: Decodable {
    let stagione: String?
    let prossimaGiornata: Int?
    let ultimoAggiornamento: String?
    let miaSquadra: String?
    let versione: String?
    let aggiornamentoInCorso: Bool?
}

struct Giocatore: Decodable, Identifiable {
    let id: Int
    let nome: String
    let ruolo: String
    let squadra: String?
    let avversario: String?
    let inCasa: Bool?
    let pVoto: Double?
    let fvAtteso: Double?
    let puntiAttesi: Double?
    let golAttesi: Double?
    let assistAttesi: Double?
    let indice: Double?
    let dubbio: Bool?
    let diffidato: Bool?
    let titolarita: String?
    let dataPartita: String?
    let proprietario: String?
    let assente: Bool?
}

struct GiocatoreBreve: Decodable, Identifiable, Hashable {
    let id: Int
    let nome: String
    let ruolo: String
    let squadra: String?
    let quotazione: Double?
}

struct PropostaMercato: Decodable, Identifiable {
    let esce: GiocatoreBreve
    let entra: GiocatoreBreve
    let guadagno: Double
    let breve: Double?
    let rimborso: Double?
    let creditiDopo: Double?
    let fattibile: Bool?
    var id: String { "\(esce.id)-\(entra.id)" }
}

struct Mercato: Decodable {
    let squadra: String?
    let proposte: [PropostaMercato]
    let svincolati: Int?
    let creditiResidui: Double?
}

struct ElencoGiocatori: Decodable {
    let giornata: Int?
    let giocatori: [Giocatore]
}

struct PartitaCalendario: Decodable, Identifiable {
    let giornata: Int
    let avversario: String
    let inCasa: Bool?
    let difficolta: Double?
    let data: String?
    var id: Int { giornata }
}

struct SquadraCalendario: Decodable, Identifiable {
    let squadra: String
    let media: Double?
    let partite: [PartitaCalendario]
    var id: String { squadra }
}

struct Calendario: Decodable {
    let giornate: [Int]
    let squadre: [SquadraCalendario]
}

struct AnagraficaGiocatore: Decodable {
    let id: Int
    let nome: String
    let ruolo: String
    let squadra: String?
    let quotazione: Double?
    let quotazioneIniziale: Double?
    let fvm: Double?
}

struct StagioneGiocatore: Decodable {
    let presenze: Double?
    let conVoto: Double?
    let mediaVoto: Double?
    let fantamedia: Double?
    let gol: Double?
    let assist: Double?
    let ammonizioni: Double?
    let espulsioni: Double?
}

struct SchedaGiocatore: Decodable {
    let calciatore: AnagraficaGiocatore
    let stagione: StagioneGiocatore?
    let previsione: Giocatore?
    let proprietario: String?
}

struct SquadraLega: Decodable, Identifiable {
    let nome: String
    let mia: Bool?
    let giocatori: Int?
    var id: String { nome }
}

struct GiocatoreRosa: Decodable, Identifiable {
    let id: Int?
    let nome: String
    let ruolo: String
    let squadra: String?
    let costo: Double?
    let quotazione: Double?
    var ident: String { "\(id ?? -1)-\(nome)" }
}

struct Rosa: Decodable {
    let nome: String
    let mia: Bool?
    let giocatori: [GiocatoreRosa]
}

struct PropostaScambio: Decodable, Identifiable {
    let mia: String?
    let altra: String
    let `do`: [GiocatoreBreve]
    let ricevo: [GiocatoreBreve]
    let guadagnoMio: Double
    let guadagnoLoro: Double
    let perGiornataMio: [Double]?
    let perGiornataLoro: [Double]?
    let breveMio: Double?
    let breveLoro: Double?
    let giornate: [Int]?
    var id: String { altra + "|" + `do`.map { String($0.id) }.joined(separator: ",") + "|" + ricevo.map { String($0.id) }.joined(separator: ",") }
}

struct ProposteScambi: Decodable {
    let giornate: [Int]?
    let proposte: [PropostaScambio]
}

struct FormazioneBreve: Decodable {
    let modulo: String?
    let punteggioAtteso: Double?
    let squadra: String?
}

struct Avviso: Decodable, Identifiable {
    let id: Int
    let nome: String
    let ruolo: String?
    let squadra: String?
    let tipo: String?
    let nota: String?
    let inFormazione: Bool?
}

struct Partita: Decodable, Identifiable {
    let data: String
    let casa: String
    let trasferta: String
    let giocata: Bool?
    var id: String { data + casa + trasferta }
}

struct Oggi: Decodable {
    let giornata: Int
    let inizio: String?
    let iniziata: Bool?
    let conProbabili: Bool?
    let formazione: FormazioneBreve?
    let avvisi: [Avviso]?
    let migliori: [Giocatore]?
    let partite: [Partita]?
}

struct Formazione: Decodable {
    let squadra: String?
    let giornata: Int
    let modulo: String
    let punteggioAtteso: Double
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let conProbabili: Bool?
}

/// Date del server: "2026-10-27 18:30", ora italiana.
enum Quando {
    private static let italia = Locale(identifier: "it_IT")

    private static let lettura: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f
    }()

    private static let scrittura: DateFormatter = {
        let f = DateFormatter()
        f.locale = italia
        f.timeZone = TimeZone(identifier: "Europe/Rome")
        f.dateFormat = "EEE d MMM, HH:mm"
        return f
    }()

    static func data(_ testo: String?) -> Date? {
        guard let testo else { return nil }
        return lettura.date(from: String(testo.prefix(16)))
    }

    static func leggibile(_ testo: String?) -> String {
        guard let d = data(testo) else { return testo ?? "" }
        return scrittura.string(from: d)
    }
}
