import Foundation

/// Una voce di «Tutti i numeri» nel Confronto: il nome del numero e il valore già scritto di ognuno dei due giocatori.
/// La stessa voce serve alla tabella (`NumeriInTabella`) e all'elenco del testo grande (`NumeriInElenco`).
struct VoceNumeriConfronto: Identifiable {
    let titolo: String
    /// Il valore del primo giocatore (colonna di sinistra).
    let a: String
    /// Il valore del secondo giocatore (colonna di destra).
    let b: String

    var id: String { titolo }

    /// La frase letta da VoiceOver: «Indice: Pinarotti 72, Rossi 65».
    func frase(_ x: Giocatore, _ y: Giocatore) -> String {
        "\(titolo): \(x.nomeCorto) \(a), \(y.nomeCorto) \(b)"
    }

    /// Da fare (#293).
    static func quandoGioca(_ quota: Double?) -> String { "\(Formato.percento(quota))%" }

    /// Le voci, nell'ordine di sempre.
    @MainActor
    static func voci(_ x: Giocatore, _ y: Giocatore) -> [VoceNumeriConfronto] {
        let numeri: [(String, (Giocatore) -> String)] = [
            ("Indice", { "\(Formato.intero($0.indice))" }),
            ("Avversario", { "\(ColoriSquadra.sigla($0.avversario)) \($0.inCasa == true ? "casa" : "fuori")" }),
            ("Partita", { PillDifficolta.nome($0.difficolta) }),
            ("Gioca", { "\(Formato.percento($0.pVoto))%" }),
            ("Fantavoto atteso (se gioca)", { Formato.punti($0.fvAtteso) }),
            ("Punti attesi", { Formato.decimali($0.puntiAttesi, cifre: 2) }),
            ("Parte titolare", { "\(Formato.percento($0.quotaTitolare))%" }),
            ("Segna", { "\(Formato.percento($0.pGol))%" }),
            ("Assist", { "\(Formato.percento($0.pAssist))%" }),
            ("Giallo", { "\(Formato.percento($0.pGiallo))%" }),
        ]
        return numeri.map { VoceNumeriConfronto(titolo: $0.0, a: $0.1(x), b: $0.1(y)) }
    }
}
