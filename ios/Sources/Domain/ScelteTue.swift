import Foundation

/// `scelte_tue` dentro `GET /api/diario`: le giornate in cui i tuoi undici erano diversi dai consigliati. La pagina Giornate legge
/// `per_giornata` (nomi dei cambi e differenza di punti, calcolati dal server). Tutti i campi sono opzionali: un server più vecchio
/// non manda il blocco e le righe dicono solo di chi sono i punti.
struct ScelteTue: Decodable {
    let giornate: Int?
    let meglioTua: Int?
    let meglioConsigliata: Int?
    let pari: Int?
    let puntiDifferenza: Double?
    let percentualeTua: Double?
    let pochiDati: Bool?
    let perGiornata: [SceltaGiornata]?
    /// La frase del server sulle giornate senza verdetto (#614): quante non entrano nel confronto perché la consigliata di allora
    /// non era stata salvata, o che finora hai schierato gli stessi titolari della consigliata. Si mostra così com'è; null o
    /// assente (server di prima) = niente da dire.
    let nota: String?
}

struct SceltaGiornata: Decodable, Identifiable {
    let stagione: String?
    /// Il numero di Serie A: identifica la giornata.
    let giornata: Int?
    /// Il numero della giornata nella lega (facoltativo: `null` fuori dalla stagione in corso, assente nei server vecchi).
    let giornataLega: Int?
    let haiScelto: [String]?
    let consigliava: [String]?
    let puntiTua: Double?
    let puntiConsigliata: Double?
    let differenza: Double?
    /// `tua`, `consigliata` o `pari`; un valore nuovo che l'app non conosce si tratta come «pari».
    let esito: String?

    var id: String { "\(stagione ?? "")-\(giornata ?? 0)" }

    /// «Giornata 6 · 9ª di Serie A», come la web e le voci del Diario (#299); senza numero della lega «9ª giornata di Serie A».
    var titolo: String { giornata.map { TempiLega.etichetta(serieA: $0, lega: giornataLega) } ?? "Giornata" }

    private enum Chiavi: String, CodingKey {
        case stagione, giornata, giornataLega, haiScelto, consigliava, puntiTua, puntiConsigliata, differenza, esito
    }

    /// Tollerante come `VoceDiario`: un campo in un formato che l'app non conosce vale «assente» e non fa sparire il Diario.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: Chiavi.self)
        stagione = try? c.decodeIfPresent(String.self, forKey: .stagione)
        giornata = try? c.decodeIfPresent(Int.self, forKey: .giornata)
        giornataLega = try? c.decodeIfPresent(Int.self, forKey: .giornataLega)
        haiScelto = try? c.decodeIfPresent([String].self, forKey: .haiScelto)
        consigliava = try? c.decodeIfPresent([String].self, forKey: .consigliava)
        puntiTua = try? c.decodeIfPresent(Double.self, forKey: .puntiTua)
        puntiConsigliata = try? c.decodeIfPresent(Double.self, forKey: .puntiConsigliata)
        differenza = try? c.decodeIfPresent(Double.self, forKey: .differenza)
        esito = try? c.decodeIfPresent(String.self, forKey: .esito)
    }
}
