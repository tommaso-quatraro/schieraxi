import Foundation

extension StatoDati {
    /// La taratura di «gioca N%» con le probabili (#379): il campo `calibrazione.taratura` di `/api/stato-dati`
    /// (`taratura_probabili.riepilogo` del server). Stato, versione, numeri della prova e motivo sono quelli del server: l'app li
    /// scrive e basta. Un server vecchio non lo manda; vale `null` se il server non riesce a leggerlo. Un campo che non si legge vale
    /// nil, così la pagina si apre lo stesso.
    struct Taratura: Decodable {
        /// I numeri della prova sulle ultime giornate (per una versione tornata ai numeri di partenza: le giornate dopo la sua prova).
        struct Prova: Decodable {
            let giornate: Int?
            /// Punteggio di Brier della formula provata, di quella di prima e dei numeri mostrati.
            let brier: Double?
            let brierPrima: Double?
            let brierMostrati: Double?
            /// Scarto tra previsto e giocato della formula provata, come quota (0,021 = 2,1 punti).
            let calibrazione: Double?
        }

        /// `in_attesa`, `attiva`, `non_attiva` o `spenta`.
        let stato: String?
        /// Giornate del registro buone per la taratura, e quante ne servono per la prima prova.
        let giornate: Int?
        let minimo: Int?
        /// La versione attiva o dell'ultimo verdetto: un numero sul server, qui come testo.
        let versione: String?
        /// Da quando è attiva («2027-01-15T10:00:00»).
        let dal: String?
        let prova: Prova?
        /// Un codice (`non_migliora`, `poche_giornate`, …) o nil.
        let motivo: String?

        private enum CodingKeys: String, CodingKey {
            case stato, giornate, minimo, versione, dal, prova, motivo
        }

        init(from decoder: any Decoder) throws {
            let c = try? decoder.container(keyedBy: CodingKeys.self)
            func campo<T: Decodable>(_ chiave: CodingKeys) -> T? {
                try? c?.decodeIfPresent(T.self, forKey: chiave)
            }
            stato = campo(.stato)
            giornate = campo(.giornate)
            minimo = campo(.minimo)
            if let numero: Int = campo(.versione) {
                versione = String(numero)
            } else {
                versione = campo(.versione)
            }
            dal = campo(.dal)
            prova = campo(.prova)
            motivo = campo(.motivo)
        }
    }
}
