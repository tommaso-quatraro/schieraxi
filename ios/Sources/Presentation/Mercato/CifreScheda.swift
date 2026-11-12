import SwiftUI

/// Le cifre in testa alla scheda del giocatore, come `cifre-scheda` della web (#616): a sinistra il fantavoto atteso «se gioca»
/// grande e neutro (a partita finita il fantavoto preso, o lo stato della partita); accanto «gioca N%», arancio fra 50 e 79 e
/// rosso sotto 50, con lo stato a parole sotto (a partita in corso lo stato della partita). Testi e numeri: `LetturaScheda.cifre`.
struct CifreScheda: View {
    let cifre: LetturaScheda.Cifre
    /// Grande, ma segue Dynamic Type.
    @ScaledMetric(relativeTo: .largeTitle) private var misuraNumero: CGFloat = 54

    var body: some View {
        switch cifre {
        case .nessunaPrevisione:
            Label(Catalogo.Mercato.nessunaPrevisionePer, systemImage: "info.circle")
                .font(.subheadline)
                .foregroundStyle(Color.attenzione)
                .fixedSize(horizontal: false, vertical: true)
        case .cifre(let prima, let accanto):
            FilaAdattiva(allineamento: .top, spazio: 20) {
                cifraPrima(prima)
                if let accanto { cifraAccanto(accanto) }
                Spacer(minLength: 0)
            }
        }
    }

    /// «Fantavoto atteso, se gioca», come la web.
    static let nomeAtteso = Catalogo.Mercato.fantavotoAtteso + ", " + Catalogo.Formazione.seGioca

    private var carattereGrande: Font {
        .system(size: min(misuraNumero, 110), weight: .bold, design: .rounded)
    }

    @ViewBuilder
    private func cifraPrima(_ prima: LetturaScheda.Prima) -> some View {
        switch prima {
        case .atteso(let fv):
            VStack(alignment: .leading, spacing: 0) {
                Text(Self.nomeAtteso).font(.subheadline).foregroundStyle(Color.testoSecondario)
                FantavotoCheSale(valore: fv).font(carattereGrande).foregroundStyle(.primary)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(Self.nomeAtteso + ": " + Formato.punti(fv))
        case .preso(let fv):
            VStack(alignment: .leading, spacing: 0) {
                Text(Catalogo.Mercato.fantavoto).font(.subheadline).foregroundStyle(Color.testoSecondario)
                Text(Formato.punti(fv)).font(carattereGrande).monospacedDigit()
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(Catalogo.Mercato.fantavoto + " " + Formato.punti(fv))
        case .stato(let testo):
            Text(testo).font(.title2.bold())
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    @ViewBuilder
    private func cifraAccanto(_ accanto: LetturaScheda.Accanto) -> some View {
        switch accanto {
        case .stato(let testo):
            Text(testo).font(.title2.bold())
                .fixedSize(horizontal: false, vertical: true)
        case .gioca(let percento, let livello, let parola):
            VStack(alignment: .leading, spacing: 4) {
                Text(Catalogo.Mercato.gioca).font(.subheadline).foregroundStyle(Color.testoSecondario)
                Text(String(percento) + "%").font(.title.bold()).monospacedDigit()
                    .foregroundStyle(Self.colore(livello))
                if let parola {
                    PillolaEtichetta(etichetta: Etichetta(testo: parola.testo, tono: parola.classe == .rossa ? .negativo : .attenzione))
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(Self.voceGioca(percento: percento, parola: parola))
        }
    }

    /// Il colore di «gioca N%»: solo sotto l'80% (il numero lo dice comunque).
    static func colore(_ livello: SogliaGioca.Livello) -> Color {
        switch livello {
        case .sicuro: return .primary
        case .medio: return .attenzione
        case .basso: return .malus
        }
    }

    /// Per VoiceOver: «gioca all'85 per cento, In dubbio», con le parole della pedina della web (`formazione.voce_gioca`,
    /// `formazione.voce_gioca_v` davanti ai numeri che si leggono con una vocale).
    static func voceGioca(percento: Int, parola: ParolaStato?) -> String {
        let vocale = percento == 1 || percento == 8 || percento == 11 || (80...89).contains(percento)
        let numero = String(percento)
        let gioca = vocale ? Catalogo.Formazione.voceGiocaV(p: numero) : Catalogo.Formazione.voceGioca(p: numero)
        return [gioca, parola?.testo].compactMap { $0 }.joined(separator: ", ")
    }
}

#Preview("Cifre della scheda") {
    let json = #"{"id": 7, "nome": "Leonel Marténi", "ruolo": "A", "squadra": "inter", "fv_atteso": 7.9, "p_voto": 0.62, "dubbio": true}"#
    if let g: Giocatore = try? Decodifica.decodifica(Data(json.utf8)) {
        CifreScheda(cifre: LetturaScheda.cifre(g)).padding()
    }
}
