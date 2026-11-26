import Foundation

/// Impostazioni › Informazioni, le righe della versione (#931): prima quella del server, come la web (`versione` di `/api/stato`,
/// `info.versione`), poi quella dell'app installata, che ha solo l'iPhone (`info.versione_app`, differenza ammessa). Quando una
/// manca, la lineetta della web («–»). Logica pura, provata da `VersioniInformazioniTests`.
enum VersioniInformazioni {
    struct Riga: Equatable {
        let titolo: String
        let valore: String
    }

    static func righe(server: String?, app: String?) -> [Riga] {
        func oLineetta(_ testo: String?) -> String {
            let pulito = testo?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return pulito.isEmpty ? "–" : pulito
        }
        return [Riga(titolo: Catalogo.Info.versione, valore: oLineetta(server)),
                Riga(titolo: Catalogo.Info.versioneApp, valore: oLineetta(app))]
    }
}
