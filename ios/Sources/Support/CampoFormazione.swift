import SwiftUI

/// Una «pedina» sul campo, da leggere senza legenda: il volto (fondo con i colori della SUA squadra) con il fantavoto atteso in una
/// pillola scura, il cognome, «gioca 85%» (sotto il 70%: pillola arancio con l'icona di avviso) e l'avversario («vs NAP» in casa,
/// «@ NAP» in trasferta) con un distintivo nei colori sociali. Niente anelli colorati con un significato nascosto. Testi in `LetturaPedina`.
struct PedinaCampo: View {
    let g: Giocatore
    var diametro: CGFloat = 44
    /// true nell'immagine da condividere: colori fissi (sempre su sfondo scuro).
    var perImmagine = false
    /// Nel campo a video un tocco apre la scheda del giocatore (nell'immagine da condividere no).
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
        VStack(spacing: 2) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, indice: nil, dimensione: diametro, nome: g.nome, ruolo: g.ruolo)
                .overlay(alignment: .bottom) {
                    PillolaFantavoto(valore: g.fvAtteso, diametro: diametro).offset(y: 8)
                }
                .padding(.bottom, 8)
            Text(g.nomeCorto)
                .font(.caption.weight(.semibold))   // 12 pt a misura normale, segue Dynamic Type
                .dynamicTypeSize(...DynamicTypeSize.xxLarge)   // ma con un tetto: il campo ha spazio fisso
                .foregroundStyle(.white)
                .lineLimit(1).minimumScaleFactor(0.6)
                .shadow(color: .black.opacity(0.5), radius: 1)
            if let gioca = LetturaPedina.gioca(g.pVoto) {
                RigaGioca(testo: gioca, incerto: LetturaPedina.incerto(g.pVoto))
            }
            RigaAvversario(avversario: g.avversario, inCasa: g.inCasa)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(LetturaPedina.voce(nome: g.nome, ruolo: nomeRuolo(g.ruolo), fvAtteso: g.fvAtteso, pVoto: g.pVoto,
                                               avversario: g.avversario, inCasa: g.inCasa))
    }
}

/// Il fantavoto atteso sotto il volto: pillola scura con il numero bianco, uguale per tutti i ruoli (il ruolo si legge dalla fila).
struct PillolaFantavoto: View {
    let valore: Double?
    var diametro: CGFloat = 44
    /// 1 a misura normale; cresce con il testo grande (Dynamic Type), fino a 1,4 volte.
    @ScaledMetric(relativeTo: .caption2) private var scalaTesto: CGFloat = 1

    var body: some View {
        Text(Formato.punti(valore))
            .font(.system(size: max(10, diametro * 0.27) * min(scalaTesto, 1.4), weight: .heavy, design: .rounded)).monospacedDigit()
            .foregroundStyle(.white)
            .padding(.horizontal, 6).padding(.vertical, 1)
            .background(Color(red: 0.03, green: 0.06, blue: 0.04).opacity(0.92), in: Capsule())
            .overlay(Capsule().strokeBorder(Color.white.opacity(0.35), lineWidth: 0.5))
            .numerico(valore ?? 0)
    }
}

/// «gioca 85%»: bianco se è quasi sicuro di giocare; sotto il 70% pillola arancio con l'icona di avviso (non solo il colore).
struct RigaGioca: View {
    let testo: String
    let incerto: Bool

    var body: some View {
        Group {
            if incerto {
                HStack(spacing: 2) {
                    Image(systemName: "exclamationmark.triangle.fill").imageScale(.small)
                    Text(testo)
                }
                .foregroundStyle(.black)
                .padding(.horizontal, 5).padding(.vertical, 1)
                // arancio fisso (quello del tema scuro): il prato è scuro anche nel tema chiaro, e il nero sopra si legge bene
                .background(Color(red: 1.0, green: 0.69, blue: 0.29), in: Capsule())
            } else {
                Text(testo)
                    .foregroundStyle(.white.opacity(0.95))   // sul prato a 0,8 il contrasto non bastava (controllo di accessibilità)
                    .shadow(color: .black.opacity(0.5), radius: 1)
            }
        }
        .font(.caption2.weight(.semibold))   // segue Dynamic Type (a misura normale 11 pt; la scala minima lo stringe se serve)
        .dynamicTypeSize(...DynamicTypeSize.xLarge)   // tetto più basso: il campo non cambia larghezza
        .lineLimit(1).minimumScaleFactor(0.6)
    }
}

/// «vs [NAP]» in casa, «@ [NAP]» in trasferta. Il distintivo ha i colori sociali e la sigla: mai lo stemma ufficiale.
struct RigaAvversario: View {
    let avversario: String?
    let inCasa: Bool?

    var body: some View {
        if let avversario, !avversario.isEmpty {
            HStack(spacing: 3) {
                if let prefisso = LetturaPedina.prefisso(inCasa: inCasa) {
                    Text(prefisso).font(.caption2.weight(.bold)).foregroundStyle(.white)
                        .shadow(color: .black.opacity(0.5), radius: 1)
                }
                DistintivoSquadra(squadra: avversario)
            }
            .dynamicTypeSize(...DynamicTypeSize.xLarge)
            .lineLimit(1).minimumScaleFactor(0.6)
        }
    }
}

