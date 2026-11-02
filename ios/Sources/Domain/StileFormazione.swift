import Foundation

/// Gli stili della formazione a parole, uguali al server (`LIVELLI_RISCHIO` in `fanta/formazione.py`, `docs/STILI.md`) e alla
/// web app. Il server manda già nome e descrizione: questi servono solo con un server vecchio che non li manda.
enum StileFormazione {
    static let nomi: [Int: String] = [-2: "Molto sicura", -1: "Sicura", 0: "Equilibrata", 1: "Rischiosa", 2: "Molto rischiosa"]

    static func descrizione(_ rischio: Int) -> String {
        switch rischio {
        case ...(-2):
            return "Punta su chi gioca quasi di sicuro e preferisce difese più folte: meno rischio di una brutta giornata, a costo di qualche punto atteso."
        case -1:
            return "Titolari più sicuri e, a parità di punti, una difesa più folta: perde al massimo qualche decimo di punto atteso."
        case 0:
            return "La via di mezzo: punti attesi alti ma con un po' di prudenza sui titolari. Non è lo stile con il massimo assoluto di punti attesi: «Rischiosa» a volte ne mostra qualche decimo in più."
        case 1:
            return "Qualche rischio in più su chi può fare molti punti e, a parità, un attaccante in più: più possibilità di una giornata eccezionale."
        default:
            return "Punta sul colpo e sul reparto offensivo: la giornata eccezionale è più probabile, ma anche quella brutta."
        }
    }

    /// Quando il modulo con la stella non è quello con più punti attesi (stili prudenti: rischio ≤ 0), la frase che lo spiega,
    /// come la web app (`formazione.stella_non_massimo`). Nil se a schermo i punti sono uguali o se non serve spiegare.
    static func stellaNonMassimo(_ livello: LivelloRischio) -> String? {
        guard livello.rischio <= 0,
              let stella = livello.moduli.first(where: { $0.modulo == livello.modulo }),
              let primo = livello.moduli.max(by: { $0.punteggioAtteso < $1.punteggioAtteso }),
              primo.modulo != stella.modulo,
              (primo.punteggioAtteso * 10).rounded() > (stella.punteggioAtteso * 10).rounded()
        else { return nil }
        return "Il \(primo.modulo) ha qualche decimo di punti attesi in più, ma con titolari meno sicuri: "
            + "con lo stile «\(livello.nome)» il \(stella.modulo) è la scelta più prudente."
    }
}
