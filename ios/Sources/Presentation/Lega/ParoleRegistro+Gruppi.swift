import Foundation

/// La riga di un gruppo di «Quanto ci azzecca il modello» in Stato dei dati. Numeri e correzione arrivano dal server: qui si
/// scrivono e basta.
extension ParoleRegistro {
    /// La riga sotto il nome del gruppo; senza giocatori «ancora nessun dato».
    static func gruppo(_ g: StatoDati.GruppoCalibrazione, fattore: Double?) -> String {
        guard let n = g.n, n > 0 else { return Catalogo.Sd.nessunDato }
        return "\(Formato.plurale(n, "giocatore", "giocatori")) · \(n == 1 ? "ha" : "hanno") giocato \(Formato.percento(g.osservato))% · previsto \(Formato.percento(g.previsto))%\(g.indicativo == true ? Catalogo.Sd.pochiDati : "")"
    }
}
