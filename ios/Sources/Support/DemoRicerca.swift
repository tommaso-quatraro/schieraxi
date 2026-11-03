import Foundation

// La ricerca per nome della demo (`/api/giocatori?q=…&limite=…`), come `cerca_giocatori` di fanta/server.py: nel listone della
// lega inventata, senza badare ad accenti, maiuscole e segni; prima chi comincia con il testo, poi per quotazione (#246).

extension LegaDemo {
    /// Lettere che la scomposizione Unicode non semplifica da sola (`_LETTERE_SPECIALI` di fanta/nomi.py).
    private static let lettereSpeciali: [Character: String] = [
        "ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "þ": "th", "ı": "i", "œ": "oe",
    ]
    private static let lettereECifre = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyz0123456789")

    /// Un nome come lo confronta il server (`normalizza` di fanta/nomi.py): minuscolo, senza accenti, apostrofi e segni
    /// («Çalvaroğlu» → «calvaroglu», «N'Dicka» → «ndicka»). Non `localizedStandardContains`: la ricerca deve trovare gli stessi
    /// giocatori del server, che normalizza così.
    static func normalizza(_ testo: String) -> String {
        let semplice = testo.map { lettereSpeciali[$0] ?? String($0) }.joined()
            .folding(options: [.diacriticInsensitive, .caseInsensitive], locale: nil)
            .lowercased()
            .filter { !"'’`".contains($0) }
        return semplice.components(separatedBy: lettereECifre.inverted).filter { !$0.isEmpty }.joined(separator: " ")
    }

    /// I giocatori il cui nome contiene il testo cercato, al massimo `limite` (tra 1 e 100): prima chi comincia così, poi chi ha
    /// la quotazione più alta, a parità nell'ordine del listone.
    static func cerca(_ testo: String, limite: Int) -> [CalciatoreDemo] {
        let cercato = normalizza(testo)
        guard !cercato.isEmpty else { return [] }
        let trovati: [(posto: Int, giocatore: CalciatoreDemo, comincia: Bool)] = tutti.enumerated().compactMap { (i, p) in
            let nome = normalizza(p.nome)
            return nome.contains(cercato) ? (posto: i, giocatore: p, comincia: nome.hasPrefix(cercato)) : nil
        }
        let ordinati = trovati.sorted { x, y in
            if x.comincia != y.comincia { return x.comincia }
            let qx = quotazione(x.giocatore), qy = quotazione(y.giocatore)
            return qx != qy ? qx > qy : x.posto < y.posto
        }
        return ordinati.prefix(max(1, min(limite, 100))).map { $0.giocatore }
    }
}
