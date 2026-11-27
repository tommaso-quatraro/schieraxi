import Foundation

/// La riga di un gruppo di «Quanto ci azzecca il modello» in Stato dei dati, uguale alla web (`apriStatoDati` in
/// `fanta/web/app.js`): «312 giocatori · hanno giocato 94% · previsto 91% · correzione ×1,03» (`sd.n_giocatori`,
/// `sd.hanno_giocato`, `sd.pochi_dati`, `sd.correzione`). Numeri e correzione (`calibrazione.fattori`, quella che il modello usa
/// davvero) arrivano dal server: qui si scrivono e basta. `LaMiaLegaComeLaWebTests` le prova.
extension ParoleRegistro {
    /// La riga sotto il nome del gruppo; senza giocatori «ancora nessun dato». «hanno giocato» anche con un giocatore solo, come
    /// la web; la correzione solo per i gruppi che il server corregge.
    static func gruppo(_ g: StatoDati.GruppoCalibrazione, fattore: Double?) -> String {
        guard let n = g.n, n > 0 else { return Catalogo.Sd.nessunDato }
        var riga = "\(Catalogo.Sd.nGiocatori(n)) · "
            + Catalogo.Sd.hannoGiocato(o: "\(Formato.percento(g.osservato))%", p: "\(Formato.percento(g.previsto))%")
        if g.indicativo == true { riga += Catalogo.Sd.pochiDati }
        if let fattore, fattore != 0 { riga += " · " + Catalogo.Sd.correzione(f: fattoreScritto(fattore)) }
        return riga
    }

    /// Il fattore con i decimali che ha, al massimo tre, come `fNum(f, { maximumFractionDigits: 3 })` della web: «1,03», «1».
    private static func fattoreScritto(_ fattore: Double) -> String {
        fattore.formatted(.number.precision(.fractionLength(0...3)).grouping(.never).locale(Formato.locale))
    }
}
