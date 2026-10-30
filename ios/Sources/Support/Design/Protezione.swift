import SwiftUI

/// Copre la schermata (con una sfocatura e il marchio) quando l'app non è in primo piano: l'anteprima nel selettore delle app
/// (app switcher) non deve mostrare password, nomi utente o il codice di recupero.
struct SchermoProtetto: ViewModifier {
    @Environment(\.scenePhase) private var fase

    func body(content: Content) -> some View {
        content
            .overlay {
                if fase != .active {
                    ZStack {
                        Rectangle().fill(.regularMaterial)
                        Marchio(lato: 72)
                    }
                    .ignoresSafeArea()
                    .accessibilityHidden(true)
                }
            }
    }
}

extension View {
    /// Oscura la vista quando l'app va in secondo piano (vedi `SchermoProtetto`).
    func schermoProtetto() -> some View { modifier(SchermoProtetto()) }
}

/// Vero mentre lo schermo è registrato, condiviso o trasmesso (registrazione schermo, AirPlay): il codice di recupero non si mostra.
@MainActor
final class StatoRegistrazioneSchermo: ObservableObject {
    @Published private(set) var registrato: Bool
    private var osservatore: NSObjectProtocol?

    init() {
        registrato = Self.leggi()
        osservatore = NotificationCenter.default.addObserver(forName: UIScreen.capturedDidChangeNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.registrato = Self.leggi() }
        }
    }

    deinit {
        if let osservatore { NotificationCenter.default.removeObserver(osservatore) }
    }

    private static func leggi() -> Bool {
        UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.screen.isCaptured }.contains(true)
    }
}
