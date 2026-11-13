import CoreFoundation
import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// Pedine del campo sempre intere (issue #274, come la web dal #265). Sull'iPhone il cognome stava su una riga e si
/// rimpicciolisce fino al 60% (`minimumScaleFactor(0.6)`): in una fila da cinque dell'iPhone piccolo un cognome lungo
/// scendeva sotto i 12 punti. Lo stesso per «⚠ gioca 45%» e «vs NAP». Ora vanno a capo (il cognome con il trattino, dove
/// l'italiano lo mette) e il carattere non si rimpicciolisce più.
/// Si misura con `ImageRenderer` (come `EtichetteIntereTests`): con una larghezza proposta l'immagine ha la misura che la vista
/// si prende. Un testo che si rimpicciolisce su una riga non cresce in altezza; uno che va a capo sì, di almeno una riga.
/// L'altezza di una riga la dà UIKit, non il codice che si prova. Nomi inventati.
@Suite("Pedine del campo: cognome intero a capo, mai rimpicciolito")
struct PedinaInteraTests {

    /// Una pedina in una fila da cinque sull'iPhone piccolo (SE, 375 punti): 375 − 2 × 16 (margini della pagina)
    /// − 2 × 12 (carta) − 2 × 6 (campo) = 307, meno 4 spazi da 2 tra le pedine = 299, diviso 5.
    static let cinquePerFila: CGFloat = 59.8
    /// La stessa fila nella colonna più stretta: 320 punti (Split View dell'iPad, iPhone SE con lo zoom dello schermo).
    static let cinquePerFilaStretta: CGFloat = 48.8
    /// Lo spazio del campo dentro la carta sull'iPhone piccolo: 375 − 2 × 16 − 2 × 12.
    static let campoPiccolo: CGFloat = 319

    static let cognomeLungo = "Castelvecchiarini"
    static let cognomeCorto = "Orvi"
    static let trattinoMorbido = "\u{00AD}"

    /// Un titolare inventato: in dubbio («⚠ gioca 45%»), in trasferta contro il Napoli.
    private static func giocatore(_ nome: String, id: Int = 1, ruolo: String = "C") throws -> Giocatore {
        let json = #"{"id": \#(id), "nome": "\#(nome)", "ruolo": "\#(ruolo)", "squadra": "milan", "avversario": "napoli", "in_casa": false, "p_voto": 0.45, "fv_atteso": 6.8}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// Un 3-5-2 con cognomi lunghi: cinque centrocampisti nella stessa fila.
    private static func trecinquedue() throws -> [Giocatore] {
        let nomi: [(String, String)] = [
            ("P", "Montefalcone"),
            ("D", "Bartolomeinetti"), ("D", "Pierantonacci"), ("D", "Santangelotti"),
            ("C", "Castelvecchiarini"), ("C", "Roccaforteschi"), ("C", "Valdinocchiari"), ("C", "Ivo Sorvani"), ("C", "Hamit Çalvaroğlu"),
            ("A", "Leonel Marténi"), ("A", "Zosaba Ndorti"),
        ]
        return try nomi.enumerated().map { i, voce in try giocatore(voce.1, id: 100 + i, ruolo: voce.0) }
    }

    /// La misura della vista quando le si propone la larghezza data (nil: tutto lo spazio che vuole), alla taglia del testo data.
    @MainActor
    private static func misura<V: View>(_ vista: V, larghezza: CGFloat?, taglia: DynamicTypeSize = .large) -> CGSize {
        let disegno = ImageRenderer(content: vista.dynamicTypeSize(taglia))
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: nil)
        disegno.scale = 1
        return disegno.uiImage?.size ?? .zero
    }

    /// L'altezza di una riga del carattere del cognome (`.caption`) alla taglia del testo data.
    private static func rigaCognome(_ taglia: DynamicTypeSize) -> CGFloat {
        let tratti = UITraitCollection(preferredContentSizeCategory: UIContentSizeCategory(taglia))
        return UIFont.preferredFont(forTextStyle: .caption1, compatibleWith: tratti).lineHeight
    }

    // MARK: cognome

