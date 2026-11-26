import SwiftUI

/// Impostazioni › Scrivici (come `paginaScrivici` della web, 26/11/2026): un commento a chi gestisce il server, solo con un account.
/// La casella va a capo e tiene al massimo `ScriviciViewModel.massimo` caratteri; «Invia» resta spento finché è vuota. Riuscito: la
/// casella si svuota e sotto c'è «Grazie, l'abbiamo ricevuto.»; non riuscito: il messaggio del server, e il testo scritto resta.
struct ScriviciPagina: View {
    @StateObject private var vm: ScriviciViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: ScriviciViewModel(server: server))
    }

    var body: some View {
        List {
            TitoloNellaPagina()
            Section {
                Text(Catalogo.Scrivici.spiega)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Section(titolo: Catalogo.Scrivici.campo) {
                TextEditor(text: $vm.testo)
                    .frame(minHeight: 160)
                    .accessibilityLabel(Catalogo.Scrivici.campo)
                    .disabled(vm.inCorso)
                    .onChange(of: vm.testo) { _, nuovo in vm.cambiato(nuovo) }
                Button { Task { await vm.invia() } } label: {
                    HStack(spacing: 10) {
                        if vm.inCorso { ProgressView() }
                        Text(Catalogo.Scrivici.invia)
                    }
                    .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(!vm.puoInviare)
            }
            if let esito = vm.esito {
                Section {
                    Label(esito, systemImage: "checkmark.circle")
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            if let errore = vm.errore {
                Section {
                    Label(errore, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(Color.attenzione)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Sfondo())
        .titoloPagina(Catalogo.Scrivici.voce)
        .onChange(of: vm.esito) { _, testo in
            if let testo { AccessibilityNotification.Announcement(testo).post() }
        }
        .onChange(of: vm.errore) { _, testo in
            if let testo { AccessibilityNotification.Announcement(testo).post() }
        }
        .schermoProtetto()   // il testo che si sta scrivendo non deve comparire nell'anteprima del selettore delle app
    }
}

/// La logica di Scrivici, senza la vista (la provano `ScriviciComeLaWebTests`).
@MainActor
final class ScriviciViewModel: ObservableObject {
    /// Il tetto del server (`feedback.MAX_CARATTERI`), contato come lui: in caratteri Unicode, non in lettere composte.
    static let massimo = 2000

    let server: any ServerClient
    private let versione: String?
    @Published var testo = ""
    @Published private(set) var inCorso = false
    @Published private(set) var esito: String?
    @Published private(set) var errore: String?

    /// `versione`: quella dell'app che scrive (di base quella che mostra Informazioni).
    init(server: any ServerClient, versione: String? = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String) {
        self.server = server
        self.versione = versione
    }

    var puoInviare: Bool {
        !inCorso && !testo.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// A ogni cambio della casella: oltre il massimo si taglia (come `maxlength` della web); quando chi scrive ricomincia, il grazie
    /// e l'errore di prima spariscono (la casella svuotata dall'invio non li tocca).
    func cambiato(_ nuovo: String) {
        if nuovo.unicodeScalars.count > Self.massimo {
            testo = String(String.UnicodeScalarView(nuovo.unicodeScalars.prefix(Self.massimo)))
        }
        if !nuovo.isEmpty {
            esito = nil
            errore = nil
        }
    }

    func invia() async {
        guard puoInviare else { return }
        inCorso = true
        esito = nil
        errore = nil
        defer { inCorso = false }
        do {
            _ = try await server.corpoJSON("POST", "/api/feedback", CorpoScrivici(testo: testo, versione: versione))
            testo = ""
            esito = Catalogo.Scrivici.grazie
        } catch {
            errore = (error as? LocalizedError)?.errorDescription ?? Catalogo.Scrivici.nonInviato
        }
    }
}

/// Il corpo di `POST /api/feedback`: la piattaforma la decide il server (intestazione `X-Schieraxi-Client`).
struct CorpoScrivici: Encodable {
    let testo: String
    let versione: String?
}
