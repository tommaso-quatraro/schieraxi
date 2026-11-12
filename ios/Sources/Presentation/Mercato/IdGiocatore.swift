/// La scheda di un giocatore da aprire sopra la schermata (identificata dall'id del giocatore). `contesto` c'è quando si apre
/// dalla Formazione: la previsione già letta, il perché del titolare e «Sostituisci» (`ContestoScheda`).
struct IdGiocatore: Identifiable {
    let id: Int
    var contesto: ContestoScheda? = nil
}
