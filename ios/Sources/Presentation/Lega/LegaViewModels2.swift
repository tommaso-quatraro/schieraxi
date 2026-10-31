import SwiftUI
import UniformTypeIdentifiers

/// Importazione delle rose da un Excel di Leghe, da un CSV o da un file di testo, o dal testo copiato dalla pagina delle rose.
@MainActor
final class ImportaExcelViewModel: ViewModelBase {
    private let server: any ServerClient

    @Published var inCorso = false
    @Published var esito: EsitoImportazione?
    @Published var errore: String?
    /// «Togli le squadre che non sono nel file»: di norma le squadre assenti restano com'erano.
    @Published var sostituisciTutto = false
    @Published var testoRose = ""

    init(server: any ServerClient) {
        self.server = server
        super.init()
    }

    /// Excel, CSV, TSV, testo (e qualsiasi altro file: se iOS non riconosce il tipo, si controlla il file dopo la scelta).
    var tipiAmmessi: [UTType] { FileRose.tipiAmmessi }

    /// L'indirizzo dell'importazione da file, con la scelta «togli le squadre che non sono nel file».
    var percorsoFile: String { "/api/rose/file?sostituisci_tutto=\(sostituisciTutto ? "true" : "false")" }

    func importa(_ risultato: Result<[URL], Error>) async {
        guard case .success(let urls) = risultato, let url = urls.first else {
            if case .failure(let e) = risultato { errore = e.localizedDescription }
            return
        }
        if inCorso { return }   // un secondo file mentre il primo è in viaggio: si ignora
        inCorso = true
        defer { inCorso = false }
        do {
            let dati: Data
            do {
                dati = try await LetturaFile.leggi(url)
            } catch let e as FileRose.Errore {
                throw e
            } catch {
                throw ErroreFile.nonLeggibile
            }
            // Estensione e contenuto: se il selettore ha lasciato passare un file che non va, si dice cosa non va e non si invia niente.
            switch FileRose.prepara(nome: url.lastPathComponent, dati: dati) {
            case .failure(let e):
                esito = nil
                errore = e.localizedDescription
                Haptics.esito(riuscito: false)
                return
            case .success(let preparato):
                esito = try await server.caricaFile(percorsoFile, nome: preparato.nome, dati: dati, tipo: preparato.tipo)
            }
            errore = nil
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            esito = nil
            errore = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }

    /// Il file non si è potuto leggere (permessi, iCloud non raggiungibile...).
    enum ErroreFile: LocalizedError {
        case nonLeggibile
        var errorDescription: String? {
            "Non riesco a leggere il file. Salvalo su questo iPhone (Files > Sul mio iPhone) e scegli quella copia."
        }
    }

    /// Importa il testo incollato (se non si ha il file Excel).
    func importaTesto() async {
        let testo = testoRose.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !testo.isEmpty else {
            errore = "Incolla prima il testo delle rose."
            return
        }
        inCorso = true
        defer { inCorso = false }
        do {
            esito = try await server.posta("POST", "/api/rose/testo", RichiestaRoseTesto(testo: testo, sostituisci_tutto: sostituisciTutto))
            errore = nil
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        } catch {
            esito = nil
            if (error as? ErroreApi)?.eConflitto == true { _ = try? await server.grezzo("/api/squadre") }   // rilegge la versione nuova (e il suo ETag)
            errore = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

/// Il corpo dell'importazione da testo: chiavi identiche a quelle del server.
struct RichiestaRoseTesto: Encodable {
    let testo: String
    let sostituisci_tutto: Bool
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
