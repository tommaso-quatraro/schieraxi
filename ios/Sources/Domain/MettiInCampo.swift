import Foundation

// «Metti in campo» (#778, come la web con #643): la domanda e la risposta di `POST /api/formazione/metti-in-campo` (contratto in
// docs/API.md). Il calcolo è tutto del server: l'app manda gli 11 in campo e mostra i numeri che tornano.

/// La domanda: chi entra, gli 11 in campo e la giornata della Formazione.
struct RichiestaMettiInCampo: Encodable {
    let entra: Int
    let titolari: [Int]
    var giornata: Int? = nil
}

/// La risposta: i punti attesi della formazione di adesso e chi può lasciare il posto a `entra`, dal cambio che rende di più.
struct RispostaMettiInCampo: Decodable {
    let giornata: Int?
    let entra: Int?
    let punteggioAtteso: Double?
    let uscite: [UscitaMettiInCampo]?
}

/// Un titolare che può lasciare il posto: il modulo dopo il cambio, se è diverso da quello di adesso, i punti attesi della
/// formazione dopo il cambio e la differenza da quelli di adesso (calcolata dal server sui due numeri arrotondati).
struct UscitaMettiInCampo: Decodable {
    let esce: Int?
    let modulo: String?
    let cambiaModulo: Bool?
    let punteggioAtteso: Double?
    let differenza: Double?
}
