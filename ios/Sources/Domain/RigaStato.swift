import Foundation

/// La riga sotto il titolo della pagina Giornate, come la riga di stato della web (`rigaStato` e `caricaInfo` di `app.js`, #863):
/// «Giornata 13 · 13ª di Serie A · Real Esempio · dati del 26 ott 23:55». I pezzi vengono da `GET /api/stato` (`prossima_giornata`,
/// `prossima_giornata_lega`, `mia_squadra`, `ultimo_aggiornamento`) e un pezzo che manca non si scrive; la giornata con
/// `NomeGiornata`, come ovunque. Se `/api/stato` non risponde, «Server non raggiungibile», come la web. Testi dal catalogo comune
/// (`testata.*`).
struct RigaStato: Equatable {
    /// I pezzi nell'ordine della web: la giornata, la mia squadra, la data dei dati (o «Server non raggiungibile» da solo).
    let pezzi: [String]
    /// La mia squadra, per lo stemma davanti (nil senza squadra o senza server, come la web).
    let squadra: String?
    /// La riga intera per VoiceOver: la giornata detta per intero e la virgola al posto di «·».
    let voce: String

    /// La riga come la scrive la web, con « · » fra i pezzi.
    var testo: String { pezzi.joined(separator: " · ") }

    /// nil finché `/api/stato` non ha mai risposto: niente da dire, come la web prima della sua prima lettura.
    init?(info: InfoServer?, nonRaggiungibile: Bool) {
        if nonRaggiungibile {
            pezzi = [Catalogo.Testata.offline]
            squadra = nil
            voce = Catalogo.Testata.offline
            return
        }
        guard let info else { return nil }
        let giornata = info.prossimaGiornata.flatMap { $0 > 0 ? NomeGiornata(serieA: $0, lega: info.prossimaGiornataLega) : nil }
        let mia = info.miaSquadra.flatMap { $0.isEmpty ? nil : $0 }
        let dati = Self.dati(info.ultimoAggiornamento)
        pezzi = [giornata?.intero, mia, dati].compactMap { $0 }
        squadra = mia
        voce = [giornata?.voce, mia, dati].compactMap { $0 }.joined(separator: ", ")
    }

    /// «dati del 26 ott 23:55» (ora italiana) o, senza una data che si capisce, «dati mai aggiornati»: le frasi del catalogo
    /// cominciano con « · » (sulla web seguono la squadra nella testata) e qui, come la web, la riga lo toglie.
    private static func dati(_ ultimo: String?) -> String {
        let frase = Quando.data(ultimo).map { Catalogo.Testata.datiDel(data: Quando.giornoEMese($0), ora: Quando.ora($0)) }
            ?? Catalogo.Testata.mai
        return frase.replacingOccurrences(of: #"^\s*·\s*"#, with: "", options: .regularExpression)
    }
}
