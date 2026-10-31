import Foundation

/// Un giocatore delle rose che l'importazione non ha riconosciuto nel listone (resta senza codice).
struct GiocatoreDaSistemare: Identifiable, Hashable {
    let squadra: String
    let nome: String
    var id: String { "\(squadra)|\(nome)" }
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
            r.giocatori.filter { $0.id == nil }.map { GiocatoreDaSistemare(squadra: r.nome, nome: $0.nome) }
        }
    }
}
