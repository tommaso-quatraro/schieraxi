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
    let quotazione: Double?
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
    // Analisi completa (`completo=true`, scambi N contro M con conguaglio): tutti opzionali, un server più vecchio non li manda.
    let completo: Bool?
    /// Le rose dopo lo scambio sono valide per tutte e due le squadre e i crediti bastano.
    let valido: Bool?
    let problemi: [String]?
    let rose: RoseDopoScambio?
    let valoreRosa: LatiScambio<VariazioneRosa>?
    let panchina: LatiScambio<VariazioneRosa>?
    let conguaglio: ConguaglioScambio?
    /// Punti attesi in stagione, con il valore dei crediti scambiati (se si è indicato un conguaglio).
    let nettoMio: Double?
    let nettoLoro: Double?
    let giudizio: GiudizioScambio?
    var id: String { altra + "|" + `do`.map { String($0.id) }.joined(separator: ",") + "|" + ricevo.map { String($0.id) }.joined(separator: ",") }
}

/// Un valore per me e uno per l'altra squadra.
struct LatiScambio<T: Decodable>: Decodable {
    let mio: T?
    let loro: T?
}

struct VariazioneRosa: Decodable {
    let prima: Double?
    let dopo: Double?
    let variazione: Double?
    let percentuale: Double?
}

struct RoseDopoScambio: Decodable {
    let mio: RosaDopoScambio?
    let loro: RosaDopoScambio?
}

struct RosaDopoScambio: Decodable {
    let squadra: String?
    let valida: Bool?
    let problemi: [String]?
    let modulo: String?
}

/// I crediti scambiati: positivo = li ricevi tu (e la squadra «loro» li paga).
struct ConguaglioScambio: Decodable {
    let crediti: Int?
    let valido: Bool?
    let problema: String?
    let residui: LatiScambio<Double>?
    let dopo: LatiScambio<Double>?
    /// «nessuno», «loro» o «tu».
    let chiPaga: String?
    let tassoMio: Double?
    let tassoLoro: Double?
    let valoreMio: Double?
    let valoreLoro: Double?
}

struct GiudizioScambio: Decodable {
    let chi: String?
    let testo: String?
    let soglia: Double?
    let spiegazione: [String]?
}

struct RepartiScambio: Decodable {
    let mio: [String: Double]?
    let loro: [String: Double]?
}

/// Le ricerche di scambi che restano oggi (il server ne conta un numero al giorno; l'amministratore non ha limite: `tetto` nil).
struct LimiteRicerche: Decodable, Equatable {
    let restano: Int?
    let tetto: Int?

    /// «Ne restano 3 oggi su 20»; nil se non c'è un limite o non si sa.
    var testo: String? {
        guard let restano, let tetto else { return nil }
        return "Ne \(restano == 1 ? "resta" : "restano") \(restano) oggi su \(tetto)"
    }
}

struct ProposteScambi: Decodable {
    let giornate: [Int]?
    let proposte: [PropostaScambio]
    /// Quante ricerche restano oggi (facoltativo: server vecchio o amministratore).
    let ricerche: LimiteRicerche?
}

struct FormazioneBreve: Decodable {
    let modulo: String?
    let punteggioAtteso: Double?
    let squadra: String?
    let dev: Double?
    let intervallo: IntervalloPunti?
    /// true se è la formazione salvata dall'utente (non la consigliata). Letto in modo tollerante: se manca o ha un tipo strano vale «consigliata».
    private let tuaSceltaLetta: Tollerante<Bool>?
    var tuaScelta: Bool { tuaSceltaLetta?.valore ?? false }

    private enum CodingKeys: String, CodingKey {
        case modulo, punteggioAtteso, squadra, dev, intervallo
        case tuaSceltaLetta = "tuaScelta"
    }

    /// Titolo della scheda in Oggi, coerente con quello che mostra.
    var titoloScheda: String { tuaScelta ? "La tua scelta" : "La formazione consigliata" }
}

struct Avviso: Decodable, Identifiable {
    let id: Int
    let nome: String
    let ruolo: String?
    let squadra: String?
    let tipo: String?
    let nota: String?
    let inFormazione: Bool?
    /// Probabilità di giocare (0-1), per i dubbi: «Dubbio (55%)» come nella web app.
    var pVoto: Double? = nil
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
    /// Quando si chiude l'invio della formazione (prima partita meno i minuti della lega). Facoltativo (server vecchio).
    let scadenza: String?
    let minutiScadenza: Int?
    /// Il numero della giornata nella lega (può essere diverso da quello di Serie A). Facoltativo; `null` prima che la lega parta.
    let giornataLega: Int?
    let iniziata: Bool?
    let conProbabili: Bool?
    let formazione: FormazioneBreve?
    let avvisi: [Avviso]?
    let migliori: [Giocatore]?
    let partite: [Partita]?
    /// Le cose da fare (max 8, dal server): un pulsante per riga con il suo collegamento. Facoltativo (server vecchio).
    let daFare: [DaFareVoce]?
    /// true se la lega non ha ancora le rose: Oggi mostra il benvenuto con «Importa le rose». Facoltativo (server vecchio).
    let senzaRose: Bool?
    /// I miei titolari consigliati per squadra: servono a evidenziare le partite in cui giocano. Facoltativo (server vecchio).
    let mieiTitolari: MieiTitolari?
    /// Quanto sono fresche le probabili (facoltativo: server vecchio o probabili assenti). Letto in modo tollerante.
    let probabili: Tollerante<ProbabiliFresche>?
}

