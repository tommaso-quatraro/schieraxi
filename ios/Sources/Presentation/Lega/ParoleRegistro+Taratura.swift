import Foundation

/// La riga della taratura di «gioca N%» con le probabili in Stato dei dati (#379), uguale alla web: `rigaTaratura` di
/// `fanta/web/app.js` e i testi `sd.tar_*` del catalogo comune (`Catalogo+Sd.swift`; `TaraturaProbabiliTests` prova le frasi composte). Stato, versione, numeri
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
            parti = [giornate < minimo ? Catalogo.Sd.tarInAttesaSu(giornate, m: String(minimo)) : Catalogo.Sd.tarInAttesa(giornate)]
        case "attiva":
            let versione = t.versione ?? "–"
            let accesa = giornoMese(t.dal).map { Catalogo.Sd.tarAttivaDal(d: $0, v: versione) } ?? Catalogo.Sd.tarAttiva(v: versione)
            let rimandato = t.motivo == "scadenza_vicina" ? motivoTaratura(t.motivo, giornate: giornate) : nil
            parti = [accesa, t.prova.map(provaTaratura), rimandato]
        case "non_attiva":
            parti = [Catalogo.Sd.tarNonAttiva, motivoTaratura(t.motivo, giornate: giornate)]
        case "spenta":
            parti = [Catalogo.Sd.tarSpenta]
        default:
            return nil
        }
        return Catalogo.Sd.tarRiga(s: parti.compactMap { $0 }.joined(separator: " · "))
    }

    /// La frase di un motivo del server (`sd.tar_m_*`); nil per un codice che l'app non conosce (niente codici per l'utente).
    static func motivoTaratura(_ codice: String?, giornate: Int) -> String? {
        switch codice ?? "" {
        case "non_migliora": return Catalogo.Sd.tarMNonMigliora
        case "poche_giornate": return Catalogo.Sd.tarMPocheGiornate(n: String(giornate))
        case "fuori_soglia": return Catalogo.Sd.tarMFuoriSoglia
        case "incoerente": return Catalogo.Sd.tarMIncoerente
        case "peggiorata": return Catalogo.Sd.tarMPeggiorata
        case "scadenza_vicina": return Catalogo.Sd.tarMScadenzaVicina
        case "spenta_a_mano": return Catalogo.Sd.tarMSpentaAMano
        default: return nil
        }
    }

    /// I numeri della prova (`sd.tar_prova`): Brier con quattro cifre, scarto in punti con una cifra e senza «,0»; «–» se mancano.
    static func provaTaratura(_ p: StatoDati.Taratura.Prova) -> String {
        Catalogo.Sd.tarProva(p.giornate ?? 0, b: Formato.decimali(p.brier, cifre: 4), c: punti(p.calibrazione, per: 100),
                             p: Formato.decimali(p.brierPrima, cifre: 4))
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
