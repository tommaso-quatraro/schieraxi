import Foundation

/// Chi mette i crediti del conguaglio, come i due pulsanti della web: «Ricevo» (ti danno i crediti) e «Pago» (li dai tu).
enum VersoConguaglio: CaseIterable, Identifiable {
    case ricevo, pago

    var id: Self { self }

    /// Il nome del pulsante (`scambi.ricevo_crediti`, `scambi.pago_crediti`).
    var nome: String { self == .ricevo ? TestiScambi.ricevoCrediti : TestiScambi.pagoCrediti }
}
