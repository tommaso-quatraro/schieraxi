import SwiftUI

/// Le voci «legali» di Impostazioni > Informazioni, con gli stessi nomi e lo stesso ordine della web: Privacy, Termini d'uso e
/// Crediti e fonti (le pagine del server dell'utente), poi Codice sorgente (solo se il server dà l'indirizzo).
/// Gli indirizzi non stanno nell'app: si compongono con quello del server. Quali voci: `InformazioniLegali.vociInformazioni`.
struct RigheLegali: View {
    let server: any ServerClient
    @AppStorage("indirizzo") private var indirizzo = ""
    @State private var sorgente: URL?

    /// Nella prova con dati di esempio e nelle foto della demo (`Demo.attivo`) non c'è un server vero: niente collegamenti a un
    /// indirizzo finto, solo «Crediti e fonti» dentro l'app. Così le foto mostrano quello che vede chi fa la prova.
    private var voci: [VoceInformazioni] {
        InformazioniLegali.vociInformazioni(prova: Demo.attivo, server: IndirizzoServer.attuale)
    }

    var body: some View {
        Group {
            ForEach(voci, id: \.self) { voce in
                switch voce {
                case .browser(_, let url):
                    Link(destination: url) {
                        Label(voce.titolo, systemImage: voce.icona).labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityHint("Si apre nel browser")
                case .creditiNellApp:
                    NavigationLink(value: PaginaImpostazioni.crediti) {
                        Label(voce.titolo, systemImage: voce.icona).labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                    }
                }
            }
            if let sorgente {
                Link(destination: sorgente) {
                    Label("Codice sorgente", systemImage: "chevron.left.forwardslash.chevron.right").labelStyle(.voce(.orange)).frame(minHeight: Tema.areaTocco)
                }
                .accessibilityHint("Si apre nel browser")
            }
        }
        .task(id: indirizzo) { sorgente = await Self.cercaSorgente(server) }
    }

    /// Il campo facoltativo `sorgente` di `/api/stato`: se manca, o non è un indirizzo https, la voce non compare.
    /// Nella prova e nelle foto della demo non si chiede niente: lì la voce non c'è, come per le pagine del server.
    static func cercaSorgente(_ server: any ServerClient) async -> URL? {
        if Demo.attivo { return nil }
        let stato: StatoSorgente? = try? await server.get("/api/stato")
        return InformazioniLegali.sorgente(stato?.sorgente)
    }
}

/// Impostazioni mentre la prova con dati di esempio è accesa: dice dov'è l'utente e come uscire.
struct SezioneProvaEsempio: View {
    @State private var chiedi = false

    var body: some View {
        Section(titolo: "Prova con dati di esempio") {
            Label("Stai guardando una lega inventata. Niente account, niente rete.", systemImage: "play.circle")
                .font(.subheadline).foregroundStyle(Color.testoSecondario)
            Button("Esci dalla prova", role: .destructive) { chiedi = true }
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

/// «Crediti e fonti» dentro l'app, solo per la prova con dati di esempio e le foto della demo (senza server): a chi appartiene
/// cosa. Con un server vero la voce apre la sua pagina «Crediti e fonti», la stessa della web. Nessuna libreria di terzi.
struct CreditiEFontiView: View {
    var body: some View {
        List {
            Section(titolo: "Licenza di SchieraXI") {
                Text("SchieraXI è software libero, con licenza GNU Affero General Public License 3.0 (AGPL-3.0). Puoi leggerlo, usarlo, modificarlo e condividerlo secondo i patti di quella licenza. Il testo completo è nel codice sorgente.")
                    .font(.subheadline)
            }
            Section(titolo: "Componenti di terzi") {
                Text("Nessuna libreria di terzi: l'app usa solo i componenti che trovi in iOS.")
                    .font(.subheadline)
            }
            Section(titolo: "Caratteri e simboli") {
                Text("I caratteri sono quelli di sistema di Apple (San Francisco). I simboli sono SF Symbols di Apple. Restano di Apple e si usano secondo la sua licenza: non fanno parte della licenza di SchieraXI.")
                    .font(.subheadline)
            }
            Section(titolo: "Dati e nomi") {
                Text("SchieraXI non è affiliata né approvata da Lega Serie A, da Fantacalcio.it o dalle società di calcio. I nomi dei calciatori e delle squadre appartengono ai rispettivi titolari e sono usati solo per descrivere i dati. I volti sono disegni creati dall'app, non fotografie.")
                    .font(.subheadline)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Sfondo())
        .navigationTitle("Crediti e fonti")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview("Crediti e fonti") {
    NavigationStack { CreditiEFontiView() }
}
