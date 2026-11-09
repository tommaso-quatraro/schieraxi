/// Le frasi di Oggi che non sono una costante del catalogo. I testi fissi le viste li prendono da `Catalogo.Oggi`, `Catalogo.Df` e
/// `Catalogo.Live`, generati dal catalogo comune con la web (`fanta/testi/`, `python script/testi.py --scrivi`, #494); la prova è
/// `OggiDalCatalogoTests`.
enum TestiOggi {
    /// Sopra il modulo: `oggi.tua_formazione` o, se è la formazione salvata da te, `oggi.tua_formazione_scelta`.
    static func titoloFormazione(tuaScelta: Bool) -> String {
        tuaScelta ? Catalogo.Oggi.tuaFormazioneScelta : Catalogo.Oggi.tuaFormazione
    }
    /// Cosa legge VoiceOver sulle cifre della formazione: «Modulo 4-3-3, 65,5 punti attesi». Senza il titolo della carta
    /// («La tua formazione», «Prossima giornata»), che VoiceOver ha appena letto come intestazione.
    static func voceCifre(modulo: String?, punti: Double?) -> String {
        "Modulo \(modulo ?? "non disponibile"), \(Formato.punti(punti)) \(Catalogo.Oggi.puntiAttesi)"
    }
    /// Il banner delle novità (`oggi.novita_banner`): senza stelline né «tocca per vedere» (`docs/STILE-SENZA-AI.md`). La web lo
    /// scrive in grassetto con `<b>`: qui i segni si tolgono e il grassetto lo mette la vista.
    static func novita(_ versione: String) -> String {
        Catalogo.Oggi.novitaBanner(versione: versione).replacingOccurrences(of: #"<[^>]+>"#, with: "", options: .regularExpression)
    }

    // MARK: Da fare (`cardDaFare` di `fanta/web/dafare.js`, testi `df.*`, #436)

    /// Le voci che si vedono subito (`DF_VISIBILI` della web); le altre stanno sotto «Altre N cose da fare».
    static let daFareVisibili = 4
    /// La priorità delle voci urgenti (`DF_URGENTE` della web).
    static let prioritaUrgente = 1
    /// Il titolo con il numero delle voci, per VoiceOver: «Da fare, 3».
    static func daFareVoce(_ n: Int) -> String { "\(Catalogo.Df.daFare), \(n)" }
}
