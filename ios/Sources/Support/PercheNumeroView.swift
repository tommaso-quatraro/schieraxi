import SwiftUI

/// I motivi del fantavoto atteso, uno per riga: «+1,1 · Segna più della media del ruolo». Sotto, il riferimento
/// (il giocatore medio del ruolo). Lo stesso blocco sta nella scheda del giocatore e nel foglio della Formazione.
struct BloccoPercheNumero: View {
    let perche: PercheNumero
    @ScaledMetric(relativeTo: .subheadline) private var larghezzaEffetto: CGFloat = 52

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(perche.righe) { r in
                HStack(alignment: .center, spacing: 10) {
                    effetto(r)
                    Text(r.testo)
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(r.voce)
            }
            Text(perche.nota)
                .font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func colore(_ v: PercheNumero.Verso) -> Color {
        switch v {
        case .su: return .verde
        case .giu: return .malus
        case .avviso: return .attenzione
        case .neutro: return .secondary
        }
    }

    @ViewBuilder
    private func effetto(_ r: PercheNumero.Riga) -> some View {
        let tinta = colore(r.verso)
        Group {
            if let e = r.effetto {
                Text(e).font(.subheadline.weight(.bold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
            } else {
                Image(systemName: r.verso == .avviso ? "exclamationmark.triangle.fill" : "circle.fill")
                    .font(r.verso == .avviso ? .subheadline : .caption2)
            }
        }
        .foregroundStyle(tinta)
        .frame(minWidth: larghezzaEffetto, minHeight: 28)
        .background(tinta.opacity(0.14), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .accessibilityHidden(true)
    }
}

/// Il numero del fantavoto atteso con «gioca N%», grande: in testa al foglio «Perché questo numero».
struct NumeroFantavotoGrande: View {
    let g: Giocatore

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 0) {
                NumeroCheSale(valore: g.fvAtteso ?? 0).font(.system(size: 48, weight: .bold, design: .rounded))
                Text(FantavotoAtteso.nome + " · se gioca").font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 0) {
                Text("\(Formato.percento(g.pVoto))%").font(.title2.bold()).monospacedDigit()
                Text("gioca").font(.caption).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(FantavotoAtteso.nome) \(Formato.punti(g.fvAtteso)) se gioca. Gioca al \(Formato.percento(g.pVoto)) per cento.")
    }
}

/// Il foglio che si apre toccando il numero nella Formazione: numero, «gioca N%», i motivi e la definizione.
/// I dati sono già quelli della formazione (nessuna attesa). «Apri la scheda» porta alla scheda intera del giocatore.
struct PercheNumeroSheet: View {
    let g: Giocatore
    /// Chiamata con «Apri la scheda»: chi apre il foglio lo chiude e poi apre la scheda.
    var apriScheda: (() -> Void)?
    @Environment(\.dismiss) private var chiudi

    private var partita: String {
        var t = (g.squadra ?? "").capitalized
        if let a = g.avversario, !a.isEmpty { t += (g.inCasa == true ? " in casa contro " : " in trasferta contro ") + a.capitalized }
        if let d = g.dataPartita { t += " · " + Quando.leggibile(d) }
        return t
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 14) {
                        AvatarGiocatore(id: g.id, squadra: g.squadra, indice: g.indice, dimensione: 64, nome: g.nome, ruolo: g.ruolo)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(g.nome).font(.title2.bold()).accessibilityAddTraits(.isHeader)
                            Text(partita).font(.subheadline).foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 0)
                    }
                    .accessibilityElement(children: .combine)
                    Carta {
                        NumeroFantavotoGrande(g: g)
                        BarraPercentuale(valore: g.pVoto ?? 0)
                    }
                    if let p = PercheNumero(g) {
                        Carta(PercheNumero.titolo, simbolo: "list.bullet.rectangle") { BloccoPercheNumero(perche: p) }
                    }
                    Text(FantavotoAtteso.definizione)
                        .font(.footnote).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    if let apriScheda {
                        Button(action: apriScheda) {
                            Label("Apri la scheda", systemImage: "person.text.rectangle").frame(maxWidth: .infinity, minHeight: 44)
                        }
                        .pulsanteVetro()
                        .keyboardShortcut(.defaultAction)
                    }
                }
                .padding(16)
                .frame(maxWidth: 560)
                .frame(maxWidth: .infinity)
            }
            .background(Sfondo())
            .navigationTitle(PercheNumero.titolo)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() }.keyboardShortcut(.cancelAction) } }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}

#Preview("Perché questo numero") {
    let json = """
    {"id": 7, "nome": "Brunvalli", "ruolo": "A", "squadra": "torino", "avversario": "genoa", "in_casa": true, "p_voto": 0.72, "fv_atteso": 7.6,
     "fv_atteso_medio_ruolo": 6.9,
     "perche_numero": [{"chiave": "gioca", "testo": "gioca il 72%: dubbio", "effetto": null},
                       {"chiave": "gol", "testo": "segna più della media del ruolo (41% di segnare)", "effetto": 0.9},
                       {"chiave": "partita", "testo": "partita difficile in casa", "effetto": -0.3}]}
    """
    if let g: Giocatore = try? Decodifica.decodifica(Data(json.utf8)) {
        PercheNumeroSheet(g: g, apriScheda: {})
    }
}
