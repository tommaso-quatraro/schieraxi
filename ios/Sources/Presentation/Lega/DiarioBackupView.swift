import SwiftUI
import UniformTypeIdentifiers

// MARK: - Diario delle giornate

@MainActor
final class DiarioViewModel: ViewModelBase {
    let caricatore: Caricatore<DiarioRisposta>

    init(server: any ServerClient) {
        caricatore = Caricatore<DiarioRisposta>("/api/diario", server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async { await caricatore.ricarica() }
}

/// Per ogni giornata finita: i punti fatti dalla formazione schierata e da quella che il modello avrebbe consigliato.
struct DiarioView: View {
    @StateObject private var vm: DiarioViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: DiarioViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let d = vm.caricatore.dato {
                    Section {
                        Text("Per ogni giornata finita: i punti fatti (\"attesi\" = quelli previsti prima) dalla formazione che hai schierato e da quella che il modello avrebbe consigliato con i dati di allora e la rosa di oggi. La panchina è scelta dal sistema in entrambi i casi.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    if let s = d.sintesi, (s.giornate ?? 0) > 0 { sintesi(s) }
                    if (d.giornate ?? []).isEmpty {
                        VistaVuota(titolo: "Diario ancora vuoto", icona: "book.closed",
                                   descrizione: "Si riempie dopo la prima giornata finita (serve la tua squadra indicata in Lega).")
                            .listRowBackground(Color.clear)
                    }
                    ForEach(d.giornate ?? []) { voce in giornata(voce) }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Diario")
        .ricercaGlobale()
        .refreshable { await vm.carica() }
        .task { await vm.carica() }
    }

    private func sintesi(_ s: SintesiDiario) -> some View {
        Section("In sintesi (\(s.giornate ?? 0) giornate)") {
            RigaValore(titolo: "Punti medi tuoi", valore: Formato.punti(s.puntiSchierata), cifreFisse: true)
            RigaValore(titolo: "Punti medi del modello", valore: Formato.punti(s.puntiConsigliata), cifreFisse: true)
            RigaValore(titolo: "Meglio tu – meglio il modello", valore: "\(s.meglioTua ?? 0)–\(s.meglioConsigliata ?? 0)", cifreFisse: true)
        }
    }

    private func giornata(_ v: VoceDiario) -> some View {
        Section {
            if let s = v.schierata {
                riga("La tua (\(s.modulo ?? "–"))", s)
            } else {
                Text("Non avevi salvato la tua formazione per questa giornata.").font(.footnote).foregroundStyle(.secondary)
            }
            if let c = v.consigliata { riga("Del modello (\(c.modulo ?? "–"))", c) }
            if let frase = v.differenze { Text(frase).font(.footnote).foregroundStyle(.secondary) }
        } header: {
            Text("Giornata \(v.giornata ?? 0)" + (v.stagione.map { " · \($0)" } ?? ""))
        }
    }

    private func riga(_ titolo: String, _ f: FormazioneDiario) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(titolo)
            Spacer()
            VStack(alignment: .trailing, spacing: 0) {
                Text(Formato.punti(f.reale)).font(.headline).monospacedDigit()
                Text("attesi \(Formato.punti(f.atteso))").font(.caption).foregroundStyle(.secondary).monospacedDigit()
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(titolo): \(Formato.punti(f.reale)) punti, attesi \(Formato.punti(f.atteso))")
    }
}

// MARK: - Backup

@MainActor
final class BackupViewModel: ViewModelBase {
    private let server: any ServerClient
    /// Il file pronto da condividere (cartella temporanea).
    @Published var file: URL?
    @Published var inCorso = false
    @Published var messaggio: String?
    @Published var riuscito = false
    /// Un backup letto dal telefono e controllato, in attesa della conferma.
    @Published var daRipristinare: Data?
    @Published var chiediConferma = false

    init(server: any ServerClient) {
        self.server = server
        super.init()
    }

    /// Scarica il backup dal server e lo scrive in un file temporaneo da condividere.
    func prepara() async {
        guard !inCorso else { return }
        inCorso = true
        defer { inCorso = false }
        do {
            let dati = try await server.grezzo("/api/backup")
            if case .failure(let e) = FileBackup.controlla(dati) { throw e }
            pulisci()
            let cartella = FileManager.default.temporaryDirectory.appendingPathComponent("backup-schieraxi", isDirectory: true)
            try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
            let url = cartella.appendingPathComponent(FileBackup.nomeFile(dati))
            try dati.write(to: url, options: [.atomic, .completeFileProtection])
            file = url
            esito("Backup pronto: toccalo per condividerlo o salvarlo in Files.", riuscito: true)
        } catch {
            esito(error.localizedDescription, riuscito: false)
        }
    }

    /// Il file scelto per il ripristino: si controlla qui e poi si chiede conferma.
    func scegli(_ risultato: Result<[URL], Error>) async {
        guard case .success(let urls) = risultato, let url = urls.first else {
            if case .failure(let e) = risultato { esito(e.localizedDescription, riuscito: false) }
            return
        }
        do {
            let dati = try await LetturaFile.leggi(url, massimo: FileBackup.massimoByte)
            if case .failure(let e) = FileBackup.controlla(dati) { throw e }
            daRipristinare = dati
            chiediConferma = true
        } catch let e as FileBackup.Errore {
            esito(e.localizedDescription, riuscito: false)
        } catch let e as FileRose.Errore {
            esito(e == .troppoGrande ? FileBackup.Errore.troppoGrande.localizedDescription : e.localizedDescription, riuscito: false)
        } catch {
            esito("Non riesco a leggere il file. Salvalo su questo iPhone (Files > Sul mio iPhone) e scegli quella copia.", riuscito: false)
        }
    }

    func ripristina() async {
        guard let dati = daRipristinare, !inCorso else { return }
        inCorso = true
        defer { inCorso = false }
        do {
            let risposta = try await server.richiesta("POST", "/api/backup/ripristina", corpo: dati)
            let r: RisultatoRipristino? = try? Decodifica.decodifica(risposta)
            daRipristinare = nil
            // Dopo il ripristino regole, rose, scelte e osservati sono altri: via le copie su disco e gli ETag, si rilegge tutto.
            Cache.svuotaTutto()
            VersioniRisorse.condivise.azzera()
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
            esito("Ripristinati \(r?.ripristinati?.count ?? 0) file. I dati di prima restano sul server in dati/backup-prima-del-ripristino.json.", riuscito: true)
        } catch {
            daRipristinare = nil
            esito(error.localizedDescription, riuscito: false)
        }
    }

    func annullaRipristino() { daRipristinare = nil }

    /// Il file temporaneo contiene dati personali: non resta sul telefono.
    func pulisci() {
        if let file { try? FileManager.default.removeItem(at: file) }
        file = nil
    }

    private func esito(_ testo: String, riuscito: Bool) {
        messaggio = testo
        self.riuscito = riuscito
        Haptics.esito(riuscito: riuscito)
    }
}

struct BackupView: View {
    @StateObject private var vm: BackupViewModel
    @State private var scegli = false

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: BackupViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section {
                    Text("Un file con regole, rose, scelte, osservati e impostazioni degli avvisi: serve se cambi server o vuoi una copia al sicuro. Non contiene chiavi né le notifiche già attivate. Ripristinando, i dati di prima restano nel file dati/backup-prima-del-ripristino.json sul server.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("Salva una copia") {
                    Button {
                        Task { await vm.prepara() }
                    } label: {
                        if vm.inCorso { ProgressView() } else { Label("Scarica il backup", systemImage: "arrow.down.doc") }
                    }
                    .disabled(vm.inCorso)
                    .frame(minHeight: 44)
                    if let url = vm.file {
                        ShareLink(item: url, subject: Text("Backup di SchieraXI")) {
                            Label("Condividi \(url.lastPathComponent)", systemImage: "square.and.arrow.up")
                        }
                        .frame(minHeight: 44)
                    }
                }
                Section("Rimetti una copia") {
                    Button {
                        scegli = true
                    } label: {
                        Label("Ripristina da file", systemImage: "arrow.up.doc")
                    }
                    .disabled(vm.inCorso)
                    .frame(minHeight: 44)
                }
                if let m = vm.messaggio {
                    Section {
                        Label(m, systemImage: vm.riuscito ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                            .foregroundStyle(vm.riuscito ? Color.verde : Color.attenzione)
                            .font(.footnote)
                    }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Backup")
        .ricercaGlobale()
        .fileImporter(isPresented: $scegli, allowedContentTypes: [.json, .plainText], allowsMultipleSelection: false) { risultato in
            Task { await vm.scegli(risultato) }
        }
        .confirmationDialog("Ripristino il backup?", isPresented: $vm.chiediConferma, titleVisibility: .visible) {
            Button("Ripristina", role: .destructive) { Task { await vm.ripristina() } }
            Button("Annulla", role: .cancel) { vm.annullaRipristino() }
        } message: {
            Text("Regole, rose, scelte, osservati e impostazioni degli avvisi presenti nel file sostituiscono quelli di adesso.")
        }
        .onDisappear { vm.pulisci() }
    }
}