/// La sigla di tre lettere di una squadra di Serie A nei suoi colori (fondo il primo colore, bordo il secondo, testo scuro o chiaro
/// secondo il contrasto). Sostituisce gli stemmi ufficiali, che sono marchi registrati.
struct DistintivoSquadra: View {
    let squadra: String?

    var body: some View {
        let colori = ColoriSquadra.esadecimali(squadra)
        Text(ColoriSquadra.sigla(squadra))
            .font(.caption2.weight(.heavy)).monospaced()
            .foregroundStyle(LetturaPedina.testoScuro(suEsadecimale: colori.0) ? Color.black : Color.white)
            .padding(.horizontal, 4).padding(.vertical, 1)
            .background(Color(esadecimale: colori.0), in: RoundedRectangle(cornerRadius: 4, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 4, style: .continuous).strokeBorder(Color(esadecimale: colori.1), lineWidth: 1))
    }
}

/// La legenda del campo: gli stessi pezzi delle pedine, su un ritaglio di prato, con la spiegazione accanto.
/// Testi uguali alla web app (`formazione.legenda_*` in testi.js). Con `chiudi` ha il pulsante «Ho capito» (la prima volta,
/// sopra il campo); senza, sta nel riquadro che si apre con «Cosa vuol dire».
struct LegendaCampo: View {
    var chiudi: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            voce("fantavoto atteso se gioca, con le regole della tua lega") {
                PillolaFantavoto(valore: 6.8)
            }
            voce("probabilità che giochi") { RigaGioca(testo: "gioca 85%", incerto: false) }
            voce("sotto il 70%: il posto è a rischio") { RigaGioca(testo: "gioca 45%", incerto: true) }
            voce("gioca in casa contro la squadra della sigla") { RigaAvversario(avversario: "napoli", inCasa: true) }
            voce("gioca fuori casa contro la squadra della sigla") { RigaAvversario(avversario: "napoli", inCasa: false) }
            voce("Il volto ha i colori della sua squadra. Tocca il fantavoto atteso per sapere perché è quello.") {
                AvatarGiocatore(id: 4321, squadra: "napoli", indice: nil, dimensione: 30, nome: nil, ruolo: "C")
            }
            if let chiudi {
                Button(action: chiudi) {
                    Text("Ho capito").font(.subheadline.weight(.semibold)).frame(minHeight: 44).padding(.horizontal, 8)
                }
                .pulsanteVetro()
            }
        }
    }

    private func voce<Esempio: View>(_ testo: String, @ViewBuilder esempio: () -> Esempio) -> some View {
        HStack(spacing: 12) {
            esempio()
                .frame(width: 92, height: 36)
                .background(Color(red: 0.10, green: 0.40, blue: 0.24), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                .environment(\.colorScheme, .dark)
                .accessibilityHidden(true)
            Text(testo).font(.footnote).fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
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
    var perImmagine = false

    /// Nel campo a video le pedine entrano una dopo l'altra e un tocco apre la scheda; nell'immagine da condividere no.
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

    @ViewBuilder
    private func pedina(_ g: Giocatore) -> some View {
        if perImmagine {
            PedinaCampo(g: g, diametro: diametro, perImmagine: true)
        } else {
            PedinaCampo(g: g, diametro: diametro, perImmagine: false, apribile: apribile)
                .transizione(.scale(scale: 0.6).combined(with: .opacity))
        }
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

/// L'immagine da condividere (si disegna con `ImageRenderer`): titolo, campo con i titolari, panchina. Sempre su fondo scuro, 360 x 450 punti.
struct ImmagineFormazione: View {
    let giornata: Int
    var giornataLega: Int? = nil
    let squadra: String
    let modulo: String
    /// nil se i punti di una formazione a mano non sono ancora calcolati: nell'immagine non si scrivono.
    let punti: Double?
    let titolari: [Giocatore]
    let panchina: [Giocatore]

    var body: some View {
        VStack(spacing: 10) {
            VStack(spacing: 2) {
                Text("\(TempiLega.etichetta(serieA: giornata, lega: giornataLega)) · \(modulo)").font(.system(size: 22, weight: .bold, design: .rounded)).foregroundStyle(.white)
                Text([squadra, punti.map { "\(Formato.punti($0)) punti attesi" }].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")).font(.system(size: 13, weight: .medium)).foregroundStyle(.white.opacity(0.85))
            }
            CampoFormazione(titolari: titolari, diametro: 42, perImmagine: true)
            Text("Panchina: " + panchina.map(\.nomeCorto).joined(separator: ", "))
                .font(.system(size: 12, weight: .medium)).foregroundStyle(.white.opacity(0.85))
                .multilineTextAlignment(.center).lineLimit(3)
                .frame(maxWidth: .infinity)
            Spacer(minLength: 0)
            Text("Il numero sotto il volto è il fantavoto atteso · vs in casa, @ in trasferta").font(.system(size: 10, weight: .semibold)).foregroundStyle(Color(red: 0.24, green: 0.86, blue: 0.59))
        }
        .padding(.horizontal, 14).padding(.top, 18).padding(.bottom, 12)
        .frame(width: 360, height: 490)
        .background(LinearGradient(colors: [Color(red: 0.05, green: 0.14, blue: 0.09), Color(red: 0.03, green: 0.06, blue: 0.04)], startPoint: .top, endPoint: .bottom))
        .environment(\.colorScheme, .dark)
    }
}
