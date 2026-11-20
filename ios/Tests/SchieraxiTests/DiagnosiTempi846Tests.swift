import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

// DIAGNOSI DELLA #846, DA TOGLIERE: misura quanto lavora il thread principale nei passi della foto `formazione-in-corso` sull'iPad
// orizzontale (costruzione della demo, svuotamento dei dati, decodifica, disposizione del campo e della pagina). Fallisce sempre,
// apposta, per scrivere i tempi nel registro della corsa (la riga contiene «failed:», che il passo «Righe con errori» raccoglie).

@MainActor
@Suite("Diagnosi #846: tempi del thread principale (da togliere)")
struct DiagnosiTempi846Tests {
    private static func ms(_ d: Duration) -> String {
        let c = d.components
        return String(format: "%.0f ms", Double(c.seconds) * 1000 + Double(c.attoseconds) / 1e15)
    }

    private static func server(_ demo: FinteServer) -> ServerDiProva {
        ServerDiProva(indirizzo: "https://prova-846-tempi-\(UUID().uuidString).invalid") { metodo, percorso, corpo in
            try await demo.richiesta(metodo, percorso, corpo: corpo)
        }
    }

    /// Il tempo della prima disposizione di `vista` in una finestra vera di `misura` punti.
    private static func pagina<V: View>(_ vista: V, misura: CGSize, classe: UserInterfaceSizeClass) -> String {
        guard let scena = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else { return "senza scena" }
        let finestra = UIWindow(windowScene: scena)
        finestra.frame = CGRect(origin: .zero, size: misura)
        let ospite = UIHostingController(rootView: vista.environment(\.horizontalSizeClass, classe))
        finestra.rootViewController = ospite
        finestra.isHidden = false
        let t = ContinuousClock().measure {
            ospite.view.setNeedsLayout()
            ospite.view.layoutIfNeeded()
        }
        let t2 = ContinuousClock().measure {
            ospite.view.setNeedsLayout()
            ospite.view.layoutIfNeeded()
        }
        finestra.isHidden = true
        finestra.rootViewController = nil
        return "\(ms(t)) (poi \(ms(t2)))"
    }

    @Test("Tempi dei passi della foto formazione-in-corso")
    func tempi() async throws {
        var righe: [String] = []
        let orologio = ContinuousClock()

        var inCorso: FinteServer?
        let tDemo = orologio.measure { inCorso = FinteServer.demoFase("formazione-in-corso", adesso: Date()) }
        righe.append("demo in corso costruita \(Self.ms(tDemo))")
        let demoInCorso = try #require(inCorso)

        let tSvuota = orologio.measure { DatiLocali.svuota() }
        righe.append("svuota \(Self.ms(tSvuota))")

        let nome = "tempi-846-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        let luoghi = TokenWidget.Luoghi(archivio: MemoriaToken(), memoria: memoria, cartella: { nil }, portachiavi: MemoriaCollegamento(),
                                        sincronizza: {})

        let demos: [(String, FinteServer)] = [("in corso", demoInCorso), ("prima", FinteServer.demo)]
        for (etichetta, demo) in demos {
            let srv = Self.server(demo)
            let dati = try await srv.grezzo("/api/formazione")
            let tDecodifica = try orologio.measure { _ = try Decodifica.decodifica(dati) as Formazione }
            let oggi = OggiViewModel(server: srv, conPromemoria: false)
            let vm = FormazioneViewModel(server: srv, oggi: oggi, memoria: memoria, promemoria: {})
            let tCarica = await orologio.measure { await FormazioneView.ricarica(vm, oggi: oggi) }
            let f = try #require(vm.formazione, "\(etichetta): la Formazione arriva")
            let titolari = vm.vista(f).titolari
            righe.append("\(etichetta): decodifica \(Self.ms(tDecodifica)), carica \(Self.ms(tCarica))")

            for larghezza in [422.0, 375.0, 361.0] {
                let disegno = ImageRenderer(content: CampoFormazione(titolari: titolari).frame(width: larghezza))
                disegno.scale = 1
                var altezza: CGFloat = 0
                let t = orologio.measure { altezza = disegno.uiImage?.size.height ?? 0 }
                righe.append("\(etichetta) campo \(Int(larghezza)): \(Self.ms(t)) alto \(Int(altezza))")
            }

            let sessione = SessioneAccount(server: srv, archivio: MemoriaToken(), memoria: memoria, pulisci: {}, widget: luoghi)
            let schermi: [(String, CGSize, UserInterfaceSizeClass)] = [
                ("ipad orizzontale", CGSize(width: 940, height: 834), .regular),
                ("ipad verticale", CGSize(width: 834, height: 1112), .regular),
                ("iphone", CGSize(width: 393, height: 760), .compact),
            ]
            for (dove, misura, classe) in schermi {
                let vista = FormazioneView(vm: vm, oggi: oggi).environmentObject(Navigazione()).environmentObject(sessione)
                righe.append("\(etichetta) pagina \(dove): \(Self.pagina(vista, misura: misura, classe: classe))")
            }
        }

        Issue.record(Comment(rawValue: "tempi 846 failed: " + righe.joined(separator: " | ")))
    }
}
