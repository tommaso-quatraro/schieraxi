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
    /// A giornata iniziata (quando `titolarita` arriva vuota): `fatto`, `senza_voto`, `attesa_voti`, `in_corso`, `da_giocare`, `rinviata`.
    let statoPartita: String?
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
    /// L'etichetta pronta dal server (`fanta/etichette.py`, `{codice, testo, tono}`): il suo testo va mostrato com'è, al posto
    /// della titolarità composta qui. Facoltativa e tollerante: un server vecchio non la manda, una forma strana vale «niente».
    let etichetta: Avviso.EtichettaPronta?
    /// Solo nella scheda del giocatore: la giornata a cui si riferisce la previsione.
    let giornata: Int?
    /// Solo nella scheda: la stessa giornata con il numero della lega (facoltativo, si preferisce a `giornata`).
    let giornataLega: Int?
    /// «Perché questo numero» (facoltativo: i server più vecchi non lo mandano). Letto senza far fallire la scheda.
    private let percheNumero: Tollerante<[Tollerante<MotivoNumero>]>?
    /// Il fantavoto atteso del giocatore medio del suo ruolo (il riferimento dei motivi). Facoltativo.
    private let fvAttesoMedioRuolo: Tollerante<Double>?
    /// A giornata iniziata, il fantavoto preso con le regole della lega (`stato_partita` `fatto`; server dal 2/11/2026). Facoltativo.
    private let fvPreso: Tollerante<Double>?
    /// Il modo del rinvio se la sua partita è rinviata (`aspetta`, `senza_voto`, `voto_ufficio`), assente se si gioca. Facoltativo.
    private let rinvio: Tollerante<String>?

    /// Il fantavoto preso, se il server lo manda ed è un numero vero.
    var fantavotoPreso: Double? {
        guard let v = fvPreso?.valore, v.isFinite else { return nil }
        return v
    }

    /// Il modo del rinvio della sua partita (`rinvio` del server); nil se la partita si gioca o il server non lo dice.
    var modoRinvio: String? { rinvio?.valore }

    /// I motivi del fantavoto atteso, dal più pesante; nil se il server non li manda (server vecchio), vuoto se nessuno spicca.
    var motiviNumero: [MotivoNumero]? {
        guard let lista = percheNumero?.valore else { return nil }
        return lista.compactMap(\.valore)
    }

    /// Il fantavoto atteso di un giocatore medio del ruolo, se il server lo manda ed è un numero vero.
    var mediaRuolo: Double? {
        guard let v = fvAttesoMedioRuolo?.valore, v.isFinite else { return nil }
        return v
    }
}

/// Un motivo del fantavoto atteso (`perche_numero`): `effetto` è in fantavoti rispetto a un giocatore medio del ruolo,
/// nil per «gioca N%» (non cambia il fantavoto «se gioca»). Tollerante: un campo strano resta vuoto.
struct MotivoNumero: Decodable, Equatable {
    var chiave: String?
    var testo: String?
    var effetto: Double?

    private enum Chiavi: String, CodingKey { case chiave, testo, effetto }

    init(chiave: String? = nil, testo: String? = nil, effetto: Double? = nil) {
        self.chiave = chiave; self.testo = testo; self.effetto = effetto
    }

    init(from decoder: Decoder) throws {
        guard let k = try? decoder.container(keyedBy: Chiavi.self) else { return }
        chiave = (try? k.decodeIfPresent(String.self, forKey: .chiave)) ?? nil
        testo = (try? k.decodeIfPresent(String.self, forKey: .testo)) ?? nil
        effetto = (try? k.decodeIfPresent(Double.self, forKey: .effetto)) ?? nil
    }
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
    /// Probabilità di giocare (0-1), per i dubbi: «In dubbio · gioca 55%» come nella web app.
    var pVoto: Double? = nil
    /// L'etichetta pronta dal server (`fanta/etichette.py`): `testo` va mostrato com'è, al posto di quello composto da `tipo`
    /// e `pVoto`. Facoltativa: un server vecchio non la manda.
    var etichetta: EtichettaPronta? = nil
    /// Lo stesso giocatore può avere più avvisi (dubbio e diffidato): l'id da solo non basta per le liste.
    var ident: String { "\(id)-\(tipo ?? "")" }

    /// `{codice, testo, tono}` del server. Tollerante: un valore con una forma strana vale «niente etichetta» e non rompe Oggi.
    struct EtichettaPronta: Decodable {
        let codice: String?
        let testo: String?
        let tono: String?

