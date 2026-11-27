import SwiftUI

/// La scheda di un giocatore aperta sopra la schermata (`Navigazione.scheda`). Aperta dalla Formazione legge lo stato di adesso
/// (`FormazioneViewModel.contestoAttuale`), come la web che a ogni ridisegno accende o spegne «Sostituisci» e «Metti in campo»
/// nella scheda aperta: toccato un giocatore mentre arrivano i dati, i pulsanti ci sono subito, spenti, e si accendono quando i
/// dati arrivano (prima la scheda teneva la fotografia presa all'apertura, e i pulsanti non comparivano più: collaudo del 26/11).
/// Da altrove (rose, ricerca, Giornate) la scheda non ha contesto e aspetta `/api/giocatore`.
struct SchedaAperta: View {
    let scheda: IdGiocatore
    let server: any ServerClient
    @ObservedObject var formazione: FormazioneViewModel
    /// «Sostituisci» e «Metti in campo»: chi apre il foglio lo chiude e poi apre l'elenco.
    let sostituisci: () -> Void
    let mettiInCampo: () -> Void

    var body: some View {
        GiocatoreSheet(id: scheda.id, server: server, contesto: contesto, sostituisci: sostituisci, mettiInCampo: mettiInCampo)
    }

    /// Dalla Formazione il contesto di adesso; da altrove nessuno.
    private var contesto: ContestoScheda? {
        guard let aperta = scheda.contesto else { return nil }
        return formazione.contestoAttuale(scheda.id, aperta: aperta)
    }
}
