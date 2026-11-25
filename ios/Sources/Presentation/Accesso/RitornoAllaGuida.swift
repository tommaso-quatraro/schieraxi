import Foundation

/// «Importa le rose» aperta da un passo della configurazione guidata.
struct RitornoAllaGuida {
    /// La guida ha chiesto la pagina delle rose.
    mutating func importaChiesta() {}

    /// La pila delle Impostazioni è cambiata: vero quando la guida va riaperta.
    mutating func pilaCambiata(_ pagine: [PaginaImpostazioni]) -> Bool { false }

    /// La pagina delle rose è stata chiesta dalla guida e non è ancora stata lasciata.
    var attivo: Bool { false }
}
