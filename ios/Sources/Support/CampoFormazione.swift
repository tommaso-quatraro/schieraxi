import SwiftUI

/// Una «pedina» sul campo, da leggere senza legenda: il volto (fondo con i colori della SUA squadra) con il fantavoto atteso in una
/// pillola scura, il cognome, «gioca 85%» (sotto il 70%: pillola arancio con l'icona di avviso; a partita iniziata il fantavoto
/// preso o lo stato della partita, «Rinviata» per una partita rinviata: `EsitoPedina`) e l'avversario («vs NAP» in casa,
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
            // intero e a capo, mai rimpicciolito (12 punti al minimo): vedi `CognomePedina`
            CognomePedina(nome: g.nomeCorto)
            // a partita iniziata o rinviata l'esito al posto di «gioca N%», come la web (`EsitoPedina`, #283 #284)
            if let esito = g.esitoPedina {
                RigaGioca(testo: esito, incerto: false)
            } else if let gioca = LetturaPedina.gioca(g.pVoto) {
                RigaGioca(testo: gioca, incerto: LetturaPedina.incerto(g.pVoto))
            }
            RigaAvversario(avversario: g.avversario, inCasa: g.inCasa)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(g.vocePedina)
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
/// Se la pedina è stretta va a capo tra le parole («⚠ gioca» sopra «45%»), come la web: il carattere non si rimpicciolisce.
struct RigaGioca: View {
    let testo: String
    let incerto: Bool

    var body: some View {
        Group {
            if incerto {
                // l'icona dentro il testo, così va a capo insieme alle parole
                Text("\(Image(systemName: "exclamationmark.triangle.fill")) \(testo)")
                    .foregroundStyle(.black)
                    .padding(.horizontal, 5).padding(.vertical, 1)
                    // arancio fisso (quello del tema scuro): il prato è scuro anche nel tema chiaro, e il nero sopra si legge bene.
                    // Su una riga è una capsula (il raggio supera metà altezza e si ferma lì); su due righe angoli tondi, come la web.
                    .background(Color(red: 1.0, green: 0.69, blue: 0.29), in: .rect(cornerRadius: 8))
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

/// «vs [NAP]» in casa, «@ [NAP]» in trasferta. Il distintivo ha i colori sociali e la sigla: mai lo stemma ufficiale.
/// Se la pedina è stretta «vs» va sopra la sigla, come la web: niente testo rimpicciolito.
struct RigaAvversario: View {
    let avversario: String?
    let inCasa: Bool?

    var body: some View {
        if let avversario, !avversario.isEmpty {
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 3) {
                    prefisso
                    DistintivoSquadra(squadra: avversario)
                }
                VStack(spacing: 1) {
                    prefisso
                    DistintivoSquadra(squadra: avversario)
                }
            }
            .dynamicTypeSize(...DynamicTypeSize.xLarge)
        }
    }

    @ViewBuilder private var prefisso: some View {
        if let prefisso = LetturaPedina.prefisso(inCasa: inCasa) {
            Text(prefisso).font(.caption2.weight(.bold)).foregroundStyle(.white)
                .shadow(color: .black.opacity(0.5), radius: 1)
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

/// L'immagine da condividere (si disegna con `ImageRenderer`): titolo, campo con i titolari, panchina. Sempre su fondo scuro,
/// larga 360 punti e alta almeno 490: se i cognomi vanno a capo il campo cresce e l'immagine con lui. Alta 490 fissi tagliava
/// già il titolo e la legenda (foto `formazione-immagine` del 3/11/2026, issue #274).
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
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
            Text("Il numero sotto il volto è il fantavoto atteso · vs in casa, @ in trasferta").font(.system(size: 10, weight: .semibold)).foregroundStyle(Color(red: 0.24, green: 0.86, blue: 0.59))
        }
        .fixedSize(horizontal: false, vertical: true)   // alta quanto serve: niente righe tagliate per stare in 490 punti
        .padding(.horizontal, 14).padding(.top, 18).padding(.bottom, 12)
        .frame(width: 360)
        .frame(minHeight: 490, alignment: .top)
        .background(LinearGradient(colors: [Color(red: 0.05, green: 0.14, blue: 0.09), Color(red: 0.03, green: 0.06, blue: 0.04)], startPoint: .top, endPoint: .bottom))
        .environment(\.colorScheme, .dark)
    }
}
