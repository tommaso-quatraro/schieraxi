import SwiftUI

/// Scegli a mano gli undici che hai schierato in una giornata già finita (per il Diario). Si parte da quelli già salvati o, in mancanza,
/// da quelli della consigliata; il server controlla che siano undici della tua rosa con un modulo valido.
/// Se il server rifiuta, l'errore si vede qui dentro, sopra il conto «N di 11»: la lista del Diario sotto il foglio non si vede.
struct FormazioneManualeDiarioView: View {
    let voce: VoceDiario
    /// Salva i titolari scelti: nil se è andata bene (il foglio si chiude), altrimenti l'errore da mostrare.
    let salva: ([Int]) async -> String?
    @StateObject private var rosa: Caricatore<Rosa>
    @Environment(\.dismiss) private var chiudi
    @State private var scelti: Set<Int> = []
    @State private var inCorso = false
    @State private var partito = false
    @State private var errore: String?

    init(voce: VoceDiario, server: any ServerClient, salva: @escaping ([Int]) async -> String?) {
        self.voce = voce
        self.salva = salva
        _rosa = StateObject(wrappedValue: Caricatore<Rosa>("/api/rosa", cache: false, ascolta: false, server: server))
    }

    private let reparti = [("P", "Portieri"), ("D", "Difensori"), ("C", "Centrocampisti"), ("A", "Attaccanti")]

    /// Chi era titolare: la formazione schierata se c'è, altrimenti la consigliata.
    private var iniziali: Set<Int> {
        let titolari = (voce.schierata ?? voce.consigliata)?.titolari ?? []
        return Set(titolari.compactMap(\.id))
    }

    var body: some View {
        NavigationStack {
            List {
                if let r = rosa.dato {
                    Section {
                        Text("\(voce.titolo): tocca i giocatori che hai schierato. Servono 11 titolari.")
                            .font(.footnote).foregroundStyle(Color.testoSecondario)
                    }
                    ForEach(reparti, id: \.0) { reparto in
                        let giocatori = r.giocatori.filter { $0.ruolo == reparto.0 && $0.id != nil }
                        if !giocatori.isEmpty {
                            Section(titolo: reparto.1) {
                                ForEach(giocatori, id: \.ident) { g in riga(g) }
                            }
                        }
                    }
                } else if let e = rosa.errore {
                    ErroreVista(messaggio: e) { Task { await rosa.ricarica() } }
                } else {
                    ScheletroRighe(righe: 6).listRowBackground(Color.clear)
                }
            }
            .navigationTitle("Cosa hai schierato")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task {
                            inCorso = true
                            errore = nil
                            errore = await salva(scelti.sorted())
                            inCorso = false
                            if errore == nil { chiudi() }
                        }
                    } label: { if inCorso { ProgressView() } else { Text("Salva") } }
                    .disabled(scelti.count != 11 || inCorso)
                }
            }
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 6) {
                    if let errore {
                        Label(errore, systemImage: "exclamationmark.triangle.fill")
                            .font(.footnote.weight(.semibold)).foregroundStyle(Color.attenzione)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    Text("\(scelti.count) di 11")
                        .font(.subheadline.weight(.semibold)).monospacedDigit()
                        .foregroundStyle(scelti.count == 11 ? Color.verde : (scelti.count > 11 ? Color.attenzione : Color.testoSecondario))
                        .frame(maxWidth: .infinity)
                }
                .padding(.vertical, 8).padding(.horizontal, Tema.margine)
                .background(.bar)
            }
            // cambiando i giocatori l'errore di prima non vale più
            .onChange(of: scelti) { errore = nil }
            .task {
                await rosa.ricarica()
                if !partito { scelti = iniziali; partito = true }
            }
        }
    }

    private func riga(_ g: GiocatoreRosa) -> some View {
        let id = g.id ?? -1
        let scelto = scelti.contains(id)
        return Button {
            if scelto { scelti.remove(id) } else { scelti.insert(id) }
        } label: {
            HStack(spacing: 10) {
                Image(systemName: scelto ? "checkmark.circle.fill" : "circle").foregroundStyle(scelto ? Color.verde : Color.testoSecondario)
                AvatarGiocatore(id: g.id, squadra: g.squadraSlug ?? g.squadra, dimensione: 34, conNumero: false, nome: g.nome, ruolo: g.ruolo)
                Text(g.nome)
                Spacer()
            }
            .frame(minHeight: 44)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(scelto ? .isSelected : [])
    }
}
