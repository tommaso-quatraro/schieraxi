import SwiftUI
import UniformTypeIdentifiers

/// Importazione delle rose in due passi (piano «Ingresso facile»): il testo incollato o il file (Excel, CSV, testo) passa prima
/// dall'anteprima del server, che non salva niente; l'utente sistema i dubbi e sceglie la sua squadra; poi «Conferma e salva»
/// manda lo stesso contenuto con le scelte. La usano Lega > Aggiorna le rose e il primo avvio (che porta lì).
@MainActor
final class ImportaExcelViewModel: ViewModelBase {
    private let server: any ServerClient

    /// Da dove vengono le rose da controllare: il testo incollato o un file (nome e tipo già pronti per il server).
    enum Sorgente: Equatable {
        case testo(String)
        case file(nome: String, tipo: String, dati: Data)
    }

    @Published var inCorso = false
    /// L'esito dell'ultimo salvataggio (cosa è cambiato).
    @Published var esito: EsitoImportazione?
    @Published var errore: String?
    /// «Togli le squadre che non sono nel file»: di norma le squadre assenti restano com'erano.
    @Published var sostituisciTutto = false
    @Published var testoRose = ""

    /// L'anteprima da controllare (nil = si sta ancora scegliendo cosa importare, o si è già salvato).
    @Published private(set) var anteprima: AnteprimaRose?
    /// Un messaggio sopra l'anteprima (le rose sono cambiate nel frattempo e l'anteprima è stata rifatta).
    @Published private(set) var messaggioAnteprima: String?
    /// Le scelte sui dubbi, per chiave (`AnteprimaLogica.chiave`). Restano quando l'anteprima si rifà dopo un 412.
    @Published private(set) var scelte: [String: SceltaDubbio] = [:]
    /// I giocatori trovati con la ricerca, per chiave: si aggiungono alle opzioni del menu.
    @Published private(set) var trovati: [String: CandidatoAnteprima] = [:]
    /// La squadra dell'utente scelta nell'anteprima («» = nessuna).
    @Published var mia = "" { didSet { if mia != oldValue { miaDecisa = true } } }

    private var miaDecisa = false
    private(set) var sorgente: Sorgente?
    /// «Togli le squadre che non sono nel file» com'era al momento dell'anteprima: il salvataggio usa lo stesso valore.
    private var sostituisciAnteprima = false
    /// L'ETag delle rose dato dall'anteprima: si rimanda in If-Match al salvataggio (se nel frattempo cambiano: 412).
    private(set) var etagAnteprima: String?

    static let roseCambiate = "Nel frattempo le rose sono cambiate, forse da un altro dispositivo: le ho rilette. Ricontrolla e conferma di nuovo."

    init(server: any ServerClient) {
        self.server = server
        super.init()
    }

    /// Excel, CSV, TSV, testo (e qualsiasi altro file: se iOS non riconosce il tipo, si controlla il file dopo la scelta).
    var tipiAmmessi: [UTType] { FileRose.tipiAmmessi }

    private func conScelta(_ base: String, sostituisci: Bool) -> String {
        "\(base)?sostituisci_tutto=\(sostituisci ? "true" : "false")"
    }

    /// L'indirizzo dell'importazione da file, con la scelta «togli le squadre che non sono nel file».
    var percorsoFile: String { conScelta("/api/rose/file", sostituisci: sostituisciTutto) }

    /// Un file scelto (selettore, «Apri con SchieraXI», Condividi): si controlla qui, poi va all'anteprima.
    func importa(_ risultato: Result<[URL], Error>) async {
        guard case .success(let urls) = risultato, let url = urls.first else {
            if case .failure(let e) = risultato { errore = e.localizedDescription }
            return
        }
        if inCorso { return }   // un secondo file mentre il primo è in viaggio: si ignora
        let dati: Data
        do {
            dati = try await LetturaFile.leggi(url)
        } catch let e as FileRose.Errore {
            mostraErrore(e.localizedDescription)
            return
        } catch {
            mostraErrore(ErroreFile.nonLeggibile.localizedDescription)
            return
        }
        // Estensione e contenuto: se il selettore ha lasciato passare un file che non va, si dice cosa non va e non si invia niente.
        switch FileRose.prepara(nome: url.lastPathComponent, dati: dati) {
        case .failure(let e):
            mostraErrore(e.localizedDescription)
        case .success(let preparato):
            await controlla(.file(nome: preparato.nome, tipo: preparato.tipo, dati: dati), nuova: true)
        }
    }

