import SwiftUI
import Testing
@testable import Schieraxi

/// Cambi consigliati con il testo grande (issue #247). Nella foto `iphone_scuro_testogrande_mercato-consigliati` la riga dei
/// dettagli finiva con «rimborso 11, costo 19, crediti…»: il testo aveva `.lineLimit(2)`. Lo stesso limite tagliava i nomi
/// della carta, il nome nelle righe dell'elenco dei giocatori e la riga di spiegazione sopra l'elenco.
/// Ora ogni testo va a capo intero: niente «…» e niente testo rimpicciolito.
/// Si misura con `ImageRenderer` (come `EtichetteIntereTests`): con una larghezza proposta l'immagine ha l'altezza che la vista
/// si prende. Un testo tagliato a due righe non cresce più quando il testo si allunga: per questo si confrontano due altezze.
@Suite("Cambi consigliati e elenco dei giocatori: testi interi con il testo grande")
struct CambiConsigliatiInteriTests {

    /// Una carta su iPhone: 390 punti meno i margini di 16 per lato.
    private static let larghezza: CGFloat = 358
    /// Nomi inventati che con il testo grandissimo stanno su più di due righe; il secondo ha due parole in più.
    private static let nomeLungo = "Gianmarco Pierantoni Castelvecchi"
    private static let nomeLunghissimo = "Gianmarco Pierantoni Castelvecchi Bartolomei Santangelo"

    /// L'altezza che la vista si prende quando è larga `larghezza` punti, alla taglia del testo data.
    @MainActor
    private static func altezza<V: View>(_ vista: V, larghezza: CGFloat = CambiConsigliatiInteriTests.larghezza,
                                         taglia: DynamicTypeSize) -> CGFloat {
        let disegno = ImageRenderer(content: vista.dynamicTypeSize(taglia))
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: nil)
        disegno.scale = 1
        return disegno.uiImage?.size.height ?? 0
    }

    /// L'altezza di una riga sola del carattere dato, per dire «più di due righe» senza numeri scritti a mano.
    @MainActor
    private static func riga(_ font: Font, taglia: DynamicTypeSize) -> CGFloat {
        altezza(Text("Riga").font(font), taglia: taglia)
    }

    private static func proposta(entra: String = "Aldo Pinarotti", esce: String = "Bruno Fosola", breve: Double? = 1.4,
                                 creditiDopo: Double? = 1, fattibile: Bool? = false) -> PropostaMercato {
        PropostaMercato(
            esce: GiocatoreBreve(id: 2, nome: esce, ruolo: "A", squadra: "Prova", quotazione: 22),
            entra: GiocatoreBreve(id: 1, nome: entra, ruolo: "A", squadra: "Prova", quotazione: 19),
            guadagno: 3.4, breve: breve, rimborso: 11, creditiDopo: creditiDopo, fattibile: fattibile,
            giornate: [10, 11, 12, 13, 14])
    }

    @MainActor
    @Test("La riga «crediti dopo · rimborso · costo» si legge intera: va a capo invece di finire con «…»")
    func rigaDettagliIntera() throws {
        let lunga = Self.proposta()
        // senza punti delle prossime giornate e senza «crediti dopo» la carta non ha la riga dei dettagli, come la web (#256)
        let corta = Self.proposta(breve: nil, creditiDopo: nil, fattibile: nil)
        let testoLungo = try #require(CartaCambio.dettaglio(lunga))
        #expect(testoLungo.contains("crediti dopo 1 (non bastano)"))
        #expect(CartaCambio.dettaglio(corta) == nil)

        // le due taglie delle foto: «testo grande» e «testo massimo»
        for taglia in [DynamicTypeSize.accessibility2, .accessibility5] {
            // quanto deve crescere la carta: almeno quanto il testo intero, misurato nella larghezza di tutta la carta
            // (dentro la carta il testo ha meno spazio, quindi va a capo almeno altrettanto)
            let interoLungo = Self.altezza(Text(testoLungo).font(.caption), taglia: taglia)
            #expect(interoLungo > Self.riga(.caption, taglia: taglia) * 2,
                    "\(taglia): la prova ha senso solo se il testo intero supera due righe")

            let cresce = Self.altezza(CartaCambio(proposta: lunga), taglia: taglia)
                - Self.altezza(CartaCambio(proposta: corta), taglia: taglia)
            #expect(cresce >= interoLungo - 2,
                    "\(taglia): la carta cresce di \(cresce) punti, il testo intero ne chiede \(interoLungo): la riga è tagliata")
        }
    }

    @MainActor
    @Test("I nomi di chi entra e di chi esce vanno a capo interi, senza «…» e senza rimpicciolirsi")
    func nomiDellaCartaInteri() {
        let taglia = DynamicTypeSize.accessibility5
        func carta(entra: String = "Aldo Pinarotti", esce: String = "Bruno Fosola") -> CGFloat {
            Self.altezza(CartaCambio(proposta: Self.proposta(entra: entra, esce: esce)), taglia: taglia)
        }
        // con il nome tagliato a due righe le due carte sono alte uguali (o la seconda più bassa, col testo rimpicciolito)
        let entra = carta(entra: Self.nomeLunghissimo) - carta(entra: Self.nomeLungo)
        let esce = carta(esce: Self.nomeLunghissimo) - carta(esce: Self.nomeLungo)
        #expect(entra >= Self.riga(.headline, taglia: taglia) * 0.9, "chi entra: la carta cresce solo di \(entra) punti")
        #expect(esce >= Self.riga(.caption, taglia: taglia) * 0.9, "chi esce: la carta cresce solo di \(esce) punti")
    }

    @MainActor
    @Test("Nell'elenco dei giocatori (e nelle ricerche) il nome va a capo intero")
    func nomeDellElencoIntero() {
        let taglia = DynamicTypeSize.accessibility5
        func rigaElenco(_ nome: String) -> CGFloat {
            let breve = GiocatoreBreve(id: 3, nome: nome, ruolo: "C", squadra: "Prova", quotazione: 12)
            return Self.altezza(RigaElencoGiocatore(breve: breve, nonGioca: false), taglia: taglia)
        }
        let cresce = rigaElenco(Self.nomeLunghissimo) - rigaElenco(Self.nomeLungo)
        #expect(cresce >= Self.riga(.headline, taglia: taglia) * 0.9, "la riga cresce solo di \(cresce) punti: il nome è tagliato")
    }

    @MainActor
    @Test("La spiegazione sopra l'elenco dei giocatori va a capo intera anche in una colonna stretta")
    func legendaIntera() {
        let taglia = DynamicTypeSize.accessibility5
        let stretta: CGFloat = 288   // Split View dell'iPad: 320 punti meno i margini
        let intero = Self.altezza(Text(ClassificaView.legendaBreve).font(.caption), larghezza: stretta, taglia: taglia)
        let legenda = Self.altezza(LegendaElenco(aperta: .constant(false)), larghezza: stretta, taglia: taglia)
        #expect(intero > Self.riga(.caption, taglia: taglia) * 2, "la prova ha senso solo se il testo intero supera due righe")
        #expect(legenda >= intero - 2, "la spiegazione è alta \(legenda) punti, il testo intero \(intero): è tagliata")
    }
}
