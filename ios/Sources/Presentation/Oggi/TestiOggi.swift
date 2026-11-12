/// Le frasi di Oggi che non sono una costante del catalogo. I testi fissi le viste li prendono da `Catalogo.Oggi` e `Catalogo.Df`,
/// generati dal catalogo comune con la web (`fanta/testi/`, `python script/testi.py --scrivi`, #494); la prova è
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

    // MARK: Da fare (`cardDaFare` di `fanta/web/dafare.js`, testi `df.*`, #436)

    /// Le voci che si vedono subito (`DF_VISIBILI` della web); le altre stanno sotto «Altre N cose da fare».
    static let daFareVisibili = 4
    /// La priorità delle voci urgenti (`DF_URGENTE` della web).
    static let prioritaUrgente = 1
    /// Il titolo con il numero delle voci, per VoiceOver: «Da fare, 3».
    static func daFareVoce(_ n: Int) -> String { "\(Catalogo.Df.daFare), \(n)" }
}
