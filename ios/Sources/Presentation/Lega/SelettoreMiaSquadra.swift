import SwiftUI

/// Il selettore della propria squadra, come `sceltaMiaSquadra` della web (#863): dentro «Non è la tua squadra?» della rosa della mia
/// squadra e nella pagina «La mia squadra» quando non è ancora scelta (`SceltaSquadraView`). Una scelta si salva subito (`scegli`,
/// cioè `LegaViewModel.scegliMiaSquadra`); se non va, sotto c'è il motivo e il selettore torna alla squadra di prima.
struct SelettoreMiaSquadra: View {
    let squadre: [SquadraLega]
    let scegli: @MainActor (String) async -> String?
    @State private var scelta: String
    @State private var errore: String?
    @State private var inCorso = false

    init(squadre: [SquadraLega], scegli: @escaping @MainActor (String) async -> String?) {
        self.squadre = squadre
        self.scegli = scegli
        _scelta = State(initialValue: Self.mia(squadre))
    }

    var body: some View {
        Picker(ParoleSquadre.tuaSquadra, selection: $scelta) {
            ForEach(squadre) { Text($0.nome).tag($0.nome) }
        }
        .frame(minHeight: Tema.areaTocco)
        .disabled(inCorso)
        .onChange(of: scelta) { _, nuova in
            guard !nuova.isEmpty, nuova != Self.mia(squadre) else { return }
            Task { await salva(nuova) }
        }
        if let errore {
            Text(errore)
                .font(.footnote).foregroundStyle(Color.attenzione)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// La squadra segnata come mia («» finché non è scelta: il selettore non ne mostra nessuna, come prima).
    private static func mia(_ squadre: [SquadraLega]) -> String {
        squadre.first { $0.mia == true }?.nome ?? ""
    }

    private func salva(_ nome: String) async {
        inCorso = true
        defer { inCorso = false }
        errore = await scegli(nome)
        if errore != nil { scelta = Self.mia(squadre) }
    }
}

#Preview("La tua squadra") {
    let squadre = [SquadraLega(nome: "Nuvola Ovest", mia: true, giocatori: 25, creditiResidui: 12, immagini: nil),
                   SquadraLega(nome: "Borgo Alto", mia: false, giocatori: 25, creditiResidui: 30, immagini: nil)]
    List { SelettoreMiaSquadra(squadre: squadre) { _ in nil } }
}
