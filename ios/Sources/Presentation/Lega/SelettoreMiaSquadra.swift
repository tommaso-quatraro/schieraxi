import SwiftUI

/// Il selettore della propria squadra, come `sceltaMiaSquadra` della web (#863): dentro «Non è la tua squadra?» della rosa della mia
/// squadra e nella pagina «La mia squadra» quando non è ancora scelta (`SceltaSquadraView`). Una scelta si salva subito (`scegli`,
/// cioè `LegaViewModel.scegliMiaSquadra`); se non va, sotto c'è il motivo e il selettore torna alla mia squadra, con il nome che ha
/// adesso: anche quando non va le squadre si rileggono (per esempio dopo il 412 di una squadra rinominata altrove).
struct SelettoreMiaSquadra: View {
    let squadre: [SquadraLega]
    let scegli: @MainActor (String) async -> String?
    @State private var scelta: String
    /// La squadra segnata come mia nelle squadre lette per ultime: segue l'elenco quando si rilegge.
    @State private var mia: String
    @State private var errore: String?
    @State private var inCorso = false

    init(squadre: [SquadraLega], scegli: @escaping @MainActor (String) async -> String?) {
        self.squadre = squadre
        self.scegli = scegli
        _scelta = State(initialValue: Self.segnata(squadre))
        _mia = State(initialValue: Self.segnata(squadre))
    }

    var body: some View {
        Picker(ParoleSquadre.tuaSquadra, selection: $scelta) {
            ForEach(squadre) { Text($0.nome).tag($0.nome) }
        }
        .frame(minHeight: Tema.areaTocco)
        .disabled(inCorso)
        .onChange(of: scelta) { _, nuova in
            guard !nuova.isEmpty, nuova != mia else { return }
            Task { await salva(nuova) }
        }
        .onChange(of: Self.segnata(squadre)) { _, nuova in
            mia = nuova
            if !inCorso { scelta = nuova }
        }
        if let errore {
            Text(errore)
                .font(.footnote).foregroundStyle(Color.attenzione)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// La squadra segnata come mia («» finché non è scelta: il selettore non ne mostra nessuna, come prima).
    private static func segnata(_ squadre: [SquadraLega]) -> String {
        squadre.first { $0.mia == true }?.nome ?? ""
    }

    private func salva(_ nome: String) async {
        inCorso = true
        defer { inCorso = false }
        errore = await scegli(nome)
        // `mia` è stato: dopo la rilettura delle squadre ha già il nome di adesso
        if errore != nil { scelta = mia }
    }
}

#Preview("La tua squadra") {
    let squadre = [SquadraLega(nome: "Nuvola Ovest", mia: true, giocatori: 25, creditiResidui: 12, immagini: nil),
                   SquadraLega(nome: "Borgo Alto", mia: false, giocatori: 25, creditiResidui: 30, immagini: nil)]
    List { SelettoreMiaSquadra(squadre: squadre) { _ in nil } }
}
