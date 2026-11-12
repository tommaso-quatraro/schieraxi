import Foundation

// Parti dell'app (non del widget) per le cose da fare di Oggi: dove portano e in che ordine.

extension DestinazioneDaFare {
    /// Dove porta: prima il collegamento `schieraxi://`, poi la sezione scritta a parole; altrimenti da nessuna parte.
    var destinazione: Destinazione? {
        if let link, let url = URL(string: link), let d = Collegamenti.interpreta(url) { return d }
        if let sezione, let s = Sezione.da(nome: sezione) { return .sezione(s) }
        return nil
    }
}

extension DaFareVoce {
    /// Le schede tolte il 12/11/2026 (#634): Cambi consigliati («mercato») e Scambi. Il server manda ancora le sue righe come prima.
    static let schedeTolte = ["mercato", "scambi"]
    /// I due consigli delle funzioni tolte (il cambio con uno svincolato e lo scambio): non si mostrano, come sulla web
    /// (`DF_TIPI_TOLTI` di `fanta/web/dafare.js`). Si guarda il tipo della riga, non dove porta.
    static let tipiTolti = ["svincolato", "scambio"]

    /// Una riga che resta ma portava a una scheda tolta (il reparto scoperto: «Cerca un rimpiazzo»): apre la rosa della propria
    /// squadra, e il pulsante lo dice (come `dfAllaRosa` della web).
    var allaRosa: Bool { Self.schedeTolte.contains(destinazione?.scheda ?? "") }

    /// Cosa dice il pulsante: quello del server, «Vedi la rosa» per le righe che aprono la rosa, «Apri» se il server non lo dice.
    var testoPulsante: String { allaRosa ? Catalogo.Lega.vediRosa : (azione ?? Catalogo.Df.apri) }
}

extension Oggi {
    /// Le cose da fare in ordine di urgenza (a parità, l'ordine del server), senza voci vuote.
    var cosePerOrdine: [DaFareVoce] {
        (daFare ?? []).enumerated().filter { !$0.element.testo.isEmpty }
            .sorted { ($0.element.priorita ?? 3, $0.offset) < ($1.element.priorita ?? 3, $1.offset) }
            .map(\.element)
    }
}
