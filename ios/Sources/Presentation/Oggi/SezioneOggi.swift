/// Le sezioni di Oggi, dall'alto in basso, nell'ordine della web (`mostraOggi` di `fanta/web/app.js`, grafica B, #416):
/// la giornata con il conto alla rovescia, poi la formazione con «Apri la formazione» (l'azione principale nel primo schermo),
/// Partita rinviata, Da fare e novità; poi I tuoi migliori, Da controllare, Indisponibili, Diffidati e Partite del turno.
/// Niente nome né slogan in cima. Ogni sezione si nasconde da sola se non ha niente da mostrare.
/// Sull'iPad le sezioni vanno in colonne (`Colonne`) sempre in quest'ordine di lettura.
/// La prova è `OggiComeLaWebTests`, che confronta quest'ordine con il codice della web.
enum SezioneOggi: Hashable, Sendable {
    /// Lega senza rose: il benvenuto con «Importa le rose» (sulla web è una pagina a parte).
    case benvenuto
    /// Il server non manda una giornata: una frase al posto del conto alla rovescia.
    case senzaGiornata
    /// Giornata e conto alla rovescia (con la maglia della squadra).
    case conto
    /// Giornata finita: com'è andata.
    case riepilogo
    /// Giornata in corso: punti fatti finora e a fine giornata.
    case inCorso
    /// Giornata in corso: chi va a punteggio.
    case chiGioca
    /// Giornata in corso: i cambi dalla panchina.
    case cambiPanchina
    /// Modulo, punti attesi, «Apri la formazione» e probabili (a giornata finita, quella della prossima).
    case formazione
    /// Partita rinviata.
    case rinvio
    case daFare
    /// Il banner «Novità della versione …».
    case novita
    /// Il suggerimento «tocca un giocatore» (solo iPhone), prima del primo elenco di giocatori.
    case suggerimento
    case migliori
    case daControllare
    case indisponibili
    case diffidati
    case partite

    /// Le sezioni di una fase, in ordine. Come la web: prima della scadenza consigli e avvisi; a giornata in corso i punti e chi
    /// gioca, niente consigli né avvisi; a giornata finita il riepilogo, la prossima formazione, indisponibili e diffidati.
    static func ordine(fase: FaseGiornata, conGiornata: Bool) -> [SezioneOggi] {
        var sezioni: [SezioneOggi] = [.benvenuto, conGiornata ? .conto : .senzaGiornata]
        switch fase {
        case .prima:
            if conGiornata { sezioni.append(.formazione) }
            sezioni.append(contentsOf: [SezioneOggi.rinvio, .daFare, .novita])
            sezioni.append(contentsOf: [SezioneOggi.suggerimento, .migliori, .daControllare, .indisponibili, .diffidati])
        case .inCorso:
            // sulla web è una carta sola: punti, poi chi va a punteggio, poi i cambi dalla panchina
            sezioni.append(contentsOf: [SezioneOggi.inCorso, .chiGioca, .cambiPanchina, .rinvio, .daFare, .novita])
        case .finita:
            sezioni.append(.riepilogo)
            if conGiornata { sezioni.append(.formazione) }
            sezioni.append(contentsOf: [SezioneOggi.rinvio, .daFare, .novita, .indisponibili, .diffidati])
        }
        sezioni.append(.partite)
        return sezioni
    }

    /// «Mancano le probabili formazioni…» sotto «Apri la formazione»: come la web, solo prima della scadenza e solo se il server
    /// dice che mancano (`con_probabili: false`; un server vecchio che non lo dice non fa comparire l'avviso).
    static func avvisoProbabili(fase: FaseGiornata, conProbabili: Bool?) -> Bool {
        fase == .prima && conProbabili == false
    }
}
