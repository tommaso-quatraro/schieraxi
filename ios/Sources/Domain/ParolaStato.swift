import Foundation

/// Lo stato del giocatore a parole prima della partita, come `parolaStato` di app.js (#616): solo ciò che dice se non gioca («In
/// dubbio», «Rinviata», «Infortunato», «Squalificato», «Fuori»). Le parole della titolarità («Probabile titolare», …) non si
/// mostrano più: «titolare» vuol dire la tua formazione, e quanto è probabile che giochi lo dice «gioca N%».
/// Il codice viene dall'etichetta del server (`etichetta.codice`); con un server vecchio dai campi grezzi.
struct ParolaStato: Equatable {
    enum Classe: Equatable, Sendable {
        /// Da guardare: arancio.
        case arancio
        /// Non gioca di sicuro: rosso.
        case rossa
    }

    let codice: String
    /// Il testo dell'etichetta del server senza « · gioca N%», o la parola del catalogo.
    let testo: String
    let classe: Classe

    /// Infortunato, squalificato o fuori: la parola basta, «gioca 0%» non serve (`nonGiocaDiSicuro` della web).
    var nonGiocaDiSicuro: Bool { classe == .rossa }

    /// Le parole e i colori della web (`PAROLE_STATO` di app.js).
    static let parole: [String: (testo: String, classe: Classe)] = [
        "in_dubbio": (Catalogo.Tit.inDubbio, .arancio),
        "rinviata": (Catalogo.Tit.stRinviata, .arancio),
        "infortunato": (Catalogo.Oggi.infortunato, .rossa),
        "squalificato": (Catalogo.Oggi.squalificato, .rossa),
        "fuori": (Catalogo.Tit.fuori, .rossa),
    ]
}

extension ParolaStato {
    /// nil per chi non ha uno stato da dire (come `codiceStato` della web).
    init?(_ g: Giocatore) {
        let pronta = g.etichetta?.testoPronto
        let codice: String?
        if pronta != nil {
            codice = g.etichetta?.codice
        } else if let s = g.stato, s == "infortunato" || s == "squalificato" {
            codice = s
        } else if g.titolarita == "fuori" {
            codice = "fuori"
        } else if g.modoRinvio != nil || g.statoPartita == "rinviata" {
            codice = "rinviata"
        } else if g.dubbio == true {
            codice = "in_dubbio"
        } else {
            codice = nil
        }
        guard let codice, let parola = Self.parole[codice] else { return nil }
        let testo = pronta.flatMap { $0.components(separatedBy: " · ").first } ?? parola.testo
        self.init(codice: codice, testo: testo, classe: parola.classe)
    }
}
