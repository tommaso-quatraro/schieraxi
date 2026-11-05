import SwiftUI

/// Uno dei due giocatori in cima a «Chi schierare?»: volto, nome, partita, posto nella formazione del sistema e «Consigliato» se
/// è lui da schierare.
struct ColonnaDuello: View {
    let g: Giocatore
    let scelto: Bool
    /// Il posto nella formazione del sistema, con il codice del server («titolare», «panchina 2», «fuori»:
    /// `Confronto.codicePosto`); nil senza formazione.
    let posto: String?
    /// Gli angoli del fondo sotto la pillola del posto: gli stessi di `PillolaEtichetta`, che crescono con il testo.
    @ScaledMetric(relativeTo: .caption2) private var raggioPillola: CGFloat = 10

    /// Il posto sotto il nome, come la web (`intest` di `apriConfronto`, #311): le parole di `testoPosto`, «Titolare» nella pillola
    /// verde, «Panchina 2» e «Non schierato» in quella grigia. Nil senza posto o con un codice che non si conosce: niente pillola.
    nonisolated static func etichettaPosto(_ codice: String?) -> Etichetta? {
        guard let codice else { return nil }
        let testo = SceltaDallaRosaViewModel.testoPosto(codice)
        return testo.isEmpty ? nil : Etichetta(testo: testo, tono: codice == "titolare" ? .positivo : .neutro)
    }

    /// Quello che legge VoiceOver: nome, ruolo, posto (se c'è), indice, punti attesi e «consigliato».
    var voce: String {
        let parti: [String?] = [g.nome, nomeRuolo(g.ruolo), Self.etichettaPosto(posto)?.testo, "indice \(Formato.intero(g.indice))",
                                "punti attesi \(Formato.punti(g.puntiAttesi))", scelto ? "consigliato" : nil]
        return parti.compactMap { $0 }.joined(separator: ", ")
    }

    var body: some View {
        VStack(spacing: 6) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, indice: g.indice, dimensione: 64, nome: g.nome, ruolo: g.ruolo)
            // intero, anche su più righe con il testo grande: mai «…» (#254, `NomiInteriTests`)
            Text(g.nome).font(.headline).multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            Text(Self.partita(g)).font(.caption).foregroundStyle(Color.testoSecondario)
            if let etichetta = Self.etichettaPosto(posto) {
                // Sotto la pillola il fondo della scheda: sul verde del consigliato la scritta resta leggibile come nelle altre
                // pillole (almeno 4,5:1, `ContrastoPilloleTests`). Senza, «Titolare» verde su verde nel foglio scuro scende a 4,4:1.
                PillolaEtichetta(etichetta: etichetta)
                    .background(Color.sfondoScheda, in: .rect(cornerRadius: raggioPillola, style: .continuous))
            }
            if scelto {
                Label("Consigliato", systemImage: "checkmark.seal.fill").font(.caption.bold()).foregroundStyle(Color.verde)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(10)
        .background(scelto ? Color.verde.opacity(0.14) : Color.clear, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo + 2, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(voce)
    }

    /// La partita sotto il nome, come la web (`partitaRiga`, #302): «INT vs ROM» in casa, «INT @ ROM» in trasferta, prima la squadra
    /// del giocatore; senza avversario solo la sua sigla.
    static func partita(_ g: Giocatore) -> String {
        let mia = ColoriSquadra.sigla(g.squadra), altra = ColoriSquadra.sigla(g.avversario)
        guard !altra.isEmpty else { return mia }
        return "\(mia) \(g.inCasa == true ? "vs" : "@") \(altra)"
    }
}
