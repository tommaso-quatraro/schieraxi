import SwiftUI

/// Una riga delle scelte di un cambio, come `riga-gioc` di «Sostituisci» e di «Metti in campo» della web: volto, nome, partita e
/// le etichette della web nel suo ordine (`EtichetteRiga`: lo stato, «gioca N%», le parole in più della riga come «Si passa al …»,
/// «Diffidato», la nota); a destra il numero grande del cambio, se c'è, e sotto il fantavoto atteso. Con il testo molto
/// grande i numeri vanno sotto il nome: affiancati, il nome andava a capo a ogni sillaba. La usano `SceltaSostituto` e
/// `SceltaChiEsce`.
struct RigaCambio: View {
    let giocatore: Giocatore
    /// Il numero grande, già scritto con il segno («+0,9», «−0,4»); nil = niente numero.
    let numero: String?
    /// Il numero è un guadagno: verde.
    let positivo: Bool
    /// Cosa vuol dire il numero, per VoiceOver: si legge subito dopo il numero.
    let voceNumero: String
    /// Cosa fa il tocco, per VoiceOver.
    let suggerimento: String
    /// Le parole in più della riga, dopo «gioca N%» e prima di «Diffidato» («Si passa al 4-4-2»).
    var altre: [String] = []
    @Environment(\.dynamicTypeSize) private var taglia

    var body: some View {
        let pezzi = EtichetteRiga.pezzi(giocatore, inPiu: altre)
        Group {
            if taglia.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 6) {
                    avatar
                    dati(pezzi)
                    numeri(allineamento: .leading)
                }
            } else {
                HStack(alignment: .center, spacing: 10) {
                    avatar
                    dati(pezzi)
                    Spacer(minLength: 6)
                    numeri(allineamento: .trailing)
                }
            }
        }
        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(voce(pezzi))
        .accessibilityHint(suggerimento)
        // Controllo vocale: basta dire il nome, non tutta la riga
        .accessibilityInputLabels([giocatore.nome])
    }

    /// Il colore di un'etichetta, come le pillole della web: arancio, rosso o grigio (vedi `EtichetteRiga`).
    static func colore(_ tono: LetturaPedina.Pezzo.Tono) -> Color {
        switch tono {
        case .basso: return Color.malus
        case .medio: return Color.attenzione
        case .parola: return Color.testoSecondario
        }
    }

    private var avatar: some View {
        AvatarGiocatore(id: giocatore.id, squadra: giocatore.squadra, dimensione: 40, nome: giocatore.nome, ruolo: giocatore.ruolo)
    }

    /// Nome, partita e le etichette.
    private func dati(_ pezzi: [LetturaPedina.Pezzo]) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(giocatore.nome).font(.headline).fixedSize(horizontal: false, vertical: true)
            Text(RigaGiocatore.sottotitolo(giocatore, adesso: Orologio.adesso())).font(.caption).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(Array(pezzi.enumerated()), id: \.offset) { _, pezzo in
                Text(pezzo.testo).font(.caption.weight(.semibold))
                    .foregroundStyle(Self.colore(pezzo.tono))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    /// Il numero del cambio, grande, e sotto il fantavoto atteso.
    private func numeri(allineamento: HorizontalAlignment) -> some View {
        VStack(alignment: allineamento, spacing: 0) {
            if let numero {
                Text(numero).font(.title3.bold()).monospacedDigit()
                    .foregroundStyle(positivo ? Color.verde : Color.primary)
            }
            Text(Catalogo.Formazione.fvAttesoBreve(fv: Formato.punti(giocatore.fvAtteso))).font(.caption2)
                .foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// La riga per VoiceOver: il nome, il numero con quello che vuol dire, il fantavoto atteso e le etichette, nel loro ordine.
    private func voce(_ pezzi: [LetturaPedina.Pezzo]) -> String {
        var parti = [giocatore.nome]
        if let numero { parti.append("\(numero) \(voceNumero)") }
        parti.append(Catalogo.Formazione.fvAttesoBreve(fv: Formato.punti(giocatore.fvAtteso)))
        return (parti + pezzi.map(\.testo)).joined(separator: ", ")
    }
}
