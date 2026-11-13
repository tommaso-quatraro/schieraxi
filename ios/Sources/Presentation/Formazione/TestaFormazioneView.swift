import SwiftUI

/// La testa della Formazione (`TestaFormazione`), come `testaGiornata` della web: prima della scadenza «Giornata 8 · 11ª di Serie A»
/// e «Si chiude sab 31 14:50 fra 3 h 10 min»; in corso i punti fatti finora; finita com'è andata con «Com'è andata» e sotto la
/// prossima giornata; arrivato a partite cominciate la frase della prossima. Il conto si aggiorna ogni 30 secondi.
struct TestaFormazioneView: View {
    /// Nil per la formazione di un'altra squadra: solo la giornata.
    let oggi: Oggi?
    let formazione: Formazione
    /// «Com'è andata»: apre le giornate su quella appena finita.
    let comeAndata: (Int?) -> Void
    @ScaledMetric(relativeTo: .largeTitle) private var corpoGrande: CGFloat = 40

    var body: some View {
        TimelineView(.periodic(from: Date(), by: 30)) { contesto in
            let t = TestaFormazione.per(oggi: oggi, formazione: formazione, adesso: Orologio.daSistema(contesto.date))
            VStack(alignment: .leading, spacing: 8) {
                if let nota = t.nota {
                    Text(nota).font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityAddTraits(.isStaticText)
                }
                if t.comeAndata != nil {
                    finita(t)
                } else {
                    giornata(t)
                    punti(t)
                }
                if let sotto = t.sotto {
                    Text(sotto).font(.subheadline).foregroundStyle(Color.testoSecondario)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let recuperi = t.recuperi {
                    Label(recuperi, systemImage: "calendar.badge.clock")
                        .font(.subheadline).foregroundStyle(Color.attenzione)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let prossima = t.prossima {
                    Text(prossima).font(.headline).padding(.top, 6)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityAddTraits(.isHeader)
                }
                if let chiude = t.chiude { scadenza(chiude, t.manca) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// «Giornata 8 · 11ª di Serie A», a giornata in corso con accanto «in corso» in grassetto.
    @ViewBuilder
    private func giornata(_ t: TestaFormazione) -> some View {
        if let g = t.giornata {
            Group {
                if t.inCorso {
                    Text("\(g) · \(Text(Catalogo.Formazione.inCorso).bold())")
                } else {
                    Text(g)
                }
            }
            .font(.headline)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityAddTraits(.isHeader)
        }
    }

    /// Il numero grande e le sue parole: «40,0 punti finora · circa 75 a fine giornata». Con il testo grande le parole vanno sotto.
    @ViewBuilder
    private func punti(_ t: TestaFormazione) -> some View {
        if let p = t.punti {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .firstTextBaseline, spacing: 8) { numero(p); parole(t) }
                VStack(alignment: .leading, spacing: 2) { numero(p); parole(t) }
            }
            .accessibilityElement(children: .combine)
        }
    }

    private func numero(_ p: String) -> some View {
        Text(p).font(.system(size: corpoGrande, weight: .bold, design: .rounded)).monospacedDigit()
            .lineLimit(1).minimumScaleFactor(0.6)
    }

    @ViewBuilder
    private func parole(_ t: TestaFormazione) -> some View {
        if let testo = t.testoPunti {
            Text(testo).font(.subheadline).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// Giornata finita: titolo e punti a sinistra, «Com'è andata» a destra (sotto, se non c'è posto).
    private func finita(_ t: TestaFormazione) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) { giornata(t); punti(t) }
                Spacer(minLength: 8)
                pulsanteComeAndata(t)
            }
            VStack(alignment: .leading, spacing: 8) {
                giornata(t)
                punti(t)
                pulsanteComeAndata(t)
            }
        }
    }

    private func pulsanteComeAndata(_ t: TestaFormazione) -> some View {
        Button { comeAndata(t.comeAndata) } label: {
            Text(Catalogo.Formazione.comeAndata).frame(minHeight: Tema.areaTocco)
        }
        .pulsanteVetro()
        .accessibilityHint("Mostra le giornate giocate, con i punti di ogni giocatore")
    }

    /// «Si chiude sab 31 14:50» in grassetto e accanto, piccolo, «fra 3 h 10 min».
    private func scadenza(_ chiude: String, _ manca: String?) -> some View {
        Group {
            if let manca {
                Text("\(Text(chiude).bold()) \(Text(manca).foregroundStyle(Color.testoSecondario))")
            } else {
                Text(chiude).bold()
            }
        }
        .font(.subheadline)
        .fixedSize(horizontal: false, vertical: true)
    }
}
