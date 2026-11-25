import SwiftUI

/// La foto `giornate-confronto` (#842, solo demo): Giornate › Dettagli con a video la fine della voce «la consigliata contro la
/// tua», cioè la frase «…avresti fatto 1,0 punti in più.». La frase è l'ultima della voce: con il testo grande la voce è più alta
/// dello schermo, quindi la lista porta il bordo basso della voce in fondo allo schermo (`.bottom`), non la cima in alto (con la
/// cima in alto la frase uscirebbe dal basso). Nell'app vera le identità non cambiano niente.
enum ConfrontoDemo {
    /// L'identità dei numeri di «Dettagli» (`PrecisioneView`), una riga della lista.
    static let idDettagli = "demo-dettagli"
    /// L'identità della voce del confronto, dentro quella riga.
    static let idConfronto = "demo-confronto"
}

extension View {
    /// Solo in demo, nella foto `giornate-confronto`, appena le giornate ci sono: prima la riga dei Dettagli, poi la voce del
    /// confronto, tutte e due con il bordo basso in fondo allo schermo. La voce sta dentro la riga e la lista potrebbe non trovarla:
    /// allora resta lo scorrimento alla riga, e sotto il confronto c'è solo la voce corta dei punti della squadra (la demo della foto
    /// non ha i suoi numeri). Fuori dalla demo non fa niente.
    func demoScorriAlConfronto(proxy: ScrollViewProxy, pronto: Bool) -> some View {
        task(id: pronto) {
            guard pronto, Demo.attivo, Demo.foto == "giornate-confronto" else { return }
            try? await Task.sleep(for: .milliseconds(700))
            proxy.scrollTo(ConfrontoDemo.idDettagli, anchor: .bottom)
            try? await Task.sleep(for: .milliseconds(400))
            proxy.scrollTo(ConfrontoDemo.idConfronto, anchor: .bottom)
        }
    }
}
