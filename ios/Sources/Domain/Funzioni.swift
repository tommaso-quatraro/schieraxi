import SwiftUI

/// La «dieta delle funzioni»: il server dice quali funzioni sono accese per chi chiede (`GET /api/funzioni`) e l'app nasconde
/// schermate e pulsanti di quelle spente. Una funzione che il server non nomina vale «accesa»; se il server non risponde
/// (o è vecchio) si vede tutto, come prima.
enum Funzione {
    static let stiliRidotti = "stili_ridotti"
    static let confronto = "confronto"
    static let elencoGiocatori = "elenco_giocatori"
    static let seguiti = "seguiti"
    static let diario = "diario"
    static let backup = "backup"
    static let squadreAltrui = "squadre_altrui"
    static let aspettoAvanzato = "aspetto_avanzato"
    static let novita = "novita"
    static let live = "live"
    static let asta = "asta"
    static let scambiTrova = "scambi_trova"
    static let scambiCostruisci = "scambi_costruisci"
    static let immaginiWeb = "immagini_web"
    /// Crediti di tutte le squadre: il server la tiene spenta di norma, quindi serve che la accenda.
    static let crediti = "crediti"
    /// «Sotto il cofano»: il server la tiene spenta di norma, quindi la voce compare solo se la accende.
    static let sottoIlCofano = "sotto_il_cofano"
    /// Movimenti e storico: se il server non la nomina (versione vecchia) vale acceso.
    static let movimenti = "movimenti"
}

/// Cosa è acceso e se l'utente ha chiesto «Mostra tutte le funzioni». Valore semplice: sta nell'ambiente di SwiftUI
/// (`\.funzioni`), così ogni schermata lo legge senza dipendere da un oggetto (anteprime e test vedono tutto acceso).
struct StatoFunzioni: Equatable, Sendable {
    var scelte: [String: Bool] = [:]
    var mostraTutte = false

    static let tutteAccese = StatoFunzioni()

    /// Una chiave che manca vale «acceso». Con «Mostra tutte» il server manda già tutto `true`: qui si controlla comunque.
    func acceso(_ id: String) -> Bool {
        mostraTutte || scelte[id] != false
    }

    /// Dopo un 404 con il campo `funzione`: da qui in poi la schermata la nasconde (come fa la web app).
    func spenta(_ id: String) -> StatoFunzioni {
        var copia = self
        copia.scelte[id] = false
        return copia
    }
}

/// La risposta di `GET` e `PUT /api/funzioni`: `{"funzioni": {"live": true, ...}, "mostra_tutte": false}`.
/// Tutti i campi sono facoltativi (un server diverso non deve rompere l'app). Si legge con `snake: false`: le chiavi
/// del dizionario (`stili_ridotti`) non devono essere trasformate.
struct RispostaFunzioni: Decodable, Equatable {
    var funzioni: [String: Bool]?
    var mostraTutte: Bool?

    enum CodingKeys: String, CodingKey {
        case funzioni
        case mostraTutte = "mostra_tutte"
    }

    var stato: StatoFunzioni {
        StatoFunzioni(scelte: funzioni ?? [:], mostraTutte: mostraTutte ?? false)
    }
}

/// Il corpo di `PUT /api/funzioni`.
struct CorpoMostraTutte: Encodable {
    let mostraTutte: Bool

    enum CodingKeys: String, CodingKey { case mostraTutte = "mostra_tutte" }
}

extension Notification.Name {
    /// Il server ha risposto 404 con il campo `funzione`: quella funzione è spenta (userInfo: `funzione`).
    static let funzioneSpenta = Notification.Name("it.schieraxi.app.funzioneSpenta")
}

private struct FunzioniChiave: EnvironmentKey {
    static let defaultValue = StatoFunzioni.tutteAccese
}

extension EnvironmentValues {
    /// Le funzioni accese per questo utente (la radice dell'app la imposta; altrove vale «tutto acceso»).
    var funzioni: StatoFunzioni {
        get { self[FunzioniChiave.self] }
        set { self[FunzioniChiave.self] = newValue }
    }
}

extension String {
    /// Il testo fisso che il server mette nel messaggio di una funzione spenta («... non è disponibile in questa versione dell'app...»).
    static let fraseFunzioneSpenta = "non è disponibile in questa versione dell'app"

    /// Il messaggio dice che la funzione è spenta: la schermata mostra «Non disponibile», senza «Riprova».
    var dicePerFunzioneSpenta: Bool { localizedCaseInsensitiveContains(Self.fraseFunzioneSpenta) }
}
