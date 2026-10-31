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
        cosePerOrdine.filter { voce in
            switch voce.tipo {
            case "certificato", "server": return tecniche
            case "backup": return tecniche && funzioni.acceso(Funzione.backup)
            case "diario": return funzioni.acceso(Funzione.diario)
            case "scambio": return funzioni.acceso(Funzione.scambiTrova)
            default: return true
            }
        }
    }
}
