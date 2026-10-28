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
    // Dettagli della previsione (scheda del giocatore, confronto, ballottaggi): tutti opzionali.
    let votoAtteso: Double?
    let rigoriAttesi: Double?
    let portaInviolata: Double?
    let pGol: Double?
    let pAssist: Double?
    let pGiallo: Double?
    let pRosso: Double?
    let quotaTitolare: Double?
    /// Da 1 (partita facile) a 5 (molto dura).
    let difficolta: Double?
    let golSquadra: Double?
    let golAvversario: Double?
    /// «titolare», «panchina», «infortunato»... come lo scrivono le probabili formazioni.
    let stato: String?
    let percentuale: Double?
    let nota: String?
    let motivi: [String]?
    /// Solo nella scheda del giocatore: la giornata a cui si riferisce la previsione.
    let giornata: Int?
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
    let giornate: [Int]?
    var id: String { "\(esce.id)-\(entra.id)" }
}

struct Mercato: Decodable {
    let squadra: String?
    let proposte: [PropostaMercato]
    let svincolati: Int?
    let creditiResidui: Double?
    let rimborsoIpotizzato: Double?
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
    let squadraSlug: String?
    let quotazione: Double?
    let quotazioneIniziale: Double?
    let fvm: Double?
}

struct StagioneGiocatore: Decodable {
    let giornateGiocateSerieA: Double?
    let presenze: Double?
    let conVoto: Double?
    let mediaVoto: Double?
    let fantamedia: Double?
    let gol: Double?
    let assist: Double?
    let ammonizioni: Double?
    let espulsioni: Double?
    let golSubiti: Double?
    let rigSegnati: Double?
    let rigParati: Double?
}

struct SchedaGiocatore: Decodable {
    let calciatore: AnagraficaGiocatore
    let stagione: StagioneGiocatore?
    let previsione: Giocatore?
    let proprietario: String?
    /// Voto e fantavoto giornata per giornata (per il grafico e la forma).
    let voti: [VotoGiornata]?
    let avanzate: StatisticheAvanzate?
    let rendimento: Rendimento?
}

/// I sigilli dell'immagine di una squadra della lega: stemma e maglia caricati dall'utente.
struct ImmaginiSquadra: Decodable, Equatable {
    let stemma: Bool?
    let maglia: Bool?
}

struct SquadraLega: Decodable, Identifiable {
    let nome: String
    let mia: Bool?
    let giocatori: Int?
    let creditiResidui: Double?
    let immagini: ImmaginiSquadra?
    var id: String { nome }
}

struct GiocatoreRosa: Decodable, Identifiable {
    let id: Int?
    let nome: String
    let ruolo: String?
    let squadra: String?
    let squadraSlug: String?
    let costo: Double?
    let quotazione: Double?
    let previsione: Giocatore?
    var ident: String { "\(id ?? -1)-\(nome)" }
}

struct Rosa: Decodable {
    let nome: String
    let mia: Bool?
    let creditiResidui: Double?
    let aggiornato: String?
    let giocatori: [GiocatoreRosa]
    let avvisi: [String]?
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
    /// Variazione percentuale dei punti attesi per reparto («mio» e «loro»): [P, D, C, A].
    let reparti: RepartiScambio?
    let percentualeMio: Double?
    let quotazioneDo: Double?
    let quotazioneRicevo: Double?
    var id: String { altra + "|" + `do`.map { String($0.id) }.joined(separator: ",") + "|" + ricevo.map { String($0.id) }.joined(separator: ",") }
}

struct RepartiScambio: Decodable {
    let mio: [String: Double]?
    let loro: [String: Double]?
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
    let dev: Double?
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
    let fuori: [Giocatore]?
    let senzaDati: [String]?
    let dev: Double?
}

struct RuoloAsta: Decodable, Identifiable {
    struct Voce: Decodable, Identifiable {
        let id: Int
        let nome: String
        let squadra: String?
        let quotazione: Double?
        let prezzo: Double?
        let puntiStagione: Double?
    }
    let ruolo: String
    let quota: Double?
    let crediti: Double?
    /// Solo nella riparazione: i posti da riempire in quel reparto.
    let posti: Double?
    let giocatori: [Voce]
    var id: String { ruolo }
}

struct PianoAsta: Decodable {
    let crediti: Double?
    let squadre: Int?
    let panchina: Double?
    let ruoli: [RuoloAsta]
}

