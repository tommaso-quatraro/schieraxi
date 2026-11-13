import SwiftUI

/// Una «pedina» sul campo, come `pedina` della web (#616, #673) con in più il volto (decisione 2 del proprietario): il volto (fondo
/// con i colori della SUA squadra) con il fantavoto atteso in una pillola scura (a partita finita quello preso; vuota, solo il bordo,
/// quando a formazione chiusa il numero è ancora l'atteso), il cognome, «gioca N%» solo sotto l'80% (pillola arancio con l'icona di
/// avviso, rossa sotto il 50%, `SogliaGioca`), lo stato a parole («In dubbio», «Infortunato» in rosso), a partita cominciata il suo
/// stato, a formazione chiusa quando gioca chi deve ancora giocare. Niente avversario: sta nella scheda. Testi e frase per VoiceOver
/// in `LetturaPedina.contenuto`.
struct PedinaCampo: View {
    let g: Giocatore
    var diametro: CGFloat = 44
    /// Un tocco apre la scheda del giocatore.
    var apribile = false
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.spazioZoom) private var zoom

    var body: some View {
        if apribile {
            Button { apri(g.id) } label: { pedina.contentShape(Rectangle()) }
                .buttonStyle(StilePressione())
                .origineZoom(g.id, zoom)
                .accessibilityHint("Apre la scheda del giocatore")
        } else {
            pedina
        }
    }

    private var pedina: some View {
        let c = LetturaPedina.contenuto(g, adesso: Orologio.adesso())
        return VStack(spacing: 2) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, dimensione: diametro, nome: g.nome, ruolo: g.ruolo)
                .overlay(alignment: .bottom) {
                    PillolaFantavoto(valore: c.valore, vuota: c.attesa, diametro: diametro).offset(y: 8)
                }
                .padding(.bottom, 8)
            // intero e a capo, mai rimpicciolito (12 punti al minimo): vedi `CognomePedina`
            CognomePedina(nome: g.nomeCorto)
            ForEach(Array(c.pezzi.enumerated()), id: \.offset) { _, pezzo in
                RigaGioca(testo: pezzo.testo, incerto: pezzo.tono != .parola, basso: pezzo.tono == .basso)
            }
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(c.voce)
    }
}

/// Il fantavoto sotto il volto, uguale per tutti i ruoli (il ruolo si legge dalla fila): pillola scura piena con il numero bianco;
/// vuota, solo il bordo bianco, quando il numero è l'atteso a partita cominciata o da giocare a formazione chiusa (`vuota`), come il
/// disco della pedina «attesa» della web: così il fantavoto preso e quello atteso non si confondono. Il fondo della pillola vuota è
/// il verde del prato, non trasparente: sopra il volto la scritta resta leggibile. VoiceOver li distingue già a parole
/// (`LetturaPedina.contenuto`).
struct PillolaFantavoto: View {
    let valore: Double?
    /// Il numero è l'atteso mentre la partita è cominciata o deve ancora giocare (`LetturaPedina.Contenuto.attesa`).
    var vuota = false
    var diametro: CGFloat = 44
    /// 1 a misura normale; cresce con il testo grande (Dynamic Type), fino a 1,4 volte.
    @ScaledMetric(relativeTo: .caption2) private var scalaTesto: CGFloat = 1

    /// Il verde del prato a metà campo (fra i due colori del `CampoFormazione`).
    static let prato = Color(red: 0.10, green: 0.40, blue: 0.24)

    var body: some View {
        Text(Formato.punti(valore))
            .font(.system(size: max(10, diametro * 0.27) * min(scalaTesto, 1.4), weight: vuota ? .bold : .heavy, design: .rounded))
            .monospacedDigit()
            // su una riga sola anche con il testo grande: «10,0» (un fantavoto preso) andava a capo dopo la virgola
            .lineLimit(1)
            .fixedSize()
            .foregroundStyle(.white)
            .padding(.horizontal, 6).padding(.vertical, 1)
            .background(vuota ? Self.prato : Color(red: 0.03, green: 0.06, blue: 0.04).opacity(0.92), in: Capsule())
            .overlay(Capsule().strokeBorder(Color.white.opacity(vuota ? 0.9 : 0.35), lineWidth: vuota ? 1.5 : 0.5))
            .numerico(valore ?? 0)
    }
}