/// Quando sono state lette le probabili formazioni (campo `probabili` di Oggi). Ogni campo è facoltativo.
struct ProbabiliFresche: Decodable, Equatable {
    let aggiornateIl: String?
    let minutiFa: Int?
    let eta: String?
    let testo: String?
    let vecchie: Bool?
    let avviso: String?

    /// La riga discreta: «Probabili aggiornate alle 13:05 · 2 ore fa». Nil se il server non ha mandato il testo.
    var riga: String? {
        let t = testo?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let e = eta?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if t.isEmpty { return nil }
        return e.isEmpty ? t : "\(t) · \(e)"
    }

    /// L'avviso in evidenza: solo se le probabili sono vecchie e c'è la frase.
    var avvisoVisibile: String? {
        guard vecchie == true else { return nil }
        let a = avviso?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return a.isEmpty ? nil : a
    }
}

/// Una cosa da fare in Oggi: «Giocatore 044 è in dubbio: sostituiscilo», «Aggiorna le rose», «Rinnova l'app»...
struct DaFareVoce: Decodable, Identifiable, Equatable {
    let id: String
    /// dubbio, formazione, svincolato, scambio, rose, certificato, diario, backup, server, primo_avvio
    let tipo: String?
    let testo: String
    /// 1 = urgente ... 3 = quando puoi.
    let priorita: Int?
    /// Cosa dice il pulsante («Sostituisci», «Vedi»...).
    let azione: String?
    let destinazione: DestinazioneDaFare?

    private enum Chiavi: String, CodingKey { case id, tipo, testo, priorita, azione, destinazione }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        // l'id può essere un testo o un numero: si legge in tutti e due i modi
        if let t = try? k.decode(String.self, forKey: .id) { id = t }
        else if let n = try? k.decode(Int.self, forKey: .id) { id = String(n) }
        else { id = UUID().uuidString }
        tipo = try? k.decodeIfPresent(String.self, forKey: .tipo)
        testo = (try? k.decode(String.self, forKey: .testo)) ?? ""
        priorita = try? k.decodeIfPresent(Int.self, forKey: .priorita)
        azione = try? k.decodeIfPresent(String.self, forKey: .azione)
        destinazione = try? k.decodeIfPresent(DestinazioneDaFare.self, forKey: .destinazione)
    }

    init(id: String, tipo: String? = nil, testo: String, priorita: Int? = nil, azione: String? = nil, destinazione: DestinazioneDaFare? = nil) {
        self.id = id; self.tipo = tipo; self.testo = testo; self.priorita = priorita; self.azione = azione; self.destinazione = destinazione
    }
}

struct DestinazioneDaFare: Decodable, Equatable {
    let scheda: String?
    let sezione: String?
    /// `schieraxi://...`
    let link: String?

    init(scheda: String? = nil, sezione: String? = nil, link: String? = nil) { self.scheda = scheda; self.sezione = sezione; self.link = link }
}

struct OpzioneModulo: Decodable, Identifiable {
    let modulo: String
    let punteggioAtteso: Double
    let dev: Double?
    let titolari: [Int]
    let panchina: [Int]
    /// La fascia dei punti (8 volte su 10). Facoltativa (server vecchio).
    let intervallo: IntervalloPunti?
    var id: String { modulo }
}

struct LivelloRischio: Decodable, Identifiable {
    let rischio: Int
    /// Id dello stile (-2...2, come `rischio`) e una riga che lo spiega: i server vecchi non li mandano.
    let stile: Int?
    let descrizione: String?
    let nome: String
    let modulo: String
    let punteggioAtteso: Double
    let moduli: [OpzioneModulo]
    let intervallo: IntervalloPunti?
    var id: Int { rischio }
}

struct Formazione: Decodable {
    let squadra: String?
    let giornata: Int
    /// Il numero della giornata nella lega (facoltativo: server vecchio, o lega non ancora partita).
    let giornataLega: Int?
    let modulo: String
    let punteggioAtteso: Double
    let titolari: [Giocatore]
    let panchina: [Giocatore]
    let conProbabili: Bool?
    let livelli: [LivelloRischio]?
    /// Lo stile da proporre per primo (di solito 0, «Equilibrata»).
    let stileConsigliato: Int?
    let schede: [String: Giocatore]?
    let fuori: [Giocatore]?
    let senzaDati: [String]?
    let dev: Double?
    let intervallo: IntervalloPunti?
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

// MARK: - Tipi usati da Oggi (stanno qui perché Modelli.swift è compilato anche dal widget)

/// Un elemento di un elenco letto senza far fallire tutto: se è sbagliato o ha il tipo diverso, `valore` resta nil
/// e gli altri elementi si leggono lo stesso (un campo nuovo o strano del server non deve rompere una schermata).
struct Tollerante<T: Decodable>: Decodable {
    let valore: T?
    init(from decoder: Decoder) throws {
        valore = try? T(from: decoder)
    }
}

/// Un mio titolare consigliato (campo `miei_titolari` di Oggi): serve a evidenziare le partite in cui gioca.
struct MioTitolare: Decodable, Identifiable, Equatable {
    let id: Int
    let nome: String
    let ruolo: String?
    /// La squadra (la chiave sotto cui sta nel campo del server): non arriva dal JSON del titolare, la mette `MieiTitolari`.
    var squadra: String? = nil

