import Foundation

// Le risposte del server (JSON con nomi_in_snake_case, convertiti da Decodifica). Quasi tutto è opzionale: un campo mancante non deve rompere la schermata.

struct InfoServer: Decodable {
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
    let ruolo: String?
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
    /// Lo stesso giocatore può avere più avvisi (dubbio e diffidato): l'id da solo non basta per le liste.
    var ident: String { "\(id)-\(tipo ?? "")" }
}

struct Partita: Decodable, Identifiable {
    let data: String?
    let casa: String
    let trasferta: String
    let giocata: Bool?
    var id: String { (data ?? "") + casa + trasferta }
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

struct OpzioneModulo: Decodable, Identifiable {
    let modulo: String
    let punteggioAtteso: Double
    let titolari: [Int]
    let panchina: [Int]
    var id: String { modulo }
}

struct LivelloRischio: Decodable, Identifiable {
    let rischio: Int
    let nome: String
    let modulo: String
    let punteggioAtteso: Double
    let moduli: [OpzioneModulo]
    var id: Int { rischio }
}

struct Formazione: Decodable {
    let squadra: String?
    let giornata: Int
    let modulo: String
    let punteggioAtteso: Double
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let conProbabili: Bool?
    let livelli: [LivelloRischio]?
    let schede: [String: Giocatore]?
}

struct RuoloAsta: Decodable, Identifiable {
    struct Voce: Decodable, Identifiable {
        let id: Int
        let nome: String
        let squadra: String?
        let prezzo: Double?
        let puntiStagione: Double?
    }
    let ruolo: String
    let quota: Double?
    let crediti: Double?
    let giocatori: [Voce]
    var id: String { ruolo }
}

struct PianoAsta: Decodable {
    let crediti: Double?
    let squadre: Int?
    let ruoli: [RuoloAsta]
}

struct VoceNovita: Decodable, Identifiable {
    let versione: String
    let data: String?
    let titolo: String
    let voci: [String]
    var id: String { versione }
}

struct AggiornamentoDati: Decodable, Identifiable {
    let cosa: String
    let quando: String?
    let errori: [String]?
    var id: String { cosa + (quando ?? "") }
}

struct StatoDati: Decodable {
    struct Partite: Decodable { let totali: Int?; let giocate: Int? }
    let stagione: String?
    let aggiornamenti: [AggiornamentoDati]?
    let calciatori: Int?
    let partite: Partite?
    let voti: Int?
    let coppeFino: String?
}

struct EsitoImportazione: Decodable {
    let squadreImportate: [String]?
    let totaleSquadre: Int?
    let avvisi: [String]?
    let miaSquadra: String?
    let riepilogo: String?
}


extension FormazioneBreve {
    /// false quando il server non ha ancora una formazione (modulo mancante o «–», punti assenti).
    var disponibile: Bool {
        guard let m = modulo?.trimmingCharacters(in: .whitespaces), !m.isEmpty, !["-", "–", "—"].contains(m) else { return false }
        return punteggioAtteso != nil
    }
}
