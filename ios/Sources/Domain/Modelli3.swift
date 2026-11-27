import Foundation

// Altre risposte del server, usate solo dall'app (il widget non le compila): affidabilità, regole riconosciute, stagione...
// Come per gli altri modelli, quasi tutto è opzionale: un campo mancante non deve rompere la schermata.

// MARK: - Prova del modello

struct RigaAffidabilita: Decodable, Identifiable, Equatable {
    let giornata: Int
    let erroreModello: Double?
    let erroreFantamedia: Double?
    let puntiModello: Double?
    let puntiFantamedia: Double?
    let puntiPerfetta: Double?
    var id: Int { giornata }
}

struct SintesiAffidabilita: Decodable, Equatable {
    let giornate: Int?
    let erroreModello: Double?
    let erroreFantamedia: Double?
    let puntiModello: Double?
    let puntiFantamedia: Double?
    let puntiPerfetta: Double?
    /// `modello_batte_fantamedia` (#982): il server dice se i punti del modello valgono almeno quelli da fantamedia. Nil con un
    /// server di prima.
    let modelloBatteFantamedia: Bool?

    /// I punti della formazione del modello in verde, come la web (classe `positivo`): lo decide il server. Con un server di prima,
    /// senza il campo, il confronto dei due numeri che faceva la web; senza uno dei due numeri, no.
    var batteFantamedia: Bool {
        if let deciso = modelloBatteFantamedia { return deciso }
        guard let modello = puntiModello, let fantamedia = puntiFantamedia else { return false }
        return modello >= fantamedia
    }
}

/// `/api/affidabilita`: la prova del modello sulle giornate passate (vuota se non è ancora stata fatta).
struct Affidabilita: Decodable {
    let calcolato: String?
    let righe: [RigaAffidabilita]?
    let sintesi: SintesiAffidabilita?
}

// MARK: - Regole e stagione

/// Un valore riconosciuto nel testo del regolamento: la chiave dice quale regola cambia («bonus.assist», «panchina.numero»...).
/// Si mostra con `AnteprimaRegolamento`.
struct ModificaRegola: Decodable, Identifiable {
    let chiave: String
    let etichetta: String
    let valore: JSONValue
    let riga: String?
    var id: String { chiave }
}

/// Una regola che il server lascia da impostare a mano sotto una riga dubbia (in `da_controllare` arrivano `chiave` ed `etichetta`,
/// come in `modifiche`; l'app mostra l'etichetta).
struct RegolaDaImpostare: Decodable, Equatable {
    let etichetta: String?
}

/// Una riga del regolamento incollato da controllare a mano (#684, #733): con numeri non letti, o dubbia anche senza numeri.
/// `regole` è vuoto per una riga che non nomina regole da impostare.
struct RigaDaControllare: Decodable, Equatable {
    let riga: String?
    let regole: [RegolaDaImpostare]?
}

/// Un valore letto nel regolamento incollato che con le regole di adesso non si può salvare così com'è (`non_applicabili`, #881):
/// come `ModificaRegola`, più il perché del server. `motivo` è il testo in italiano; `motivo_frase` (chiave e parametri per
/// tradurlo) all'iPhone non serve e non si legge, come per le altre frasi del server.
struct ValoreNonApplicabile: Decodable, Equatable {
    let chiave: String?
    let etichetta: String?
    let valore: JSONValue?
    let riga: String?
    let motivo: String?
}

struct RiconoscimentoRegole: Decodable {
    let modifiche: [ModificaRegola]
    /// Le righe con numeri non lette: le mostra solo chi non riceve `da_controllare` (un server di prima del 19/11/2026).
    let nonRiconosciute: [String]?
    /// Le righe da controllare a mano, nell'ordine del testo incollato (dal 19/11/2026). Un server di prima non lo manda.
    let daControllare: [RigaDaControllare]?
    /// I valori letti che non si possono salvare così come sono, con il perché (dal 25/11/2026, #881): non sono in `modifiche`,
    /// quindi «Applica ai campi» non li mette nei campi. Un server di prima non lo manda.
    let nonApplicabili: [ValoreNonApplicabile]?
}

struct RichiestaTesto: Encodable {
    let testo: String
}

struct StatoStagione: Decodable, Equatable {
    let corrente: String?
    let rose: String?
    /// true quando le rose sono di una stagione finita: si può archiviare e ripartire.
    let nuova: Bool?
}

// MARK: - Aggiornamento dei dati, icona, foto

struct AvvioAggiornamento: Decodable {
    let avviato: Bool?
    let messaggio: String?
}

struct StatoAggiornamento: Decodable, Equatable {
    let inCorso: Bool?
    let righe: [String]?
    let errori: [String]?
    /// Vero a giro finito se non è arrivato nessun dato (collaudo del 27/11/2026); un server di prima non lo manda.
    let nessunDatoNuovo: Bool?
}

struct IconaServer: Decodable, Equatable {
    let scelta: String?
    let elenco: [String]?
}

struct FotoDisponibili: Decodable, Equatable {
    let ids: [Int]
}
