import Foundation

extension Giocatore {
    /// Il nome senza le iniziali finali («Marteni L.» → «Marteni»): per i titoli stretti.
    var nomeCorto: String {
        var parti = nome.split(separator: " ").map(String.init)
        while parti.count > 1, let ultima = parti.last, ultima.hasSuffix("."), ultima.count <= 3 { parti.removeLast() }
        return parti.joined(separator: " ")
    }
}

extension Confronto {
    /// Il giocatore consigliato dal sistema.
    var vincitore: Giocatore? { giocatori.first { $0.id == consigliato } }

    /// Chi schierare «nella formazione»: se uno solo dei due è titolare, è lui; se lo sono tutti e due (o nessuno) non c'è scelta da fare.
    var schierato: Giocatore? {
        guard let f = formazione, giocatori.count == 2 else { return nil }
        let titolareA = f.postoA == "titolare", titolareB = f.postoB == "titolare"
        if titolareA && !titolareB { return giocatori[0] }
        if titolareB && !titolareA { return giocatori[1] }
        return nil
    }

    /// Le cause che contano: quelle con un effetto visibile, più sempre «giocare».
    var fattoriVisibili: [FattoreConfronto] {
        fattori.filter { abs($0.effetto) >= 0.005 || $0.chiave == "giocare" }
    }

    /// L'effetto più grande (almeno 0,3): fa da «fondo scala» delle barre.
    var massimoEffetto: Double {
        max(0.3, fattori.map { abs($0.effetto) }.max() ?? 0)
    }

    /// Differenza di punti attesi, da soli, tra il primo e il secondo giocatore.
    var differenzaPunti: Double? {
        guard giocatori.count == 2, let a = giocatori[0].puntiAttesi, let b = giocatori[1].puntiAttesi else { return nil }
        return a - b
    }

    /// A chi va una causa: 1 = al primo giocatore, -1 = al secondo, 0 = pari.
    static func verso(_ effetto: Double) -> Int {
        effetto > 0.02 ? 1 : effetto < -0.02 ? -1 : 0
    }
}