    private enum CodingKeys: String, CodingKey { case id, nome, ruolo }
}

/// I miei titolari per squadra. Tollerante: un elemento sbagliato si salta, un campo mancante non rompe Oggi.
struct MieiTitolari: Decodable, Equatable {
    /// Chiave = squadra normalizzata (minuscole, senza trattini né trattini bassi).
    private(set) var perSquadra: [String: [MioTitolare]] = [:]

    init(perSquadra: [String: [MioTitolare]] = [:]) {
        var nuovo: [String: [MioTitolare]] = [:]
        for (squadra, elenco) in perSquadra { nuovo[Self.chiave(squadra)] = elenco }
        self.perSquadra = nuovo
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        guard let grezzo = try? c.decode([String: Tollerante<[Tollerante<MioTitolare>]>].self) else { return }
        for (squadra, elenco) in grezzo {
            perSquadra[Self.chiave(squadra)] = (elenco.valore ?? []).compactMap(\.valore).map { t in
                var t = t
                t.squadra = squadra
                return t
            }
        }
    }

    /// Il decodificatore converte «hellas_verona» in «hellasVerona»: si confronta senza maiuscole e separatori.
    static func chiave(_ squadra: String) -> String {
        squadra.lowercased().filter { $0 != "_" && $0 != "-" && $0 != " " }
    }

    func titolari(di squadra: String) -> [MioTitolare] { perSquadra[Self.chiave(squadra)] ?? [] }

    /// I titolari delle due squadre della partita, quelli di casa prima.
    func titolari(casa: String, trasferta: String) -> [MioTitolare] { titolari(di: casa) + titolari(di: trasferta) }
}

// MARK: - Fascia dei punti attesi (sta qui perché Modelli.swift è compilato anche dal widget)

/// La fascia dei punti attesi (campo `intervallo` del server): «tra 62 e 84, 8 volte su 10».
/// Tollerante: se il campo è sbagliato o incompleto resta vuoto, senza rompere la schermata che lo contiene.
struct IntervalloPunti: Decodable, Equatable {
    var basso: Double?
    var alto: Double?
    /// Quota dei casi dentro la fascia, per esempio 0,8.
    var confidenza: Double?
    /// true se la fascia è ancora poco provata: va detto.
    var indicativo: Bool?

    private enum Chiavi: String, CodingKey { case basso, alto, confidenza, indicativo }

    init(basso: Double? = nil, alto: Double? = nil, confidenza: Double? = nil, indicativo: Bool? = nil) {
        self.basso = basso; self.alto = alto; self.confidenza = confidenza; self.indicativo = indicativo
    }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        basso = (try? k.decodeIfPresent(Double.self, forKey: .basso)) ?? nil
        alto = (try? k.decodeIfPresent(Double.self, forKey: .alto)) ?? nil
        confidenza = (try? k.decodeIfPresent(Double.self, forKey: .confidenza)) ?? nil
        indicativo = (try? k.decodeIfPresent(Bool.self, forKey: .indicativo)) ?? nil
    }

    /// I due estremi ci sono e sono numeri veri, in ordine.
    var valido: Bool {
        guard let basso, let alto, basso.isFinite, alto.isFinite else { return false }
        return basso <= alto
    }

    /// «8 volte su 10» (o «19 volte su 20»); nil se la confidenza manca o non è tra 0 e 1.
    var quanteVolte: String? {
        guard let c = confidenza, c.isFinite, c > 0, c < 1 else { return nil }
        for base in [10, 20, 100] {
            let n = c * Double(base)
            if abs(n - n.rounded()) < 0.001 { return "\(Int(n.rounded())) volte su \(base)" }
        }
        return "\(Formato.intero(c * 100)) volte su 100"
    }

    /// «tra 62 e 84 · 8 volte su 10» (+ « (indicativo)»), o nil se la fascia non è valida.
    var testo: String? {
        guard valido else { return nil }
        var t = "tra \(Formato.intero(basso)) e \(Formato.intero(alto))"
        if let v = quanteVolte { t += " · \(v)" }
        if indicativo == true { t += " (indicativo)" }
        return t
    }

    /// Il testo da mostrare accanto ai punti attesi: la fascia, oppure «oscilla di ±N» se manca (server vecchio).
    static func frase(_ intervallo: IntervalloPunti?, dev: Double?) -> String? {
        if let t = intervallo?.testo { return t }
        guard let dev, dev.isFinite, dev >= 0 else { return nil }
        return "oscilla di ±\(Formato.intero(dev))"
    }
}
