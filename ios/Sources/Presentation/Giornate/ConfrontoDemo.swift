import SwiftUI

/// La foto `giornate-confronto` (#842, solo demo): Giornate › Dettagli con a video la fine della voce «la consigliata contro la
/// tua», cioè la frase «…avresti fatto 1,0 punti in più.». La frase è l'ultima della voce: con il testo grande la voce è più alta
/// dello schermo, quindi la lista porta il bordo basso dei Dettagli in fondo allo schermo (`.bottom`), non la cima in alto (con la
/// cima in alto la frase uscirebbe dal basso). Nell'app vera l'identità non cambia niente.
enum ConfrontoDemo {
    /// L'identità dei numeri di «Dettagli» (`PrecisioneView`), una riga della lista: è lì che arriva la foto.
    static let idDettagli = "demo-dettagli"
}

extension View {
    /// Solo in demo, nella foto `giornate-confronto`, appena la cima della pagina è completa (`GiornateViewModel.cimaCompleta`): la
    /// riga dei Dettagli con il bordo basso in fondo allo schermo. Prima si scorreva appena c'erano i Dettagli, e la riga sotto il
    /// titolo (#863), se arrivava dopo, riportava la lista in cima: la voce restava sotto lo schermo (3 corse su 6 il 25/11; 5 lanci su 7
    /// nella corsa di diagnosi 45668942279). La voce del confronto sta dentro la riga e la lista non la trova (uno scorrimento a lei non muoveva
    /// niente): sotto il confronto c'è solo la voce corta dei punti della squadra (la demo della foto non ha i suoi numeri), così la
    /// fine del confronto è a video anche con il testo grande. Fuori dalla demo non fa niente.
    func demoScorriAlConfronto(proxy: ScrollViewProxy, pronto: Bool) -> some View {
        task(id: pronto) {
            guard pronto, Demo.attivo, Demo.foto == "giornate-confronto" else { return }
            try? await Task.sleep(for: .milliseconds(700))
            proxy.scrollTo(ConfrontoDemo.idDettagli, anchor: .bottom)
        }
    }
}
