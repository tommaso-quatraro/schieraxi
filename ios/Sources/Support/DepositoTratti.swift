import Foundation

/// I tratti grossolani di tutti i giocatori (versione 2 degli avatar, `GET /api/avatar`): si scaricano una volta per apertura
/// dell'app e si tengono su disco (Caches), così i volti si disegnano subito. Senza tratti il volto viene tutto dal codice.
@MainActor
final class DepositoTratti: ObservableObject {
    static let condiviso = DepositoTratti()

    /// Cambia quando arrivano tratti nuovi: i volti si ridisegnano.
    @Published private(set) var versione = 0
    private var mappa: [Int: TrattiVolto] = [:]
    private var scaricato = false
    private var inCorso = false
    private let file: URL?

    static let massimoByte = 5 * 1024 * 1024
    static let massimoVoci = 50_000

    init(cartella: URL? = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first) {
        file = cartella?.appendingPathComponent("avatar-tratti.json")
        if let file, let dati = try? Data(contentsOf: file), let letti = Self.leggi(dati) { mappa = letti }
    }

    func tratti(per id: Int) -> TrattiVolto? { mappa[id] }

    var quanti: Int { mappa.count }

    /// Scarica i tratti (una volta per apertura; se non riesce ci riprova alla prossima richiesta).
    func caricaSeServe(server: any ServerClient = ServerCorrente.condiviso) async {
        if Demo.attivo || scaricato || inCorso { return }
        inCorso = true
        defer { inCorso = false }
        guard let dati = try? await server.grezzo("/api/avatar"), let letti = Self.leggi(dati) else { return }
        scaricato = true
        if letti != mappa {
            mappa = letti
            versione += 1
            if let file { try? dati.write(to: file, options: .atomic) }
        }
    }

    // MARK: lettura

    private struct Risposta: Decodable {
        let tratti: [String: Voce]?
    }

    /// Una voce rovinata non deve far perdere le altre.
    private struct Voce: Decodable {
        let valore: TrattiVolto?
        init(from decoder: Decoder) throws { valore = try? TrattiVolto(from: decoder) }
    }

    /// Legge la risposta di `/api/avatar`: `{"versione": 2, "tratti": {"<id>": {...}}}`. `nil` se non è nel formato.
    static func leggi(_ dati: Data) -> [Int: TrattiVolto]? {
        guard !dati.isEmpty, dati.count <= massimoByte, let r = try? JSONDecoder().decode(Risposta.self, from: dati), let voci = r.tratti else { return nil }
        var mappa: [Int: TrattiVolto] = [:]
        for (chiave, voce) in voci.prefix(massimoVoci) {
            guard let id = Int(chiave), (0...4_294_967_295).contains(id), let t = voce.valore else { continue }
            mappa[id] = t
        }
        return mappa
    }
}
