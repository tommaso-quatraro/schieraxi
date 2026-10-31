import SwiftUI

/// Una «pedina» sul campo: avatar con il fantavoto atteso in un cartellino, il cognome sotto. Un anello arancio avverte che non è titolare sicuro.
struct PedinaCampo: View {
    let g: Giocatore
    var diametro: CGFloat = 44
    /// true nell'immagine da condividere: colori fissi (sempre su sfondo scuro).
    var perImmagine = false
    /// Nel campo a video un tocco apre la scheda del giocatore (nell'immagine da condividere no).
    var apribile = false
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.spazioZoom) private var zoom

    private var incerto: Bool { g.titolarita != nil && g.titolarita != "titolare" }

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
        VStack(spacing: 3) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, indice: nil, dimensione: diametro, nome: g.nome, ruolo: g.ruolo)
                .overlay(Circle().strokeBorder(incerto ? Color.attenzione : Color.white.opacity(0.0), lineWidth: 3))
                .overlay(alignment: .topTrailing) {
                    Text(Formato.punti(g.fvAtteso))
                        .font(.system(size: max(10, diametro * 0.26), weight: .heavy, design: .rounded)).monospacedDigit()
                        .foregroundStyle(.black)
                        .padding(.horizontal, 4)
                        .background(Color.ruolo(g.ruolo), in: Capsule())
                        .shadow(color: .black.opacity(0.3), radius: 2, y: 1)
                        .numerico(g.fvAtteso ?? 0)
                        .offset(x: 6, y: -4)
                }
            Text(g.nomeCorto)
                .font(.system(size: perImmagine ? 12 : 12, weight: .semibold))
                .foregroundStyle(.white)
                .lineLimit(1).minimumScaleFactor(0.6)
                .shadow(color: .black.opacity(0.5), radius: 1)
            Text("\(Formato.percento(g.pVoto))% · \(ColoriSquadra.sigla(g.avversario))\(g.inCasa == false ? " (f)" : "")")
                .font(.system(size: 9.5))
                .foregroundStyle(.white.opacity(0.8))
                .lineLimit(1).minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(g.nome), \(nomeRuolo(g.ruolo)), fantavoto atteso \(Formato.punti(g.fvAtteso)), gioca al \(Formato.percento(g.pVoto)) per cento")
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
    let punti: Double
    let titolari: [Giocatore]
    let panchina: [Giocatore]

    var body: some View {
        VStack(spacing: 10) {
            VStack(spacing: 2) {
                Text("\(TempiLega.etichetta(serieA: giornata, lega: giornataLega)) · \(modulo)").font(.system(size: 22, weight: .bold, design: .rounded)).foregroundStyle(.white)
                Text("\(squadra) · \(Formato.punti(punti)) punti attesi").font(.system(size: 13, weight: .medium)).foregroundStyle(.white.opacity(0.7))
            }
            CampoFormazione(titolari: titolari, diametro: 42, perImmagine: true)
            Text("Panchina: " + panchina.map(\.nomeCorto).joined(separator: ", "))
                .font(.system(size: 12, weight: .medium)).foregroundStyle(.white.opacity(0.75))
                .multilineTextAlignment(.center).lineLimit(3)
                .frame(maxWidth: .infinity)
            Spacer(minLength: 0)
            Text("Il numero nel cerchio è il fantavoto atteso").font(.system(size: 10, weight: .semibold)).foregroundStyle(Color(red: 0.24, green: 0.86, blue: 0.59))
        }
        .padding(.horizontal, 14).padding(.top, 18).padding(.bottom, 12)
        .frame(width: 360, height: 490)
        .background(LinearGradient(colors: [Color(red: 0.05, green: 0.14, blue: 0.09), Color(red: 0.03, green: 0.06, blue: 0.04)], startPoint: .top, endPoint: .bottom))
        .environment(\.colorScheme, .dark)
    }
}
