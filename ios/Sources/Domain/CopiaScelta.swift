import Foundation

/// La scelta della giornata letta dal server, tenuta sul telefono accanto alla copia della Formazione, come la copia «giornata» della
/// web, che ha dentro la scelta (revisione della #694): riaprendo l'app senza rete, e mentre arrivano i dati nuovi, in campo c'è la
/// formazione salvata e non la consigliata al suo posto. `FormazioneViewModel` la scrive dopo ogni lettura o salvataggio riusciti e la
/// legge una volta all'apertura; finché il server non risponde i comandi che scrivono restano spenti. Sta fra le copie del telefono
/// (`Cache`), che all'uscita dall'account si cancellano tutte.
struct CopiaScelta: Codable, Equatable {
    /// Il nome sotto cui sta fra le copie del telefono (`Cache`): non è un indirizzo del server.
    static let percorso = "/copia/scelta"

    let giornata: Int
    /// Gli 11 salvati; nil = nessuna scelta (vale la consigliata).
    var titolari: [Int]?
    var modulo: String?
    var eraConsigliata: Bool?
    var messa: Bool?
    /// La scelta salvata non si può più schierare (vale la consigliata).
    var nonValida: Bool
    /// La valutazione del server per 11 che non sono un modulo già calcolato (modulo, punti, panchina e fascia del campo).
    var valutazione: Valutazione?

    struct Valutazione: Codable, Equatable {
        let modulo: String
        let punteggioAtteso: Double
        var dev: Double?
        var panchina: [Int]
        var basso: Double?
        var alto: Double?
    }

    init(giornata: Int, scelta: SceltaSalvata?, nonValida: Bool, valutazione: ValutazioneManuale?) {
        self.giornata = giornata
        titolari = scelta?.titolari
        modulo = scelta?.modulo
        eraConsigliata = scelta?.eraConsigliata
        messa = scelta?.messa
        self.nonValida = nonValida
        self.valutazione = valutazione.map {
            Valutazione(modulo: $0.modulo, punteggioAtteso: $0.punteggioAtteso, dev: $0.dev, panchina: $0.panchina,
                        basso: $0.intervallo?.basso, alto: $0.intervallo?.alto)
        }
    }

    /// La scelta salvata com'era quando è stata letta (nil = nessuna).
    var scelta: SceltaSalvata? {
        titolari.map { SceltaSalvata(titolari: $0, modulo: modulo, eraConsigliata: eraConsigliata, messa: messa) }
    }

    /// La valutazione del server com'era, con quello che serve al campo.
    var valutazioneManuale: ValutazioneManuale? {
        valutazione.map {
            ValutazioneManuale(modulo: $0.modulo, punteggioAtteso: $0.punteggioAtteso, dev: $0.dev, panchina: $0.panchina,
                               differenza: nil, consigliata: nil, consigliataStessoModulo: nil, bruttaGiornata: nil,
                               giornataEccezionale: nil, intervallo: IntervalloPunti(basso: $0.basso, alto: $0.alto))
        }
    }

    /// I byte da tenere sul telefono.
    var dati: Data? { try? JSONEncoder().encode(self) }

    /// La copia letta dal telefono; nil se non si legge (per esempio scritta da una versione diversa dell'app).
    static func da(_ dati: Data) -> CopiaScelta? { try? JSONDecoder().decode(CopiaScelta.self, from: dati) }
}