        private enum CodingKeys: String, CodingKey { case codice, testo, tono }

        init(from decoder: Decoder) throws {
            let c = try? decoder.container(keyedBy: CodingKeys.self)
            codice = (try? c?.decodeIfPresent(String.self, forKey: .codice)) ?? nil
            testo = (try? c?.decodeIfPresent(String.self, forKey: .testo)) ?? nil
            tono = (try? c?.decodeIfPresent(String.self, forKey: .tono)) ?? nil
        }
    }
}

struct Partita: Decodable, Identifiable {
    let data: String?
    let casa: String
    let trasferta: String
    let giocata: Bool?
    /// `da_giocare`, `in_corso`, `finita`, `rinviata` (facoltativo: server vecchio; un valore strano si ignora).
    let stato: String?
    var id: String { (data ?? "") + casa + trasferta }

    private enum CodingKeys: String, CodingKey { case data, casa, trasferta, giocata, stato }

    init(data: String?, casa: String, trasferta: String, giocata: Bool?, stato: String? = nil) {
        self.data = data; self.casa = casa; self.trasferta = trasferta; self.giocata = giocata; self.stato = stato
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: CodingKeys.self)
        data = try k.decodeIfPresent(String.self, forKey: .data)
        casa = try k.decode(String.self, forKey: .casa)
        trasferta = try k.decode(String.self, forKey: .trasferta)
        giocata = try k.decodeIfPresent(Bool.self, forKey: .giocata)
        stato = (try? k.decodeIfPresent(String.self, forKey: .stato)) ?? nil
    }
}

struct Oggi: Decodable {
    /// `null` (o assente) se il calendario non è pronto, la stagione è finita o l'account è nuovo e senza rose.
    let giornata: Int?
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
    /// La fase della giornata: `prima`, `in_corso`, `finita` (facoltativa: se manca vale `prima`, come i server vecchi).
    let fase: Tollerante<String>?
    /// Solo con la fase `in_corso`: punti fatti finora, chi va a punteggio, cambi dalla panchina. `null` se non si sa cosa hai schierato.
    let inCorso: Tollerante<GiornataInCorso>?
    /// Solo con la fase `finita`: com'è andata la giornata appena chiusa.
    let riepilogo: Tollerante<RiepilogoGiornata>?
    /// Solo con la fase `finita`: la prossima giornata e da quando conviene prepararla.
    let prossima: Tollerante<ProssimaGiornata>?
    /// Partite rinviate della giornata e cosa vale per i loro giocatori (`null` se non ce ne sono). Facoltativo (server vecchio).
    let rinvio: Tollerante<SceltaRinvio>?
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

/// Una cosa da fare in Oggi: «Leonel è in dubbio: sostituiscilo», «Aggiorna le rose», «Rinnova l'app»...
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
    /// Perché te lo consiglia, in una frase breve (facoltativo).
    let motivo: String?

    private enum Chiavi: String, CodingKey { case id, tipo, testo, priorita, azione, destinazione, motivo }

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
        motivo = (try? k.decodeIfPresent(String.self, forKey: .motivo)) ?? nil
    }

    init(id: String, tipo: String? = nil, testo: String, priorita: Int? = nil, azione: String? = nil, destinazione: DestinazioneDaFare? = nil, motivo: String? = nil) {
        self.motivo = motivo
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
    /// Il perché delle scelte che sembrano storte, una riga per titolare (#356). Facoltativo (server vecchio).
    let percheScelta: [PercheScelta]?
    var id: String { modulo }
}

