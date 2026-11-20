import Foundation

/// Le etichette sotto il nome nelle righe di «Metti in campo» e di «Sostituisci», e sotto il titolo di «Metti in campo» per chi
/// entra (#778), come `etichetteGiocatore` della web con `giocaPoco`. Nell'ordine:
/// 1. lo stato a parole («In dubbio», «Rinviata», «Infortunato», «Squalificato», «Fuori», `ParolaStato`) o, a partita cominciata
///    senza voto, lo stato della partita («Partita in corso», «Voto in arrivo»);
/// 2. «gioca N%» sotto l'80%, ma non per chi non gioca di sicuro né a partita cominciata;
/// 3. le parole in più della riga (`inPiu`: «Si passa al 4-4-2»);
/// 4. «Diffidato»;
/// 5. la nota della fonte che spiega lo stato (`LetturaScheda.nota`, come `notaStato` della web).
/// I colori come le pillole della web: arancio per «In dubbio», «Rinviata», «Diffidato» e «gioca N%» fra 50 e 79; rosso per chi
/// non gioca di sicuro e per «gioca N%» sotto 50; grigio per lo stato della partita, le parole in più e la nota.
enum EtichetteRiga {
    static func pezzi(_ g: Giocatore, inPiu: [String] = []) -> [LetturaPedina.Pezzo] {
        typealias Pezzo = LetturaPedina.Pezzo
        let esito = g.esitoPartita
        let stato: ParolaStato? = esito == nil ? ParolaStato(g) : nil
        var pezzi: [Pezzo] = []
        if let esito, esito.fv == nil, let testo = esito.testo {
            pezzi.append(Pezzo(testo: testo, tono: .parola))
        } else if let stato {
            pezzi.append(Pezzo(testo: stato.testo, tono: stato.nonGiocaDiSicuro ? .basso : .medio))
        }
        if esito == nil, !(stato?.nonGiocaDiSicuro ?? false), SogliaGioca.daMostrare(g.pVoto) {
            pezzi.append(Pezzo(testo: "gioca \(Formato.percento(SogliaGioca.letta(g.pVoto)))%",
                               tono: SogliaGioca.livello(g.pVoto) == .basso ? .basso : .medio))
        }
        pezzi += inPiu.map { Pezzo(testo: $0, tono: .parola) }
        if g.diffidato == true { pezzi.append(Pezzo(testo: Catalogo.Oggi.diffidatoTipo, tono: .medio)) }
        if let nota = LetturaScheda.nota(g) { pezzi.append(Pezzo(testo: nota, tono: .parola)) }
        return pezzi
    }
}
