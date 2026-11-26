import Foundation

/// La partita di un giocatore quando è cominciata, come `esitoPartita` di app.js: «gioca N%» non serve più.
/// - `fv`: il fantavoto preso, a partita finita con il voto (`fv_preso` del server) o il voto d'ufficio; nil in tutti gli altri casi.
/// - `testo`: quello che la pedina scrive al posto di «gioca N%»: «fantavoto 6,5» o lo stato della partita («Partita in corso»,
///   «Voto in arrivo», «Senza voto»), con le parole del server (`etichetta.testo`) o, con un server vecchio, di testi.js.
/// - `parola`: accanto al voto, la parola del server quando il voto non viene dal campo: «Voto d'ufficio» (#895, etichetta
///   `voto_ufficio`: partita rinviata con il voto d'ufficio della lega, già contato tra i punti fatti). nil negli altri casi.
/// La pedina del campo aggiunge la partita rinviata (`EsitoPedina`); le righe dei giocatori no (`RigaGiocatore`), come la web.
struct EsitoPartita: Equatable {
    let fv: Double?
    let testo: String?
    let parola: String?

    /// nil se la partita non è cominciata, anche se è rinviata (tranne con il voto d'ufficio). Il `codice` dell'etichetta serve solo
    /// per decidere.
    init?(etichetta: Avviso.EtichettaPronta?, statoPartita: String?, fvPreso: Double?) {
        let pronta = etichetta?.testoPronto
        let codice = pronta == nil ? nil : etichetta?.codice
        // il voto d'ufficio si mostra come un voto preso, con la sua parola (come la web dopo la #899)
        if codice == "voto_ufficio", let fvPreso, fvPreso.isFinite {
            fv = fvPreso
            testo = "fantavoto \(Formato.punti(fvPreso))"
            parola = pronta
            return
        }
        guard EsitoPedina.statiIniziata.contains(statoPartita ?? "") || EsitoPedina.codiciIniziata.contains(codice ?? "") else {
            return nil
        }
        parola = nil
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

    /// Rimasto senza voto (#895, come `senzaVoto` della web): il suo fantavoto atteso non conta più (al suo posto entra una riserva,
    /// o niente) e la pedina non lo mostra. Con l'etichetta del server decide il suo codice, altrimenti lo stato della partita.
    var rimastoSenzaVoto: Bool {
        (etichetta?.testoPronto != nil ? etichetta?.codice : statoPartita) == "senza_voto"
    }
}