/// Una riga del perché della scelta (`perche_scelta` del modulo, `fanta/perche_scelta.py`): un titolare con meno punti attesi di
/// un escluso dello stesso ruolo (o incerto con la riserva sicura) e il motivo, già scritto dal server. Campi facoltativi: una riga
/// incompleta si salta, non fa fallire la Formazione.
struct PercheScelta: Decodable {
    let titolare: Int?
    /// Il giocatore che la riga nomina (l'escluso o la riserva).
    let altro: Int?
    let testo: String?
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
    /// `true` dopo la scadenza della giornata (le partite sono cominciate): la formazione non si può più cambiare. Facoltativo.
    let iniziata: Bool?
    /// La tua scelta salvata per la giornata, con la regola del server: "nessuna", "valida" o "non_valida" (non si può più
    /// schierare: vale la consigliata). Solo per la tua squadra. Facoltativo (server vecchio: manca).
    let statoScelta: String?
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
    /// Il registro delle giornate (#344, `registro_giornate.riepilogo` del server): le medie delle ultime `finestra` giornate misurate
    /// con le soglie e il verdetto (`regge`, solo con `verdetto`), e una riga per giornata. Un server vecchio non lo manda.
    struct Registro: Decodable {
        /// Le chiavi «I2_calibrazione»... arrivano come `i2Calibrazione` (`convertFromSnakeCase`); «I1» resta com'è.
        struct Soglie: Decodable {
            let i1: Double?
            let i2Calibrazione: Double?
            let i2Brier: Double?
            let i3Minimo: Double?
            let i3Massimo: Double?
            enum CodingKeys: String, CodingKey { case i1 = "I1", i2Calibrazione, i2Brier, i3Minimo, i3Massimo }
        }
        /// Per ogni misura: vero se regge, falso se no, nil finché non c'è il verdetto o manca il numero.
        struct Regge: Decodable {
            let i1: Bool?
            let i2: Bool?
            let i3: Bool?
            enum CodingKeys: String, CodingKey { case i1 = "I1", i2 = "I2", i3 = "I3" }
        }
        /// Una giornata salvata o persa (`persa`: il motivo in breve, scritto dal server).
        struct Giornata: Decodable, Identifiable {
            let stagione: String?
            let giornata: Int?
            let persa: String?
            var id: String { "\(stagione ?? "")-\(giornata ?? -1)" }
        }
        let finestra: Int?
        let soglie: Soglie?
        let giornate: Int?
        let erroreModello: Double?
        let erroreFantamedia: Double?
        let i1: Double?
        let brier: Double?
        let calibrazione: Double?
        let copertura: Double?
        let verdetto: Bool?
        let regge: Regge?
        let perGiornata: [Giornata]?
    }
    /// Gli indicatori del consiglio di formazione (#366, `indicatori_consiglio.riepilogo` del server), sommati sui Diari di tutti: le
    /// medie delle ultime `finestra` giornate con le soglie e il verdetto (`regge`, solo con `verdetto`). Un server vecchio non lo manda.
    struct Consiglio: Decodable {
        /// «C1», «C2», «C3» restano come sono; «C4_senza_motivo» arriva come `c4SenzaMotivo` (`convertFromSnakeCase`).
        struct Soglie: Decodable {
            let c1: Double?
            let c2: Double?
            let c3: Double?
            let c4SenzaMotivo: Double?
            enum CodingKeys: String, CodingKey { case c1 = "C1", c2 = "C2", c3 = "C3", c4SenzaMotivo }
        }
        /// Per ogni indicatore: vero se regge, falso se no, nil finché non c'è il verdetto o manca il numero.
        struct Regge: Decodable {
            let c1: Bool?
            let c2: Bool?
            let c3: Bool?
            let c4: Bool?
            enum CodingKeys: String, CodingKey { case c1 = "C1", c2 = "C2", c3 = "C3", c4 = "C4" }
        }
        let finestra: Int?
        let soglie: Soglie?
        let giornate: Int?
        /// Le formazioni misurate (una per utente e giornata).
        let voci: Int?
        /// Punti veri a giornata della consigliata mostrata meno la scelta semplice, e meno la schierata quando è diversa.
        let menoS2: Double?
        let menoSchierata: Double?
        /// Cambi a formazione nelle 24 ore prima della scadenza (media) e quanti valevano meno di 1 punto atteso (totale).
        let cambi: Double?
        let cambiSottoSoglia: Int?
        /// Titolari sotto il 20% o fuori, e quanti di loro con un compagno di ruolo al 50% o più tra gli esclusi (totali).
        let improbabili: Int?
        let conCompagno: Int?
        /// Scelte che sembrano strane e quante spiegate (totali); parte dei titolari senza un motivo loro nel «perché».
        let storte: Int?
        let spiegate: Int?
        let senzaMotivo: Double?
        let verdetto: Bool?
        let regge: Regge?
    }
    let stagione: String?
    let aggiornamenti: [AggiornamentoDati]?
    let calciatori: Int?
    let partite: Partite?
    let voti: Int?
    let foto: Int?
    let probabili: [Probabili]?
    let calibrazione: Calibrazione?
    let coppeFino: String?
    let registro: Registro?
    let consiglio: Consiglio?
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

// MARK: - Fasi della giornata (campi facoltativi di Oggi, dal 1/11/2026; stanno qui perché Modelli.swift è compilato anche dal widget)

/// Letture che non falliscono mai: tipo sbagliato o `null` = nil; in un elenco un elemento sbagliato si salta.
private extension KeyedDecodingContainer {
    func facoltativo<T: Decodable>(_ tipo: T.Type, _ chiave: Key) -> T? {
        (try? decodeIfPresent(tipo, forKey: chiave)) ?? nil
    }

