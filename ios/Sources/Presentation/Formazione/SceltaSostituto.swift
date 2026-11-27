import SwiftUI

/// «Sostituisci» (dalla scheda di un titolare), come `apriSostituzione` della web: i compagni dello stesso ruolo che non sono
/// titolari, nell'ordine del server (dal cambio che rende di più). Il numero grande è la `differenza` del server: i punti attesi
/// della formazione dopo il cambio meno quelli di adesso, verde se positiva (prima era la differenza fra i due giocatori, che non
/// tornava con la formazione dopo il cambio); sotto il nome la partita con il posto in formazione («Panchina 2», «Non schierato»,
/// come la web) e le etichette della web; a destra il fantavoto atteso. Mentre il server risponde «Carico…»; nessun compagno: la
/// frase della web; `giocatore_bloccato`: la frase del server al posto dell'elenco, come informazione; un altro errore: il motivo.
/// Un tocco su una riga fa il cambio, che si salva da solo (`FormazioneViewModel.scegliSostituto`); finché il cambio non si può
/// fare (si rilegge, la formazione si è chiusa) le righe sono spente e sopra di loro c'è il perché (`motivoSpento`).
struct SceltaSostituto: View {
    let elenco: ElencoSostituti
    /// Perché adesso il cambio non si può fare (`FormazioneViewModel.motivoCambiSpenti`); nil = le righe si toccano.
    var motivoSpento: String? = nil
    let scelto: (Int) -> Void
    @Environment(\.dismiss) private var chiudi

    private var uscente: Giocatore { elenco.uscente }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    contenuto
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

    @ViewBuilder
    private var contenuto: some View {
        switch elenco.stato {
        case .carico:
            Text(Catalogo.Comune.carico).foregroundStyle(Color.testoSecondario)
        case .entrate(let righe):
            if righe.isEmpty {
                Text(Catalogo.Formazione.nessunAltroGiocatore).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                if let motivoSpento { MotivoCambiSpenti(motivo: motivoSpento) }
                ForEach(righe) { r in
                    Button { scelto(r.entra.id) } label: { riga(r) }
                        .buttonStyle(.plain)
                        .disabled(motivoSpento != nil)
                        .opacity(motivoSpento == nil ? 1 : 0.5)
                }
            }
        case .informazione(let frase):
            // non è un guasto (la sua partita è cominciata): una frase, che VoiceOver legge quando compare
            Text(frase).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
                .onAppear { AccessibilityNotification.Announcement(frase).post() }
        case .errore(let motivo):
            Label(motivo, systemImage: "exclamationmark.triangle")
                .fixedSize(horizontal: false, vertical: true)
                .onAppear { AccessibilityNotification.Announcement(motivo).post() }
        }
    }

    /// Un compagno che può entrare: la differenza del server con il segno («+0,9», «−0,4», «0,0»), verde se positiva, e dove sta
    /// adesso nella formazione.
    private func riga(_ r: ElencoSostituti.Riga) -> some View {
        RigaCambio(giocatore: r.entra, numero: r.differenza.map { Formato.conSegno($0) }, positivo: (r.differenza ?? 0) > 0,
                   voceNumero: Catalogo.Formazione.puntiRispetto(nome: uscente.nome),
                   suggerimento: "Mette \(r.entra.nome) al posto di \(uscente.nome)", posto: r.posto)
    }
}
