import Foundation

extension Funzione {
    /// Il calendario con la difficoltà: il server non lo nomina (la difficoltà sta già nella scheda del giocatore).
    /// Si vede solo se il server lo accende apposta o con «Mostra tutte le funzioni».
    static let calendario = "calendario"
}

extension StatoFunzioni {
    /// Come `acceso`, ma «Mostra tutte» non basta: serve che il server non l'abbia spenta.
    /// Per le funzioni che il server blocca per tutti anche con «Mostra tutte» (immagini da indirizzo web, diretta).
    func accesoDavvero(_ id: String) -> Bool {
        scelte[id] != false
    }

    /// Una funzione che compare solo se il server la accende apposta (o con «Mostra tutte»): una chiave che manca vale «spenta».
    func accesoSoloSeNominato(_ id: String) -> Bool {
        mostraTutte || scelte[id] == true
    }

    /// Il calendario con la difficoltà.
    var vedeCalendario: Bool { accesoSoloSeNominato(Funzione.calendario) }
}

extension Oggi {
    /// Le cose da fare che questo utente può usare: quelle di una funzione spenta non si vedono, e le voci tecniche
    /// (certificato di SideStore, server, copia di sicurezza) solo a chi gestisce l'app (`tecniche`).
    func cose(funzioni: StatoFunzioni, tecniche: Bool) -> [DaFareVoce] {
        raggruppaDiario(cosePerOrdine).filter { voce in
            switch voce.tipo {
            case "certificato", "server": return tecniche
            case "backup": return tecniche && funzioni.acceso(Funzione.backup)
            case "diario": return funzioni.acceso(Funzione.diario)
            case "scambio": return funzioni.acceso(Funzione.scambiTrova)
            default: return true
            }
        }
    }

    /// Più giornate finite da confermare diventano UNA riga («Le giornate 5 e 6 sono finite...») con un solo pulsante:
    /// il diario le mostra tutte. Il numero è quello della lega (come lo scrive il server), non della Serie A.
    func raggruppaDiario(_ voci: [DaFareVoce]) -> [DaFareVoce] {
        let diario = voci.filter { $0.tipo == "diario" }
        guard diario.count > 1 else { return voci }
        let numeri = diario.compactMap { Self.numeroGiornata(in: $0.testo) }
        guard numeri.count == diario.count, let prima = diario.first else { return voci }
        let giornate = Array(Set(numeri)).sorted()
        let elenco = giornate.count > 1
            ? giornate.dropLast().map(String.init).joined(separator: ", ") + " e " + String(giornate[giornate.count - 1])
            : String(giornate[0])
        let unica = DaFareVoce(id: "diario:gruppo", tipo: "diario",
                               testo: "Le giornate \(elenco) sono finite: dimmi se hai schierato la consigliata.",
                               priorita: diario.compactMap(\.priorita).min(), azione: "Vedi", destinazione: prima.destinazione)
        var fatto = false
        return voci.compactMap { voce in
            guard voce.tipo == "diario" else { return voce }
            if fatto { return nil }
            fatto = true
            return unica
        }
    }

    /// Il numero in «La giornata 6 è finita...».
    static func numeroGiornata(in testo: String) -> Int? {
        guard let r = testo.range(of: #"(?<=giornata )\d+"#, options: .regularExpression) else { return nil }
        return Int(testo[r])
    }
}
