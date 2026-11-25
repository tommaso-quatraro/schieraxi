import Foundation

/// I campi numerici dell'editor delle regole, con il titolo della loro riga (lo stesso che legge VoiceOver), e il controllo prima di
/// salvare, come la web (#889, dopo la #886: `problemaCampo` e `salva` in `vistaRegole`, `fanta/web/app.js`). «Salva le regole» si
/// ferma al primo campo che non va, nell'ordine della pagina, e dice quale: senza un numero («è vuoto: scrivi un numero»), con i
/// decimali in un campo di numeri interi, o fuori dai limiti del server (`LimitiRegole`). Con − e + sull'iPhone non si scrive un
/// campo vuoto né un decimale in un campo intero: il controllo vale per i valori arrivati così (regole incomplete, o salvate prima
/// con limiti più larghi). Si controllano solo i campi che si salvano, come la web. Logica pura: la provano i test.
enum CampiRegole {
    /// Un campo con − e +.
    struct Campo: Equatable, Sendable {
        /// Dove sta il numero nel JSON delle regole; è anche la chiave del suo limite in `/limiti-regole.json`.
        let percorso: String
        /// Il titolo della riga.
        let nome: String
        /// Vero per i numeri interi (giocatori, cambi, crediti): sulla pagina si scrivono senza decimali.
        var intero = false
    }

    private static let ruoli = ["P", "D", "C", "A"]
    /// I ruoli al plurale, come `NOMI_RUOLO` della web: le righe della rosa e dei posti fissi in panchina.
    private static let nomiRuolo = ["P": Catalogo.Ruolo.pPl, "D": Catalogo.Ruolo.dPl, "C": Catalogo.Ruolo.cPl, "A": Catalogo.Ruolo.aPl]

    /// «Gol di un portiere» e gli altri ruoli, come `rigaGol` della web.
    static let gol: [Campo] = [("P", "portiere"), ("D", "difensore"), ("C", "centrocampista"), ("A", "attaccante")]
        .map { Campo(percorso: "bonus.gol.\($0.0)", nome: Catalogo.Regole.golDi(ruolo: $0.1)) }
    /// Bonus e malus come `bonusRighe` e `malusRighe` della web (`bonus.*` del catalogo comune).
    static let bonus: [Campo] = [("assist", Catalogo.Bonus.assist), ("rigore_segnato", Catalogo.Bonus.rigoreSegnato),
                                 ("rigore_parato", Catalogo.Regole.rigoreParatoP),
                                 ("portiere_imbattuto", Catalogo.Bonus.portiereImbattuto), ("mvp", Catalogo.Bonus.mvp)]
        .map { Campo(percorso: "bonus.\($0.0)", nome: $0.1) }
    static let malus: [Campo] = [("ammonizione", Catalogo.Bonus.ammonizione), ("espulsione", Catalogo.Bonus.espulsione),
                                 ("autogol", Catalogo.Bonus.autogol), ("rigore_sbagliato", Catalogo.Bonus.rigoreSbagliato),
                                 ("gol_subito_portiere", Catalogo.Bonus.golSubitoPortiere)]
        .map { Campo(percorso: "bonus.\($0.0)", nome: $0.1) }
    static let minDifensori = Campo(percorso: "modificatore_difesa.min_difensori", nome: Catalogo.Regole.mdMin, intero: true)
    static let posti: [Campo] = ruoli.map { Campo(percorso: "panchina.posti.\($0)", nome: nomiRuolo[$0] ?? $0, intero: true) }
    static let giocatoriPanchina = Campo(percorso: "panchina.numero", nome: Catalogo.Regole.giocatoriPanchina, intero: true)
    static let cambi = Campo(percorso: "panchina.max_sostituzioni", nome: Catalogo.Regole.cambiMassimi, intero: true)
    static let votoSenzaSostituto = Campo(percorso: "voto_senza_sostituto", nome: Catalogo.Regole.vu)
    static let rosa: [Campo] = ruoli.map { Campo(percorso: "rosa.\($0)", nome: nomiRuolo[$0] ?? $0, intero: true) }
    static let crediti = Campo(percorso: "crediti_iniziali", nome: Catalogo.Regole.creditiIniziali, intero: true)
    static let votoRinviate = Campo(percorso: "voto_ufficio_rinviate", nome: Catalogo.Regole.rvVoto)

