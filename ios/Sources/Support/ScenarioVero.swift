import Foundation

/// «Fotografie dal vero»: le risposte di un server vero, con i nomi inventati, in un momento preciso della giornata
/// (prima della scadenza, giornata a metà, giornata finita). Mostrano i casi che i dati demo scritti a mano non hanno:
/// partite rinviate, nomi lunghi, voti a metà, giocatori senza percentuale, rose da 25, una formazione salvata.
///
/// I file `fotografie/<scenario>.json` li prepara `prove/fotografie_dal_vero.py` (repository del server); il workflow degli
/// screenshot li copia nella cartella Documenti dell'app nel simulatore e avvia l'app con `-DEMO -DEMO_SCENARIO <scenario>`.
/// Vale SOLO con `-DEMO` (mai nell'uso normale né nella «Prova con dati di esempio»); i file non entrano nell'IPA.
struct ScenarioVero {
    let nome: String
    /// Il momento della fotografia: l'orologio dell'app parte da qui (`Orologio`).
    let adesso: Date
    let file: FileScenario

    /// Il file di uno scenario. Tutto facoltativo: un file vecchio o diverso non fa cadere l'app (si torna alla demo di sempre).
    struct FileScenario: Decodable {
        let scenario: String?
        let adesso: String?
        let giornata: Int?
        let demo: Scelte?
        let risposte: [String: String]?
    }

    /// Cosa aprire nelle schermate che in demo scelgono un giocatore, una squadra o un testo.
    struct Scelte: Decodable {
        let giocatore: Int?
        let confronto: [Int]?
        let foto: [Int]?
        let cerca: String?
        let miaSquadra: String?
        let rosaAltra: String?
        let stemmi: [String]?
        let offerta: String?

        enum CodingKeys: String, CodingKey {
            case giocatore, confronto, foto, cerca, stemmi, offerta
            case miaSquadra = "mia_squadra"
            case rosaAltra = "rosa_altra"
        }
    }

    /// Lo scenario chiesto all'avvio (nil se non c'è o se il file manca: in quel caso resta la demo di sempre).
    static let attuale: ScenarioVero? = carica()

    var risposte: [String: String] { file.risposte ?? [:] }
    var giocatore: Int? { file.demo?.giocatore }
    var rosaAltra: String? { file.demo?.rosaAltra }
    var offerta: String? { file.demo?.offerta }
    var confronto: (Int, Int)? {
        guard let c = file.demo?.confronto, c.count == 2 else { return nil }
        return (c[0], c[1])
    }

    /// Solo lettere minuscole, cifre e trattini: il nome diventa parte di un percorso.
    static func nomeValido(_ nome: String) -> Bool {
        !nome.isEmpty && nome.count <= 40 && nome.unicodeScalars.allSatisfy { CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyz0123456789-").contains($0) }
    }

    private static func carica() -> ScenarioVero? {
        guard Demo.daLancio, let nome = Demo.argomento("DEMO_SCENARIO"), nomeValido(nome),
              let documenti = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else { return nil }
        let url = documenti.appendingPathComponent("fotografie", isDirectory: true).appendingPathComponent(nome + ".json")
        guard let dati = try? Data(contentsOf: url) else { return nil }
        return leggi(dati, nome: nome)
    }

    /// Legge il file di uno scenario; nil se non è valido (senza momento o senza risposte).
    static func leggi(_ dati: Data, nome: String) -> ScenarioVero? {
        guard let file = try? JSONDecoder().decode(FileScenario.self, from: dati),
              let adesso = Quando.data(file.adesso), !(file.risposte ?? [:]).isEmpty else { return nil }
        return ScenarioVero(nome: nome, adesso: adesso, file: file)
    }

    /// Le rotte che la fotografia non ha e che non dipendono dalla lega: valgono quelle della demo di sempre.
    static let dallaDemo = ["/api/account/", "/api/rose/", "/api/regole/riconosci", "/api/aggiorna", "/api/novita"]

    /// Il server finto con le risposte della fotografia. Foto dei giocatori e stemmi sono disegnati (mai immagini vere).
    var server: FinteServer {
        var tutte = FinteServer.demo.risposte.filter { chiave, _ in Self.dallaDemo.contains { chiave.hasPrefix($0) } }
        for (chiave, testo) in risposte { tutte[chiave] = testo }
        let foto = Set(file.demo?.foto ?? [])
        let stemmi = Set(file.demo?.stemmi ?? [])
        tutte["/api/foto-disponibili"] = "{\"ids\": [" + foto.sorted().map(String.init).joined(separator: ",") + "]}"
        var s = FinteServer(risposte: tutte, binari: { percorso in ScenarioVero.immagine(percorso, foto: foto, stemmi: stemmi) })
        s.indirizzoFinto = "https://finto-\(nome).invalid"      // la copia salvata di ogni scenario resta separata
        return s
    }

    /// Una foto o uno stemma disegnati al volo (come nella demo), solo per i giocatori e le squadre che ce l'hanno.
    static func immagine(_ percorso: String, foto: Set<Int>, stemmi: Set<String>) -> Data? {
        if percorso.hasPrefix("/api/foto/"), let id = Int(percorso.dropFirst("/api/foto/".count)), foto.contains(id) {
            return DemoImmagini.foto(id)
        }
        if percorso.hasPrefix("/api/squadre/immagine"), let c = URLComponents(string: "https://demo.invalid" + percorso) {
            let valori = Dictionary((c.queryItems ?? []).compactMap { v in v.value.map { (v.name, $0) } }, uniquingKeysWith: { a, _ in a })
            guard let nome = valori["squadra"], stemmi.contains(nome) else { return nil }
            return valori["tipo"] == "maglia" ? DemoImmagini.maglia(nome) : DemoImmagini.stemma(nome)
        }
        return nil
    }
}
