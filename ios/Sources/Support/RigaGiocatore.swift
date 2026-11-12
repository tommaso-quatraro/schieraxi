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

extension EnvironmentValues {
    /// Cambia sezione (per esempio dal pulsante «Apri la formazione» di Oggi).
    var vaiASezione: (Sezione) -> Void {
        get { self[VaiASezioneChiave.self] }
        set { self[VaiASezioneChiave.self] = newValue }
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

/// Riga di un giocatore: volto, nome, partita, etichette e a destra il numero (fantavoto atteso e
/// «gioca N%» prima della partita, fantavoto preso dopo: vedi `numero`). Con `apribile` un tocco apre la scheda del giocatore,
/// che dice anche «Perché questo numero» (come la web, #616: niente più un foglio a parte sul numero).
struct RigaGiocatore: View {
    let g: Giocatore
    var apribile = false
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.dynamicTypeSize) private var tagliaTesto
    @Environment(\.spazioZoom) private var zoom
    @ScaledMetric(relativeTo: .body) private var lato: CGFloat = 46

    /// Come la web: «INT @ MIL · sab 31 20:45» (in trasferta) o «ATA vs PAR · oggi 20:45» (in casa), con le sigle e prima
    /// la squadra del giocatore; senza partita solo la sigla. «oggi», «ieri», «domani» si contano dall'ora dell'app
    /// (`Orologio`), la stessa di Oggi: nella demo a giornata in corso il momento della demo (#424).
    private var sottotitolo: String { Self.sottotitolo(g, adesso: Orologio.adesso()) }

    /// Il sottotitolo della riga con «oggi», «ieri», «domani» contati da `adesso`.
    nonisolated static func sottotitolo(_ g: Giocatore, adesso: Date) -> String {
        let mia = ColoriSquadra.sigla(g.squadra)
        let altra = ColoriSquadra.sigla(g.avversario)
        var parti: [String] = []
        if !altra.isEmpty {
            parti.append("\(mia) \(g.inCasa == true ? "vs" : "@") \(altra)")
        } else if !mia.isEmpty {
            parti.append(mia)
        }
        if Quando.data(g.dataPartita) != nil { parti.append(Quando.leggibile(g.dataPartita, adesso: adesso)) }
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
        if Quando.data(g.dataPartita) != nil { parti.append(Quando.leggibile(g.dataPartita, adesso: Orologio.adesso())) }
        return parti.joined(separator: ", ")
    }

    /// Il fantavoto atteso se gioca, da `Formato.punti` come il campo, la scheda e il widget: a metà si arrotonda come la web
    /// (6,25 → 6,3), sempre con la virgola anche con il telefono in inglese, e «–» se il server non manda il numero (#251).
    /// Da un server senza `fv_atteso` restano i punti attesi, come nel Mercato.
    nonisolated static func testoPunti(_ g: Giocatore) -> String {
        Formato.punti(g.fvAtteso ?? g.puntiAttesi)
    }

    /// Il numero grande a destra della riga, come `voceGiocatore` di app.js (#313): prima della partita, e con la partita
    /// rinviata, il fantavoto atteso; a partita iniziata il fantavoto preso, o «–» se non c'è ancora (o non ci sarà).
    nonisolated static func numero(_ g: Giocatore) -> String {
        guard let esito = g.esitoPartita else { return testoPunti(g) }
        return Formato.punti(esito.fv)
    }

    /// La riga piccola sotto il numero: «gioca 72%» prima della partita, «fantavoto» (`mercato.fantavoto` della web) sotto il
    /// fantavoto preso; nil a partita iniziata senza voto, perché lo stato della partita lo dice già la pillola dell'etichetta.
    nonisolated static func sottoNumero(_ g: Giocatore) -> String? {
        guard let esito = g.esitoPartita else { return "gioca \(Formato.percento(g.pVoto))%" }
        return esito.fv == nil ? nil : Catalogo.Mercato.fantavoto
    }

    /// Il colore di «gioca N%» sotto il numero, con la soglia unica della scheda e della pedina (`SogliaGioca`, come `numeriRiga`
    /// della web): arancio fra 50 e 79, rosso sotto 50. nil (grigio) dall'80%, a partita iniziata, per un assente e per chi non
    /// gioca di sicuro (infortunato, squalificato, fuori: lo dice la parola). Vale per ogni riga, anche fra i sostituti.
    nonisolated static func livelloGioca(_ g: Giocatore) -> SogliaGioca.Livello? {
        guard g.esitoPartita == nil, g.assente != true, ParolaStato(g)?.nonGiocaDiSicuro != true else { return nil }
        let livello = SogliaGioca.livello(g.pVoto)
        return livello == .sicuro ? nil : livello
    }

    /// Frase letta da VoiceOver per tutta la riga: le stesse cose che si vedono. A partita iniziata «fantavoto 3,5» come la
    /// pedina del campo, o niente: il «–» non si legge e lo stato della partita arriva con le etichette.
    nonisolated static func voce(_ g: Giocatore) -> String {
        var parti = [g.nome, nomeRuolo(g.ruolo)]
        let partita = partitaAVoce(g)
        if !partita.isEmpty { parti.append(partita) }
        if g.assente == true {
            parti.append("assente")
        } else {
            if let esito = g.esitoPartita {
                if esito.fv != nil, let preso = esito.testo { parti.append(preso) }
            } else {
                parti.append("fantavoto atteso \(testoPunti(g))")
                parti.append("gioca al \(Formato.percento(g.pVoto)) per cento")
            }
        }
        parti.append(contentsOf: g.etichette.map { $0.testo.lowercased() })
        return parti.joined(separator: ", ")
    }

    /// Lo stesso numero, per far scorrere le cifre quando cambia.
    private var puntiValore: Double { g.fvAtteso ?? g.puntiAttesi ?? 0 }

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
                if let sotto { Text(sotto).font(.caption).foregroundStyle(coloreSotto) }
            }
        } else {
            VStack(alignment: .trailing, spacing: 2) {
                cifra(.title3.weight(.bold), solo: sotto == nil)
                if let sotto { Text(sotto).font(.caption2).foregroundStyle(coloreSotto) }
            }
        }
    }

    /// «gioca N%» arancio o rosso sotto l'80% (`livelloGioca`), altrimenti grigio come «fantavoto».
    private var coloreSotto: Color {
        switch Self.livelloGioca(g) {
        case .medio?: return .attenzione
        case .basso?: return .malus
        default: return .testoSecondario
        }
    }

    /// Il numero grande (`numero`). `solo`: senza la riga sotto, cioè il «–» di una partita iniziata senza voto, grigio come
    /// sulla web (lo stato della partita lo dice la pillola).
    private func cifra(_ carattere: Font, solo: Bool) -> some View {
        Text(Self.numero(g)).font(carattere).monospacedDigit().numerico(numeroValore)
            .foregroundStyle(solo ? AnyShapeStyle(Color.testoSecondario) : AnyShapeStyle(.foreground))
    }

    /// Il numero grande come valore, per far scorrere le cifre quando cambia.
    private var numeroValore: Double {
        guard let esito = g.esitoPartita else { return puntiValore }
        return esito.fv ?? 0
    }

    private var avatar: some View {
        AvatarGiocatore(id: g.id, squadra: g.squadra, dimensione: min(lato, 64), nome: g.nome, ruolo: g.ruolo)
    }

    /// `conNumero` falso: la riga senza il numero a destra.
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

    var body: some View {
        if apribile {
            Button { apri(g.id) } label: { contenuto.frame(minHeight: 44).contentShape(Rectangle()) }
                .buttonStyle(StilePressione())
                .origineZoom(g.id, zoom)
                .contextMenu {
                    Button { apri(g.id) } label: { Label(Catalogo.Perche.apriScheda, systemImage: "person.text.rectangle") }
                    Button { UIPasteboard.general.string = g.nome } label: { Label("Copia il nome", systemImage: "doc.on.doc") }
                }
                .accessibilityHint("Apre la scheda del giocatore")
        } else {
            contenuto
        }
    }
}
