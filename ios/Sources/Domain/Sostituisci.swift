import Foundation

// «Sostituisci» (come la web dal 26/11/2026): la domanda e la risposta di `POST /api/formazione/sostituisci` (contratto in
// docs/API.md), il contrario di «Metti in campo». Il calcolo è tutto del server: l'app manda gli 11 in campo e mostra i numeri che
// tornano. Prima l'app scriveva la differenza fra i due giocatori, che non tornava con la formazione dopo il cambio.

/// La domanda: chi esce, gli 11 in campo e la giornata della Formazione.
struct RichiestaSostituisci: Encodable {
    let esce: Int
    let titolari: [Int]
    var giornata: Int? = nil
}

/// La risposta: i punti attesi della formazione di adesso e chi può prendere il posto di `esce`, dal cambio che rende di più.
struct RispostaSostituisci: Decodable {
    let giornata: Int?
    let esce: Int?
    let punteggioAtteso: Double?
    let entrate: [EntrataSostituisci]?
}

/// Un compagno che può entrare: i punti attesi della formazione dopo il cambio e la differenza da quelli di adesso (calcolata dal
/// server sui due numeri arrotondati).
struct EntrataSostituisci: Decodable {
    let entra: Int?
    let punteggioAtteso: Double?
    let differenza: Double?
}
