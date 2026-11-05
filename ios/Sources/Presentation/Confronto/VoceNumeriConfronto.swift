import Foundation

/// Una voce di «Tutti i numeri» nel Confronto: il nome del numero e il valore già scritto di ognuno dei due giocatori.
/// La stessa voce serve alla tabella (`NumeriInTabella`) e all'elenco del testo grande (`NumeriInElenco`).
/// Voci e valori con le parole della tabella della web (`apriConfronto` di app.js, chiavi `mercato.*` di testi.js, #293).
struct VoceNumeriConfronto: Identifiable {
    let titolo: String
    /// Il valore del primo giocatore (colonna di sinistra).
    let a: String
    /// Il valore del secondo giocatore (colonna di destra).
    let b: String
    /// Come li legge VoiceOver, se diverso da quello che si vede (l'avversario per intero, non «vs COM»).
    var voceA: String? = nil
    var voceB: String? = nil

    var id: String { titolo }

    /// La frase letta da VoiceOver: «Indice: Pinarotti 72, Rossi 65».
    func frase(_ x: Giocatore, _ y: Giocatore) -> String {
        "\(titolo): \(x.nomeCorto) \(voceA ?? a), \(y.nomeCorto) \(voceB ?? b)"
    }

    /// «Quando gioca» a parole, con le soglie di `partenzaAParole` della web (quota delle partite da titolare): «quasi sempre
    /// titolare», «a volte titolare», «di solito entra dopo»; «–» senza il dato. Niente percentuale: l'unica sul giocare è «Gioca».
    static func quandoGioca(_ quota: Double?) -> String {
        guard let quota, quota.isFinite else { return "–" }
        return quota >= 0.7 ? "quasi sempre titolare" : quota >= 0.4 ? "a volte titolare" : "di solito entra dopo"
    }

    /// L'avversario come sulle pedine e nella web (`vsAt`): «vs COM» in casa, «@ COM» in trasferta; «–» se non si sa.
    static func avversario(_ g: Giocatore) -> String {
        let sigla = ColoriSquadra.sigla(g.avversario)
        guard !sigla.isEmpty else { return "–" }
        return "\(g.inCasa == true ? "vs" : "@") \(sigla)"
    }

    /// Lo stesso a voce, con il nome intero: «in casa contro Como», «in trasferta contro Como». Nil se non si sa.
    static func avversarioAVoce(_ g: Giocatore) -> String? {
        LetturaPedina.nomeSquadra(g.avversario).map { "\(g.inCasa == true ? "in casa" : "in trasferta") contro \($0)" }
    }

    /// Le voci, nell'ordine della web. In testa alla riga con la maiuscola (la web scrive «segna», «assist», «giallo»).
    @MainActor
    static func voci(_ x: Giocatore, _ y: Giocatore) -> [VoceNumeriConfronto] {
        let numeri: [(String, (Giocatore) -> String)] = [
            ("Indice", { "\(Formato.intero($0.indice))" }),
            ("Avversario", avversario),
            ("Partita", { PillDifficolta.nome($0.difficolta) }),
            ("Gioca", { "\(Formato.percento($0.pVoto))%" }),
            ("Fantavoto atteso", { Formato.punti($0.fvAtteso) }),
            ("Atteso ponderato (con la probabilità di giocare)", { Formato.decimali($0.puntiAttesi, cifre: 2) }),
            ("Quando gioca", { quandoGioca($0.quotaTitolare) }),
            ("Segna", { "\(Formato.percento($0.pGol))%" }),
            ("Assist", { "\(Formato.percento($0.pAssist))%" }),
            ("Giallo", { "\(Formato.percento($0.pGiallo))%" }),
        ]
        return numeri.map { titolo, valore in
            let aVoce = titolo == "Avversario"
            return VoceNumeriConfronto(titolo: titolo, a: valore(x), b: valore(y),
                                       voceA: aVoce ? avversarioAVoce(x) : nil, voceB: aVoce ? avversarioAVoce(y) : nil)
        }
    }
}
