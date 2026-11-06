import SwiftUI

/// La carta della formazione di Oggi, con le parole della web («La tua formazione», «punti attesi», «Apri la formazione»):
/// modulo, punti attesi con la fascia, il pulsante e le probabili. Dopo una giornata finita parla della PROSSIMA: si chiama così
/// e dice da quando prepararla.
struct CartaFormazioneOggi: View {
    let oggi: Oggi
    @Environment(\.vaiASezione) private var vaiASezione

    var body: some View {
        let finita = oggi.faseGiornata == .finita
        Carta(finita ? "Prossima giornata" : TestiOggi.titoloFormazione(tuaScelta: oggi.formazione?.tuaScelta ?? false),
              simbolo: finita ? "calendar.badge.clock" : "sportscourt") {
            if let p = oggi.prossimaGiornata {
                Label(TestiFase.prossima(p), systemImage: "clock")
                    .font(.subheadline)
                    .fixedSize(horizontal: false, vertical: true)
            }
            let disponibile = oggi.formazione?.disponibile == true
            if let f = oggi.formazione, disponibile {
                cifre(f)
                Button { vaiASezione(.formazione) } label: {
                    Label(TestiOggi.apriFormazione, systemImage: "sportscourt").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .pulsanteVetro(prominente: true)
            } else {
                Text("Formazione non disponibile.").foregroundStyle(Color.testoSecondario)
            }
            // Fuori dal controllo «formazione disponibile», come la web (#416): le probabili possono mancare anche quando i punti
            // attesi non ci sono ancora, ed è proprio allora che serve saperlo.
            if SezioneOggi.avvisoProbabili(fase: oggi.faseGiornata, conProbabili: oggi.conProbabili) {
                Label(TestiOggi.mancanoProbabili, systemImage: "clock")
                    .font(.footnote)
                    .foregroundStyle(Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if disponibile, let p = oggi.probabili?.valore {
                if let avviso = p.avvisoVisibile {
                    Label(avviso, systemImage: "exclamationmark.triangle.fill")
                        .font(.subheadline.weight(.semibold)).foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let riga = p.riga {
                    Text(riga).font(.footnote).foregroundStyle(Color.testoSecondario)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityLabel(riga)
                }
            }
        }
    }

    /// Modulo grande a sinistra, punti attesi e fascia a destra.
    private func cifre(_ f: FormazioneBreve) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(f.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold))
            Spacer()
            VStack(alignment: .trailing, spacing: 0) {
                // Lo stesso numero della Formazione, scritto subito giusto (#416): un numero che sale da 0 restava a metà
                // in una foto o con l'app lenta. Se cambia dopo (dati nuovi) le cifre scorrono, come nella Formazione.
                Text(Formato.punti(f.punteggioAtteso))
                    .font(.title2.bold())
                    .monospacedDigit()
                    .numerico(f.punteggioAtteso ?? 0)
                Text(TestiOggi.puntiAttesi).font(.caption).foregroundStyle(Color.testoSecondario)
                if let fascia = IntervalloPunti.frase(f.intervallo, dev: f.dev) {
                    Text(fascia).font(.caption2).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.trailing)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(TestiOggi.voceCifre(modulo: f.modulo, punti: f.punteggioAtteso))
    }
}
