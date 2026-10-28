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
