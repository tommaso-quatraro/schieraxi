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

/// L'avatar di un giocatore, UGUALE PER TUTTI: il volto illustrato generato dal suo codice (`AvatarVolto`, specifica in
/// docs/AVATAR.md del repository web: stesso id, stesso volto su web, iOS e Android), nel cerchio con i colori della squadra.
/// Niente foto e niente rete. Con `indice` (0-100) ha attorno l'anello dell'indice e, se `conNumero`, il numero in un cartellino.
/// I portieri (`ruolo` P) hanno la maglia grigia e i guanti. Per VoiceOver è nascosto: il significato sta già nel testo della riga.
struct AvatarGiocatore: View {
    let id: Int?
    let squadra: String?
    var indice: Double? = nil
    var dimensione: CGFloat = 46
    var conNumero = true
    /// Non serve più al disegno (prima per le iniziali): resta per non cambiare i punti di chiamata.
    var nome: String? = nil
    var ruolo: String? = nil
    /// L'anello si riempie da zero quando l'avatar compare. Con «Ridurre movimento» compare con una dissolvenza.
    @State private var anello: Double = 0
    @State private var comparso = false
    @Environment(\.accessibilityReduceMotion) private var ridotto
    /// I tratti di tutti i giocatori (versione 2): quando arrivano i volti si ridisegnano.
    @ObservedObject private var tratti = DepositoTratti.condiviso
    /// 1 a misura normale; cresce con il testo grande (Dynamic Type), fino a 1,4 volte.
    @ScaledMetric(relativeTo: .caption2) private var scalaTesto: CGFloat = 1

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
            AvatarVolto(id: id ?? 0, squadra: squadra, portiere: ruolo?.uppercased() == "P", tratti: id.flatMap { tratti.tratti(per: $0) })
                .padding(indice == nil ? 0 : spessore + 1.5)
                // ingresso breve con molla (scala da .86 a 1); con «Ridurre movimento» solo dissolvenza
                .scaleEffect(comparso || ridotto ? 1 : 0.86)
                .opacity(comparso ? 1 : 0)
        }
        .frame(width: dimensione, height: dimensione)
        .overlay(alignment: .bottomTrailing) {
            if conNumero, let indice {
                Text("\(Formato.intero(indice))")
                    .font(.system(size: max(9, dimensione * 0.24) * min(scalaTesto, 1.4), weight: .heavy, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.white)
                    .padding(.horizontal, 4)
                    .background(Color.indice(indice), in: Capsule())
                    .overlay(Capsule().strokeBorder(Color.black.opacity(0.25), lineWidth: 0.5))
                    .offset(x: dimensione * 0.1, y: dimensione * 0.1)
            }
        }
        .task { await DepositoTratti.condiviso.caricaSeServe() }
        .onAppear {
            withAnimation(.smooth(duration: 0.9)) { anello = frazione }
            withAnimation(ridotto ? .easeInOut(duration: 0.3) : .spring(duration: 0.4, bounce: 0.15)) { comparso = true }
        }
        .onChange(of: indice) { _, _ in withAnimation(Tema.morbida) { anello = frazione } }
        .accessibilityHidden(true)
    }

    /// Le iniziali del cognome (due lettere): «Leonel Marténi» → «MA», «Di Corvara» → «DI», «Pelayo» → «PE».
    static func iniziali(_ nome: String?) -> String? {
        let parole = (nome ?? "").split(whereSeparator: { $0 == " " }).map(String.init)
        guard let primo = parole.first else { return nil }
        let cognome = parole.count > 1 ? parole.dropFirst().joined() : primo
        let lettere = cognome.filter { $0.isLetter }
        guard !lettere.isEmpty else { return nil }
        return String(lettere.prefix(2)).uppercased()
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
