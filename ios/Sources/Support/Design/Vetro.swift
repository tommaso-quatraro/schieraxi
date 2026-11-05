import SwiftUI

// Liquid Glass (iOS 26) con ripiego per iOS 18 e 19...: ogni funzione nuova passa da qui, dietro `#available`.
// Le schermate usano solo questi nomi e non sanno su quale versione girano.

@available(iOS 26.0, *)
private func vetroDi(tinta: Color?, interattivo: Bool) -> Glass {
    var vetro = Glass.regular
    if let tinta { vetro = vetro.tint(tinta) }
    if interattivo { vetro = vetro.interactive() }
    return vetro
}

extension View {
    /// Sfondo di vetro (Liquid Glass) nella forma data; su iOS 18 un materiale sfocato. Da usare per i controlli che
    /// «galleggiano» sopra i contenuti (etichette, pulsanti, selettori), non per le schede dei contenuti.
    @ViewBuilder
    func vetro<S: Shape>(in forma: S, tinta: Color? = nil, interattivo: Bool = false) -> some View {
        if #available(iOS 26.0, *) {
            self.glassEffect(vetroDi(tinta: tinta, interattivo: interattivo), in: forma)
        } else {
            self.background(.ultraThinMaterial, in: forma)
                .overlay { if let tinta { forma.fill(tinta.opacity(0.22)) } }
        }
    }

    /// Pulsante di vetro (iOS 26) o con contorno (iOS 18). `prominente` per l'azione principale: un pulsante pieno, con la
    /// scritta leggibile sul suo fondo (`PulsantePieno`). Ogni pulsante pieno dell'app passa da qui (`tests/test_design_web.py`).
    @ViewBuilder
    func pulsanteVetro(prominente: Bool = false) -> some View {
        if prominente {
            modifier(PulsantePieno())
        } else {
            if #available(iOS 26.0, *) { self.buttonStyle(.glass) } else { self.buttonStyle(.bordered) }
        }
    }

    /// Bordi di scorrimento morbidi (iOS 26): i contenuti sfumano sotto le barre invece di tagliarsi.
    @ViewBuilder
    func bordiMorbidi() -> some View {
        if #available(iOS 26.0, *) {
            self.scrollEdgeEffectStyle(.soft, for: .all)
        } else {
            self
        }
    }

    /// Le schede in fondo alla barra delle schede si riducono scorrendo (iOS 26).
    @ViewBuilder
    func barraSchedeCheSiRiduce() -> some View {
        if #available(iOS 26.0, *) {
            self.tabBarMinimizeBehavior(.onScrollDown)
        } else {
            self
        }
    }

    /// L'immagine o il colore dietro un'intestazione continua sotto le barre e ai lati (iOS 26).
    @ViewBuilder
    func sfondoEsteso() -> some View {
        if #available(iOS 26.0, *) {
            self.backgroundExtensionEffect()
        } else {
            self
        }
    }
}

/// Il pulsante pieno (l'azione principale): fondo il colore dell'app (`.glassProminent` su iOS 26, `.borderedProminent` su iOS 18).
/// La scritta la sceglie l'app: lo stile di sistema la fa bianca anche sul verde chiaro del tema scuro (1,8:1, issue #248); qui è
/// `Color.scrittaPulsante`, come `--azione-testo` della web. Spento, il fondo diventa grigio e la scritta il grigio dell'app
/// (`Color.testoSecondario`): si legge ancora cosa farà il pulsante («Riprova tra 34 s»), mentre il verde quasi nero sul grigio
/// scuro dello scuro sparirebbe. Un solo modificatore con il colore che cambia, non due rami: il pulsante resta lo stesso
/// quando si accende (VoiceOver non perde il punto).
private struct PulsantePieno: ViewModifier {
    @Environment(\.isEnabled) private var attivo

    func body(content: Content) -> some View {
        Group {
            if #available(iOS 26.0, *) {
                content.buttonStyle(.glassProminent)
            } else {
                content.buttonStyle(.borderedProminent)
            }
        }
        .foregroundStyle(attivo ? Color.scrittaPulsante : Color.testoSecondario)
    }
}

/// Raggruppa più elementi di vetro vicini: su iOS 26 si fondono come gocce quando si avvicinano.
struct GruppoVetro<Contenuto: View>: View {
    var spazio: CGFloat = 12
    @ViewBuilder let contenuto: () -> Contenuto

    var body: some View {
        if #available(iOS 26.0, *) {
            GlassEffectContainer(spacing: spazio) { contenuto() }
        } else {
            contenuto()
        }
    }
}