/// Riparazione di febbraio (`/api/asta?modo=riparazione`): solo gli svincolati, con i consigli per la mia squadra.
struct PianoRiparazione: Decodable {
    struct PerTe: Decodable, Identifiable {
        let id: Int
        let nome: String
        let ruolo: String?
        let squadra: String?
        let prezzo: Double?
        let miglioramento: Double?
        let alPostoDi: String?
    }
    let modo: String?
    let tuoiCrediti: Double?
    let creditiLega: Double?
    let postiLiberi: Double?
    let nota: String?
    let ruoli: [RuoloAsta]
    let perTe: [PerTe]?
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
    struct Probabili: Decodable, Identifiable { let giornata: Int; let giocatori: Int?; let rilevato: String?; var id: Int { giornata } }
    /// Quanto le probabilità previste somigliano a chi ha davvero giocato (un gruppo per fascia di titolarità).
    struct GruppoCalibrazione: Decodable, Identifiable {
        let gruppo: String
        let n: Int?
        let osservato: Double?
        let previsto: Double?
        let indicativo: Bool?
        var id: String { gruppo }
    }
    struct Calibrazione: Decodable { let giornate: Int?; let gruppi: [GruppoCalibrazione]? }
    let stagione: String?
    let aggiornamenti: [AggiornamentoDati]?
    let calciatori: Int?
    let partite: Partite?
    let voti: Int?
    let foto: Int?
    let probabili: [Probabili]?
    let calibrazione: Calibrazione?
    let coppeFino: String?
}

struct EsitoImportazione: Decodable {
    let squadreImportate: [String]?
    let totaleSquadre: Int?
    let avvisi: [String]?
    let miaSquadra: String?
    let riepilogo: String?
    let differenze: Differenze?
}

/// Un giocatore nei movimenti delle rose (scambi, svincolati presi, tagli).
struct GiocatoreMovimento: Decodable, Identifiable {
    let id: Int?
    let nome: String
    let ruolo: String?
    let squadra: String?
    let costo: Double?
    var ident: String { "\(id ?? -1)-\(nome)" }
}

struct ScambioMovimento: Decodable, Identifiable {
    let squadre: [String]
    let daA: [GiocatoreMovimento]
    let daB: [GiocatoreMovimento]
    var id: String { squadre.joined(separator: ">") + daA.map(\.ident).joined() }
}

struct GruppoMovimento: Decodable, Identifiable {
    let squadra: String
    let giocatori: [GiocatoreMovimento]
    var id: String { squadra }
}

struct CreditoMovimento: Decodable, Identifiable {
    let squadra: String
    let prima: Double?
    let dopo: Double?
    var id: String { squadra }
}

/// Cosa è cambiato nelle rose da un'importazione all'altra. Lo stesso modello vale per l'esito dell'importazione e per lo storico
/// (`/api/movimenti`), dove c'è anche la data.
struct Differenze: Decodable, Identifiable {
    let quando: String?
    let primaImportazione: Bool?
    let nessunaDifferenza: Bool?
    let scambi: [ScambioMovimento]?
    let svincolatiPresi: [GruppoMovimento]?
    let tagliati: [GruppoMovimento]?
    let crediti: [CreditoMovimento]?
    let testo: String?
    var id: String { (quando ?? "") + (testo ?? "") }
}


extension FormazioneBreve {
    /// false quando il server non ha ancora una formazione (modulo mancante o «–», punti assenti).
    var disponibile: Bool {
        guard let m = modulo?.trimmingCharacters(in: .whitespaces), !m.isEmpty, !["-", "–", "—"].contains(m) else { return false }
        return punteggioAtteso != nil
    }
}


// MARK: - Scheda del giocatore: voti, statistiche avanzate, rendimento

/// Una giornata giocata: voto, fantavoto e bonus (nil dove non ha preso voto).
struct VotoGiornata: Decodable, Identifiable, Equatable {
    let giornata: Int
    let voto: Double?
    let fv: Double?
    let gol: Double?
    let assist: Double?
    var id: Int { giornata }
}

struct StagionePrecedente: Decodable, Identifiable, Equatable {
    let stagione: String
    let minuti: Double?
    let gol: Double?
    let xg: Double?
    let assist: Double?
    let xa: Double?
    var id: String { stagione }
}

struct StatisticheAvanzate: Decodable, Equatable {
    struct Per90: Decodable, Equatable {
        let xg: Double?
        let xa: Double?
        let tiri: Double?
    }
    let minuti: Double?
    let xg: Double?
    let xa: Double?
    let tiri: Double?
    let passaggiChiave: Double?
    let rigoriCalciati: Double?
    let punizioni: Double?
    let per90: Per90?
    let stagioniPrecedenti: [StagionePrecedente]?
}

/// «Rende sopra o sotto le occasioni?»: punti a partita in più (o in meno) di quanto dicono xG e xA.
struct Rendimento: Decodable, Equatable {
    let sovraRendimento: Double?
    let golMenoXg: Double?
    let assistMenoXa: Double?
}
