import Foundation

// Partite rinviate (contratto «Partite rinviate» in `docs/API.md`): cosa vale per i giocatori di una partita rinviata, anche a
// settimane dopo. La regola della lega sta nelle regole (`partite_rinviate`, `voto_ufficio_rinviate`); per una sola giornata la
// si cambia con `PUT /api/regole/rinvio`. Tutti i campi sono facoltativi: con un server vecchio non compare niente.
// I modelli (`SceltaRinvio`, `PartitaRinviata`, `GiocatoreRinviato`, `ModoRinvio`) stanno in Modelli.swift (li legge anche il widget).

/// Il corpo di `PUT /api/regole/rinvio`: `modo` nil = torna alla regola della lega.
struct CorpoRinvio: Encodable, Equatable {
    let giornata: Int
    let modo: String?
    let stagione: String?
}

extension Oggi {
    /// Le partite rinviate della giornata (riquadro «Partita rinviata»), solo se ce n'è almeno una.
    var partiteRinviate: SceltaRinvio? {
        guard let r = rinvio?.valore, !r.partite.isEmpty else { return nil }
        return r
    }
}

/// I testi dei rinvii, uguali alla web app (`oggi.rinvio_*`, `regole.rv_*` in testi.js), in un posto solo.
enum TestiRinvio {
    static func titolo(_ quante: Int) -> String { quante > 1 ? "Partite rinviate" : "Partita rinviata" }

    static let domanda = "Per questa giornata i loro giocatori"

    /// La voce del menu: «aspettano il recupero (conta il suo voto)»…
    static func nomeModo(_ modo: String?, voto: Double?) -> String {
        switch modo {
        case ModoRinvio.aspetta: return "aspettano il recupero (conta il suo voto)"
        case ModoRinvio.senzaVoto: return "restano senza voto (entra la riserva)"
        case ModoRinvio.votoUfficio: return "prendono il voto d'ufficio (\(numero(voto ?? 6)))"
        default: return modo ?? ""
        }
    }

    /// «6», «5,5».
    static func numero(_ v: Double) -> String { Formato.decimali(v, cifre: v.rounded() == v ? 0 : 1) }

    /// «UDI vs MIL»: le sigle, prima la squadra di casa, come le partite del turno e la carta della web (`cardRinvio`, #284).
    static func partita(_ p: PartitaRinviata) -> String { "\(ColoriSquadra.sigla(p.casa)) vs \(ColoriSquadra.sigla(p.trasferta))" }

    /// La stessa partita per VoiceOver, con i nomi interi come le partite del turno: «Udinese contro Milan».
    static func partitaAVoce(_ p: PartitaRinviata) -> String { "\(p.casa.capitalized) contro \(p.trasferta.capitalized)" }

    /// «recupero mer 18 nov 20:45» (la data come `quando` della web: «oggi 20:45», «dom 8 15:00», oltre la settimana con il
    /// mese) oppure «recupero da definire». `adesso` serve solo ai test.
    static func recupero(_ p: PartitaRinviata, adesso: Date = Date()) -> String {
        guard Quando.data(p.data) != nil else { return "recupero da definire" }
        return "recupero \(Quando.leggibile(p.data, adesso: adesso))"
    }

    static func miei(_ s: SceltaRinvio) -> String? {
        s.miei.isEmpty ? nil : "I tuoi giocatori coinvolti: \(s.miei.map(\.nome).joined(separator: ", "))"
    }

    /// La riga sotto il menu: regola della lega oppure scelta solo per questa giornata.
    static func nota(_ s: SceltaRinvio) -> String {
        if s.eccezione {
            return "Scelta solo per questa giornata. Di solito la tua lega: \(nomeModo(s.predefinito, voto: s.votoUfficio))."
        }
        return "È la regola della tua lega (Altro › Regole). Se per questa giornata la lega decide diversamente, cambiala qui: vale solo per questa giornata."
    }

    /// Nel riepilogo della giornata finita: «Manca il recupero di ATA vs PAR: i punti possono ancora cambiare.» Nil se non manca
    /// niente. Le partite scritte come la carta del rinvio (`partita`), uguale alla web (`oggi.recupero_manca` con `partitaVs`, #310).
    static func recuperoManca(_ recuperi: [PartitaRinviata]) -> String? {
        let partite = recuperi.map { partita($0) }
        return partite.isEmpty ? nil : "Manca il recupero di \(partite.joined(separator: ", ")): i punti possono ancora cambiare."
    }

    static let salvato = "Fatto: consigli aggiornati per questa giornata"

    // MARK: regole della lega

    static let sezioneRegole = "Partite rinviate"
    static let aiutoRegole = "Cosa fa la lega con i giocatori di una partita rinviata, anche a settimane dopo. Per una sola giornata puoi cambiarlo da Oggi."

    /// L'etichetta corta nel selettore delle regole.
    static func etichetta(_ modo: String) -> String {
        switch modo {
        case ModoRinvio.aspetta: return "Aspetta il recupero"
        case ModoRinvio.senzaVoto: return "Senza voto"
        case ModoRinvio.votoUfficio: return "Voto d'ufficio"
        default: return modo
        }
    }

    static func spiega(_ modo: String) -> String {
        switch modo {
        case ModoRinvio.senzaVoto: return "I giocatori restano senza voto: entra la riserva."
        case ModoRinvio.votoUfficio: return "Tutti prendono lo stesso voto, senza bonus né malus."
        default: return "Si aspetta il recupero e conta il voto preso lì: i giocatori restano schierabili."
        }
    }
}
