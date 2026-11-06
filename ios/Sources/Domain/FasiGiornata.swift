import Foundation

/// Le tre fasi della giornata in Oggi (campo `fase` di `GET /api/oggi`, contratto «fasi della giornata» nel repository del server).
enum FaseGiornata: String {
    /// La formazione si può ancora cambiare: Oggi come sempre (consigli, «Da controllare», migliori).
    case prima
    /// Scadenza passata, partite in corso o da giocare: punti fatti finora, niente consigli su chi schierare.
    case inCorso = "in_corso"
    /// La giornata di prima è finita da poco: riepilogo e prossima giornata.
    case finita
}

extension Oggi {
    /// Fase mancante (server vecchio) o sconosciuta = `prima`: il comportamento di sempre.
    var faseGiornata: FaseGiornata { FaseGiornata(rawValue: fase?.valore ?? "") ?? .prima }

    /// «Da controllare», migliori, indisponibili e diffidati: solo finché la formazione si può cambiare.
    var conConsigli: Bool { faseGiornata == .prima }

    /// Entrato in SchieraXI a giornata già iniziata, senza una formazione per lei (`senza_formazione` del server, solo nella fase
    /// `in_corso`): come la web, «Questa giornata è già iniziata» e la prossima da preparare. Un server vecchio non lo manda.
    var senzaFormazioneInCorso: Bool { faseGiornata == .inCorso && senzaFormazione?.valore == true }

    /// Il blocco della giornata in corso (solo nella sua fase).
    var giornataInCorso: GiornataInCorso? { faseGiornata == .inCorso ? inCorso?.valore : nil }
    /// Il riepilogo della giornata finita (solo nella sua fase).
    var riepilogoGiornata: RiepilogoGiornata? { faseGiornata == .finita ? riepilogo?.valore : nil }
    /// La prossima giornata da preparare: nella fase `finita` e per chi è entrato a giornata iniziata (`senza_formazione`).
    var prossimaGiornata: ProssimaGiornata? { faseGiornata == .finita || senzaFormazioneInCorso ? prossima?.valore : nil }
}

/// I testi delle fasi della giornata, con le parole della web (`cardInCorso`, `valoreLive`, `cardSenzaFormazione` e `cardRiepilogo`
/// di `fanta/web/app.js`, chiavi `oggi.*` di `fanta/web/testi.js`, #436). La prova è `OggiFasiComeLaWebTests`, che li confronta con
/// `testi.js`: una parola cambiata su un lato solo fa fallire il test.
enum TestiFase {
    // MARK: giornata in corso

    /// `oggi.punti_finora`
    static let puntiFinora = "Punti fatti finora"
    /// `oggi.a_fine_giornata`
    static let aFineGiornata = "A fine giornata"
    /// «≈ 77,7», come la web: i punti previsti a fine giornata sono una stima.
    static func previsti(_ punti: Double?) -> String { "≈ \(Formato.punti(punti))" }
    /// `oggi.attesi_prima`: «attesi prima: 65,5».
    static func attesiPrima(_ punti: Double) -> String { "attesi prima: \(Formato.punti(punti))" }
    /// `oggi.dalla_panchina`, sotto chi va a punteggio entrando dalla panchina.
    static let dallaPanchina = "entrato dalla panchina"
    /// `oggi.cambi_panchina`
    static let cambiPanchina = "Cambi dalla panchina"
    /// `oggi.tutti_giocato`
    static let tuttiGiocato = "Hanno giocato tutti: mancano solo i voti ufficiali."
    /// `oggi.nessun_sostituto`
    static let nessunSostituto = "nessun sostituto"

    /// Il fantavoto: una cifra decimale, due se servono (6,25).
    static func fantavoto(_ v: Double) -> String {
        let decimi = v * 10
        return Formato.decimali(v, cifre: abs(decimi - decimi.rounded()) < 0.001 ? 1 : 2)
    }

    /// Cosa scrivere a destra del giocatore, come `valoreLive` della web: il fantavoto; per chi deve ancora giocare la data della
    /// partita («sab 8 18:00», come le partite del turno); altrimenti lo stato con le parole della web (`oggi.st_*`).
    static func valore(_ g: GiocatoreInCorso, adesso: Date = Orologio.adesso()) -> String {
        switch g.stato {
        case "fatto": return g.fantavoto.map(fantavoto) ?? Formato.punti(nil)
        case "da_giocare":
            if let d = Quando.data(g.data) { return Quando.relativa(d, adesso: adesso) }
            return "Da giocare"
        case "senza_voto": return "Senza voto"
        case "attesa_voti": return "Voto in arrivo"
        case "in_corso": return "Partita in corso"
        case "rinviata": return "Rinviata"
        default: return "Da giocare"           // come la web: uno stato sconosciuto vale «Da giocare»
        }
    }

    /// Lo stato del giocatore detto a voce: «fantavoto 7,5», «gioca sabato 8 novembre alle 15:00»...
    static func valoreVoce(_ g: GiocatoreInCorso) -> String {
        switch g.stato {
        case "fatto": return g.fantavoto.map { "fantavoto \(fantavoto($0))" } ?? "ha giocato"
        case "senza_voto": return "senza voto"
        case "attesa_voti": return "voto in arrivo"
        case "in_corso": return "partita in corso"
        case "rinviata": return "rinviata"
        default:
            if let d = Quando.data(g.data) { return "gioca \(Quando.giorno(d)) alle \(Quando.ora(d))" }
            return "deve ancora giocare"
        }
    }

