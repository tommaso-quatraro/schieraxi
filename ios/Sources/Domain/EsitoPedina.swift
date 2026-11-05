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
        let pronta = etichetta?.testoPronto
        let codice = pronta == nil ? nil : etichetta?.codice
        if statiIniziata.contains(statoPartita ?? "") || codiciIniziata.contains(codice ?? "") {
            if let fvPreso, fvPreso.isFinite, codice == "voto" || statoPartita == "fatto" {
                return "fantavoto \(Formato.punti(fvPreso))"
            }
            return pronta ?? statoPartita.flatMap { Giocatore.nomiStatoPartita[$0]?.0 }
        }
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

    /// La frase di VoiceOver della pedina: quella di `LetturaPedina.voce` e, a partita iniziata o rinviata, l'esito al posto di
    /// «gioca al N per cento» (come `vocePedina` della web): «Rossi, difensore, fantavoto atteso 6,5, Partita in corso, …».
    var vocePedina: String {
        let ruoloAVoce = nomeRuolo(ruolo)
        guard let esito = esitoPedina else {
            return LetturaPedina.voce(nome: nome, ruolo: ruoloAVoce, fvAtteso: fvAtteso, pVoto: pVoto, avversario: avversario, inCasa: inCasa)
        }
        var parti = [nome, ruoloAVoce, "fantavoto atteso \(Formato.punti(fvAtteso))", esito]
        if let avv = LetturaPedina.nomeSquadra(avversario) {
            parti.append("avversario \(avv)" + (inCasa == true ? ", in casa" : inCasa == false ? ", in trasferta" : ""))
        }
        return parti.joined(separator: ", ")
    }
}