    /// Le chiavi dei limiti delle fasce del modificatore difesa (ogni fascia è una coppia [media, bonus] in `soglie`).
    static let limiteMediaFascia = "modificatore_difesa.soglie.media"
    static let limiteBonusFascia = "modificatore_difesa.soglie.bonus"

    /// Il primo campo che non si può salvare, con la frase della web; nil se si possono salvare tutti. `fasce` sono le fasce del
    /// modificatore nell'ordine della pagina (il numero della fascia nella frase è il suo posto, come «Fascia 2, media almeno» di
    /// VoiceOver); senza, quelle delle regole.
    static func problema(_ regole: JSONValue, fasce: [RegoleLogica.Fascia]? = nil, limiti: LimitiRegole) -> String? {
        voci(regole, fasce: fasce ?? RegoleLogica.fasce(regole)).lazy.compactMap { problema(di: $0, limiti: limiti) }.first
    }

    /// Un numero da controllare: il nome della riga, il valore, la chiave del limite.
    private struct Voce {
        let nome: String
        let valore: JSONValue?
        let intero: Bool
        let limite: String
    }

    /// I numeri che «Salva le regole» manda, nell'ordine della pagina: il modificatore solo acceso; i posti per ruolo solo con i
    /// posti fissi, e allora non il numero della panchina (è la loro somma); il voto d'ufficio solo acceso; il voto delle partite
    /// rinviate solo se il server conosce la regola, anche quando è nascosto (come la web) ma allora solo se c'è.
    private static func voci(_ regole: JSONValue, fasce: [RegoleLogica.Fascia]) -> [Voce] {
        func voce(_ campo: Campo) -> Voce {
            Voce(nome: campo.nome, valore: regole.valore(campo.percorso), intero: campo.intero, limite: campo.percorso)
        }
        var voci = (gol + bonus + malus).map(voce)
        if regole.valore("modificatore_difesa.attivo")?.booleano == true {
            voci.append(voce(minDifensori))
            for (posto, fascia) in fasce.enumerated() {
                let nomi = TestiRegole.nomiFascia(posto: posto + 1)
                voci.append(Voce(nome: nomi.media, valore: JSONValue.numero(fascia.media), intero: false, limite: limiteMediaFascia))
                voci.append(Voce(nome: nomi.bonus, valore: JSONValue.numero(fascia.bonus), intero: false, limite: limiteBonusFascia))
            }
        }
        if case .oggetto? = regole.valore("panchina.posti") {
            voci += posti.map(voce)
        } else {
            voci.append(voce(giocatoriPanchina))
        }
        voci.append(voce(cambi))
        if let voto = regole.valore("voto_senza_sostituto"), voto != .nullo {
            voci.append(voce(votoSenzaSostituto))
        }
        voci += (rosa + [crediti]).map(voce)
        if let modo = regole.valore("partite_rinviate")?.testo,
           modo == ModoRinvio.votoUfficio || regole.valore(votoRinviate.percorso)?.numero != nil {
            voci.append(voce(votoRinviate))
        }
        return voci
    }

    /// Cosa non va in un numero, con le frasi della web; nil se va bene.
    private static func problema(di voce: Voce, limiti: LimitiRegole) -> String? {
        guard let numero = voce.valore?.numero, numero.isFinite else { return Catalogo.Regole.campoVuoto(campo: voce.nome) }
        if voce.intero && numero != numero.rounded() { return Catalogo.Regole.intero(campo: voce.nome) }
        let intervallo = limiti.intervallo(voce.limite)
        guard intervallo.contains(numero) else {
            return Catalogo.Regole.fuoriLimiti(campo: voce.nome, max: cifra(intervallo.upperBound), min: cifra(intervallo.lowerBound))
        }
        return nil
    }

    /// Un limite scritto nella frase, come `cifraLimite` della web: «−20» con il meno tipografico, gli interi senza decimali
    /// («100000»), gli altri con due.
    static func cifra(_ valore: Double) -> String {
        let assoluto = abs(valore)
        let testo = assoluto == assoluto.rounded() && assoluto < 1e15 ? String(Int(assoluto)) : Formato.decimali(assoluto, cifre: 2)
        return (valore < 0 ? "\u{2212}" : "") + testo
    }
}