/// «gioca 85%»: bianco se è quasi sicuro di giocare; sotto l'80% pillola arancio con l'icona di avviso (non solo il colore), sotto
/// il 50% rossa (`basso`), come la web. Se la pedina è stretta va a capo tra le parole («⚠ gioca» sopra «45%»), come la web: il
/// carattere non si rimpicciolisce.
struct RigaGioca: View {
    let testo: String
    let incerto: Bool
    /// Sotto il 50%: la pillola è rossa invece che arancio.
    var basso = false

    var body: some View {
        Group {
            if incerto {
                // l'icona dentro il testo, così va a capo insieme alle parole
                Text("\(Image(systemName: "exclamationmark.triangle.fill")) \(testo)")
                    .foregroundStyle(.black)
                    .padding(.horizontal, 5).padding(.vertical, 1)
                    // arancio e rosso fissi (quelli del tema scuro): il prato è scuro anche nel tema chiaro, e il nero sopra si
                    // legge bene. Su una riga è una capsula (il raggio supera metà altezza e si ferma lì); su due righe angoli tondi.
                    .background(basso ? Color(red: 1.0, green: 0.42, blue: 0.37) : Color(red: 1.0, green: 0.69, blue: 0.29),
                                in: .rect(cornerRadius: 8))
            } else {
                Text(testo)
                    .foregroundStyle(.white.opacity(0.95))   // sul prato a 0,8 il contrasto non bastava (controllo di accessibilità)
                    .shadow(color: .black.opacity(0.5), radius: 1)
            }
        }
        .font(.caption2.weight(.semibold))   // segue Dynamic Type: 11 pt a misura normale, mai rimpicciolito
        .dynamicTypeSize(...DynamicTypeSize.xLarge)   // tetto più basso: sotto il cognome, nella stessa larghezza
        .multilineTextAlignment(.center)
        .fixedSize(horizontal: false, vertical: true)
    }
}

extension Color {
    /// Colore del ruolo (portiere, difensore, centrocampista, attaccante).
    static func ruolo(_ ruolo: String) -> Color {
        switch ruolo {
        case "P": return .ruoloP
        case "D": return .ruoloD
        case "C": return .ruoloC
        case "A": return .ruoloA
        default: return .gray
        }
    }
}

/// Il campo da calcio con gli undici titolari in fila per reparto: attaccanti in alto, portiere in basso.
struct CampoFormazione: View {
    let titolari: [Giocatore]
    var diametro: CGFloat = 44

    /// Le pedine entrano una dopo l'altra e un tocco apre la scheda.
    var apribile = false

    var body: some View {
        VStack(spacing: 10) {
            ForEach(["A", "C", "D", "P"], id: \.self) { ruolo in
                HStack(alignment: .top, spacing: 2) {
                    ForEach(titolari.filter { $0.ruolo == ruolo }) { g in
                        pedina(g)
                    }
                }
            }
        }
        .animation(Tema.molla, value: titolari.map(\.id))
        .padding(.vertical, 14).padding(.horizontal, 6)
        .frame(maxWidth: .infinity)
        .background(erba)
        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Campo con i titolari")
    }

    private func pedina(_ g: Giocatore) -> some View {
        PedinaCampo(g: g, diametro: diametro, apribile: apribile)
            .transizione(.scale(scale: 0.6).combined(with: .opacity))
    }

    /// Prato verde a fasce, con le righe del campo (area, cerchio di centrocampo, metà campo).
    private var erba: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0.12, green: 0.45, blue: 0.27), Color(red: 0.08, green: 0.34, blue: 0.20)], startPoint: .top, endPoint: .bottom)
            VStack(spacing: 0) {
                ForEach(0..<10, id: \.self) { i in
                    Rectangle().fill(i % 2 == 0 ? Color.white.opacity(0.05) : Color.clear)
                }
            }
            GeometryReader { g in
                let w = g.size.width, h = g.size.height
                Path { p in
                    p.addRect(CGRect(x: 10, y: 10, width: w - 20, height: h - 20))
                    p.move(to: CGPoint(x: 10, y: h / 2))
                    p.addLine(to: CGPoint(x: w - 10, y: h / 2))
                    p.addEllipse(in: CGRect(x: w / 2 - 34, y: h / 2 - 34, width: 68, height: 68))
                    p.addRect(CGRect(x: w / 2 - 60, y: 10, width: 120, height: 40))
                    p.addRect(CGRect(x: w / 2 - 60, y: h - 50, width: 120, height: 40))
                }
                .stroke(Color.white.opacity(0.28), lineWidth: 1.5)
            }
        }
    }
}
