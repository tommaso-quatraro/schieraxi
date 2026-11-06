/// Le sezioni di Oggi, dall'alto in basso.
enum SezioneOggi: Hashable, Sendable {
    case benvenuto, senzaGiornata, conto
    case riepilogo, inCorso, chiGioca, cambiPanchina
    case formazione, rinvio, daFare, novita
    case suggerimento, migliori, daControllare, indisponibili, diffidati
    case partite

    static func ordine(fase: FaseGiornata, conGiornata: Bool) -> [SezioneOggi] {
        var sezioni: [SezioneOggi] = [.benvenuto, conGiornata ? .conto : .senzaGiornata]
        switch fase {
        case .prima:
            sezioni.append(contentsOf: [SezioneOggi.rinvio, .daFare, .novita])
            if conGiornata { sezioni.append(.formazione) }
            sezioni.append(contentsOf: [SezioneOggi.daControllare, .suggerimento, .migliori, .indisponibili, .diffidati])
        case .inCorso:
            sezioni.append(contentsOf: [SezioneOggi.inCorso, .rinvio, .cambiPanchina, .chiGioca, .daFare, .novita])
        case .finita:
            sezioni.append(contentsOf: [SezioneOggi.riepilogo, .rinvio, .daFare, .novita])
            if conGiornata { sezioni.append(.formazione) }
        }
        sezioni.append(.partite)
        return sezioni
    }

    static func avvisoProbabili(fase: FaseGiornata, conProbabili: Bool?) -> Bool {
        conProbabili == false
    }
}
