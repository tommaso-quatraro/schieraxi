import SwiftUI

/// «Metti in campo» (dalla scheda di chi non è fra gli 11, #778), come `apriMettiInCampo` della web (#643). In cima chi entra: il
/// titolo con il suo nome, intero e a capo se serve (`titoloPagina`), sotto le sue etichette se ne ha («In dubbio», «gioca 62%»,
/// «Diffidato», la nota: le stesse delle righe, `EtichetteRiga`) e la spiegazione del numero. Poi un titolare per riga, nell'ordine
/// del server (dal cambio che rende di più): il numero grande è la `differenza` del server, i punti attesi della formazione
/// dopo il cambio meno quelli di adesso, verde se positiva; sotto il nome le etichette della web, con «Si passa al …» dopo
/// «gioca N%» se il modulo cambia; a destra il fantavoto atteso del titolare. Mentre il server risponde «Carico…»; nessun titolare: la frase
/// della web; `giocatore_bloccato`: la frase del server al posto dell'elenco, come informazione; un altro errore: il motivo.
/// Un tocco su una riga fa il cambio, che si salva da solo (`FormazioneViewModel.scegliChiEsce`).
struct SceltaChiEsce: View {
    let elenco: ElencoMettiInCampo
    let scelto: (Int) -> Void
    @Environment(\.dismiss) private var chiudi

    private var entra: Giocatore { elenco.entra }

    var body: some View {
        NavigationStack {
            List {
                TitoloNellaPagina()
                Section {
                    contenuto
                } header: {
                    testa
                }
            }
            .titoloPagina(Catalogo.Formazione.chiEscePer(nome: entra.nome), piccoloInBarra: true)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } }
            }
        }
    }

    /// Lo stato di chi entra, se ne ha uno, e la spiegazione del numero grande.
    private var testa: some View {
        VStack(alignment: .leading, spacing: 6) {
            let pezzi = EtichetteRiga.pezzi(entra)
            if !pezzi.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(Array(pezzi.enumerated()), id: \.offset) { _, pezzo in
                        Text(pezzo.testo).font(.footnote.weight(.semibold))
                            .foregroundStyle(RigaCambio.colore(pezzo.tono))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            Text(Catalogo.Formazione.esceSpiega(nome: entra.nome))
                .font(.footnote)
                .fixedSize(horizontal: false, vertical: true)
        }
        .textCase(nil)
    }

    @ViewBuilder
    private var contenuto: some View {
        switch elenco.stato {
        case .carico:
            Text(Catalogo.Comune.carico).foregroundStyle(Color.testoSecondario)
        case .uscite(let righe):
            if righe.isEmpty {
                Text(Catalogo.Formazione.nessunoLasciaPosto).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                ForEach(righe) { r in
                    Button { scelto(r.esce.id) } label: { riga(r) }
                        .buttonStyle(.plain)
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

    /// Un titolare che può lasciare il posto: la differenza del server con il segno, «Si passa al …» se il modulo cambia.
    private func riga(_ r: ElencoMettiInCampo.Riga) -> some View {
        let nuovoModulo: String? = r.cambiaModulo ? r.modulo : nil
        let altre: [String] = nuovoModulo.map { [Catalogo.Formazione.passiAl(modulo: $0)] } ?? []
        return RigaCambio(giocatore: r.esce, numero: r.differenza.map { Formato.conSegno($0) }, positivo: (r.differenza ?? 0) > 0,
                          voceNumero: Catalogo.Formazione.puntiCon(nome: entra.nome),
                          suggerimento: "Mette \(entra.nome) al posto di \(r.esce.nome)", altre: altre)
    }
}
