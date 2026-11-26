import SwiftUI

/// Il campo della Formazione sull'iPad (#896): le file dall'alto (attacco, centrocampo, difesa, portiere) e, fra la prima metà e
/// la seconda, una fascia libera dove passano la linea di metà campo e il cerchio (l'ultima vista, `MetaCampo`). Prima linea e
/// cerchio stavano a metà altezza qualunque fosse l'altezza delle file: con il testo grande il campo largo e basso metteva il
/// cerchio sopra il volto di un difensore e «Partita in corso» sopra la linea. Il campo è alto almeno `rapporto` volte la sua
/// larghezza; lo spazio in più si divide in parti uguali fra le file e la fascia. Sull'iPhone il campo resta com'era.
struct DisposizioneCampo: Layout {
    /// Altezza minima rispetto alla larghezza: tre quarti, perché un campo largo non sembri una striscia.
    static let rapporto: CGFloat = 0.75
    /// Spazio minimo fra due file della stessa metà (come lo `VStack` del campo sull'iPhone).
    static let spazio: CGFloat = 10
    /// Altezza minima della fascia di metà campo: il cerchio (68 punti) con 8 punti d'aria sopra e sotto.
    static let fascia: CGFloat = 84

    /// Dove stanno le file e la fascia, dall'alto del campo.
    struct Misure: Equatable {
        /// La cima di ogni fila.
        var cime: [CGFloat]
        var fasciaCima: CGFloat
        var fasciaAltezza: CGFloat
        var altezza: CGFloat
    }

    /// Le misure per file alte `altezze` in un campo largo `larghezza`. La fascia va dopo la prima metà delle file (2 su 4).
    static func misure(altezze: [CGFloat], larghezza: CGFloat) -> Misure {
        guard let prima = altezze.first else { return Misure(cime: [], fasciaCima: 0, fasciaAltezza: 0, altezza: 0) }
        guard altezze.count > 1 else { return Misure(cime: [0], fasciaCima: prima, fasciaAltezza: 0, altezza: prima) }
        let dopo = altezze.count / 2
        let spazi = CGFloat(altezze.count - 2)
        let naturale = altezze.reduce(0, +) + spazio * spazi + fascia
        let minima = larghezza.isFinite ? larghezza * rapporto : 0
        // lo spazio in più va diviso fra tutti gli spazi fra le file, fascia compresa
        let quota = max(0, minima - naturale) / CGFloat(altezze.count - 1)
        var cime: [CGFloat] = []
        var y: CGFloat = 0
        var fasciaCima: CGFloat = 0
        for (i, h) in altezze.enumerated() {
            if i > 0 {
                if i == dopo {
                    fasciaCima = y
                    y += fascia + quota
                } else {
                    y += spazio + quota
                }
            }
            cime.append(y)
            y += h
        }
        return Misure(cime: cime, fasciaCima: fasciaCima, fasciaAltezza: fascia + quota, altezza: y)
    }

    /// Le ultime misure e la larghezza per cui valgono: le file (pedine con volti e testi che vanno a capo) si misurano una volta
    /// sola per larghezza, non di nuovo per disporle (#846: misure ripetute fermavano lo schermo). iOS rifà la cache quando
    /// cambiano le file.
    struct Cache {
        var larghezza: CGFloat?
        var misure = Misure(cime: [], fasciaCima: 0, fasciaAltezza: 0, altezza: 0)
    }

    func makeCache(subviews: Subviews) -> Cache {
        Cache()
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) -> CGSize {
        let larghezza = larghezzaDa(proposal, subviews)
        return CGSize(width: larghezza, height: misure(subviews, larghezza, &cache).altezza)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) {
        guard let meta = subviews.last, subviews.count > 1 else { return }
        let m = misure(subviews, bounds.width, &cache)
        for (i, fila) in subviews.dropLast().enumerated() where i < m.cime.count {
            fila.place(at: CGPoint(x: bounds.minX, y: bounds.minY + m.cime[i]), anchor: .topLeading,
                       proposal: ProposedViewSize(width: bounds.width, height: nil))
        }
        meta.place(at: CGPoint(x: bounds.minX, y: bounds.minY + m.fasciaCima), anchor: .topLeading,
                   proposal: ProposedViewSize(width: bounds.width, height: m.fasciaAltezza))
    }

    /// La larghezza proposta; senza (misura ideale) quella della fila più larga.
    private func larghezzaDa(_ proposta: ProposedViewSize, _ subviews: Subviews) -> CGFloat {
        if let w = proposta.width, w.isFinite { return w }
        return subviews.dropLast().map { $0.sizeThatFits(.unspecified).width }.max() ?? 0
    }

    /// Le misure delle file (tutte le viste tranne l'ultima, la fascia) alla larghezza data, dalla cache se sono già state prese.
    private func misure(_ subviews: Subviews, _ larghezza: CGFloat, _ cache: inout Cache) -> Misure {
        if cache.larghezza == larghezza { return cache.misure }
        let altezze = subviews.dropLast().map { $0.sizeThatFits(ProposedViewSize(width: larghezza, height: nil)).height }
        let m = Self.misure(altezze: altezze, larghezza: larghezza)
        cache.larghezza = larghezza
        cache.misure = m
        return m
    }
}
