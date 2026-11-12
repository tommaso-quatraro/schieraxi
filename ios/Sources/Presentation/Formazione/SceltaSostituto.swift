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

    private func riga(_ g: Giocatore) -> some View {
        let differenza = Self.differenza(g, rispetto: uscente)
        let contenuto = LetturaPedina.contenuto(g, adesso: Orologio.adesso())
        let piu = (g.puntiAttesi ?? 0) - (uscente.puntiAttesi ?? 0) > 0.04
        return HStack(alignment: .center, spacing: 10) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, dimensione: 40, nome: g.nome, ruolo: g.ruolo)
            VStack(alignment: .leading, spacing: 2) {
                Text(g.nome).font(.headline).fixedSize(horizontal: false, vertical: true)
                Text(RigaGiocatore.sottotitolo(g, adesso: Orologio.adesso())).font(.caption).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
                ForEach(Array(contenuto.pezzi.enumerated()), id: \.offset) { _, pezzo in
                    Text(pezzo.testo).font(.caption.weight(.semibold))
                        .foregroundStyle(pezzo.tono == .basso ? Color.malus : pezzo.tono == .medio ? Color.attenzione : Color.testoSecondario)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 6)
            VStack(alignment: .trailing, spacing: 0) {
                Text(differenza).font(.title3.bold()).monospacedDigit()
                    .foregroundStyle(piu ? Color.verde : Color.primary)
                Text(Catalogo.Formazione.fvAttesoBreve(fv: Formato.punti(g.fvAtteso))).font(.caption2).foregroundStyle(Color.testoSecondario)
            }
        }
        .frame(minHeight: Tema.areaTocco)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(([g.nome, "\(differenza) \(Catalogo.Formazione.puntiRispetto(nome: uscente.nome))",
                              Catalogo.Formazione.fvAttesoBreve(fv: Formato.punti(g.fvAtteso))] + contenuto.pezzi.map(\.testo))
            .joined(separator: ", "))
        .accessibilityHint("Mette \(g.nome) al posto di \(uscente.nome)")
    }
}
