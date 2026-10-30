import Foundation

// Parti dell'app (non del widget) per le cose da fare di Oggi: dove portano e in che ordine.

extension DestinazioneDaFare {
    /// Dove porta: prima il collegamento `schieraxi://`, poi la sezione scritta a parole; altrimenti da nessuna parte.
    var destinazione: Destinazione? {
        if let link, let url = URL(string: link), let d = Collegamenti.interpreta(url) { return d }
        if let sezione, let s = Sezione(rawValue: sezione.lowercased()) { return .sezione(s) }
        return nil
    }
}

extension Oggi {
    /// Le cose da fare in ordine di urgenza (a parità, l'ordine del server), senza voci vuote.
    var cosePerOrdine: [DaFareVoce] {
        (daFare ?? []).enumerated().filter { !$0.element.testo.isEmpty }
            .sorted { ($0.element.priorita ?? 3, $0.offset) < ($1.element.priorita ?? 3, $1.offset) }
            .map(\.element)
    }
}
