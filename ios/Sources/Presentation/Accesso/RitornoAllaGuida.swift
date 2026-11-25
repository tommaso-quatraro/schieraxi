import Foundation

/// Una pagina aperta da un passo della configurazione guidata.
struct RitornoAllaGuida {
    /// Dove ha portato la guida.
    enum Meta: Equatable { case pagina(PaginaImpostazioni), widget }

    private enum Fase { case nessuna, chiesta, aperta }
    private var fase = Fase.nessuna

    /// La guida ha portato a `meta` dal passo `passo`.
    mutating func chiesta(_ meta: Meta, dalPasso passo: PassoGuidato) {
        if meta == .pagina(.importa) { fase = .chiesta }
    }

    /// La pila delle Impostazioni è cambiata: il passo da cui riaprire la guida.
    mutating func pilaCambiata(_ pagine: [PaginaImpostazioni]) -> PassoGuidato? {
        let rose = pagine.contains(.importa)
        switch (fase, rose) {
        case (.chiesta, true):
            fase = .aperta
        case (.chiesta, false):
            fase = .nessuna
        case (.aperta, false):
            fase = .nessuna
            return .rose
        default:
            break
        }
        return nil
    }

    /// Il foglio «Collega il widget» si è aperto o chiuso.
    mutating func foglioWidget(aperto: Bool) -> PassoGuidato? { nil }

    /// La pagina è stata chiesta dalla guida e non è ancora stata lasciata.
    func attivo(per pagina: PaginaImpostazioni) -> Bool { fase != .nessuna && pagina == .importa }
}
