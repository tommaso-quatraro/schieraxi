import Foundation

/// La testa della Formazione, diversa per fase della giornata (`fase` di `GET /api/oggi`), come `testaGiornata` e `testoConto` di
/// app.js (#616): prima della scadenza la giornata e quando si chiude; in corso i punti fatti finora; finita com'è andata e sotto la
/// formazione della prossima; arrivato a partite cominciate la frase della prossima. Numeri e frasi sono quelli del server, scritti
/// con le parole del catalogo comune. Logica pura, provata in `TestaFormazioneTests`.
struct TestaFormazione: Equatable {
    /// «Giornata 8 · 11ª di Serie A»; a giornata finita «Giornata 7 · 10ª di Serie A: finita». Nil per chi è arrivato a partite
    /// cominciate (lo dice la nota).
    var giornata: String?
    /// Accanto alla giornata, in grassetto, «in corso».
    var inCorso = false
    /// Il numero grande («40,0») e le parole accanto («punti finora · circa 75 a fine giornata», «punti (attesi 71,7)»).
    var punti: String?
    var testoPunti: String?
    /// Sotto i punti: «2 giocatori devono ancora giocare», «Con la consigliata: 72,0 punti (66,1 attesi).».
    var sotto: String?
    /// «Manca il recupero di UDI vs MIL: i punti possono ancora cambiare.»
    var recuperi: String?
    /// Per chi è arrivato a partite cominciate: «Giornata 8 · 11ª di Serie A: è già iniziata. Questa è la formazione per la …».
    var nota: String?
    /// «Com'è andata» porta alle giornate su questa (il numero di Serie A della giornata finita).
    var comeAndata: Int?
    /// A giornata finita, la giornata della formazione sotto: «Giornata 9 · 12ª di Serie A».
    var prossima: String?
    /// Quando si chiude la formazione mostrata: «Si chiude sab 31 14:50» (o «Formazione chiusa», «Calendario non disponibile») e
    /// accanto, piccolo, «fra 3 h 10 min». Nil dove la web non lo scrive (giornata in corso, formazione già chiusa).
    var chiude: String?
    var manca: String?
}

extension TestaFormazione {
    /// La testa per la tua formazione (`oggi` di `GET /api/oggi`) o, senza `oggi`, per quella di un'altra squadra (solo la giornata).
    /// `adesso`: l'ora dell'app, per il conto alla rovescia.
    static func per(oggi o: Oggi?, formazione f: Formazione, adesso: Date) -> TestaFormazione {
        let giornata = f.etichettaGiornata
        guard let o else { return TestaFormazione(giornata: giornata) }
        let conto = Self.conto(o, adesso: adesso)
        switch o.faseGiornata {
        case .inCorso where o.senzaFormazione?.valore == true:
            // arrivato a partite cominciate: questa giornata non si gioca, si prepara la prossima
            var nota = Catalogo.Oggi.giaIniziataTesto
            if let saltata = f.giornataSaltata {
                nota = TempiLega.elidiOrdinali(Catalogo.Formazione.perLaProssima(
                    g: TempiLega.etichetta(serieA: saltata, lega: f.giornataSaltataLega), m: giornata))
            }
            return TestaFormazione(nota: nota, chiude: conto.chiude, manca: conto.manca)
        case .inCorso:
            if let c = o.giornataInCorso {
                var parole = Catalogo.Formazione.puntiFinora
                if let previsti = c.puntiPrevisti, previsti.isFinite {
                    parole += " · " + Catalogo.Formazione.circaFine(n: Formato.decimali(previsti, cifre: 0))
                }
                let ancora = c.ancoraDaGiocare ?? 0
                return TestaFormazione(giornata: giornata, inCorso: true, punti: Formato.punti(c.puntiFatti), testoPunti: parole,
                                       sotto: ancora > 0 ? Catalogo.Oggi.ancoraDaGiocare(ancora) : Catalogo.Oggi.tuttiGiocato)
            }
        case .finita:
            if let r = o.riepilogoGiornata {
                var testa = TestaFormazione(giornata: Catalogo.Oggi.giornataFinita(g: nome(serieA: r.giornata, lega: r.giornataLega)),
                                            punti: Formato.punti(r.puntiFatti),
                                            testoPunti: r.puntiAttesi.map { Catalogo.Formazione.puntiEAttesi(n: Formato.punti($0)) }
                                                ?? Catalogo.Formazione.punti,
                                            comeAndata: r.giornata, prossima: giornata, chiude: conto.chiude, manca: conto.manca)
                if r.formazioneDi == "tua", let c = r.consigliata, c.puntiFatti != r.puntiFatti {
                    testa.sotto = Catalogo.Oggi.conConsigliata(attesi: Formato.punti(c.puntiAttesi), fatti: Formato.punti(c.puntiFatti))
                }
                testa.recuperi = TestiRinvio.recuperoManca(r.recuperi)
                return testa
            }
        case .prima:
            break
        }
        // prima della scadenza (o senza i dati della fase): la giornata e, se la formazione è ancora aperta, quando si chiude
        if f.iniziata == true { return TestaFormazione(giornata: giornata) }
        return TestaFormazione(giornata: giornata, chiude: conto.chiude, manca: conto.manca)
    }

    /// Il nome di una giornata dai suoi due numeri, come `nomeGiornata` della web: con un numero solo quello che c'è.
    static func nome(serieA: Int?, lega: Int?) -> String {
        if let serieA { return TempiLega.etichetta(serieA: serieA, lega: lega) }
        if let lega, lega > 0 { return "Giornata \(lega)" }
        return ""
    }

    /// Quando si chiude la formazione che la schermata mostra (`scadenzaDi` della web): a giornata finita, o per chi è arrivato a
    /// partite cominciate, quella della prossima; altrimenti la scadenza di Oggi (o l'inizio della prima partita).
    static func scadenza(_ o: Oggi) -> String? {
        if o.faseGiornata == .finita || o.senzaFormazione?.valore == true,
           let s = o.prossima?.valore?.scadenza?.trimmingCharacters(in: .whitespaces), !s.isEmpty {
            return s
        }
        return o.chiusura
    }

    /// «Si chiude sab 31 14:50» e «fra 3 h 10 min», come `testoConto` della web; scaduta, «Formazione chiusa»; senza una data,
    /// «Calendario non disponibile». Ogni numero resta attaccato alla sua unità (spazio che non va a capo, come la web, #286):
    /// con il testo grande «min» non va da solo sulla riga dopo.
    static func conto(_ o: Oggi, adesso: Date) -> (chiude: String, manca: String?) {
        guard let testo = scadenza(o), let fine = Quando.data(testo) else { return (Catalogo.Oggi.calendarioNo, nil) }
        guard let tempo = Quando.contoAllaRovescia(fino: fine, adesso: adesso) else { return (Catalogo.Formazione.chiusaBreve, nil) }
        let unito = tempo.replacingOccurrences(of: #"(\d) "#, with: "$1\u{00A0}", options: .regularExpression)
        return (Catalogo.Formazione.siChiude(quando: Quando.relativa(fine, adesso: adesso)), Catalogo.Formazione.fra(tempo: unito))
    }
}
