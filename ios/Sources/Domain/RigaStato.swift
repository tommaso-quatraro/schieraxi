import Foundation

/// La riga sotto il titolo della pagina Giornate, come la riga di stato della web (`rigaStato` e `caricaInfo` di `app.js`, #863):
/// «Giornata 13 · 13ª di Serie A · Real Esempio · dati del 26 ott 23:55». I pezzi vengono da `GET /api/stato` (`prossima_giornata`,
/// `prossima_giornata_lega`, `mia_squadra`, `ultimo_aggiornamento`) e un pezzo che manca non si scrive; la giornata con
/// `NomeGiornata`, come ovunque. Se `/api/stato` non risponde, «Server non raggiungibile» e dopo, se c'è, i pezzi dell'ultima
/// risposta (anche la copia salvata sul telefono), come la web dal collaudo del 26/11 (prima solo «Server non raggiungibile»). Testi
/// dal catalogo comune (`testata.*`).
struct RigaStato: Equatable {
    /// I pezzi nell'ordine della web: la giornata, la mia squadra, la data dei dati; senza server prima «Server non raggiungibile».
    let pezzi: [String]
    /// La mia squadra, per lo stemma davanti (nil senza squadra o senza server, come la web dopo una ricarica).
    let squadra: String?
    /// La riga intera per VoiceOver: la giornata detta per intero e la virgola al posto di «·».
    let voce: String

    /// La riga come la scrive la web, con « · » fra i pezzi.
    var testo: String { pezzi.joined(separator: " · ") }

    /// nil finché `/api/stato` non ha mai risposto (e non ce n'è una copia) e non si sa che il server non risponde: niente da dire,
    /// come la web prima della sua prima lettura.
    init?(info: InfoServer?, nonRaggiungibile: Bool) {
        let copia = info.map(Self.pezziDi)
        if nonRaggiungibile {
            pezzi = [Catalogo.Testata.offline] + (copia?.pezzi ?? [])
            squadra = nil
            voce = ([Catalogo.Testata.offline] + (copia?.voce ?? [])).joined(separator: ", ")
            return
        }
        guard let copia else { return nil }
        pezzi = copia.pezzi
        squadra = copia.squadra
        voce = copia.voce.joined(separator: ", ")
    }

    /// I pezzi di una risposta di `/api/stato`: a vista, per VoiceOver (la giornata detta per intero) e la mia squadra.
    private static func pezziDi(_ info: InfoServer) -> (pezzi: [String], voce: [String], squadra: String?) {
        let giornata = info.prossimaGiornata.flatMap { $0 > 0 ? NomeGiornata(serieA: $0, lega: info.prossimaGiornataLega) : nil }
        let mia = info.miaSquadra.flatMap { $0.isEmpty ? nil : $0 }
        let dati = Self.dati(info.ultimoAggiornamento)
        return ([giornata?.intero, mia, dati].compactMap { $0 }, [giornata?.voce, mia, dati].compactMap { $0 }, mia)
    }

    /// «dati del 26 ott 23:55» (ora italiana) o, senza una data che si capisce, «dati mai aggiornati»: le frasi del catalogo
    /// cominciano con « · » (sulla web seguono la squadra nella testata) e qui, come la web, la riga lo toglie.
    private static func dati(_ ultimo: String?) -> String {
        let frase = Quando.data(ultimo).map { Catalogo.Testata.datiDel(data: Quando.giornoEMese($0), ora: Quando.ora($0)) }
            ?? Catalogo.Testata.mai
        return frase.replacingOccurrences(of: #"^\s*·\s*"#, with: "", options: .regularExpression)
    }
}