    @MainActor
    @Test("Un cognome lungo in una fila da cinque va a capo: la pedina cresce di almeno una riga e resta nella sua colonna",
          arguments: [PedinaInteraTests.cinquePerFila, PedinaInteraTests.cinquePerFilaStretta])
    func cognomeLungoACapo(larghezza: CGFloat) throws {
        let lungo = try Self.giocatore(Self.cognomeLungo)
        let corto = try Self.giocatore(Self.cognomeCorto)
        for taglia in [DynamicTypeSize.large, .xxxLarge, .accessibility3] {
            let alta = Self.misura(PedinaCampo(g: lungo), larghezza: larghezza, taglia: taglia)
            let bassa = Self.misura(PedinaCampo(g: corto), larghezza: larghezza, taglia: taglia)
            // il cognome cresce con il testo grande fino a XXL, poi resta lì
            let riga = Self.rigaCognome(min(taglia, .xxLarge))
            #expect(riga > 0)
            #expect(alta.height - bassa.height >= riga * 0.9,
                    "\(taglia), \(larghezza) punti: la pedina con «\(Self.cognomeLungo)» è più alta solo di \(alta.height - bassa.height) punti (una riga: \(riga)): il cognome non va a capo")
            #expect(alta.width <= larghezza + 1, "\(taglia): la pedina esce dalla sua colonna (larga \(alta.width))")
        }
    }

    @MainActor
    @Test("Il cognome non scende sotto i 12 punti: con il testo di sistema più piccolo la pedina è alta come a misura normale")
    func cognomeMaiSottoLaMisuraMinima() throws {
        let g = try Self.giocatore(Self.cognomeCorto)
        let normale = Self.misura(PedinaCampo(g: g), larghezza: Self.cinquePerFila, taglia: .large)
        #expect(normale.height > 0)
        for taglia in [DynamicTypeSize.xSmall, .small, .medium] {
            let piccola = Self.misura(PedinaCampo(g: g), larghezza: Self.cinquePerFila, taglia: taglia)
            #expect(abs(piccola.height - normale.height) < 0.5,
                    "\(taglia): la pedina è alta \(piccola.height) punti, a misura normale \(normale.height): il cognome si è rimpicciolito")
        }
    }

    @MainActor
    @Test("Cinque pedine con il cognome lungo stanno nel campo dell'iPhone piccolo, anche con il testo grande")
    func cinquePerFilaNelCampo() throws {
        let titolari = try Self.trecinquedue()
        for taglia in [DynamicTypeSize.large, .xxxLarge, .accessibility5] {
            let campo = Self.misura(CampoFormazione(titolari: titolari), larghezza: Self.campoPiccolo, taglia: taglia)
            #expect(campo.height > 0)
            #expect(campo.width <= Self.campoPiccolo + 1, "\(taglia): il campo è largo \(campo.width) punti in \(Self.campoPiccolo)")
        }
    }

    // MARK: «gioca N%» (l'avversario non sta più sulla pedina, #673: è nella scheda)

    @MainActor
    @Test("«⚠ gioca 45%» e «gioca 85%» vanno a capo invece di rimpicciolirsi", arguments: [true, false])
    func giocaACapo(incerto: Bool) {
        let vista = RigaGioca(testo: incerto ? "gioca 45%" : "gioca 85%", incerto: incerto)
        let intera = Self.misura(vista, larghezza: nil)
        let stretta = (intera.width * 0.7).rounded(.down)
        let misura = Self.misura(vista, larghezza: stretta)
        #expect(intera.height > 0)
        #expect(misura.height >= intera.height * 1.6,
                "in \(stretta) punti è alta \(misura.height), su una riga \(intera.height): non va a capo")
        #expect(misura.width <= stretta + 1, "esce dalla pedina (larga \(misura.width) in \(stretta))")
    }

    // MARK: sillabazione

    @Test("Il cognome lungo ha i trattini morbidi dove l'italiano va a capo")
    func sillabatoLungo() {
        let pezzi = LetturaPedina.sillabato(Self.cognomeLungo).components(separatedBy: Self.trattinoMorbido)
        #expect(pezzi.count >= 3, "punti di sillabazione trovati: \(pezzi)")
        // mai una lettera sola in fondo alla riga prima del trattino, né da sola a capo
        #expect((pezzi.first?.count ?? 0) >= 2 && (pezzi.last?.count ?? 0) >= 2, "una lettera sola a un capo: \(pezzi)")
        #expect(pezzi.joined() == Self.cognomeLungo)
    }

    @Test("Togliendo i trattini morbidi torna il nome di prima (VoiceOver legge sempre il nome del server)",
          arguments: ["Castelvecchiarini", "Hamit Çalvaroğlu", "D'Orsenna", "Orvi", "Ndorti", ""])
    func sillabatoReversibile(nome: String) {
        #expect(LetturaPedina.sillabato(nome).replacingOccurrences(of: Self.trattinoMorbido, with: "") == nome)
    }

    @Test("Un nome di più parole si prova una parola per riga, prima di spezzare le parole")
    func parolePerRiga() {
        #expect(LetturaPedina.parolePerRiga("Hamit Çalvaroğlu") == "Hamit\nÇalvaroğlu")
        #expect(LetturaPedina.parolePerRiga("  Ivo   Sorvani ") == "Ivo\nSorvani")
        #expect(LetturaPedina.parolePerRiga("Castelvecchiarini") == nil, "una parola sola: niente da provare")
        #expect(LetturaPedina.parolePerRiga("") == nil)
    }

    // MARK: immagine da condividere

}
