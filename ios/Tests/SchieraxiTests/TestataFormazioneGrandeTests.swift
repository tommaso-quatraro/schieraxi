import Testing
@testable import Schieraxi

/// Issue #391: il widget Formazione grande scriveva «G8» in alto a destra anche dove «Giornata 8» entrava (come la #352 per
/// «Attesi e fatti»). La testata era una riga sola e le due parti si accorciavano in coppia: per far posto a «72,7 attesi · la tua
/// scelta» la giornata diventava «G8» prima ancora che i punti perdessero una parola. Ora la giornata sta sulla riga corta della
/// fascia («tra 65 e 81»), non su quella dei punti: le due righe scelgono ognuna la sua forma, dalla più lunga alla più corta.
/// E come vuole la #299, nei widget della Formazione mai «G8»: dove lo spazio è poco «Giornata 8» (VoiceOver legge sempre la forma
/// intera); la stessa funzione (`ParoleWidget.formeGiornata`) per il grande, il piccolo e la schermata di blocco. Numeri inventati.
@Suite("Widget Formazione: «Giornata 8», mai «G8» (#391, #299)")
struct TestataFormazioneGrandeTests {
    private let giornata = NomeGiornata(serieA: 11, lega: 8)

    @Test("La giornata ha le sue forme, le stesse con o senza la tua scelta: non si accorcia per far posto ai punti",
          arguments: [false, true])
    func giornataDaSola(tuaScelta: Bool) {
        let t = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: tuaScelta, fascia: "tra 65 e 81", giornata: giornata)
        #expect(t.formeGiornata == ["Giornata 8 · 11ª di Serie A", "Giornata 8"])
    }

    @Test("Mai «G8»: la forma più corta è «Giornata 8», la stessa nel widget grande e nel piccolo (#299)")
    func maiLaSigla() {
        let forme = ParoleWidget.formeGiornata(giornata)
        #expect(forme == ["Giornata 8 · 11ª di Serie A", "Giornata 8"])
        #expect(!forme.contains(giornata.sigla), "«\(giornata.sigla)» tra le forme: \(forme)")
        #expect(forme.last == giornata.corto)
        let grande = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: true, fascia: nil, giornata: giornata)
        #expect(grande.formeGiornata == forme, "il grande usa la stessa funzione del piccolo")
    }

    @Test("Se «Giornata 8» non entra accanto alla fascia scende sulla riga sotto: prima accanto, poi sotto, mai tagliata")
    func giornataSottoLaFascia() {
        typealias Posto = TestataFormazioneGrande.PostoGiornata
        let t = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: true, fascia: "tra 65 e 81", giornata: giornata)
        #expect(t.postiGiornata == [
            Posto(forma: "Giornata 8 · 11ª di Serie A", sotto: false), Posto(forma: "Giornata 8", sotto: false),
            Posto(forma: "Giornata 8 · 11ª di Serie A", sotto: true), Posto(forma: "Giornata 8", sotto: true),
        ])
        #expect(t.postiGiornata.last == Posto(forma: "Giornata 8", sotto: true), "l'ultimo ripiego è «Giornata 8» sotto la fascia")
    }

    @Test("Senza fascia la riga è tutta della giornata: niente posto «sotto»")
    func senzaFasciaNienteSotto() {
        let t = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: nil, giornata: giornata)
        #expect(t.postiGiornata.map(\.forma) == ["Giornata 8 · 11ª di Serie A", "Giornata 8"])
        #expect(t.postiGiornata.allSatisfy { !$0.sotto })
    }

    @Test("I punti perdono parole intere e la tua scelta resta finché entra")
    func punti() {
        let tua = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: true, fascia: "tra 65 e 81", giornata: giornata)
        #expect(tua.formePunti == ["72,7 punti attesi · la tua scelta", "72,7 attesi · la tua scelta", "72,7 attesi"])
        let consigliata = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: nil, giornata: giornata)
        #expect(consigliata.formePunti == ["72,7 punti attesi", "72,7 attesi"])
    }

    @Test("La fascia resta com'è, accanto alla giornata; senza fascia non c'è")
    func fascia() {
        #expect(TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: "tra 65 e 81", giornata: giornata).fascia
                == "tra 65 e 81")
        #expect(TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: nil, giornata: giornata).fascia == nil)
    }

    @Test("Senza il numero della lega: «11ª giornata di Serie A», poi «11ª di Serie A», mai «G11»; senza giornata niente")
    func senzaLega() {
        let t = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: nil, giornata: NomeGiornata(serieA: 11, lega: nil))
        #expect(t.formeGiornata == ["11ª giornata di Serie A", "11ª di Serie A"])
        #expect(TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: nil, giornata: nil).formeGiornata.isEmpty)
        #expect(ParoleWidget.formeGiornata(nil).isEmpty)
    }
}