    /// Il file non si è potuto leggere (permessi, iCloud non raggiungibile...).
    enum ErroreFile: LocalizedError {
        case nonLeggibile
        var errorDescription: String? {
            "Non riesco a leggere il file. Salvalo su questo iPhone (Files > Sul mio iPhone) e scegli quella copia."
        }
    }

    /// Il testo incollato (se non si ha il file): va all'anteprima.
    func importaTesto() async {
        let testo = testoRose.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !testo.isEmpty else {
            errore = "Incolla prima il testo delle rose."
            return
        }
        if inCorso { return }
        await controlla(.testo(testo), nuova: true)
    }

    /// Chiede l'anteprima. `nuova`: contenuto nuovo, si azzerano le scelte; altrimenti (rose cambiate nel frattempo) restano.
    private func controlla(_ s: Sorgente, nuova: Bool, messaggio: String? = nil) async {
        inCorso = true
        defer { inCorso = false }
        let sostituisci = nuova ? sostituisciTutto : sostituisciAnteprima
        do {
            let r: AnteprimaRose
            switch s {
            case .testo(let testo):
                r = try await server.posta("POST", "/api/rose/anteprima", RichiestaAnteprimaRose(testo: testo, sostituisci_tutto: sostituisci))
            case .file(let nome, let tipo, let dati):
                r = try await server.caricaFile(conScelta("/api/rose/anteprima/file", sostituisci: sostituisci), nome: nome, dati: dati, tipo: tipo)
            }
            if nuova {
                scelte = [:]
                trovati = [:]
                miaDecisa = false
            }
            sorgente = s
            sostituisciAnteprima = sostituisci
            // L'ETag l'ha appena ricordato il trasporto (`VersioniRisorse`, risorsa «rose»): si tiene questo, non quello di una
            // lettura successiva delle squadre, così un cambio fatto altrove nel frattempo dà 412 invece di passare inosservato.
            etagAnteprima = VersioniRisorse.condivise.leggi(server: server.indirizzo, risorsa: "rose")
            let decisa = miaDecisa ? mia : nil
            anteprima = r
            let scelta = AnteprimaLogica.mia(decisa: decisa, r)
            if scelta != mia { mia = scelta }
            miaDecisa = decisa != nil && decisa == scelta
            messaggioAnteprima = messaggio
            esito = nil
            errore = nil
        } catch {
            if error is CancellationError { return }
            mostraErrore(Self.testo(error))
        }
    }

    /// La scelta per un dubbio (quella dell'utente, altrimenti la proposta del server).
    func scelta(per g: GiocatoreAnteprima, squadra: String) -> SceltaDubbio {
        AnteprimaLogica.scelta(g, squadra: squadra, scelte: scelte)
    }

    func scegli(_ scelta: SceltaDubbio, squadra: String, testo: String) {
        scelte[AnteprimaLogica.chiave(squadra, testo)] = scelta
    }

    /// Un giocatore trovato con la ricerca diventa la scelta (e un'opzione del menu).
    func scegli(trovato c: CandidatoAnteprima, squadra: String, testo: String) {
        let k = AnteprimaLogica.chiave(squadra, testo)
        trovati[k] = c
        scelte[k] = .giocatore(c.id)
    }

    func opzioni(per g: GiocatoreAnteprima, squadra: String) -> [CandidatoAnteprima] {
        AnteprimaLogica.opzioni(g, trovato: trovati[AnteprimaLogica.chiave(squadra, g.testo)])
    }

    /// Le correzioni che partiranno con «Conferma e salva».
    var correzioni: [CorrezioneRosa] {
        guard let anteprima else { return [] }
        return AnteprimaLogica.correzioni(anteprima.squadre, scelte: scelte)
    }

