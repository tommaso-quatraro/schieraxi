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
        case .normale: return .testoSecondario
        case .attenzione: return .attenzione
        case .grave: return .malus
        }
    }
}

/// Riga di un giocatore: avatar con l'anello dell'indice, nome, partita, etichette e punti attesi.
/// Con `apribile` un tocco apre la scheda del giocatore.
struct RigaGiocatore: View {
    let g: Giocatore
    var apribile = false
    /// Se c'è (Formazione) e il server manda i motivi, il numero è un pulsante a sé che apre «Perché questo numero».
    var perche: ((Giocatore) -> Void)? = nil
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.dynamicTypeSize) private var tagliaTesto
    @Environment(\.spazioZoom) private var zoom
    @ScaledMetric(relativeTo: .body) private var lato: CGFloat = 46

    /// Come la web: «INT @ MIL · sab 31 20:45» (in trasferta) o «ATA vs PAR · oggi 20:45» (in casa), con le sigle e prima
    /// la squadra del giocatore; senza partita solo la sigla.
    private var sottotitolo: String {
        let mia = ColoriSquadra.sigla(g.squadra)
        let altra = ColoriSquadra.sigla(g.avversario)
        var parti: [String] = []
        if !altra.isEmpty {
            parti.append("\(mia) \(g.inCasa == true ? "vs" : "@") \(altra)")
        } else if !mia.isEmpty {
            parti.append(mia)
        }
        if Quando.data(g.dataPartita) != nil { parti.append(Quando.leggibile(g.dataPartita)) }
        return parti.joined(separator: " · ")
    }

    /// La partita a voce, con i nomi interi: «Inter, in trasferta contro Milan, sab 31 20:45».
    nonisolated private static func partitaAVoce(_ g: Giocatore) -> String {
        let mia = (g.squadra ?? "").capitalized
        let altra = (g.avversario ?? "").capitalized
        var parti: [String] = []
        if !altra.isEmpty {
            parti.append("\(mia), \(g.inCasa == true ? "in casa contro" : "in trasferta contro") \(altra)")
        } else if !mia.isEmpty {
            parti.append(mia)
        }
        if Quando.data(g.dataPartita) != nil { parti.append(Quando.leggibile(g.dataPartita)) }
        return parti.joined(separator: ", ")
    }

    /// Il fantavoto atteso se gioca, da `Formato.punti` come il campo, la scheda e il widget: a metà si arrotonda come la web
    /// (6,25 → 6,3), sempre con la virgola anche con il telefono in inglese, e «–» se il server non manda il numero (#251).
    /// Da un server senza `fv_atteso` restano i punti attesi, come nel Mercato.
    nonisolated static func testoPunti(_ g: Giocatore) -> String {
        Formato.punti(g.fvAtteso ?? g.puntiAttesi)
    }

    /// Il numero grande a destra della riga.
    nonisolated static func numero(_ g: Giocatore) -> String {
        testoPunti(g)
    }

    /// La riga piccola sotto il numero; nil se c'è solo il numero.
    nonisolated static func sottoNumero(_ g: Giocatore) -> String? {
        "gioca \(Formato.percento(g.pVoto))%"
    }

    /// Se il numero è un pulsante a sé che apre «Perché questo numero» (con i motivi del server).
    nonisolated static func numeroConPerche(_ g: Giocatore) -> Bool {
        g.assente != true && PercheNumero(g) != nil
    }

    /// Frase letta da VoiceOver per tutta la riga.
    nonisolated static func voce(_ g: Giocatore) -> String {
        var parti = [g.nome, nomeRuolo(g.ruolo)]
        let partita = partitaAVoce(g)
        if !partita.isEmpty { parti.append(partita) }
        if g.assente == true {
            parti.append("assente")
        } else {
            parti.append("fantavoto atteso \(testoPunti(g))")
            parti.append("gioca al \(Formato.percento(g.pVoto)) per cento")
            if let i = g.indice { parti.append("indice \(Formato.intero(i)) su 100") }
        }
        parti.append(contentsOf: g.etichette.map { $0.testo.lowercased() })
        return parti.joined(separator: ", ")
    }

    private var puntiTesto: String { Self.testoPunti(g) }
    /// Lo stesso numero, per far scorrere le cifre quando cambia.
    private var puntiValore: Double { g.fvAtteso ?? g.puntiAttesi ?? 0 }
    private var giocaPercento: Int { Formato.percento(g.pVoto) }

    private var nome: some View {
        HStack(spacing: 6) {
            BadgeRuolo(ruolo: g.ruolo, piccolo: true)
            // Il nome va a capo intero, anche su più righe: con il testo grande finiva con «…» (#254, `NomiInteriTests`).
            Text(g.nome).font(.headline)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    @ViewBuilder
    private var etichette: some View {
        let lista = g.etichette
        if !lista.isEmpty {
            // Come la web: ogni etichetta in una pillola del suo colore; le pillole vanno a capo se non ci stanno e
            // un'etichetta più larga della riga va a capo dentro la sua pillola (mai tagliata, issue #227).
            PilloleEtichette(etichette: lista)
                .padding(.top, 2)
        }
    }

    @ViewBuilder
    private var previsione: some View {
        let sotto = Self.sottoNumero(g)
        if g.assente == true {
            // Un assente non ha previsione: niente «0.0 punti, gioca 0%».
            Label("Assente", systemImage: "xmark.circle.fill").font(.caption.bold()).foregroundStyle(Color.malus)
        } else if tagliaTesto.isAccessibilitySize {
            // Testo molto grande: i punti stanno sotto il nome, su una riga, e il nome ha tutta la larghezza.
            HStack(spacing: 8) {
                cifra(.headline, solo: sotto == nil)
                if let sotto { Text(sotto).font(.caption).foregroundStyle(Color.testoSecondario) }
            }
        } else {
            VStack(alignment: .trailing, spacing: 2) {
                cifra(.title3.weight(.bold), solo: sotto == nil)
                if let sotto { Text(sotto).font(.caption2).foregroundStyle(Color.testoSecondario) }
            }
        }
    }

    /// Il numero grande (`numero`). `solo`: senza la riga sotto, cioè il «–» di una partita iniziata senza voto, grigio come
    /// sulla web (lo stato della partita lo dice la pillola).
    private func cifra(_ carattere: Font, solo: Bool) -> some View {
        Text(Self.numero(g)).font(carattere).monospacedDigit().numerico(numeroValore)
            .foregroundStyle(solo ? AnyShapeStyle(Color.testoSecondario) : AnyShapeStyle(.foreground))
    }

    /// Il numero grande come valore, per far scorrere le cifre quando cambia.
    private var numeroValore: Double { puntiValore }

    private var avatar: some View {
        AvatarGiocatore(id: g.id, squadra: g.squadra, indice: g.assente == true ? nil : g.indice, dimensione: min(lato, 64), nome: g.nome, ruolo: g.ruolo)
    }

    /// `conNumero` falso: il numero sta fuori, in un pulsante a sé (vedi `numeroPerche`).
    private func corpo(conNumero: Bool) -> some View {
        Group {
            if tagliaTesto.isAccessibilitySize {
                HStack(alignment: .top, spacing: 12) {
                    avatar
                    VStack(alignment: .leading, spacing: 2) {
                        nome
                        Text(sottotitolo).font(.caption).foregroundStyle(Color.testoSecondario)
                        etichette
                        if conNumero { previsione }
                    }
                    Spacer(minLength: 0)
                }
            } else {
                HStack(spacing: 12) {
                    avatar
                    VStack(alignment: .leading, spacing: 2) {
                        nome
                        Text(sottotitolo).font(.caption).foregroundStyle(Color.testoSecondario)
                        etichette
                    }
                    Spacer(minLength: 8)
                    if conNumero { previsione }
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Self.voce(g))
    }

    private var contenuto: some View { corpo(conNumero: true) }

    /// Il numero come pulsante: fondo tenue del colore principale e una «i», così si capisce che si tocca.
    private func numeroPerche(_ apriPerche: @escaping (Giocatore) -> Void) -> some View {
        Button { apriPerche(g) } label: {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                if tagliaTesto.isAccessibilitySize {
                    Text(puntiTesto).font(.headline).monospacedDigit().numerico(puntiValore)
                    Text("gioca \(giocaPercento)%").font(.caption).foregroundStyle(Color.testoSecondario)
                } else {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(puntiTesto).font(.title3.weight(.bold)).monospacedDigit().numerico(puntiValore)
                        Text("gioca \(giocaPercento)%").font(.caption2).foregroundStyle(Color.testoSecondario)
                    }
                }
                Image(systemName: "info.circle").font(.caption.weight(.semibold)).foregroundStyle(Color.verde)
            }
            .padding(.horizontal, 8).padding(.vertical, 4)
            .frame(minWidth: 44, minHeight: 44)
            .background(Color.verde.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(StilePressione())
        .hoverEffect(.highlight)
        .accessibilityLabel("\(FantavotoAtteso.nome) di \(g.nome): \(puntiTesto), gioca al \(giocaPercento) per cento")
        .accessibilityHint("Mostra perché questo numero")
    }

    var body: some View {
        if apribile, let apriPerche = perche, Self.numeroConPerche(g) {
            // Due pulsanti affiancati (o il numero sotto, con il testo molto grande): la riga apre la scheda, il numero il perché.
            Group {
                if tagliaTesto.isAccessibilitySize {
                    VStack(alignment: .leading, spacing: 4) {
                        rigaApribile(corpo(conNumero: false))
                        numeroPerche(apriPerche).padding(.leading, min(lato, 64) + 12)
                    }
                } else {
                    HStack(spacing: 8) {
                        rigaApribile(corpo(conNumero: false))
                        numeroPerche(apriPerche)
                    }
                }
            }
            .contextMenu {
                Button { apri(g.id) } label: { Label("Apri la scheda", systemImage: "person.text.rectangle") }
                Button { apriPerche(g) } label: { Label(PercheNumero.titolo, systemImage: "info.circle") }
                Button { UIPasteboard.general.string = g.nome } label: { Label("Copia il nome", systemImage: "doc.on.doc") }
            }
        } else if apribile {
            Button { apri(g.id) } label: { contenuto.frame(minHeight: 44).contentShape(Rectangle()) }
                .buttonStyle(StilePressione())
                .origineZoom(g.id, zoom)
                .contextMenu {
                    Button { apri(g.id) } label: { Label("Apri la scheda", systemImage: "person.text.rectangle") }
                    Button { UIPasteboard.general.string = g.nome } label: { Label("Copia il nome", systemImage: "doc.on.doc") }
                }
                .accessibilityHint("Apre la scheda del giocatore")
        } else {
            contenuto
        }
    }

    private func rigaApribile(_ vista: some View) -> some View {
        Button { apri(g.id) } label: { vista.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading).contentShape(Rectangle()) }
            .buttonStyle(StilePressione())
            .origineZoom(g.id, zoom)
            .accessibilityHint("Apre la scheda del giocatore")
    }
}
