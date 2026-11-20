import SwiftUI

/// Una riga delle scelte di un cambio, come `riga-gioc` di «Sostituisci» e di «Metti in campo» della web: volto, nome, partita e,
/// sotto l'80% o con uno stato, «gioca N%» e lo stato a parole (`LetturaPedina.contenuto`), poi le parole in più della riga
/// (`altre`: «Si passa al …»); a destra il numero grande del cambio, se c'è, e sotto il fantavoto atteso. Con il testo molto
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
    /// Le parole in più sotto lo stato («Si passa al 4-4-2»).
    var altre: [String] = []
    @Environment(\.dynamicTypeSize) private var taglia

    var body: some View {
        let contenuto = LetturaPedina.contenuto(giocatore, adesso: Orologio.adesso())
        Group {
            if taglia.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 6) {
                    avatar
                    dati(contenuto)
                    numeri(allineamento: .leading)
                }
            } else {
                HStack(alignment: .center, spacing: 10) {
                    avatar
                    dati(contenuto)
                    Spacer(minLength: 6)
                    numeri(allineamento: .trailing)
                }
            }
        }
        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(voce(contenuto))
        .accessibilityHint(suggerimento)
        // Controllo vocale: basta dire il nome, non tutta la riga
        .accessibilityInputLabels([giocatore.nome])
    }

    /// Il colore di un pezzo dello stato: arancio fra 50 e 79, rosso sotto 50 o per chi non gioca, grigio per le parole.
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

    /// Nome, partita, lo stato e le parole in più.
    private func dati(_ contenuto: LetturaPedina.Contenuto) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(giocatore.nome).font(.headline).fixedSize(horizontal: false, vertical: true)
            Text(RigaGiocatore.sottotitolo(giocatore, adesso: Orologio.adesso())).font(.caption).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(Array(contenuto.pezzi.enumerated()), id: \.offset) { _, pezzo in
                Text(pezzo.testo).font(.caption.weight(.semibold))
                    .foregroundStyle(Self.colore(pezzo.tono))
                    .fixedSize(horizontal: false, vertical: true)
            }
            ForEach(altre, id: \.self) { parola in
                Text(parola).font(.caption.weight(.semibold)).foregroundStyle(Color.testoSecondario)
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

    /// La riga per VoiceOver: il nome, il numero con quello che vuol dire, il fantavoto atteso, lo stato e le parole in più.
    private func voce(_ contenuto: LetturaPedina.Contenuto) -> String {
        var parti = [giocatore.nome]
        if let numero { parti.append("\(numero) \(voceNumero)") }
        parti.append(Catalogo.Formazione.fvAttesoBreve(fv: Formato.punti(giocatore.fvAtteso)))
        return (parti + contenuto.pezzi.map(\.testo) + altre).joined(separator: ", ")
    }
}
