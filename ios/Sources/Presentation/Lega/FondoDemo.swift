import SwiftUI

/// Le foto `lega-stato-fondo`, `lega-rosa-fondo`, `lega-stato-nostri`, `lega-stato-taratura` e `lega-stato-prova` (#425, #430, #527,
/// #842): la lista parte scorsa in fondo, dove sono le parti nuove di Stato dei dati (indicatori del consiglio) e l'ultima riga della
/// Rosa; per Stato dei dati ci sono anche tre punti di arrivo in mezzo, che col consiglio non entrano in una foto sola: i gol attesi
/// nostri, la riga della taratura di «gioca N%» (sotto i gruppi di «Quanto sono giuste le previsioni») e la frase della prova delle
/// previsioni (sotto la taratura). Vale solo in demo, con `-DEMO_FONDO`:
/// nell'app vera la lista non ha niente in più.
enum FondoDemo {
    /// L'identità dell'ultima riga della lista (`RigaFondoDemo`): è lì che scorre la foto, appena i dati sono arrivati.
    static let idRiga = "fondo-demo-lega"

    /// L'identità della prima riga del riquadro «Gol attesi nostri» (`GolAttesiNostriSezione`): dove si ferma `lega-stato-nostri`.
    static let idNostri = "fondo-demo-nostri"

    /// Dove si ferma la foto «nostri»: la riga un po' sotto il bordo alto, così sopra si vede anche il titolo del riquadro.
    static let ancoraNostri = UnitPoint(x: 0.5, y: 0.06)

    /// L'identità dell'ultimo gruppo della calibrazione (`idGruppo`): dove si ferma `lega-stato-taratura`. La riga della taratura
    /// sta nel piè della sezione, che non è una riga della lista: lo scorrimento si ferma sul gruppo subito sopra.
    static let idTaratura = "fondo-demo-taratura"

    /// Dove si ferma la foto «taratura»: l'ultimo gruppo in cima, con la riga subito sotto. Un gruppo è corto, quindi anche a testo
    /// grande la riga resta a video (una riga sotto il piè, lunga, la spingerebbe fuori dall'alto).
    static let ancoraTaratura = UnitPoint.top

    /// L'identità della frase della prova delle previsioni (la prima riga di «Quanto sono affidabili le previsioni», quella su
    /// «da fantamedia»): dove si ferma `lega-stato-prova` (#842).
    static let idProva = "fondo-demo-prova"

    /// Dove si ferma la foto «prova»: la frase un po' sotto il bordo alto, così sopra si vede anche il titolo della sezione.
    static let ancoraProva = UnitPoint(x: 0.5, y: 0.06)

    /// Vero in demo con `-DEMO_FONDO <valore>` fra gli argomenti di lancio, come per `demoInFondo`.
    static func attivo(demo: Bool, argomenti: [String]) -> Bool {
        demo && Demo.argomento("DEMO_FONDO", in: argomenti) != nil
    }

    /// Vero in demo con `-DEMO_FONDO nostri`: Stato dei dati si ferma sui gol attesi nostri invece di andare in fondo.
    static func vaAlleNostri(demo: Bool, argomenti: [String]) -> Bool {
        demo && Demo.argomento("DEMO_FONDO", in: argomenti) == "nostri"
    }

    /// Vero in demo con `-DEMO_FONDO taratura`: Stato dei dati si ferma sulla riga della taratura invece di andare in fondo.
    static func vaAllaTaratura(demo: Bool, argomenti: [String]) -> Bool {
        demo && Demo.argomento("DEMO_FONDO", in: argomenti) == "taratura"
    }

    /// Vero in demo con `-DEMO_FONDO prova`: Stato dei dati si ferma sulla frase della prova delle previsioni invece di andare in fondo.
    static func vaAllaProva(demo: Bool, argomenti: [String]) -> Bool {
        demo && Demo.argomento("DEMO_FONDO", in: argomenti) == "prova"
    }

    /// L'identità di un gruppo della calibrazione: l'ultimo (subito sopra la riga della taratura) prende `idTaratura`, gli altri
    /// tengono la loro.
    static func idGruppo(_ id: String, ultimo: String?) -> String {
        id == ultimo ? idTaratura : id
    }

    /// Vero adesso: l'app è in demo e le foto chiedono la schermata scorsa in fondo.
    static var richiesto: Bool {
        attivo(demo: Demo.attivo, argomenti: ProcessInfo.processInfo.arguments)
    }

    /// Dove deve arrivare la foto di Stato dei dati: la riga delle nostri, l'ultimo gruppo sopra la taratura, la frase della prova
    /// delle previsioni, o l'ultima riga.
    static func arrivo(demo: Bool, argomenti: [String]) -> (id: String, ancora: UnitPoint) {
        if vaAlleNostri(demo: demo, argomenti: argomenti) { return (idNostri, ancoraNostri) }
        if vaAllaTaratura(demo: demo, argomenti: argomenti) { return (idTaratura, ancoraTaratura) }
        if vaAllaProva(demo: demo, argomenti: argomenti) { return (idProva, ancoraProva) }
        return (idRiga, .bottom)
    }

    /// Dove deve arrivare adesso la foto di Stato dei dati (`arrivo` con gli argomenti di lancio).
    static var arrivoDiStato: (id: String, ancora: UnitPoint) {
        arrivo(demo: Demo.attivo, argomenti: ProcessInfo.processInfo.arguments)
    }
}
