import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// La scritta delle pillole dei giocatori («Probabile titolare», «In dubbio · gioca 62%», «Fuori») deve stare ad almeno 4,5:1
/// (WCAG 2.2, 1.4.3: è testo piccolo) sopra la sua pillola, cioè il colore dell'esito al `PillolaEtichetta.tinta` sopra il fondo
/// della riga: bianco nelle schede del chiaro, #1C1C1E nelle schede dello scuro e #2C2C2E nei fogli dello scuro (righe della
/// lista «Sostituisci» e di «Confronta con…»). Prima dell'issue #234 il rosso nei fogli dello scuro faceva 4,1:1 e l'arancio sul
/// bianco 4,7:1 (la web, con gli stessi colori, 4,4:1 e 3,8:1 nel foglio della scheda). I valori sono gli stessi della web
/// (`--eti-*` e `--verde` in fanta/web/stile.css; `tests/test_design_web.py` controlla che coincidano). Dall'issue #242 c'è anche
/// la pillola verde («Probabile titolare», «Ha giocato»), che prima sull'iPhone era grigia.
@Suite("Pillole dei giocatori leggibili in chiaro e in scuro")
struct ContrastoPilloleTests {
    private typealias RGB = (r: Double, g: Double, b: Double)

    private static func rgb(_ n: UInt32) -> RGB {
        (Double((n >> 16) & 0xff), Double((n >> 8) & 0xff), Double(n & 0xff))
    }

    private static func sopra(_ colore: RGB, _ alfa: Double, _ fondo: RGB) -> RGB {
        (alfa * colore.r + (1 - alfa) * fondo.r, alfa * colore.g + (1 - alfa) * fondo.g, alfa * colore.b + (1 - alfa) * fondo.b)
    }

    private static func luminanza(_ c: RGB) -> Double {
        func lineare(_ v: Double) -> Double { let x = v / 255; return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4) }
        return 0.2126 * lineare(c.r) + 0.7152 * lineare(c.g) + 0.0722 * lineare(c.b)
    }

    private static func contrasto(_ a: RGB, _ b: RGB) -> Double {
        let (x, y) = (luminanza(a), luminanza(b))
        return (max(x, y) + 0.05) / (min(x, y) + 0.05)
    }

    /// Per ogni tono, nello stesso ordine di `toni`: (scritta, colore della tinta) in chiaro e in scuro. La tinta è il colore
    /// dell'esito (`Etichetta.Tono.colore`: `Color.positivo`, grigio secondario, `Color.attenzione`, `Color.malus`;
    /// `scrittaEFondoDellaPillola` controlla che la pillola usi proprio questi).
    private static let toni: [Etichetta.Tono] = [.positivo, .neutro, .attenzione, .negativo]
    private static let chiaro: [(String, scritta: UInt32, tinta: UInt32)] = [
        ("positivo", Tema.pillolaPositivoChiaro, Tema.positivoChiaro),
        ("neutro", Tema.secondarioChiaro, Tema.secondarioChiaro),
        ("attenzione", Tema.pillolaAttenzioneChiaro, 0x9C5400),
        ("negativo", Tema.pillolaMalusChiaro, 0xB3261E),
    ]
    private static let scuro: [(String, scritta: UInt32, tinta: UInt32)] = [
        ("positivo", Tema.pillolaPositivoScuro, Tema.positivoScuro),
        ("neutro", Tema.secondarioScuro, Tema.secondarioScuro),
        ("attenzione", Tema.pillolaAttenzioneScuro, 0xFFB04A),
        ("negativo", Tema.pillolaMalusScuro, 0xFF6B5E),
    ]

    @MainActor
    @Test("Tema chiaro: ogni pillola almeno 4,5:1 sul bianco delle schede e sul grigio dei fondi")
    func chiaroAlmeno45() {
        let fondi: [(String, UInt32)] = [("scheda", 0xFFFFFF), ("grigio dei fondi", 0xF2F2F7)]
        for (nome, scritta, tinta) in Self.chiaro {
            for (dove, fondo) in fondi {
                let pillola = Self.sopra(Self.rgb(tinta), PillolaEtichetta.tinta, Self.rgb(fondo))
                let c = Self.contrasto(Self.rgb(scritta), pillola)
                #expect(c >= 4.5, "chiaro, \(nome) su \(dove): \(c)")
            }
        }
    }

    @MainActor
    @Test("Tema scuro: ogni pillola almeno 4,5:1 nelle schede e nei fogli")
    func scuroAlmeno45() {
        let fondi: [(String, UInt32)] = [("scheda", 0x1C1C1E), ("foglio", 0x2C2C2E)]
        for (nome, scritta, tinta) in Self.scuro {
            for (dove, fondo) in fondi {
                let pillola = Self.sopra(Self.rgb(tinta), PillolaEtichetta.tinta, Self.rgb(fondo))
                let c = Self.contrasto(Self.rgb(scritta), pillola)
                #expect(c >= 4.5, "scuro, \(nome) su \(dove): \(c)")
            }
        }
    }

    private static func esadecimale(_ colore: Color, scuro: Bool) -> String {
        let tratti = UITraitCollection(userInterfaceStyle: scuro ? .dark : .light)
        let ui = UIColor(colore).resolvedColor(with: tratti)
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        ui.getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "%02X%02X%02X", Int((r * 255).rounded()), Int((g * 255).rounded()), Int((b * 255).rounded()))
    }

    @Test("La pillola scrive e si colora con i colori misurati qui sopra")
    func scrittaEFondoDellaPillola() {
        #expect(Self.toni.count == Self.chiaro.count && Self.toni.count == Self.scuro.count)
        for (i, tono) in Self.toni.enumerated() {
            let (chiaro, scuro) = (Self.chiaro[i], Self.scuro[i])
            #expect(Self.esadecimale(tono.coloreScritta, scuro: false) == String(format: "%06X", chiaro.scritta), "scritta \(tono) in chiaro")
            #expect(Self.esadecimale(tono.coloreScritta, scuro: true) == String(format: "%06X", scuro.scritta), "scritta \(tono) in scuro")
            #expect(Self.esadecimale(tono.colore, scuro: false) == String(format: "%06X", chiaro.tinta), "fondo \(tono) in chiaro")
            #expect(Self.esadecimale(tono.colore, scuro: true) == String(format: "%06X", scuro.tinta), "fondo \(tono) in scuro")
        }
    }

    @Test("«Probabile titolare» è una pillola verde, come sulla web (#242)")
    func probabileTitolareVerde() {
        #expect(Giocatore.nomiTitolarita["titolare"]?.1 == .positivo)
        #expect(Self.esadecimale(Etichetta.Tono.positivo.coloreScritta, scuro: false) == "08643D")
        #expect(Self.esadecimale(Etichetta.Tono.positivo.coloreScritta, scuro: true) == "3DDC97")
    }
}
