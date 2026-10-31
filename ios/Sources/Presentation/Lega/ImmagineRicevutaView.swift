import SwiftUI

/// Un'immagine arrivata da fuori («Apri con SchieraXI», Condividi, Files).
struct ImmagineRicevuta: Identifiable, Equatable {
    let url: URL
    var id: URL { url }
}

/// «Stemma o divisa? Di quale squadra?»: si sceglie e si carica (ridotta, come dalla libreria foto).
struct ImmagineRicevutaView: View {
    let ricevuta: ImmagineRicevuta
    @StateObject private var squadre: Caricatore<[SquadraLega]>
    @Environment(\.dismiss) private var chiudi
    @State private var tipo = "stemma"
    @State private var squadra = ""
    @State private var immagine: UIImage?
    @State private var errore: String?
    @State private var inCorso = false
    @State private var fatto = false

    init(ricevuta: ImmagineRicevuta, server: any ServerClient) {
        self.ricevuta = ricevuta
        _squadre = StateObject(wrappedValue: Caricatore<[SquadraLega]>("/api/squadre", cache: false, server: server))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    if let immagine {
                        Image(uiImage: immagine).resizable().scaledToFit().frame(maxHeight: 180).frame(maxWidth: .infinity)
                            .accessibilityLabel("Anteprima dell'immagine")
                    } else if let errore {
                        Label(errore, systemImage: "exclamationmark.triangle").foregroundStyle(Color.attenzione)
                    } else {
                        ProgressView().frame(maxWidth: .infinity)
                    }
                }
                Section("Cos'è?") {
                    Picker("Tipo", selection: $tipo) {
                        Text("Stemma").tag("stemma")
                        Text("Divisa").tag("maglia")
                    }
                    .pickerStyle(.segmented)
                }
                Section("Di quale squadra?") {
                    Picker("Squadra", selection: $squadra) {
                        ForEach(squadre.dato ?? []) { Text($0.mia == true ? "\($0.nome) (la tua)" : $0.nome).tag($0.nome) }
                    }
                }
                Section {
                    Button {
                        Task { await salva() }
                    } label: {
                        if inCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                        else { Label(fatto ? "Fatto" : "Salva", systemImage: fatto ? "checkmark.circle.fill" : "square.and.arrow.down").frame(maxWidth: .infinity, minHeight: 44) }
                    }
                    .disabled(immagine == nil || squadra.isEmpty || inCorso || fatto)
                }
            }
            .navigationTitle("Stemma o divisa")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
            .task { await carica() }
        }
    }

    private func carica() async {
        await squadre.ricarica()
        if squadra.isEmpty { squadra = squadre.dato?.first(where: { $0.mia == true })?.nome ?? squadre.dato?.first?.nome ?? "" }
        do {
            let dati = try await LetturaFile.leggi(ricevuta.url, massimo: 20 * 1024 * 1024)
            guard let i = UIImage(data: dati) else { throw ImmagineRicevutaErrore.nonImmagine }
            immagine = i
        } catch {
            errore = (error as? ImmagineRicevutaErrore)?.errorDescription ?? "Non riesco a leggere l'immagine. Salvala su questo iPhone e riprova."
        }
    }

    private func salva() async {
        guard let immagine, let dati = immagine.datiPerServer() else { errore = "Non riesco a preparare l'immagine."; return }
        inCorso = true
        defer { inCorso = false }
        do {
            try await Immagini.condivise.invia(dati, squadra: squadra, tipo: tipo)
            fatto = true
            Haptics.esito(riuscito: true)
            try? await Task.sleep(nanoseconds: 900_000_000)
            chiudi()
        } catch {
            errore = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

enum ImmagineRicevutaErrore: LocalizedError {
    case nonImmagine
    var errorDescription: String? { "Il file non è un'immagine che posso usare (PNG, JPEG, HEIC o WebP)." }
}
