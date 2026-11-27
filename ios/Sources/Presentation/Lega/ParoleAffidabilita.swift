import Foundation

/// Le parole della prova del modello in Stato dei dati («Quanto è affidabile il modello»), uguali alla web (`mostraAffidabilita` in
/// `fanta/web/app.js`, chiavi `avv.*` del catalogo): i nomi delle tre linee del grafico, il nome che legge VoiceOver, le giornate
/// sotto la legenda e il verde sui punti del modello quando battono quelli da fantamedia. Logica pura: la prova
/// `LaMiaLegaComeLaWebTests`.
enum ParoleAffidabilita {
    /// «modello» (`avv.modello_nbsp`).
    static let modello = senzaSpazioFisso(Catalogo.Avv.modelloNbsp)
    /// «da fantamedia» (`avv.fantamedia_nbsp`).
    static let fantamedia = senzaSpazioFisso(Catalogo.Avv.fantamediaNbsp)
    /// «massimo possibile» (`avv.max_possibile`).
    static let massimo = Catalogo.Avv.maxPossibile
    /// Il nome del grafico per VoiceOver, l'`aria-label` della web (`avv.punti_delle_formazioni`).
    static let nomeGrafico = Catalogo.Avv.puntiDelleFormazioni

    /// Le voci della legenda della web finiscono con uno spazio fisso («modello &nbsp;») che le separa dalla voce dopo: la legenda
    /// del grafico dell'iPhone le separa da sola, quindi resta la parola.
    static func senzaSpazioFisso(_ testo: String) -> String {
        testo.replacingOccurrences(of: "&nbsp;", with: " ").trimmingCharacters(in: .whitespaces)
    }

    /// «dalla 5ª alla 12ª giornata di Serie A» (`avv.giornate_da_a`): dalla prima all'ultima giornata del grafico, con l'apostrofo
    /// davanti all'8ª e all'11ª come la web (`elidiOrdinali`). Nil senza giornate.
    static func giornate(_ righe: [RigaAffidabilita]) -> String? {
        let numeri = righe.map(\.giornata)
        guard let prima = numeri.min(), let ultima = numeri.max() else { return nil }
        return TempiLega.elidiOrdinali(Catalogo.Avv.giornateDaA(a: String(prima), b: String(ultima)))
    }

    /// Una giornata nell'elenco dei numeri e per VoiceOver, con i nomi della legenda: «5ª giornata di Serie A: modello 70,1,
    /// da fantamedia 66,4, massimo possibile 88,0».
    static func riga(_ r: RigaAffidabilita) -> String {
        "\(TempiLega.serieA(r.giornata)): \(modello) \(punti(r.puntiModello)), \(fantamedia) \(punti(r.puntiFantamedia)), "
            + "\(massimo) \(punti(r.puntiPerfetta))"
    }

    /// I punti della formazione del modello sono verdi quando valgono almeno quelli da fantamedia, come la web (classe `positivo`);
    /// senza uno dei due numeri, no.
    static func modelloBatteFantamedia(_ s: SintesiAffidabilita) -> Bool {
        guard let modello = s.puntiModello, let fantamedia = s.puntiFantamedia else { return false }
        return modello >= fantamedia
    }

    private static func punti(_ valore: Double?) -> String { valore.map { Formato.decimali($0) } ?? "–" }
}
