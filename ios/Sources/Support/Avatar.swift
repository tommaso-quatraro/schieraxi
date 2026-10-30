import SwiftUI

extension Color {
    /// Colore da un esadecimale RRGGBB («1e71b8»).
    init(esadecimale: String) {
        var n: UInt64 = 0
        Scanner(string: esadecimale).scanHexInt64(&n)
        self.init(red: Double((n >> 16) & 0xff) / 255, green: Double((n >> 8) & 0xff) / 255, blue: Double(n & 0xff) / 255)
    }

    /// Colore dell'indice 0-100: alto verde, medio arancio, basso rosso (come gli anelli della web app).
    static func indice(_ valore: Double) -> Color {
        valore >= 70 ? Color.verde : valore >= 40 ? .orange : .red
    }
}

/// La sagoma di una maglietta (le stesse coordinate della web app, su un quadrato 40 x 40).
struct SagomaMaglia: Shape {
    func path(in rect: CGRect) -> Path {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint {
            CGPoint(x: rect.minX + rect.width * x / 40, y: rect.minY + rect.height * y / 40)
        }
        var percorso = Path()
        percorso.move(to: p(13, 6))
        percorso.addLine(to: p(5, 11))
        percorso.addLine(to: p(8, 18))
        percorso.addLine(to: p(12, 16))
        percorso.addLine(to: p(12, 34))
        percorso.addLine(to: p(28, 34))
        percorso.addLine(to: p(28, 16))
        percorso.addLine(to: p(32, 18))
        percorso.addLine(to: p(35, 11))
        percorso.addLine(to: p(27, 6))
        percorso.addCurve(to: p(13, 6), control1: p(25, 9), control2: p(15, 9))
        percorso.closeSubpath()
        return percorso
    }
}

/// Colletto e maniche della maglietta (nel colore secondario).
struct DettagliMaglia: Shape {
    func path(in rect: CGRect) -> Path {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint {
            CGPoint(x: rect.minX + rect.width * x / 40, y: rect.minY + rect.height * y / 40)
        }
        var percorso = Path()
        percorso.move(to: p(13, 6))
        percorso.addCurve(to: p(27, 6), control1: p(15, 9), control2: p(25, 9))
        percorso.move(to: p(5, 11))
        percorso.addLine(to: p(8, 18))
        percorso.move(to: p(35, 11))
        percorso.addLine(to: p(32, 18))
        return percorso
    }
}

/// La maglietta con i colori della squadra (slug come `inter`; grigia se la squadra non si conosce).
struct MagliaView: View {
    let squadra: String?

    var body: some View {
        let colori = ColoriSquadra.esadecimali(squadra)
        ZStack {
            SagomaMaglia().fill(Color(esadecimale: colori.0))
            SagomaMaglia().stroke(Color.black.opacity(0.28), lineWidth: 1)
            DettagliMaglia().stroke(Color(esadecimale: colori.1), style: StrokeStyle(lineWidth: 2.2, lineCap: .round))
        }
        .aspectRatio(1, contentMode: .fit)
    }
}

/// L'avatar di un giocatore, UGUALE PER TUTTI: un cerchio con la sfumatura dei colori della squadra e, sopra, il volto ritagliato
/// (PNG senza sfondo, dal server: volto e spalle, sempre la stessa inquadratura) oppure, per chi non ha la foto, la stessa sagoma
/// con le iniziali del cognome. Con `indice` (0-100) ha attorno l'anello dell'indice e, se `conNumero`, il numero in un cartellino.
/// Lega > Aspetto > «Foto dei giocatori» (acceso di norma): spento, tutti con la sagoma e nessuna richiesta di foto al server.
/// Per VoiceOver è nascosto: il significato sta già nel testo della riga.
struct AvatarGiocatore: View {
    let id: Int?
    let squadra: String?
    var indice: Double? = nil
    var dimensione: CGFloat = 46
    var conNumero = true
    /// Il nome del giocatore: servono le iniziali del cognome per chi non ha la foto.
    var nome: String? = nil
    @ObservedObject private var immagini = Immagini.condivise
    @AppStorage("fotoGiocatori") private var conFoto = true
    /// L'anello si riempie da zero quando l'avatar compare.
    @State private var anello: Double = 0

    private var spessore: CGFloat { max(2.5, dimensione / 16) }
    private var frazione: Double { min(1, max(0, (indice ?? 0) / 100)) }

