import SwiftUI

/// «Tutti i numeri» di «Chi schierare?»: indice, partita, probabilità e punti attesi dei due giocatori, uno accanto all'altro.
/// In tabella come la web quando ogni parola sta intera nella sua colonna; altrimenti (testo grande, scheda stretta) in un
/// elenco, una voce per volta con sotto i due valori. Prima i nomi stavano su una riga e finivano con «…» (#272).
struct TabellaNumeriConfronto: View {
    let x: Giocatore
    let y: Giocatore

    var body: some View {
        let voci = VoceNumeriConfronto.voci(x, y)
        ViewThatFits(in: .horizontal) {
            NumeriInTabella(x: x, y: y, voci: voci)
            NumeriInElenco(x: x, y: y, voci: voci)
        }
    }
}

/// Un giocatore inventato per le anteprime.
private func giocatoreAnteprima(_ id: Int, _ nome: String, avversario: String) -> Giocatore? {
    let json = """
    {"id": \(id), "nome": "\(nome)", "ruolo": "C", "squadra": "genoa", "avversario": "\(avversario)", "in_casa": true,
     "p_voto": 0.82, "fv_atteso": 6.4, "punti_attesi": 5.25, "indice": 72, "difficolta": 2, "quota_titolare": 0.75,
     "p_gol": 0.18, "p_assist": 0.12, "p_giallo": 0.2}
    """
    return try? Decodifica.decodifica(Data(json.utf8))
}

#Preview("Testo normale: tabella") {
    if let x = giocatoreAnteprima(1, "Leonel Marteni", avversario: "roma"),
       let y = giocatoreAnteprima(2, "Gianmarco Pierantoni Castelvecchi", avversario: "juventus") {
        TabellaNumeriConfronto(x: x, y: y).padding()
    }
}

#Preview("Testo massimo: elenco") {
    if let x = giocatoreAnteprima(1, "Leonel Marteni", avversario: "roma"),
       let y = giocatoreAnteprima(2, "Gianmarco Pierantoni Castelvecchi", avversario: "juventus") {
        ScrollView { TabellaNumeriConfronto(x: x, y: y).padding() }
            .dynamicTypeSize(.accessibility5)
    }
}
