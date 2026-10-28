import SwiftUI

private struct ApriGiocatoreChiave: EnvironmentKey {
    static let defaultValue: (Int) -> Void = { _ in }
}

extension EnvironmentValues {
    /// Apre la scheda di un giocatore sopra la schermata in cui ci si trova (la imposta la radice dell'app).
    var apriGiocatore: (Int) -> Void {
        get { self[ApriGiocatoreChiave.self] }
        set { self[ApriGiocatoreChiave.self] = newValue }
    }
}

private struct VediFormazioneChiave: EnvironmentKey {
    static let defaultValue: (String) -> Void = { _ in }
}

extension EnvironmentValues {
    /// Porta nella sezione Formazione la formazione consigliata per un'altra squadra della lega (dalla rosa di quella squadra).
    var vediFormazioneDi: (String) -> Void {
        get { self[VediFormazioneChiave.self] }
        set { self[VediFormazioneChiave.self] = newValue }
    }
}

private struct VaiASezioneChiave: EnvironmentKey {
    static let defaultValue: (Sezione) -> Void = { _ in }
}

private struct ApriNovitaChiave: EnvironmentKey {
    static let defaultValue: () -> Void = {}
}

extension EnvironmentValues {
    /// Cambia sezione (per esempio dal pulsante «Apri la formazione» di Oggi).
    var vaiASezione: (Sezione) -> Void {
        get { self[VaiASezioneChiave.self] }
        set { self[VaiASezioneChiave.self] = newValue }
    }

    /// Apre Lega > Novità (dal banner «Novità nell'app» di Oggi).
    var apriNovita: () -> Void {
        get { self[ApriNovitaChiave.self] }
        set { self[ApriNovitaChiave.self] = newValue }
    }
}

extension Etichetta.Gravita {
    var colore: Color {
        switch self {
        case .normale: return .secondary
        case .attenzione: return .orange
        case .grave: return .red
        }
    }
}

/// Riga di un giocatore: avatar con l'anello dell'indice, nome, partita, etichette e punti attesi.
/// Con `apribile` un tocco apre la scheda del giocatore.
struct RigaGiocatore: View {
    let g: Giocatore
    var apribile = false
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.dynamicTypeSize) private var tagliaTesto
    @ScaledMetric(relativeTo: .body) private var lato: CGFloat = 46

    private var sottotitolo: String {
        let mia = g.squadra?.uppercased() ?? ""
        let altra = g.avversario?.uppercased() ?? ""
        if altra.isEmpty { return mia }
        return "\(mia) \(g.inCasa == true ? "vs" : "@") \(altra)"
    }

    private var puntiTesto: String { (g.puntiAttesi ?? 0).formatted(.number.precision(.fractionLength(1))) }
    private var giocaPercento: Int { Formato.percento(g.pVoto) }

    /// Frase letta da VoiceOver per tutta la riga.
    private var descrizioneVoce: String {
        var parti = [g.nome, nomeRuolo(g.ruolo)]
        if !sottotitolo.isEmpty { parti.append(sottotitolo.replacingOccurrences(of: "@", with: "in trasferta contro")) }
        if g.assente == true {
            parti.append("assente")
        } else {
            parti.append("punti attesi \(puntiTesto)")
            parti.append("gioca al \(giocaPercento) per cento")
            if let i = g.indice { parti.append("indice \(Formato.intero(i)) su 100") }
        }
        parti.append(contentsOf: g.etichette.map { $0.testo.lowercased() })
        return parti.joined(separator: ", ")
    }

    private var nome: some View {
        HStack(spacing: 6) {
            BadgeRuolo(ruolo: g.ruolo, piccolo: true)
            // Il nome può andare su due righe: con il testo grande veniva tagliato («Mateo…»).
            Text(g.nome).font(.headline).lineLimit(2)
        }
    }

    @ViewBuilder
    private var etichette: some View {
        let lista = g.etichette
        if !lista.isEmpty {
            // Un'unica riga di testo colorato (a capo se serve): più compatta di tante capsule.
            lista.enumerated().reduce(Text("")) { acc, voce in
                acc + Text(voce.offset == 0 ? "" : " · ") + Text(voce.element.testo).foregroundColor(voce.element.gravita.colore)
            }
            .font(.caption)
            .fixedSize(horizontal: false, vertical: true)
        }
    }

    @ViewBuilder
    private var previsione: some View {
        if g.assente == true {
            // Un assente non ha previsione: niente «0.0 punti, gioca 0%».
            Label("Assente", systemImage: "xmark.circle.fill").font(.caption.bold()).foregroundStyle(.red)
        } else if tagliaTesto.isAccessibilitySize {
            // Testo molto grande: i punti stanno sotto il nome, su una riga, e il nome ha tutta la larghezza.
            HStack(spacing: 8) {
                Text(puntiTesto).font(.headline).monospacedDigit()
                Text("gioca \(giocaPercento)%").font(.caption).foregroundStyle(.secondary)
            }
        } else {
            VStack(alignment: .trailing, spacing: 2) {
                Text(puntiTesto).font(.headline).monospacedDigit()
                Text("gioca \(giocaPercento)%").font(.caption2).foregroundStyle(.secondary)
            }
        }
    }

    private var avatar: some View {
        AvatarGiocatore(id: g.id, squadra: g.squadra, indice: g.assente == true ? nil : g.indice, dimensione: min(lato, 64))
    }

    private var contenuto: some View {
        Group {
            if tagliaTesto.isAccessibilitySize {
                HStack(alignment: .top, spacing: 12) {
                    avatar
                    VStack(alignment: .leading, spacing: 2) {
                        nome
                        Text(sottotitolo).font(.caption).foregroundStyle(.secondary)
                        etichette
                        previsione
                    }
                    Spacer(minLength: 0)
                }
            } else {
                HStack(spacing: 12) {
                    avatar
                    VStack(alignment: .leading, spacing: 2) {
                        nome
                        Text(sottotitolo).font(.caption).foregroundStyle(.secondary)
                        etichette
                    }
                    Spacer(minLength: 8)
                    previsione
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(descrizioneVoce)
    }

    var body: some View {
        if apribile {
            Button { apri(g.id) } label: { contenuto.frame(minHeight: 44).contentShape(Rectangle()) }
                .buttonStyle(.plain)
                .accessibilityHint("Apre la scheda del giocatore")
        } else {
            contenuto
        }
    }
}
