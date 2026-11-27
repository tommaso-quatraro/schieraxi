/// Una voce del menu del modulo (`FormazioneViewModel.vociModulo`, come `opzione` di `mostraFormazione` della web): una formazione
/// calcolata dal server («4-3-3 · 73,7 punti · consigliato», «5-3-2 · 70,7 punti») o, in cima, la tua cambiata a mano
/// («4-3-3 · 71,0 punti · la tua»).
struct VoceModulo: Identifiable, Equatable {
    /// Il modulo della formazione del server che si mette in campo scegliendo la voce; nil per la tua, che è già in campo.
    let modulo: String?
    /// Il testo della voce, dal catalogo, con i punti attesi del server.
    let etichetta: String
    /// La formazione in campo: la voce con la spunta.
    let scelta: Bool

    var id: String { modulo ?? "la-tua" }
}
