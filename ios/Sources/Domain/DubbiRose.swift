import Foundation

/// Un giocatore delle rose che l'importazione non ha riconosciuto nel listone (resta senza codice).
struct GiocatoreDaSistemare: Identifiable, Hashable {
    let squadra: String
    let nome: String
    /// La riga nella rosa della squadra (dall'alto, da 0): due righe con lo stesso nome nella stessa squadra restano due dubbi
    /// distinti, e abbinandone una sparisce solo quella, come sulla web.
    let posizione: Int
    var id: String { "\(squadra)|\(posizione)" }
}

/// Corpo di `POST /api/rose/correggi`: chiavi identiche a quelle del server.
struct RichiestaCorreggiGiocatore: Encodable {
    let squadra: String
    let nome: String
    let id: Int
}

enum DubbiRose {
    /// I giocatori senza codice di tutte le rose, in ordine di squadra.
    static func trova(in rose: [Rosa]) -> [GiocatoreDaSistemare] {
        rose.flatMap { r in
            r.giocatori.enumerated().filter { $0.element.id == nil }
                .map { GiocatoreDaSistemare(squadra: r.nome, nome: $0.element.nome, posizione: $0.offset) }
        }
    }
}
