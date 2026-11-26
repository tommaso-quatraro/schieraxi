import Foundation

/// Il passo «I tempi della lega» del primo avvio, come la web (`PA_SCADENZE`, `paScadenzaNome`, `vocePrimaGiornata`, `paTempiLeggi`
/// e `paTempiSalva` di primoavvio.js, #931): due domande, quando si chiude la formazione e da quale giornata di Serie A è partita
/// la lega. Logica pura, provata da `TempiGuidaTests`.
enum TempiGuida {
    /// I due valori del passo: minuti prima della prima partita (0 = all'inizio) e giornata di Serie A da cui parte la lega.
    struct Valori: Equatable {
        var scadenza: Int
        var prima: Int
    }

    /// Le scadenze più comuni, in minuti prima della prima partita.
    static let scadenze = [0, 5, 10, 15, 30, 60]
    /// Le giornate di Serie A da cui può partire la lega.
    static let giornate = Array(1...38)
    /// Prima di leggere le regole (o se non si leggono), i valori più comuni, come i menu della web.
    static let partenza = Valori(scadenza: 0, prima: 1)
    /// Il limite del server per la scadenza (`MAX_SCADENZA_MINUTI` di fanta/regole.py, lo stesso di `TempiLega.minutiMassimi`).
    static let minutiMassimi = 720

    /// «All'inizio della prima partita», «1 minuto prima della prima partita», «10 minuti prima della prima partita».
    static func nomeScadenza(_ minuti: Int) -> String {
        minuti == 0 ? Catalogo.Pav.scadInizio : Catalogo.Pav.scadMinuti(minuti)
    }

    /// «Dalla 1ª, con il campionato», «Dalla 2ª», «Dall'8ª».
    static func nomePrima(_ giornata: Int) -> String {
        giornata == 1 ? Catalogo.Pav.primaUno : TempiLega.elidiOrdinali(Catalogo.Pav.primaN(n: String(giornata)))
    }

    /// Le scelte della scadenza: le più comuni e, se è diversa, quella salvata, in fondo (la web la aggiunge al menu).
    static func sceltaScadenze(salvata: Int?) -> [Int] {
        guard let salvata, !scadenze.contains(salvata) else { return scadenze }
        return scadenze + [salvata]
    }

    /// I due valori delle regole lette dal server. Uno che manca o non è un numero vale come sulla web (0 minuti, dalla 1ª); uno
    /// fuori dai limiti del server si riporta dentro, così il menu ha sempre una voce scelta.
    static func valori(_ regole: JSONValue) -> Valori {
        func intero(_ percorso: String) -> Int? {
            regole.valore(percorso)?.numero.flatMap { Int(exactly: $0.rounded()) }
        }
        let scadenza = intero("scadenza_minuti").map { min(max($0, 0), minutiMassimi) } ?? partenza.scadenza
        let prima = intero("prima_giornata_lega").map { min(max($0, 1), giornate.count) } ?? partenza.prima
        return Valori(scadenza: scadenza, prima: prima)
    }

    /// Le regole da salvare: quelle appena lette, con solo questi due valori cambiati (le altre restano come sono).
    static func regole(_ lette: JSONValue, scadenza: Int, prima: Int) -> JSONValue {
        var r = lette
        r.imposta("scadenza_minuti", .intero(scadenza))
        r.imposta("prima_giornata_lega", .intero(prima))
        return r
    }
}
