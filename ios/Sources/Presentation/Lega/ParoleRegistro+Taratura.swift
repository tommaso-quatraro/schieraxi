import Foundation

/// La riga della taratura di «gioca N%» con le probabili in Stato dei dati (#379), uguale alla web: `rigaTaratura` di
/// `fanta/web/app.js` e i testi `sd.tar_*` di `fanta/web/testi.js` (`TaraturaProbabiliTests` li confronta). Stato, versione, numeri
/// della prova e motivo arrivano dal server: qui si scrivono e basta, Brier con quattro cifre e scarto in punti come il registro.
/// Sta con le parole del registro: la taratura si fa sulle giornate del registro e ne usa i numeri (`cifra`, `punti`).
extension ParoleRegistro {
    /// La frase sotto i gruppi della calibrazione; nil senza il campo o con uno stato che l'app non conosce (nessuna riga).
    static func taratura(_ t: StatoDati.Taratura?) -> String? {
        guard let t else { return nil }
        let giornate = t.giornate ?? 0
        let parti: [String?]
        switch t.stato ?? "" {
        case "in_attesa":
            let minimo = t.minimo ?? 0
            let attesa = "in attesa · \(Formato.giornate(giornate))"
            parti = [giornate < minimo ? "\(attesa) su \(minimo)" : attesa]
        case "attiva":
            let versione = t.versione ?? "–"
            let accesa = giornoMese(t.dal).map { "attiva dal \($0) (versione \(versione))" } ?? "attiva (versione \(versione))"
            let rimandato = t.motivo == "scadenza_vicina" ? motivoTaratura(t.motivo, giornate: giornate) : nil
            parti = [accesa, t.prova.map(provaTaratura), rimandato]
        case "non_attiva":
            parti = ["non attiva", motivoTaratura(t.motivo, giornate: giornate)]
        case "spenta":
            parti = ["spenta a mano"]
        default:
            return nil
        }
        return "Taratura con le probabili: " + parti.compactMap { $0 }.joined(separator: " · ")
    }

    /// La frase di un motivo del server (`sd.tar_m_*`); nil per un codice che l'app non conosce (niente codici per l'utente).
    static func motivoTaratura(_ codice: String?, giornate: Int) -> String? {
        switch codice ?? "" {
        case "non_migliora": return "non sbaglia meno dei numeri di partenza"
        case "poche_giornate": return "la prova passa, si accende con 8 giornate (ora \(giornate))"
        case "fuori_soglia": return "fuori dalle soglie di scarto o di Brier"
        case "incoerente": return "i numeri tarati non sono validi"
        case "peggiorata": return "tornata ai numeri di partenza: sbagliava di più nelle ultime giornate"
        case "scadenza_vicina": return "cambio rimandato: la prima partita è tra meno di 24 ore"
        case "spenta_a_mano": return "spenta a mano"
        default: return nil
        }
    }

    /// I numeri della prova (`sd.tar_prova`): Brier con quattro cifre, scarto in punti con una cifra e senza «,0»; «–» se mancano.
    static func provaTaratura(_ p: StatoDati.Taratura.Prova) -> String {
        let n = p.giornate ?? 0
        let dove = n == 1 ? "nell'ultima giornata" : "nelle ultime \(n) giornate"
        return "\(dove) Brier \(Formato.decimali(p.brier, cifre: 4)) invece di \(Formato.decimali(p.brierPrima, cifre: 4)), "
            + "scarto \(punti(p.calibrazione, per: 100))"
    }

    /// «15/1» dalla data del server («2027-01-15T10:00:00»), senza passare dal fuso orario; nil se non è una data.
    static func giornoMese(_ testo: String?) -> String? {
        guard let testo else { return nil }
        let c = Array(testo.prefix(10))
        let cifre = [0, 1, 2, 3, 5, 6, 8, 9]
        guard c.count == 10, c[4] == "-", c[7] == "-", cifre.allSatisfy({ ("0"..."9").contains(c[$0]) }),
              let mese = Int(String(c[5...6])), let giorno = Int(String(c[8...9])) else { return nil }
        return "\(giorno)/\(mese)"
    }
}
