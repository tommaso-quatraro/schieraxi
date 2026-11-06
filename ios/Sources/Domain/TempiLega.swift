import Foundation

/// I «tempi della lega»: la scadenza della formazione (prima partita meno i minuti scelti) e la numerazione della lega,
/// che può partire da una giornata di Serie A diversa dalla prima. Tutti i campi del server sono facoltativi.
extension Oggi {
    /// Quando si chiude la formazione: `scadenza`, o l'inizio della prima partita se il server non la manda (o è vuota).
    var chiusura: String? {
        if let s = scadenza?.trimmingCharacters(in: .whitespaces), !s.isEmpty { return s }
        return inizio
    }

    /// Il numero da mostrare: quello della lega se c'è (e ha senso), altrimenti quello di Serie A.
    /// Nil se il server non manda nessuna giornata.
    var giornataMostrata: Int? {
        if let g = giornataLega, g > 0 { return g }
        return giornata
    }

    /// La giornata con i suoi due numeri (lega e Serie A). Nil senza giornata di Serie A.
    var nomeGiornata: NomeGiornata? { giornata.map { NomeGiornata(serieA: $0, lega: giornataLega) } }

    /// «Giornata 7 · 10ª di Serie A» (#299). Nil senza giornata.
    var etichettaGiornata: String? { nomeGiornata?.intero }

    /// Account senza rose, o lega senza giornata: Oggi non ha una formazione da mostrare.
    var senzaGiornata: Bool { giornata == nil }
}

extension Formazione {
    var nomeGiornata: NomeGiornata { NomeGiornata(serieA: giornata, lega: giornataLega) }
    var etichettaGiornata: String { nomeGiornata.intero }
}

/// Il nome di una giornata con i suoi due numeri, come su Leghe (#299, `docs/COERENZA-WEB-IPHONE.md`): quello della lega
/// (`giornata_lega`) e quello di Serie A (`giornata`). È l'unica regola dell'app e dei widget per scrivere una giornata:
/// le forme qui sotto vanno dalla più lunga alla più corta, e VoiceOver legge sempre i due numeri (`voce`).
struct NomeGiornata: Equatable, Sendable {
    let serieA: Int
    /// Nil per le stagioni passate, prima che la lega parta e con un server che non manda il numero (o lo manda non valido).
    let lega: Int?

    init(serieA: Int, lega: Int?) {
        self.serieA = serieA
        self.lega = lega.flatMap { $0 > 0 ? $0 : nil }
    }

    /// «11ª di Serie A»: la parte di Serie A, accanto o sotto «Giornata 8».
    var diSerieA: String { "\(serieA)ª di Serie A" }

    /// Dove c'è spazio: «Giornata 8 · 11ª di Serie A». Senza il numero della lega: «11ª giornata di Serie A».
    var intero: String {
        guard let lega else { return "\(serieA)ª giornata di Serie A" }
        return "Giornata \(lega) · \(diSerieA)"
    }

    /// La prima riga quando lo spazio è poco: «Giornata 8» (con `sotto` sulla riga dopo, se c'è posto).
    /// Senza il numero della lega: «11ª di Serie A».
    var corto: String { lega.map { "Giornata \($0)" } ?? diSerieA }

    /// La seconda riga sotto `corto`: «11ª di Serie A». Nil senza il numero della lega (`corto` dice già tutto).
    var sotto: String? { lega == nil ? nil : diSerieA }

    /// L'ultimo ripiego per gli spazi strettissimi dei widget: «G8» (senza il numero della lega «G11», come prima).
    var sigla: String { "G\(lega ?? serieA)" }

    /// Per VoiceOver, sempre intera: «Giornata 8, 11ª di Serie A» (la virgola al posto di «·», come nelle altre frasi lette).
    var voce: String {
        guard let lega else { return intero }
        return "Giornata \(lega), \(diSerieA)"
    }

    /// Le forme di una riga sola, dalla più lunga alla più corta, per scegliere la prima che entra (`ViewThatFits`).
    var forme: [String] { Self.senzaDoppioni([intero, corto, sigla]) }

    /// Le forme per i widget piccoli, senza la forma intera: «Giornata 8», poi «G8».
    var formeCorte: [String] { Self.senzaDoppioni([corto, sigla]) }

    private static func senzaDoppioni(_ forme: [String]) -> [String] {
        var elenco: [String] = []
        for forma in forme where !elenco.contains(forma) { elenco.append(forma) }
        return elenco
    }
}

enum TempiLega {
    /// «Giornata 7 · 10ª di Serie A»: i due numeri, come la web (#299). Lega mancante o non valida: «10ª giornata di Serie A».
    static func etichetta(serieA: Int, lega: Int?) -> String { NomeGiornata(serieA: serieA, lega: lega).intero }

    /// «10ª giornata di Serie A»: dove si parla solo del calendario e dei dati di Serie A.
    static func serieA(_ giornata: Int) -> String { NomeGiornata(serieA: giornata, lega: nil).intero }

    /// La sigla corta per gli spazi strettissimi: «G7» (il numero di lega se c'è, altrimenti quello di Serie A).
    static func sigla(serieA: Int, lega: Int?) -> String { NomeGiornata(serieA: serieA, lega: lega).sigla }

    /// L'apostrofo davanti all'8ª e all'11ª, come la web (`elidiOrdinali`) e il server (`frasi.elidi_ordinali`):
    /// «dalla 11ª giornata di Serie A» → «dall'11ª giornata di Serie A», «la 8ª» → «l'8ª». Le altre («la 18ª», «la 1ª») restano.
    static func elidiOrdinali(_ testo: String) -> String {
        testo.replacingOccurrences(of: #"\b(l|all|dall|dell|nell|sull)a (8ª|11ª)"#, with: "$1'$2", options: .regularExpression)
    }

    /// La riga sotto il modulo in Formazione, come la web (#437): «Giornata 8 · 11ª di Serie A · la tua scelta» in modifica a mano
    /// (`formazione.la_tua_scelta`), altrimenti «· modulo consigliato» o «· modulo scelto».
    static func didascalia(giornata: String, scelta: Bool, comeConsigliato: Bool) -> String {
        giornata + " · " + (scelta ? "la tua scelta" : comeConsigliato ? "modulo consigliato" : "modulo scelto")
    }

    static let minutiMassimi = 720.0
    static let primaGiornataMassima = 38.0

    /// «Con la prima giornata 4: la giornata 1 della lega è la 4ª di Serie A.» Valori fuori dai limiti si riportano dentro.
    static func spiegaPartenza(_ prima: Double) -> String {
        let n = Int(min(max(prima, 1), primaGiornataMassima))
        return n == 1 ? "La lega parte dalla prima giornata di Serie A: i due numeri coincidono."
                      : "La giornata 1 della lega è la \(n)ª di Serie A: prima di allora per la lega non esiste nulla."
    }

    /// «Si chiude 30 minuti prima della prima partita.» / «…all'inizio della prima partita.»
    static func spiegaScadenza(_ minuti: Double) -> String {
        let m = Int(min(max(minuti, 0), minutiMassimi))
        if m == 0 { return "La formazione si chiude all'inizio della prima partita." }
        return "La formazione si chiude \(Formato.plurale(m, "minuto", "minuti")) prima della prima partita."
    }
}
