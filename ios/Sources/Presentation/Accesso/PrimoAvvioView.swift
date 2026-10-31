import SwiftUI

/// Il primo avvio (o dopo una reinstallazione): l'app non conosce ancora il server. L'indirizzo non sta dentro l'app
/// (il repository e l'IPA sono pubblici): si scrive qui, si prova e si salva sul telefono. Poi l'app va avanti da sola.
struct PrimoAvvioView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                VStack(spacing: 10) {
                    Marchio(lato: 96)
                    Text("SchieraXI")
                        .font(.system(.largeTitle, design: .rounded, weight: .semibold))
                        .accessibilityHidden(true)
                    Text("Scrivi l'indirizzo del tuo server per cominciare.")
                        .font(.subheadline).foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 12)
                Carta {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Indirizzo del server", systemImage: "server.rack").font(.headline)
                        Text("È l'indirizzo con cui apri SchieraXI dal browser, per esempio \(Config.esempioIndirizzo). Deve cominciare con https://. Resta solo su questo telefono e puoi cambiarlo in Impostazioni.")
                            .font(.footnote).foregroundStyle(.secondary)
                        ProvaServerView()
                    }
                }
                Text("Se il tuo server è raggiungibile solo da una VPN, tienila accesa.")
                    .font(.footnote).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                provaConDati
            }
            .frame(maxWidth: 520)
            .padding(Tema.margine)
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Sfondo())
    }
}

extension PrimoAvvioView {
    /// Chi non ha ancora un server può guardare l'app con una lega inventata: niente account, niente rete, niente da scrivere.
    fileprivate var provaConDati: some View {
        VStack(spacing: 8) {
            Divider().padding(.vertical, 4)
            Text("Non hai ancora un server?")
                .font(.subheadline).foregroundStyle(.secondary)
            Button {
                ProvaEsempio.avvia()
            } label: {
                Label("Prova con dati di esempio", systemImage: "play.circle")
                    .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .buttonStyle(.bordered)
            .accessibilityHint("Apre l'app con una lega inventata, senza account e senza rete")
            Text("Una lega inventata, senza account e senza rete. Esci quando vuoi da Impostazioni.")
                .font(.footnote).foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
    }
}

#Preview("Primo avvio") {
    PrimoAvvioView()
}
