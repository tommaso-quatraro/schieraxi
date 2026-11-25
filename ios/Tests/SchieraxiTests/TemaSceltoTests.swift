import SwiftUI
import Testing
@testable import Schieraxi

// Il chiaro e lo scuro dell'app (#845). La scelta di Impostazioni › Aspetto vale su ogni schermata, anche sull'accesso e sul primo
// avvio, che stanno fuori dalle schede. Nelle foto del simulatore (`-DEMO_ASPETTO` di `scripts/screenshot.sh`) vale l'aspetto
// del giro anche dove il tema resta «Automatico» (la foto `impostazioni-aspetto`): al primo giro dopo l'accensione il simulatore
// era ancora chiaro e le foto «scuro» di accesso e Aspetto uscivano chiare (corsa 44739068749).
struct TemaSceltoTests {
    @Test func laSceltaDiAspetto() {
        #expect(TemaScelto.schema(tema: "auto", foto: nil) == nil)
        #expect(TemaScelto.schema(tema: "chiaro", foto: nil) == .light)
        #expect(TemaScelto.schema(tema: "scuro", foto: nil) == .dark)
        #expect(TemaScelto.schema(tema: "viola", foto: nil) == nil, "una scelta che non si conosce segue il dispositivo")
    }

    @Test func nelleFotoValeLAspettoDelGiro() {
        #expect(TemaScelto.schema(tema: "auto", foto: "scuro") == .dark, "impostazioni-aspetto: «Automatico» e scuro")
        #expect(TemaScelto.schema(tema: "auto", foto: "chiaro") == .light)
        #expect(TemaScelto.schema(tema: "chiaro", foto: "scuro") == .dark)
        #expect(TemaScelto.schema(tema: "scuro", foto: "altro") == .dark, "un aspetto che non si conosce non cambia niente")
    }

    @Test func lAspettoDelleFotoSoloConLArgomentoDemo() {
        #expect(TemaScelto.foto(argomenti: ["-DEMO", "-DEMO_ASPETTO", "scuro"]) == "scuro")
        #expect(TemaScelto.foto(argomenti: ["-DEMO_ASPETTO", "scuro"]) == nil, "senza -DEMO non è una foto")
        #expect(TemaScelto.foto(argomenti: ["-DEMO", "-DEMO_ASPETTO"]) == nil)
        #expect(TemaScelto.foto(argomenti: ["-DEMO"]) == nil)
    }
}