    /// «Conferma e salva»: lo stesso contenuto dell'anteprima, con le scelte, la squadra dell'utente e If-Match.
    func conferma() async {
        guard anteprima != nil, let s = sorgente, !inCorso else { return }
        inCorso = true
        let correzioni = self.correzioni
        let miaSquadra = mia.isEmpty ? nil : mia
        if let etagAnteprima { VersioniRisorse.condivise.imposta(etagAnteprima, server: server.indirizzo, risorsa: "rose") }
        do {
            let e: EsitoImportazione
            switch s {
            case .testo(let testo):
                e = try await server.posta("POST", "/api/rose/testo", RichiestaRoseTesto(
                    testo: testo, sostituisci_tutto: sostituisciAnteprima,
                    correzioni: correzioni.isEmpty ? nil : correzioni, mia_squadra: miaSquadra))
            case .file(let nome, let tipo, let dati):
                var campi: [CampoModulo] = []
                if !correzioni.isEmpty {
                    campi.append(CampoModulo(nome: "correzioni", valore: String(decoding: try JSONEncoder().encode(correzioni), as: UTF8.self)))
                }
                if let miaSquadra { campi.append(CampoModulo(nome: "mia_squadra", valore: miaSquadra)) }
                e = try await server.caricaFile(conScelta("/api/rose/file", sostituisci: sostituisciAnteprima), nome: nome, dati: dati, tipo: tipo, campi: campi)
            }
            inCorso = false
            esito = e
            anteprima = nil
            sorgente = nil
            messaggioAnteprima = nil
            scelte = [:]
            trovati = [:]
            testoRose = ""          // il testo ha i nomi delle persone della lega: non resta sullo schermo
            errore = nil
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            inCorso = false
            if error is CancellationError { return }
            if (error as? ErroreApi)?.eConflitto == true {
                // le rose sono cambiate dopo l'anteprima: si rifà, tenendo le scelte
                await controlla(s, nuova: false, messaggio: Self.roseCambiate)
                return
            }
            mostraErrore(Self.testo(error))
        }
    }

    /// «Annulla»: si torna a scegliere cosa importare (il testo incollato resta).
    func annulla() {
        anteprima = nil
        sorgente = nil
        messaggioAnteprima = nil
        errore = nil
    }

    private func mostraErrore(_ testo: String) {
        errore = testo
        Haptics.esito(riuscito: false)
    }

    /// Il messaggio per l'utente: quello del server così com'è (già in italiano), il resto come lo descrive l'errore
    /// (un 429 dice anche tra quanto riprovare).
    static func testo(_ error: Error) -> String {
        if case .server(let messaggio)? = error as? ErroreApi { return messaggio }
        return error.localizedDescription
    }
}

/// Il corpo dell'importazione da testo: chiavi identiche a quelle del server. `correzioni` e `mia_squadra` si mandano solo se ci sono.
struct RichiestaRoseTesto: Encodable {
    let testo: String
    let sostituisci_tutto: Bool
    var correzioni: [CorrezioneRosa]? = nil
    var mia_squadra: String? = nil
}

/// Il tasto «Aggiorna i dati»: avvia l'aggiornamento sul server e ne segue l'avanzamento finché finisce.
@MainActor
final class AggiornaDatiViewModel: ViewModelBase {
    private let server: any ServerClient
    @Published private(set) var inCorso = false
    @Published private(set) var messaggio: String?
    @Published private(set) var errori: [String] = []
    /// Pausa tra una domanda e l'altra al server (i test la azzerano).
    var pausa: UInt64 = 2_000_000_000
    /// Dopo quante domande si smette di aspettare.
    var tentativiMassimi = 150

    init(server: any ServerClient) {
        self.server = server
        super.init()
    }

    func avvia() async {
        guard !inCorso else { return }
        inCorso = true
        errori = []
        messaggio = "Aggiornamento avviato: ci vuole circa un minuto."
        defer { inCorso = false }
        do {
            let dati = try await server.richiesta("POST", "/api/aggiorna", corpo: nil)
            let avvio: AvvioAggiornamento = try Decodifica.decodifica(dati)
            if avvio.avviato == false {
                messaggio = avvio.messaggio ?? "Aggiornamento già in corso."
                return
            }
        } catch {
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
            return
        }
        var senzaRisposta = 0
        for _ in 0..<tentativiMassimi {
            if pausa > 0 { try? await Task.sleep(nanoseconds: pausa) }
            if Task.isCancelled { return }
            do {
                let stato: StatoAggiornamento = try await server.get("/api/aggiorna")
                senzaRisposta = 0
                if stato.inCorso != true {
                    errori = stato.errori ?? []
                    messaggio = errori.isEmpty ? "Dati aggiornati." : "Aggiornato, ma con problemi: " + errori.joined(separator: "; ")
                    Haptics.esito(riuscito: errori.isEmpty)
                    NotificationCenter.default.post(name: .aggiornaTutto, object: nil)   // tutte le schermate si ricaricano
                    return
                }
            } catch {
                senzaRisposta += 1
                if senzaRisposta >= 5 {
                    messaggio = "Non riesco a sapere come è andato l'aggiornamento: riapri l'app tra poco."
                    return
                }
            }
        }
        messaggio = "L'aggiornamento sta durando più del solito: controlla tra poco."
    }
}

