import SwiftUI

/// Lo stato della pagina Giornate (#673, passo 2): le giornate finite di `GET /api/diario`, le righe aperte, «Dettagli» e la correzione
/// «Non è quello che ho schierato». Sta in `AppModel`: cambiando sezione righe aperte e «Dettagli» restano come erano.
@MainActor
final class GiornateViewModel: ViewModelBase {
    let caricatore: Caricatore<DiarioRisposta>
    let server: any ServerClient

    /// Sul telefono le righe aperte (anche più di una); sull'iPad la prima è la giornata scelta a destra.
    @Published var aperte: Set<String> = []
    /// Sull'iPad la giornata a destra (nil = la più recente).
    @Published var scelta: String?
    /// «Dettagli» aperto.
    @Published var dettagliAperti = false
    /// La giornata (numero di Serie A) da aprire quando arrivano le giornate che la contengono («Com'è andata»), come `chiesta`
    /// della web: vale finché non arriva una risposta che la contiene; la copia del telefono può non averla ancora.
    private(set) var chiesta: Int?
    /// L'esito dell'ultima correzione e la sua giornata: si mostra sotto i suoi 11.
    @Published private(set) var esito: (id: String, testo: String)?
    /// La giornata appena corretta: chiuso il foglio, VoiceOver torna sulla sua riga (`prendiCorretta`).
    private var corretta: String?
    /// Fa leggere un esito a VoiceOver. Si sostituisce nei test per contare gli annunci.
    var annuncia: @MainActor (String) -> Void = { AccessibilityNotification.Announcement($0).post() }

    init(server: any ServerClient) {
        self.server = server
        caricatore = Caricatore<DiarioRisposta>("/api/diario", server: server)
        super.init()
        osserva(caricatore)
    }

    /// La pagina pronta da mostrare (nil finché non c'è una risposta, anche dalla copia del telefono).
    var pagina: PaginaGiornate? { caricatore.dato.map(PaginaGiornate.init) }

    func carica() async {
        await caricatore.ricarica()
        applicaChiesta()
    }

    /// «Com'è andata» o un indirizzo: apre la giornata `giornata` (numero di Serie A) appena c'è; nil = la pagina com'è.
    func apri(giornata: Int?) {
        guard let giornata, giornata > 0 else { return }
        chiesta = giornata
        applicaChiesta()
    }

    /// Solo per le foto della demo (`giornate-aperta`): la giornata più recente si apre appena c'è.
    private var piuRecenteDaAprire = false

    /// Le foto della demo: `giornate-aperta` apre la giornata più recente, `giornate-dettagli` apre «Dettagli».
    func preparaFoto(_ nome: String) {
        switch nome {
        case "giornate-aperta":
            piuRecenteDaAprire = true
            applicaChiesta()
        case "giornate-dettagli":
            dettagliAperti = true
        default:
            break
        }
    }

    /// La giornata chiesta, se le giornate arrivate la contengono: la sola aperta, e quella a destra sull'iPad. La richiesta resta
    /// finché non arriva una risposta fresca del server (la copia del telefono può essere di prima della giornata).
    func applicaChiesta() {
        if piuRecenteDaAprire, let id = pagina?.righe.first?.id {
            piuRecenteDaAprire = false
            aperte = [id]
            scelta = id
        }
        guard let g = chiesta, let p = pagina else { return }
        if let id = p.id(giornata: g) {
            aperte = [id]
            scelta = id
            chiesta = nil
        } else if !caricatore.dallaCache, !caricatore.inCorso {
            chiesta = nil
        }
    }

    /// Un tocco su una riga del telefono: apre o chiude i suoi 11 sotto di lei.
    func apriChiudi(_ id: String) {
        if aperte.contains(id) { aperte.remove(id) } else { aperte.insert(id) }
    }

    /// La giornata corretta per ultima, una volta sola (chiuso il foglio con «Annulla» non c'è niente).
    func prendiCorretta() -> String? {
        defer { corretta = nil }
        return corretta
    }

    /// L'esito da mostrare sotto gli 11 di questa giornata, se è suo.
    func esito(per id: String) -> String? {
        esito?.id == id ? esito?.testo : nil
    }

    /// «Non è quello che ho schierato»: gli 11 scelti a mano per una giornata finita, con la stagione della voce (il server rifiuta
    /// quelle passate). Nil se è andata bene (il foglio si chiude e la pagina rilegge, con quella giornata aperta), altrimenti
    /// l'errore da mostrare nel foglio.
    func correggi(_ voce: VoceDiario, titolari: [Int]) async -> String? {
        guard voce.siPuoCambiare, let giornata = voce.giornata else {
            return "Non riesco a salvare adesso: riprova tra poco."
        }
        do {
            let corpo = CorpoSchierata(giornata: giornata, tipo: "manuale", titolari: titolari, stagione: voce.stagione)
            _ = try await server.corpoJSON("POST", "/api/diario/schierata", corpo)
        } catch {
            let testo = error.localizedDescription
            Haptics.esito(riuscito: false)
            annuncia(testo)
            if (error as? ErroreApi)?.eConflitto == true { await caricatore.ricarica() }
            return testo
        }
        aperte = [voce.id]
        scelta = voce.id
        corretta = voce.id
        esito = (voce.id, Catalogo.Diario.salvataManuale)
        Haptics.esito(riuscito: true)
        annuncia(Catalogo.Diario.salvataManuale)
        await caricatore.ricarica()
        return nil
    }
}

/// Il corpo di `POST /api/diario/schierata`.
struct CorpoSchierata: Encodable {
    let giornata: Int
    /// «manuale» (con `titolari`); il server accetta anche «consigliata», che l'app non manda più.
    let tipo: String
    var titolari: [Int]? = nil
    /// La stagione della voce del diario: il server rifiuta le stagioni passate invece di scrivere sulla giornata con lo stesso
    /// numero di quest'anno. Senza (nil) il campo non si manda e il server usa la stagione in corso.
    var stagione: String? = nil
}
