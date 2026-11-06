import SwiftUI

/// Come stanno nella rosa di una squadra il titolo «Crediti residui», il campo e «Salva» (issue #467).
///
/// Con il testo al massimo il campo, largo quanto il testo, lasciava a «Salva» una striscia di pochi punti e la parola andava
/// a capo una lettera per riga. Da «Accessibilità 1» in su i tre pezzi vanno uno sotto l'altro: ognuno ha tutta la larghezza.
enum DisposizioneCrediti: Equatable {
    /// Testo normale: titolo, campo e «Salva» sulla stessa riga (se non ci stanno, campo e «Salva» sotto il titolo).
    case inRiga
    /// Testo molto grande (le misure «Accessibilità»): titolo, campo e «Salva» uno sotto l'altro.
    case inColonna

    /// Lato minimo del bersaglio di tocco di «Salva»: 44 punti, come chiedono le linee guida di Apple.
    static let latoMinimoTocco: CGFloat = 44

    /// La disposizione per la dimensione del testo scelta dall'utente.
    static func per(_ dimensione: DynamicTypeSize) -> DisposizioneCrediti {
        dimensione.isAccessibilitySize ? .inColonna : .inRiga
    }
}