/// Il passaggio di stagione: archivia rose, regole, scelte e osservati della stagione finita e riparte da rose vuote.
@MainActor
final class StagioneViewModel: ViewModelBase {
    private let server: any ServerClient
    let stato: Caricatore<StatoStagione>
    @Published var inCorso = false
    @Published var archiviata = false
    @Published var errore: String?

    init(server: any ServerClient) {
        self.server = server
        stato = Caricatore<StatoStagione>("/api/stagione", cache: false, server: server)
        super.init()
        osserva(stato)
    }

    func carica() async { await stato.ricarica() }

    /// Si può archiviare solo se le rose sono di una stagione finita.
    var puoArchiviare: Bool { stato.dato?.nuova == true && !archiviata && !inCorso }

    /// Da chiamare solo dopo la conferma esplicita dell'utente.
    func archiviaERiparti() async {
        guard puoArchiviare else { return }
        inCorso = true
        defer { inCorso = false }
        do {
            try await server.invia("POST", "/api/nuova-stagione")
            // Rose, regole, scelte e osservati ripartono da capo: gli ETag ricordati sono della stagione archiviata
            // e farebbero rispondere 412 alla prima scrittura.
            VersioniRisorse.condivise.azzera()
            archiviata = true
            errore = nil
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            errore = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

/// Lo storico dei cambiamenti alle rose visti nelle importazioni.
@MainActor
final class MovimentiViewModel: ViewModelBase {
    let caricatore: Caricatore<[Differenze]>

    init(server: any ServerClient) {
        caricatore = Caricatore<[Differenze]>("/api/movimenti?limite=30", server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async { await caricatore.ricarica() }
}

/// «Giocatori da sistemare»: i nomi delle rose che l'importazione non ha riconosciuto. Si cerca quello giusto nel listone e si abbina a mano.
@MainActor
final class DubbiRoseViewModel: ViewModelBase {
    private let server: any ServerClient

    @Published private(set) var dubbi: [GiocatoreDaSistemare] = []
    @Published private(set) var caricato = false
    @Published private(set) var trovati: [GiocatoreBreve] = []
    @Published private(set) var cercando = false
    @Published private(set) var errore: String?
    @Published private(set) var sistemati = 0
    @Published var scelto: GiocatoreDaSistemare?
    /// Pausa prima di interrogare il server mentre si scrive (i test la azzerano).
    var pausa: UInt64 = 300_000_000

    init(server: any ServerClient) {
        self.server = server
        super.init()
    }

    func carica() async {
        do {
            let squadre: [SquadraLega] = try await server.get("/api/squadre")
            var rose: [Rosa] = []
            for s in squadre {
                rose.append(try await server.get("/api/rosa?squadra=\(IndirizzoServer.codifica(s.nome))"))
            }
            dubbi = DubbiRose.trova(in: rose)
            errore = nil
        } catch {
            if error is CancellationError { return }
            errore = error.localizedDescription
        }
        caricato = true
    }

    func cerca(_ testo: String) async {
        let scritto = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard scritto.count >= 2 else { trovati = []; cercando = false; return }
        if pausa > 0 { try? await Task.sleep(nanoseconds: pausa) }
        if Task.isCancelled { return }
        cercando = true
        defer { cercando = false }
        do {
            let r: [GiocatoreBreve] = try await server.get("/api/giocatori?limite=6&q=\(IndirizzoServer.codifica(scritto))")
            if Task.isCancelled { return }
            trovati = r
            errore = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            errore = error.localizedDescription
        }
    }

    /// Abbina il nome della rosa al giocatore scelto nel listone.
    func abbina(_ dubbio: GiocatoreDaSistemare, a giocatore: GiocatoreBreve) async {
        do {
            _ = try await server.corpoJSON("POST", "/api/rose/correggi", RichiestaCorreggiGiocatore(squadra: dubbio.squadra, nome: dubbio.nome, id: giocatore.id))
            dubbi.removeAll { $0 == dubbio }
            sistemati += 1
            scelto = nil
            trovati = []
            errore = nil
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            if (error as? ErroreApi)?.eConflitto == true { _ = try? await server.grezzo("/api/squadre") }
            errore = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
