import Foundation

/// Le etichette sotto il nome nelle righe di «Metti in campo» e di «Sostituisci» (#778). Scheletro per il test: per ora le stesse
/// della pedina, il codice come la web arriva nel commit dopo.
enum EtichetteRiga {
    static func pezzi(_ g: Giocatore, inPiu: [String] = []) -> [LetturaPedina.Pezzo] {
        LetturaPedina.contenuto(g).pezzi + inPiu.map { LetturaPedina.Pezzo(testo: $0, tono: .parola) }
    }
}