    func elenco<T: Decodable>(_ tipo: T.Type, _ chiave: Key) -> [T] {
        (facoltativo([Tollerante<T>].self, chiave) ?? []).compactMap(\.valore)
    }
}

/// Un giocatore della formazione schierata durante la giornata (`in_corso.giocatori`): titolari in ordine, poi la panchina.
struct GiocatoreInCorso: Decodable, Identifiable, Equatable {
    let id: Int
    let nome: String
    let ruolo: String?
    let squadra: String?
    let titolare: Bool
    /// Va a punteggio con i cambi di adesso.
    let aPunteggio: Bool
    /// `fatto` (ha il voto), `senza_voto`, `attesa_voti`, `in_corso`, `da_giocare`, `rinviata`.
    let stato: String?
    /// Il fantavoto con le regole della lega (solo con `fatto`).
    let fantavoto: Double?
    /// Ora d'inizio della sua partita («AAAA-MM-GG HH:MM»).
    let data: String?

    private enum Chiavi: String, CodingKey { case id, nome, ruolo, squadra, titolare, aPunteggio, stato, fantavoto, data }

    init(id: Int, nome: String, ruolo: String? = nil, squadra: String? = nil, titolare: Bool = true, aPunteggio: Bool = true,
         stato: String? = nil, fantavoto: Double? = nil, data: String? = nil) {
        self.id = id; self.nome = nome; self.ruolo = ruolo; self.squadra = squadra; self.titolare = titolare
        self.aPunteggio = aPunteggio; self.stato = stato; self.fantavoto = fantavoto; self.data = data
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        id = try k.decode(Int.self, forKey: .id)   // senza id l'elemento si salta (l'elenco è tollerante)
        nome = k.facoltativo(String.self, .nome) ?? ""
        ruolo = k.facoltativo(String.self, .ruolo)
        squadra = k.facoltativo(String.self, .squadra)
        titolare = k.facoltativo(Bool.self, .titolare) ?? false
        aPunteggio = k.facoltativo(Bool.self, .aPunteggio) ?? false
        stato = k.facoltativo(String.self, .stato)
        fantavoto = k.facoltativo(Double.self, .fantavoto).flatMap { $0.isFinite ? $0 : nil }
        data = k.facoltativo(String.self, .data)
    }
}

/// Chi esce o chi entra in un cambio dalla panchina.
struct PersonaCambio: Decodable, Equatable {
    let id: Int?
    let nome: String
    let ruolo: String?

    private enum Chiavi: String, CodingKey { case id, nome, ruolo }

    init(id: Int?, nome: String, ruolo: String? = nil) { self.id = id; self.nome = nome; self.ruolo = ruolo }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        id = k.facoltativo(Int.self, .id)
        nome = k.facoltativo(String.self, .nome) ?? ""
        ruolo = k.facoltativo(String.self, .ruolo)
    }
}

/// Un cambio dalla panchina con le regole della lega: già scattato (`certa`) o probabile.
struct CambioPanchina: Decodable, Equatable {
    let esce: PersonaCambio?
    /// nil = nessun sostituto possibile.
    let entra: PersonaCambio?
    let certa: Bool
    /// `senza_voto`, `fuori` (infortunato o squalificato che deve ancora giocare), `rinviata`.
    let motivo: String?

    private enum Chiavi: String, CodingKey { case esce, entra, certa, motivo }

    init(esce: PersonaCambio?, entra: PersonaCambio?, certa: Bool, motivo: String? = nil) {
        self.esce = esce; self.entra = entra; self.certa = certa; self.motivo = motivo
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        esce = k.facoltativo(PersonaCambio.self, .esce)
        entra = k.facoltativo(PersonaCambio.self, .entra)
        certa = k.facoltativo(Bool.self, .certa) ?? false
        motivo = k.facoltativo(String.self, .motivo)
    }
}