    var body: some View {
        ZStack {
            if let indice {
                Circle().stroke(Color.primary.opacity(0.12), lineWidth: spessore)
                Circle()
                    .trim(from: 0, to: CGFloat(anello))
                    .stroke(Color.indice(indice), style: StrokeStyle(lineWidth: spessore, lineCap: .round))
                    .rotationEffect(.degrees(-90))
            }
            interno
                .padding(indice == nil ? 0 : spessore + 1.5)
        }
        .frame(width: dimensione, height: dimensione)
        .overlay(alignment: .bottomTrailing) {
            if conNumero, let indice {
                Text("\(Formato.intero(indice))")
                    .font(.system(size: max(9, dimensione * 0.24), weight: .heavy, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.white)
                    .padding(.horizontal, 4)
                    .background(Color.indice(indice), in: Capsule())
                    .overlay(Capsule().strokeBorder(Color.black.opacity(0.25), lineWidth: 0.5))
                    .offset(x: dimensione * 0.1, y: dimensione * 0.1)
            }
        }
        .task(id: id) {
            if conFoto, let id { await immagini.caricaFoto(id) }
        }
        .onAppear { withAnimation(.smooth(duration: 0.9)) { anello = frazione } }
        .onChange(of: indice) { _, _ in withAnimation(Tema.morbida) { anello = frazione } }
        .accessibilityHidden(true)
    }

    private var foto: UIImage? {
        guard conFoto, let id else { return nil }
        return immagini.memoriaFoto(id)
    }

    @ViewBuilder
    private var interno: some View {
        let colori = ColoriSquadra.esadecimali(squadra)
        let base = Color(esadecimale: colori.0)
        GeometryReader { g in
            let lato = min(g.size.width, g.size.height)
            ZStack(alignment: .bottom) {
                // lo stesso fondo per tutti: la sfumatura della squadra, più scura in basso (contrasto per le iniziali)
                Circle().fill(LinearGradient(colors: [base.mix(with: .white, by: 0.18), base.mix(with: .black, by: 0.5)],
                                             startPoint: .top, endPoint: .bottom))
                if let foto {
                    // stessa inquadratura per tutti: il ritaglio occupa l'86% del cerchio, appoggiato in basso
                    Image(uiImage: foto)
                        .resizable()
                        .scaledToFit()
                        .frame(width: lato * 0.86, height: lato * 0.86)
                        .transition(.opacity)
                } else {
                    SagomaBusto()
                        .fill(Color.white.opacity(0.26))
                        .frame(width: lato * 0.8, height: lato * 0.8)
                    if let sigla = Self.iniziali(nome) {
                        Text(sigla)
                            .font(.system(size: max(8, lato * 0.26), weight: .bold, design: .rounded))
                            .monospacedDigit()
                            .foregroundStyle(.white)
                            .shadow(color: .black.opacity(0.45), radius: 1.5, y: 0.5)
                            .minimumScaleFactor(0.5)
                            .lineLimit(1)
                            .padding(.bottom, lato * 0.13)
                    }
                }
            }
            .frame(width: lato, height: lato)
        }
        .aspectRatio(1, contentMode: .fit)
        .animation(.easeOut(duration: 0.3), value: immagini.versione)
        .clipShape(Circle())
    }

    /// Le iniziali del cognome (due lettere): «Giocatore 045» → «MA», «Di Lorenzo» → «DI», «Pedro» → «PE».
    static func iniziali(_ nome: String?) -> String? {
        let parole = (nome ?? "").split(whereSeparator: { $0 == " " }).map(String.init)
        guard let primo = parole.first else { return nil }
        let cognome = parole.count > 1 ? parole.dropFirst().joined() : primo
        let lettere = cognome.filter { $0.isLetter }
        guard !lettere.isEmpty else { return nil }
        return String(lettere.prefix(2)).uppercased()
    }
}

/// La sagoma stilizzata di testa e spalle, uguale per tutti i giocatori senza foto.
struct SagomaBusto: Shape {
    func path(in rect: CGRect) -> Path {
        let w = rect.width, h = rect.height
        var p = Path()
        // testa
        p.addEllipse(in: CGRect(x: rect.minX + w * 0.32, y: rect.minY + h * 0.08, width: w * 0.36, height: h * 0.40))
        // spalle
        p.addRoundedRect(in: CGRect(x: rect.minX + w * 0.08, y: rect.minY + h * 0.56, width: w * 0.84, height: h * 0.60),
                         cornerSize: CGSize(width: w * 0.36, height: h * 0.30))
        return p
    }
}

/// Stemma o maglia di una squadra della lega (caricati dall'utente). Senza immagine: un cerchio con l'iniziale del nome
/// (o niente, con `nascondiSeMancante`).
struct StemmaSquadra: View {
    let nome: String
    var tipo = "stemma"
    var dimensione: CGFloat = 40
    var nascondiSeMancante = false
    @ObservedObject private var immagini = Immagini.condivise

    var body: some View {
        Group {
            if let img = immagini.memoriaSquadra(nome, tipo: tipo) {
                Image(uiImage: img).resizable().scaledToFit().frame(width: dimensione, height: dimensione)
            } else if nascondiSeMancante {
                Color.clear.frame(width: 1, height: 1)   // il caricamento parte lo stesso: appena arriva l'immagine compare
            } else {
                Text(String(nome.trimmingCharacters(in: .whitespaces).prefix(1)).uppercased())
                    .font(.system(size: dimensione * 0.45, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.verde)
                    .frame(width: dimensione, height: dimensione)
                    .background(Color.verde.opacity(0.18), in: Circle())
            }
        }
        .task(id: immagini.squadre[nome]) {
            await immagini.caricaSquadra(nome, tipo: tipo)
        }
        .accessibilityHidden(true)
    }
}
