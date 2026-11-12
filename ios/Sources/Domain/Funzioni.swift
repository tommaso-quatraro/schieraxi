import SwiftUI

/// Le funzioni che il server può spegnere (`GET /api/funzioni`): l'app nasconde schermate e pulsanti di quelle spente. Una funzione
/// che il server non nomina vale «accesa»; se il server non risponde (o è vecchio) si vede tutto.
/// Dal 12/11/2026 (#634) l'app guarda solo queste due, come la web: le altre funzioni dell'elenco del server non hanno più una
/// schermata, e il Diario si vede sempre.
enum Funzione {
    /// Rose e crediti delle altre squadre della lega.
    static let squadreAltrui = "squadre_altrui"
    /// Stemma e maglia da un indirizzo web (lo scarica il server: se l'amministratore la spegne è spenta per tutti).
    static let immaginiWeb = "immagini_web"
}

/// Cosa è acceso. Valore semplice: sta nell'ambiente di SwiftUI (`\.funzioni`), così ogni schermata lo legge senza dipendere da
/// un oggetto (anteprime e test vedono tutto acceso).
struct StatoFunzioni: Equatable, Sendable {
    var scelte: [String: Bool] = [:]

    static let tutteAccese = StatoFunzioni()

    /// Una chiave che manca vale «acceso».
    func acceso(_ id: String) -> Bool {
        scelte[id] != false
    }

    /// Dopo un 404 con il campo `funzione`: da qui in poi la schermata la nasconde (come fa la web app).
    func spenta(_ id: String) -> StatoFunzioni {
        var copia = self
        copia.scelte[id] = false
        return copia
    }
}

/// La risposta di `GET /api/funzioni`: `{"funzioni": {"squadre_altrui": true, ...}, "mostra_tutte": false}`.
/// Il campo è facoltativo (un server diverso non deve rompere l'app). Si legge con `snake: false`: le chiavi del dizionario
/// (`squadre_altrui`) non devono essere trasformate. «Mostra tutte le funzioni» non si sceglie più dall'app (#634): chi l'aveva
/// accesa riceve dal server le funzioni già accese, e basta quello.
struct RispostaFunzioni: Decodable, Equatable {
    var funzioni: [String: Bool]?

    var stato: StatoFunzioni {
        StatoFunzioni(scelte: funzioni ?? [:])
    }
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
