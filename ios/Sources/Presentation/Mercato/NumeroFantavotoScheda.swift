import SwiftUI

/// Il fantavoto atteso nella scheda del giocatore, il «numero eroe»: grande e neutro, con «gioca N%» a destra.
/// Senza il numero del server si legge «–», come la web (`FantavotoCheSale`, issue #262).
struct NumeroFantavotoScheda: View {
    let p: Giocatore
    /// Grande, ma segue Dynamic Type.
    @ScaledMetric(relativeTo: .largeTitle) private var misuraNumero: CGFloat = 54

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 0) {
                FantavotoCheSale(valore: p.fvAtteso)
                    .font(.system(size: min(misuraNumero, 110), weight: .bold, design: .rounded))
                    .foregroundStyle(.primary)   // neutro, come sulla web: il colore è solo per gli esiti
                Text(FantavotoAtteso.nome + " · se gioca").font(.subheadline.weight(.semibold)).foregroundStyle(Color.testoSecondario)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 0) {
                NumeroCheSale(valore: Double(Formato.percento(p.pVoto)), formato: { "\(Formato.intero($0))%" }).font(.title2.bold())
                Text("gioca").font(.caption).foregroundStyle(Color.testoSecondario)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(FantavotoAtteso.nome) \(Formato.punti(p.fvAtteso)) se gioca. Gioca al \(Formato.percento(p.pVoto)) per cento.")
    }
}
