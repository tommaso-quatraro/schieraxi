import Foundation

/// Le decisioni in cima alla Formazione (#616, #673): al massimo due voci di «Da fare» di `GET /api/oggi`, ognuna con la sua azione.
/// Quali sono e in che ordine lo dice il server con il campo `decisione` (decisione 1 del proprietario: i client non ricalcolano).
/// L'app tiene, in ordine di `decisione`, le prime che hanno ancora senso con la formazione in pagina, come `vale` della web: un
/// cambio già fatto non si propone più, «la consigliata è cambiata» vale finché in campo c'è una tua scelta diversa da lei.
/// Logica pura, provata in `DecisioniTests`.
enum Decisioni {
    /// Quante se ne mostrano (`DF_DECISIONI` della web).
    static let massimo = 2
    /// La priorità delle voci urgenti (`DF_URGENTE` della web): davanti al testo «Urgente».
    static let urgente = 1

    /// Quello che serve sapere della formazione in pagina per dire se una decisione ha ancora senso.
    struct Pagina: Equatable {
        /// Gli 11 in campo.
        var titolari: [Int]
        /// La giornata è chiusa: nessun cambio.
        var chiusa: Bool
        /// C'è una tua scelta salvata.
        var conScelta: Bool
        /// Quanti titolari in campo non sono quelli della consigliata.
        var diversi: Int
        /// Chi gestisce l'app vede anche le voci tecniche (certificato di SideStore, dati del server fermi).
        var tecniche: Bool
    }

    /// Le decisioni da mostrare, al massimo `massimo`: solo le voci con `decisione`, nel suo ordine (a pari numero l'ordine del
    /// server), che hanno ancora senso con la formazione in pagina.
    static func prime(_ voci: [DaFareVoce], pagina: Pagina) -> [DaFareVoce] {
        let scelte = voci.enumerated().filter { $0.element.decisione != nil && !$0.element.testo.isEmpty && vale($0.element, pagina) }
        let ordinate = scelte.sorted { ($0.element.decisione ?? 0, $0.offset) < ($1.element.decisione ?? 0, $1.offset) }
        return Array(ordinate.prefix(massimo).map(\.element))
    }

    /// La voce ha ancora senso con la formazione in pagina (`vale` di `mostraFormazione` della web). Le voci tecniche solo per chi
    /// gestisce l'app, come prima in Oggi; la copia di sicurezza non si fa dall'app.
    static func vale(_ v: DaFareVoce, _ p: Pagina) -> Bool {
        switch v.tipo {
        case "certificato", "server": return p.tecniche
        case "backup": return false
        case "dubbio":
            guard !p.chiusa, let g = v.giocatore, let a = v.alternativa else { return false }
            return p.titolari.contains(g.id) && !p.titolari.contains(a.id)
        default:
            if v.consigliataCambiata { return !p.chiusa && p.conScelta && p.diversi > 0 }
            return true
        }
    }

    /// «+0,9 punti attesi.»: quanto vale in più, da solo, il sostituto proposto rispetto al titolare (i punti attesi sono quelli del
    /// server), come `guadagno` della web. Niente sotto 0,05 o senza i due numeri.
    static func guadagno(_ v: DaFareVoce, puntiTitolare: Double?) -> String? {
        guard v.tipo == "dubbio", let entra = v.alternativa?.puntiAttesi, let esce = puntiTitolare else { return nil }
        let d = entra - esce
        guard d.isFinite, d >= 0.05 else { return nil }
        return Catalogo.Formazione.decisionePunti(d: Formato.conSegno(d))
    }
}

extension DaFareVoce {
    /// «La consigliata è cambiata da quando l'hai salvata» (id `consigliata:<giornata>`): il pulsante prende la consigliata di adesso.
    var consigliataCambiata: Bool { tipo == "formazione" && id.hasPrefix("consigliata:") }

    /// Il cambio di un titolare che la voce propone (`dubbio` con `alternativa`): chi esce e chi entra.
    var cambio: (esce: Int, entra: Int)? {
        guard tipo == "dubbio", let g = giocatore, let a = alternativa else { return nil }
        return (g.id, a.id)
    }

    /// Al tocco scrive sul server (un cambio di titolare, «Usa la consigliata»): spenta finché la formazione non si può cambiare.
    var scrive: Bool { cambio != nil || consigliataCambiata }

    /// Urgente: davanti al testo la parola «Urgente», non solo il colore.
    var urgente: Bool { priorita == Decisioni.urgente }
}
