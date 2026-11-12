import Foundation

/// La scheda del giocatore aperta dalla Formazione, come `stato.formaz` di app.js (#616): la previsione già letta (la scheda si
/// apre subito, senza aspettare il server), il perché del titolare e cosa ci si può fare. Lo prepara
/// `FormazioneViewModel.contestoScheda`; da altrove (Oggi, rose, ricerca) la scheda non ha contesto e aspetta `/api/giocatore`.
struct ContestoScheda {
    /// La scheda del giocatore nella risposta di `GET /api/formazione`.
    let previsione: Giocatore
    /// «Perché è titolare»: solo sulla consigliata, a formazione aperta.
    var perche: String? = nil
    /// Titolare della tua formazione ancora aperta: «Sostituisci».
    var sostituibile = false
    /// Titolare che gioca un anticipo già cominciato: al posto di «Sostituisci» la frase di `formazione.bloccati`.
    var fermo = false
}