/// Quante partite del turno sono in corso, finite, da giocare e rinviate.
struct ContoPartite: Decodable, Equatable {
    var inCorso = 0
    var finite = 0
    var daGiocare = 0
    var rinviate = 0

    private enum Chiavi: String, CodingKey { case inCorso, finite, daGiocare, rinviate }

    init(inCorso: Int = 0, finite: Int = 0, daGiocare: Int = 0, rinviate: Int = 0) {
        self.inCorso = inCorso; self.finite = finite; self.daGiocare = daGiocare; self.rinviate = rinviate
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        inCorso = max(0, k.facoltativo(Int.self, .inCorso) ?? 0)
        finite = max(0, k.facoltativo(Int.self, .finite) ?? 0)
        daGiocare = max(0, k.facoltativo(Int.self, .daGiocare) ?? 0)
        rinviate = max(0, k.facoltativo(Int.self, .rinviate) ?? 0)
    }

    var totale: Int { inCorso + finite + daGiocare + rinviate }
}

/// Il campo `in_corso` di Oggi: la giornata mentre si gioca.
struct GiornataInCorso: Decodable, Equatable {
    let giornata: Int?
    let giornataLega: Int?
    /// `tua` (la scelta salvata) o `consigliata`.
    let formazioneDi: String?
    let puntiFatti: Double?
    let puntiAttesiRestanti: Double?
    /// Punti fatti + attesi di chi non ha ancora il voto: «a fine giornata, circa».
    let puntiPrevisti: Double?
    /// Modificatore della difesa già contato, se c'è.
    let modificatore: Double?
    /// Quanti di chi va a punteggio non hanno ancora il voto.
    let ancoraDaGiocare: Int?
    let giocatori: [GiocatoreInCorso]
    let sostituzioni: [CambioPanchina]
    let partite: ContoPartite?

    private enum Chiavi: String, CodingKey {
        case giornata, giornataLega, formazioneDi, puntiFatti, puntiAttesiRestanti, puntiPrevisti, modificatore, ancoraDaGiocare
        case giocatori, sostituzioni, partite
    }

    init(giornata: Int? = nil, giornataLega: Int? = nil, formazioneDi: String? = nil, puntiFatti: Double? = nil,
         puntiAttesiRestanti: Double? = nil, puntiPrevisti: Double? = nil, modificatore: Double? = nil, ancoraDaGiocare: Int? = nil,
         giocatori: [GiocatoreInCorso] = [], sostituzioni: [CambioPanchina] = [], partite: ContoPartite? = nil) {
        self.giornata = giornata; self.giornataLega = giornataLega; self.formazioneDi = formazioneDi; self.puntiFatti = puntiFatti
        self.puntiAttesiRestanti = puntiAttesiRestanti; self.puntiPrevisti = puntiPrevisti; self.modificatore = modificatore
        self.ancoraDaGiocare = ancoraDaGiocare; self.giocatori = giocatori; self.sostituzioni = sostituzioni; self.partite = partite
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        giornata = k.facoltativo(Int.self, .giornata)
        giornataLega = k.facoltativo(Int.self, .giornataLega)
        formazioneDi = k.facoltativo(String.self, .formazioneDi)
        puntiFatti = k.facoltativo(Double.self, .puntiFatti)
        puntiAttesiRestanti = k.facoltativo(Double.self, .puntiAttesiRestanti)
        puntiPrevisti = k.facoltativo(Double.self, .puntiPrevisti)
        modificatore = k.facoltativo(Double.self, .modificatore)
        ancoraDaGiocare = k.facoltativo(Int.self, .ancoraDaGiocare)
        giocatori = k.elenco(GiocatoreInCorso.self, .giocatori)
        sostituzioni = k.elenco(CambioPanchina.self, .sostituzioni)
        partite = k.facoltativo(ContoPartite.self, .partite)
    }
}

/// I punti della formazione consigliata nel riepilogo (dal Diario).
struct PuntiConsigliata: Decodable, Equatable {
    let puntiFatti: Double?
    let puntiAttesi: Double?

    private enum Chiavi: String, CodingKey { case puntiFatti, puntiAttesi }

    init(puntiFatti: Double?, puntiAttesi: Double?) { self.puntiFatti = puntiFatti; self.puntiAttesi = puntiAttesi }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        puntiFatti = k.facoltativo(Double.self, .puntiFatti)
        puntiAttesi = k.facoltativo(Double.self, .puntiAttesi)
    }
}

