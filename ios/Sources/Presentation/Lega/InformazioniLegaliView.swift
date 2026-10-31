import SwiftUI

/// Le voci «legali» di Impostazioni > Informazioni: Privacy e Termini (le pagine del server dell'utente), Codice sorgente
/// (solo se il server dà l'indirizzo) e Licenze e crediti. Gli indirizzi non stanno nell'app: si compongono con quello del server.
struct RigheLegali: View {
    let server: any ServerClient
    @AppStorage("indirizzo") private var indirizzo = ""
    @State private var sorgente: URL?

    /// Con la prova con dati di esempio non c'è un server vero: le pagine non hanno un indirizzo e le voci non si mostrano.
    private var base: String { ProvaEsempio.attiva ? "" : IndirizzoServer.attuale }

    var body: some View {
        Group {
            ForEach(PaginaServer.allCases, id: \.self) { pagina in
                if let url = InformazioniLegali.indirizzo(pagina, server: base) {
                    Link(destination: url) {
                        Label(pagina.titolo, systemImage: pagina.icona).labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityHint("Si apre nel browser")
                }
            }
            if let sorgente {
                Link(destination: sorgente) {
                    Label("Codice sorgente", systemImage: "chevron.left.forwardslash.chevron.right").labelStyle(.voce(.orange)).frame(minHeight: Tema.areaTocco)
                }
                .accessibilityHint("Si apre nel browser")
            }
            NavigationLink(value: PaginaImpostazioni.crediti) {
                Label("Licenze e crediti", systemImage: "text.badge.checkmark").labelStyle(.voce(.green)).frame(minHeight: Tema.areaTocco)
            }
        }
        .task(id: indirizzo) { sorgente = await Self.cercaSorgente(server) }
    }

    /// Il campo facoltativo `sorgente` di `/api/stato`: se manca, o non è un indirizzo https, la voce non compare.
    static func cercaSorgente(_ server: any ServerClient) async -> URL? {
        if ProvaEsempio.attiva { return nil }
        let stato: StatoSorgente? = try? await server.get("/api/stato")
        return InformazioniLegali.sorgente(stato?.sorgente)
    }
}

/// Impostazioni mentre la prova con dati di esempio è accesa: dice dov'è l'utente e come uscire.
struct SezioneProvaEsempio: View {
    @State private var chiedi = false

    var body: some View {
        Section("Prova con dati di esempio") {
            Label("Stai guardando una lega inventata. Niente account, niente rete.", systemImage: "play.circle")
                .font(.subheadline).foregroundStyle(.secondary)
            Button("Esci dalla prova e collega il tuo server", role: .destructive) { chiedi = true }
                .frame(minHeight: Tema.areaTocco)
                .confirmationDialog("Uscire dalla prova?", isPresented: $chiedi, titleVisibility: .visible) {
                    Button("Esci dalla prova", role: .destructive) { ProvaEsempio.esci() }
                    Button("Resta", role: .cancel) {}
                } message: {
                    Text("I dati di esempio si cancellano dal telefono e SchieraXI ti chiede l'indirizzo del tuo server.")
                }
        }
    }
}

/// «Licenze e crediti»: a chi appartiene cosa. SchieraXI non usa librerie di terzi.
struct LicenzeECreditiView: View {
    let server: any ServerClient
    @State private var sorgente: URL?

    var body: some View {
        List {
            Section("Licenza di SchieraXI") {
                Text("SchieraXI è software libero, con licenza GNU Affero General Public License 3.0 (AGPL-3.0). Puoi leggerlo, usarlo, modificarlo e condividerlo secondo i patti di quella licenza. Il testo completo è nel codice sorgente.")
                    .font(.subheadline)
                if let sorgente {
                    Link(destination: sorgente) {
                        Label("Codice sorgente", systemImage: "chevron.left.forwardslash.chevron.right").frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityHint("Si apre nel browser")
                }
            }
            Section("Componenti di terzi") {
                Text("Nessuna libreria di terzi: l'app usa solo i componenti che trovi in iOS.")
                    .font(.subheadline)
            }
            Section("Caratteri e simboli") {
                Text("I caratteri sono quelli di sistema di Apple (San Francisco). I simboli sono SF Symbols di Apple. Restano di Apple e si usano secondo la sua licenza: non fanno parte della licenza di SchieraXI.")
                    .font(.subheadline)
            }
            Section("Dati e nomi") {
                Text("SchieraXI non è affiliata né approvata da Lega Serie A, da Fantacalcio.it o dalle società di calcio. I nomi dei calciatori e delle squadre appartengono ai rispettivi titolari e sono usati solo per descrivere i dati. I volti sono disegni creati dall'app, non fotografie.")
                    .font(.subheadline)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Sfondo())
        .navigationTitle("Licenze e crediti")
        .navigationBarTitleDisplayMode(.inline)
        .task { sorgente = await RigheLegali.cercaSorgente(server) }
    }
}

#Preview("Licenze e crediti") {
    NavigationStack { LicenzeECreditiView(server: FinteServer.esempio) }
}
