import SwiftUI

/// «Sostituisci» (dalla scheda di un titolare), come `apriSostituzione` della web (#616): i compagni dello stesso ruolo che non sono
/// titolari, il migliore in cima, ognuno con i punti attesi in più o in meno rispetto a lui (è già il confronto, in una riga) e il
/// suo fantavoto atteso. Un tocco fa il cambio, che si salva da solo (`FormazioneViewModel.sostituisciTitolare`).
struct SceltaSostituto: View {
    let uscente: Giocatore
    let candidati: [Giocatore]
    let scelto: (Int) -> Void
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(candidati) { g in
                        Button { scelto(g.id) } label: { riga(g) }
                            .buttonStyle(.plain)
                    }
                    if candidati.isEmpty {
                        Text(Catalogo.Formazione.nessunAltroGiocatore).foregroundStyle(Color.testoSecondario)
                    }
                } header: {
                    Text(Catalogo.Formazione.sostSpiega(nome: uscente.nome))
                        .font(.footnote).textCase(nil)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .navigationTitle(Catalogo.Formazione.alPostoDi(nome: uscente.nome))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } }
            }
        }
    }

    /// I punti attesi in più o in meno rispetto a chi esce: «+0,9», «−0,4», «0,0».
    static func differenza(_ g: Giocatore, rispetto a: Giocatore) -> String {
        Formato.conSegno((g.puntiAttesi ?? 0) - (a.puntiAttesi ?? 0))
    }

    /// Un sostituto: i punti attesi in più o in meno rispetto a chi esce, verdi da +0,05, e il suo fantavoto atteso (`RigaCambio`).
    private func riga(_ g: Giocatore) -> some View {
        RigaCambio(giocatore: g, numero: Self.differenza(g, rispetto: uscente),
                   positivo: (g.puntiAttesi ?? 0) - (uscente.puntiAttesi ?? 0) > 0.04,
                   voceNumero: Catalogo.Formazione.puntiRispetto(nome: uscente.nome),
                   suggerimento: "Mette \(g.nome) al posto di \(uscente.nome)")
    }
}