/// Il campo `riepilogo` di Oggi: la giornata appena finita.
struct RiepilogoGiornata: Decodable, Equatable {
    let giornata: Int?
    let giornataLega: Int?
    /// `tua` o `consigliata`.
    let formazioneDi: String?
    /// true = numeri del Diario (con il confronto); false = punti dai voti, il confronto arriva nel Diario.
    let nelDiario: Bool
    let puntiFatti: Double?
    let puntiAttesi: Double?
    let intervallo: IntervalloPunti?
    let consigliata: PuntiConsigliata?
    /// Le partite rinviate ancora da recuperare, solo se la lega aspetta il recupero: i punti possono ancora cambiare.
    let recuperi: [PartitaRinviata]
    /// Il menu «per questa giornata», finché manca un recupero (nil altrimenti o con un server vecchio).
    let rinvio: SceltaRinvio?

    private enum Chiavi: String, CodingKey { case giornata, giornataLega, formazioneDi, nelDiario, puntiFatti, puntiAttesi, intervallo, consigliata, recuperi, rinvio }

    init(giornata: Int? = nil, giornataLega: Int? = nil, formazioneDi: String? = nil, nelDiario: Bool = false, puntiFatti: Double? = nil,
         puntiAttesi: Double? = nil, intervallo: IntervalloPunti? = nil, consigliata: PuntiConsigliata? = nil,
         recuperi: [PartitaRinviata] = [], rinvio: SceltaRinvio? = nil) {
        self.giornata = giornata; self.giornataLega = giornataLega; self.formazioneDi = formazioneDi; self.nelDiario = nelDiario
        self.puntiFatti = puntiFatti; self.puntiAttesi = puntiAttesi; self.intervallo = intervallo; self.consigliata = consigliata
        self.recuperi = recuperi; self.rinvio = rinvio
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        giornata = k.facoltativo(Int.self, .giornata)
        giornataLega = k.facoltativo(Int.self, .giornataLega)
        formazioneDi = k.facoltativo(String.self, .formazioneDi)
        nelDiario = k.facoltativo(Bool.self, .nelDiario) ?? false
        puntiFatti = k.facoltativo(Double.self, .puntiFatti)
        puntiAttesi = k.facoltativo(Double.self, .puntiAttesi)
        intervallo = k.facoltativo(IntervalloPunti.self, .intervallo)
        consigliata = k.facoltativo(PuntiConsigliata.self, .consigliata)
        recuperi = k.elenco(PartitaRinviata.self, .recuperi)
        rinvio = k.facoltativo(SceltaRinvio.self, .rinvio)
    }
}

// MARK: - Partite rinviate (campi facoltativi `rinvio` di Oggi e `riepilogo.recuperi`/`riepilogo.rinvio`, dal 2/11/2026; testi e corpo
// della richiesta in PartiteRinviate.swift, solo nell'app)

/// Le regole delle partite rinviate (contratto «Partite rinviate» in `docs/API.md`).
enum ModoRinvio {
    /// La lega aspetta il recupero e conta il voto preso lì: i giocatori restano schierabili.
    static let aspetta = "aspetta"
    /// I giocatori restano senza voto: entra la riserva.
    static let senzaVoto = "senza_voto"
    /// Tutti prendono il voto d'ufficio, senza bonus né malus.
    static let votoUfficio = "voto_ufficio"
    /// Nell'ordine in cui si mostrano (se il server non manda `modi`).
    static let tutti = [aspetta, senzaVoto, votoUfficio]
}

/// Una partita rinviata della giornata: `data` = quella del recupero, se c'è già.
struct PartitaRinviata: Decodable, Equatable, Identifiable {
    let casa: String
    let trasferta: String
    let data: String?
    var id: String { "\(casa)-\(trasferta)" }

    private enum Chiavi: String, CodingKey { case casa, trasferta, data }

    init(casa: String, trasferta: String, data: String? = nil) { self.casa = casa; self.trasferta = trasferta; self.data = data }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        casa = try k.decode(String.self, forKey: .casa)
        trasferta = try k.decode(String.self, forKey: .trasferta)
        data = k.facoltativo(String.self, .data)
    }
}

/// Un mio giocatore che gioca una partita rinviata.
struct GiocatoreRinviato: Decodable, Equatable, Identifiable {
    let id: Int
    let nome: String
    let ruolo: String?
    let squadra: String?

