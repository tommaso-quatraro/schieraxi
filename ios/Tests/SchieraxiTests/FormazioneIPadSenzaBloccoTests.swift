import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

// Issue #846. Nella foto `ipad_scuro_orizzontale_formazione-in-corso` (corsa 44738994894) la Formazione era ferma sullo scheletro:
// due scatti di fila uguali, quindi nemmeno il marchio del caricamento si muoveva. Non era un caricamento perso: arrivati i dati,
// la prima disposizione della pagina in due colonne teneva occupato il thread principale per secondi (10,7 e 15,6 s misurati con
// questi stessi passi, corse 44754490526 e 44757536152) e lo schermo restava sull'ultimo disegno, lo scheletro. L'`HStack` delle due colonne chiedeva a
// ogni colonna anche la misura a larghezza 0 e infinita, e ogni domanda rifaceva pedine e righe dei giocatori. Si misura la
// pagina vera, con i dati della demo, in una finestra grande come la parte destra dell'iPad in orizzontale.

/// Registra le larghezze proposte alla `Sonda` (sul thread principale, come tutta la disposizione).
private final class Proposte: @unchecked Sendable {
    var larghezze: [CGFloat?] = []
}

/// Una vista che dice quali larghezze le vengono proposte e prende l'altezza data.
private struct Sonda: Layout {
    let proposte: Proposte
    let altezza: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        proposte.larghezze.append(proposal.width)
        let larghezza = proposal.width.flatMap { $0.isFinite ? $0 : nil } ?? 100
        return CGSize(width: larghezza, height: altezza)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {}
}

@MainActor
@Suite("Formazione sull'iPad: arrivati i dati, la pagina compare senza bloccare lo schermo (#846)")
struct FormazioneIPadSenzaBloccoTests {
    /// Prima della correzione, su due Mac di GitHub: 10,7 e 15,6 s a giornata in corso, 6,7 e 7,8 s prima della scadenza.
    /// In una colonna sola (iPhone) la stessa pagina chiedeva circa un secondo.
    static let soglia: Duration = .seconds(5)

    @Test("La Formazione in due colonne si dispone in meno di 5 secondi, a giornata in corso e prima della scadenza",
          arguments: ["formazione-in-corso", "formazione"])
    func primaDisposizioneInDueColonne(foto: String) async throws {
        let demo = FinteServer.demoFase(foto) ?? FinteServer.demo
        let srv = ServerDiProva(indirizzo: "https://prova-846-ipad-\(UUID().uuidString).invalid") { metodo, percorso, corpo in
            try await demo.richiesta(metodo, percorso, corpo: corpo)
        }
        let nome = "ipad-846-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi, memoria: memoria, promemoria: {})
        await FormazioneView.ricarica(vm, oggi: oggi)
        try #require(vm.formazione != nil, "la Formazione della demo arriva")

        // widget e portachiavi finti: mai quelli veri del simulatore
        let luoghi = TokenWidget.Luoghi(archivio: MemoriaToken(), memoria: memoria, cartella: { nil }, portachiavi: MemoriaCollegamento(),
                                        sincronizza: {})
        let sessione = SessioneAccount(server: srv, archivio: MemoriaToken(), memoria: memoria, pulisci: {}, widget: luoghi)
        let pagina = FormazioneView(vm: vm, oggi: oggi)
            .environmentObject(Navigazione())
            .environmentObject(sessione)
            .environment(\.horizontalSizeClass, .regular)   // le due colonne dell'iPad
        let scena = try #require(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first,
                                 "l'app che ospita i test ha una scena")
        let finestra = UIWindow(windowScene: scena)
        // la parte destra dell'iPad Pro 11" in orizzontale, accanto alla barra laterale (come nella foto)
        finestra.frame = CGRect(x: 0, y: 0, width: 940, height: 834)
        let ospite = UIHostingController(rootView: pagina)
        finestra.rootViewController = ospite
        finestra.isHidden = false
        defer {
            finestra.isHidden = true
            finestra.rootViewController = nil
        }

        let tempo = ContinuousClock().measure {
            ospite.view.setNeedsLayout()
            ospite.view.layoutIfNeeded()
        }
        #expect(tempo < Self.soglia, "\(foto): la prima disposizione della pagina ha tenuto fermo lo schermo per \(tempo)")
    }

    @Test("Le colonne uguali propongono a ogni colonna solo la sua larghezza: mai 0, infinita o nessuna")
    func colonneUgualiMisuranoUnaVolta() throws {
        let sinistra = Proposte()
        let destra = Proposte()
        let disegno = ImageRenderer(content: ColonneUguali(spazio: 14) {
            Sonda(proposte: sinistra, altezza: 50) {}
            Sonda(proposte: destra, altezza: 80) {}
        }
        .frame(width: 900)
        .background(Color.white))   // senza niente da disegnare l'immagine non nasce
        disegno.scale = 1
        let immagine = try #require(disegno.uiImage)
        let colonna = ColonneUguali.larghezzaColonna(totale: 900, colonne: 2, spazio: 14)
        #expect(colonna == 443)
        for (dove, proposte) in [("sinistra", sinistra), ("destra", destra)] {
            #expect(!proposte.larghezze.isEmpty, "la colonna di \(dove) non è stata misurata")
            #expect(proposte.larghezze.allSatisfy { $0 == colonna }, "colonna di \(dove): proposte \(proposte.larghezze)")
        }
        #expect(immagine.size.height == 80, "alta come la colonna più alta")
    }
}
