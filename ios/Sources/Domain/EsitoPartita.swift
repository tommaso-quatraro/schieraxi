import Foundation

/// La partita di un giocatore quando è cominciata, come `esitoPartita` di app.js: «gioca N%» non serve più.
/// - `fv`: il fantavoto preso, a partita finita con il voto (`fv_preso` del server); nil in tutti gli altri casi.
/// - `testo`: quello che la pedina scrive al posto di «gioca N%»: «fantavoto 6,5» o lo stato della partita («Partita in corso»,
///   «Voto in arrivo», «Senza voto»), con le parole del server (`etichetta.testo`) o, con un server vecchio, di testi.js.
/// La pedina del campo aggiunge la partita rinviata (`EsitoPedina`); le righe dei giocatori no (`RigaGiocatore`), come la web.
struct EsitoPartita: Equatable {
    let fv: Double?
    let testo: String?

    /// nil se la partita non è cominciata, anche se è rinviata. Il `codice` dell'etichetta serve solo per decidere.
    init?(etichetta: Avviso.EtichettaPronta?, statoPartita: String?, fvPreso: Double?) {
        let pronta = etichetta?.testoPronto
        let codice = pronta == nil ? nil : etichetta?.codice
        guard EsitoPedina.statiIniziata.contains(statoPartita ?? "") || EsitoPedina.codiciIniziata.contains(codice ?? "") else {
            return nil
        }
        if let fvPreso, fvPreso.isFinite, codice == "voto" || statoPartita == "fatto" {
            fv = fvPreso
            testo = "fantavoto \(Formato.punti(fvPreso))"
        } else {
            fv = nil
            testo = pronta ?? statoPartita.flatMap { Giocatore.nomiStatoPartita[$0]?.0 }
        }
    }
}

extension Giocatore {
    /// La sua partita, se è cominciata (vedi `EsitoPartita`); nil prima della partita e con la partita rinviata.
    var esitoPartita: EsitoPartita? {
        EsitoPartita(etichetta: etichetta, statoPartita: statoPartita, fvPreso: fantavotoPreso)
    }
}
