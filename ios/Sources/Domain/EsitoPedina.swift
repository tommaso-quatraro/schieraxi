import Foundation

/// Cosa scrive la pedina del campo al posto di «gioca N%», come `esitoPedina` di app.js (#283, #284):
/// - a partita iniziata il fantavoto preso («fantavoto 6,5») o lo stato della partita («Partita in corso», «Voto in arrivo»,
///   «Senza voto»): la probabilità di giocare non serve più (`docs/COERENZA-WEB-IPHONE.md`, «Probabilità di giocare»);
/// - partita rinviata, prima e dopo la scadenza: «Rinviata».
/// Le parole sono quelle del server (`etichetta.testo`); con un server vecchio le stesse di testi.js (`tit.st_*`, in
/// `Giocatore.nomiStatoPartita`). Il `codice` dell'etichetta serve solo per decidere, mai per scrivere (`docs/API.md`).
enum EsitoPedina {
    /// `stato_partita` a partita cominciata (`PARTITA_INIZIATA` di app.js).
    static let statiIniziata: Set<String> = ["in_corso", "attesa_voti", "fatto", "senza_voto"]
    /// I codici dell'etichetta a partita cominciata (`CODICI_PARTITA_INIZIATA` di app.js).
    static let codiciIniziata: Set<String> = ["voto", "senza_voto", "voto_in_arrivo", "in_corso"]

    /// Il testo sotto la pedina; nil se la partita non è cominciata e non è rinviata (allora «gioca N%»).
    static func testo(etichetta: Avviso.EtichettaPronta?, statoPartita: String?, fvPreso: Double?, rinvio: String?) -> String? {
        // a partita cominciata come `esitoPartita` (anche le righe dei giocatori); poi il rinvio, solo per la pedina
        if let partita = EsitoPartita(etichetta: etichetta, statoPartita: statoPartita, fvPreso: fvPreso) { return partita.testo }
        let pronta = etichetta?.testoPronto
        let codice = pronta == nil ? nil : etichetta?.codice
        // con l'etichetta decide il suo codice; con un server vecchio lo stato della partita o il modo del rinvio
        let rinviata = pronta == nil ? statoPartita == "rinviata" || rinvio != nil : codice == "rinviata"
        guard rinviata else { return nil }
        return pronta ?? Giocatore.nomiStatoPartita["rinviata"]?.0
    }
}

extension Giocatore {
    /// Il testo sotto la pedina al posto di «gioca N%» (vedi `EsitoPedina`); nil prima della partita.
    var esitoPedina: String? {
        EsitoPedina.testo(etichetta: etichetta, statoPartita: statoPartita, fvPreso: fantavotoPreso, rinvio: modoRinvio)
    }

    /// La frase di VoiceOver della pedina, come `vocePedina` della web (#616): le stesse cose che si vedono, senza ruolo né
    /// avversario: «Rossi, fantavoto atteso 6,8, gioca al 45 per cento, In dubbio»; a partita iniziata o rinviata l'esito al posto
    /// di «gioca al N per cento» (`LetturaPedina.contenuto`).
    var vocePedina: String { LetturaPedina.contenuto(self).voce }
}