    /// Sotto le cifre, come la web: «2 giocatori devono ancora giocare» (`oggi.ancora_da_giocare`) o, a zero, «Hanno giocato
    /// tutti: mancano solo i voti ufficiali.» (`oggi.tutti_giocato`). `ancora_da_giocare` del server conta chi va a punteggio e
    /// deve ancora giocare o sta giocando (`docs/API.md`): non i voti che mancano. Nil se il numero non c'è (server vecchio).
    static func ancora(_ n: Int?) -> String? {
        guard let n, n >= 0 else { return nil }
        switch n {
        case 0: return tuttiGiocato
        case 1: return "1 giocatore deve ancora giocare"
        default: return "\(n) giocatori devono ancora giocare"
        }
    }

    /// Un cambio dalla panchina come la web: «Rossi → Bianchi» o «Rossi → nessun sostituto». Nil senza chi esce (la web lo salta).
    static func cambio(_ c: CambioPanchina) -> String? {
        guard let esce = c.esce else { return nil }
        return "\(esce.nome) → \(c.entra?.nome ?? nessunSostituto)"
    }

    /// Lo stesso cambio per VoiceOver, che la freccia non la legge bene: «Esce Rossi, entra Bianchi, già fatto».
    static func cambioVoce(_ c: CambioPanchina) -> String? {
        guard let esce = c.esce else { return nil }
        let entra = c.entra.map { "entra \($0.nome)" } ?? nessunSostituto
        return "Esce \(esce.nome), \(entra), \(etichettaCambio(c))"
    }

    /// `oggi.cambio_fatto` o `oggi.cambio_probabile`.
    static func etichettaCambio(_ c: CambioPanchina) -> String { c.certa ? "già fatto" : "probabile" }

    // MARK: entrato a giornata iniziata (`senza_formazione`)

    /// `oggi.gia_iniziata`
    static let giaIniziata = "Questa giornata è già iniziata"
    /// `oggi.gia_iniziata_testo`
    static let giaIniziataTesto = "Sei arrivato a partite cominciate: questa la guardi e basta. Prepara la prossima."
    /// `oggi.prepara_prossima`
    static let preparaProssima = "Prepara la prossima"

    // MARK: giornata finita

    /// «Giornata 8 · 11ª di Serie A» (#299); nil se il numero di Serie A manca.
    static func giornata(serieA: Int?, lega: Int?) -> String? {
        serieA.map { TempiLega.etichetta(serieA: $0, lega: lega) }
    }

    /// Il titolo della giornata finita, come la web (`oggi.giornata_finita`): «Giornata 8 · 11ª di Serie A: finita»; `voce`:
    /// la stessa frase per VoiceOver («Giornata 8, 11ª di Serie A: finita»). Nil se il numero di Serie A manca.
    static func giornataFinita(serieA: Int?, lega: Int?, voce: Bool = false) -> String? {
        serieA.map { NomeGiornata(serieA: $0, lega: lega) }.map { "\(voce ? $0.voce : $0.intero): finita" }
    }

    /// Sopra i punti fatti: di chi è la formazione che ha contato (`oggi.la_tua_formazione` o `oggi.la_consigliata`).
    static func formazioneDi(_ r: RiepilogoGiornata) -> String { r.formazioneDi == "tua" ? "La tua formazione" : "La consigliata" }
    /// `oggi.punti_fatti`
    static let puntiFatti = "punti fatti"
    /// `oggi.punti_attesi`
    static let puntiAttesi = "punti attesi"
    /// `oggi.apri_diario`
    static let apriDiario = "Apri il Diario"

    /// Come la web (`oggi.con_consigliata`): «Con la consigliata: 72,0 punti (66,1 attesi).», solo se hai schierato una formazione
    /// tua e il server manda i punti della consigliata. Un numero che manca si scrive «–», come la web.
    static func confronto(_ r: RiepilogoGiornata) -> String? {
        guard r.formazioneDi == "tua", let c = r.consigliata else { return nil }
        return "Con la consigliata: \(Formato.punti(c.puntiFatti)) punti (\(Formato.punti(c.puntiAttesi)) attesi)."
    }

    /// `oggi.confronto_in_arrivo`, quando il Diario non ha ancora calcolato la giornata.
    static func notaDiario(_ r: RiepilogoGiornata) -> String? {
        r.nelDiario ? nil : "Il confronto con la consigliata arriva nel Diario."
    }

    // MARK: prossima giornata

    /// La riga della prossima giornata, come la web (`oggi.prossima_chiude` e poi `oggi.prossima_pronta` o `oggi.prossima_da`):
    /// «Giornata 9 · 12ª di Serie A: la formazione si chiude sab 14 14:30. Puoi già prepararla.» Nil senza scadenza (la web non
    /// scrive la riga). Si può già preparare se le probabili ci sono o se `prepara_da` manca o è passato.
    static func prossima(_ p: ProssimaGiornata, adesso: Date = Orologio.adesso()) -> String? {
        guard let scadenza = Quando.data(p.scadenza) else { return nil }
        let chiude = "la formazione si chiude \(Quando.relativa(scadenza, adesso: adesso))."
        let nome = p.giornata.map { NomeGiornata(serieA: $0, lega: p.giornataLega).intero } ?? p.giornataLega.map { "Giornata \($0)" }
        let testa = nome.map { "\($0): \(chiude)" } ?? chiude.primaMaiuscola
        let da = Quando.data(p.preparaDa)
        let gia = p.conProbabili || da.map { $0 <= adesso } ?? true
        guard !gia, let da else { return "\(testa) Puoi già prepararla." }
        return "\(testa) Conviene prepararla da \(Quando.relativa(da, adesso: adesso)), quando escono le probabili formazioni."
    }
}