    private enum Chiavi: String, CodingKey { case id, nome, ruolo, squadra }

    init(id: Int, nome: String, ruolo: String? = nil, squadra: String? = nil) {
        self.id = id; self.nome = nome; self.ruolo = ruolo; self.squadra = squadra
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        id = try k.decode(Int.self, forKey: .id)
        nome = try k.decode(String.self, forKey: .nome)
        ruolo = k.facoltativo(String.self, .ruolo)
        squadra = k.facoltativo(String.self, .squadra)
    }
}

/// Cosa vale per una giornata con una partita rinviata e cosa serve al menu «per questa giornata»: campo `rinvio` di Oggi (con
/// `partite` e `miei`) e `riepilogo.rinvio` della giornata finita (senza). Letto in modo tollerante.
struct SceltaRinvio: Decodable, Equatable {
    let stagione: String?
    let giornata: Int
    let giornataLega: Int?
    /// Quello che vale adesso per la giornata (`aspetta`, `senza_voto`, `voto_ufficio`).
    let modo: String
    /// La regola della lega.
    let predefinito: String?
    /// true = per questa giornata vale una scelta diversa da quella della lega.
    let eccezione: Bool
    /// I valori ammessi, nell'ordine in cui mostrarli.
    let modi: [String]
    /// Il voto d'ufficio della lega (anche quando non è quello scelto).
    let votoUfficio: Double?
    let partite: [PartitaRinviata]
    let miei: [GiocatoreRinviato]

    private enum Chiavi: String, CodingKey { case stagione, giornata, giornataLega, modo, valore, predefinito, eccezione, modi, votoUfficio, partite, miei }

    init(stagione: String? = nil, giornata: Int, giornataLega: Int? = nil, modo: String, predefinito: String? = nil, eccezione: Bool = false,
         modi: [String] = ModoRinvio.tutti, votoUfficio: Double? = 6, partite: [PartitaRinviata] = [], miei: [GiocatoreRinviato] = []) {
        self.stagione = stagione; self.giornata = giornata; self.giornataLega = giornataLega; self.modo = modo
        self.predefinito = predefinito; self.eccezione = eccezione; self.modi = modi; self.votoUfficio = votoUfficio
        self.partite = partite; self.miei = miei
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        giornata = try k.decode(Int.self, forKey: .giornata)
        modo = try k.decode(String.self, forKey: .modo)
        stagione = k.facoltativo(String.self, .stagione)
        giornataLega = k.facoltativo(Int.self, .giornataLega)
        predefinito = k.facoltativo(String.self, .predefinito)
        eccezione = k.facoltativo(Bool.self, .eccezione) ?? false
        let elenco = (k.facoltativo([String].self, .modi) ?? []).filter { !$0.isEmpty }
        modi = elenco.isEmpty ? ModoRinvio.tutti : elenco
        votoUfficio = k.facoltativo(Double.self, .votoUfficio) ?? k.facoltativo(Double.self, .valore)
        partite = k.elenco(PartitaRinviata.self, .partite)
        miei = k.elenco(GiocatoreRinviato.self, .miei)
    }
}

/// Il campo `prossima` di Oggi: la giornata da preparare dopo quella finita.
struct ProssimaGiornata: Decodable, Equatable {
    let giornata: Int?
    let giornataLega: Int?
    let scadenza: String?
    /// Da quando conviene preparare la formazione («AAAA-MM-GG HH:MM»).
    let preparaDa: String?
    let conProbabili: Bool

    private enum Chiavi: String, CodingKey { case giornata, giornataLega, scadenza, preparaDa, conProbabili }

    init(giornata: Int? = nil, giornataLega: Int? = nil, scadenza: String? = nil, preparaDa: String? = nil, conProbabili: Bool = false) {
        self.giornata = giornata; self.giornataLega = giornataLega; self.scadenza = scadenza; self.preparaDa = preparaDa
        self.conProbabili = conProbabili
    }

    init(from decoder: Decoder) throws {
        let k = try decoder.container(keyedBy: Chiavi.self)
        giornata = k.facoltativo(Int.self, .giornata)
        giornataLega = k.facoltativo(Int.self, .giornataLega)
        scadenza = k.facoltativo(String.self, .scadenza)
        preparaDa = k.facoltativo(String.self, .preparaDa)
        conProbabili = k.facoltativo(Bool.self, .conProbabili) ?? false
    }
}
