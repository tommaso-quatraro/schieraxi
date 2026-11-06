import Testing
@testable import Schieraxi

/// Issue #391: il widget Formazione grande scriveva «G8» in alto a destra anche dove «Giornata 8» entrava (come la #352 per
/// «Attesi e fatti»). La testata era una riga sola e le due parti si accorciavano in coppia: per far posto a «72,7 attesi · la tua
/// scelta» la giornata diventava «G8» prima ancora che i punti perdessero una parola. Ora la giornata sta sulla riga corta della
/// fascia («tra 65 e 81»), non su quella dei punti: le due righe scelgono ognuna la sua forma, dalla più lunga alla più corta,
/// e «G8» resta solo se «Giornata 8» non entra nemmeno lì. Numeri inventati.
@Suite("Widget Formazione grande: «Giornata 8» dove entra, «G8» solo se non entra (#391)")
struct TestataFormazioneGrandeTests {
    private let giornata = NomeGiornata(serieA: 11, lega: 8)

    @Test("La giornata ha le sue forme, le stesse con o senza la tua scelta: non si accorcia per far posto ai punti",
          arguments: [false, true])
    func giornataDaSola(tuaScelta: Bool) {
        let t = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: tuaScelta, fascia: "tra 65 e 81", giornata: giornata)
        #expect(t.formeGiornata == ["Giornata 8 · 11ª di Serie A", "Giornata 8", "G8"])
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

    @Test("Senza il numero della lega: «11ª giornata di Serie A», poi «11ª di Serie A», poi «G11»; senza giornata niente")
    func senzaLega() {
        let t = TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: nil, giornata: NomeGiornata(serieA: 11, lega: nil))
        #expect(t.formeGiornata == ["11ª giornata di Serie A", "11ª di Serie A", "G11"])
        #expect(TestataFormazioneGrande(puntiAttesi: 72.7, tuaScelta: false, fascia: nil, giornata: nil).formeGiornata.isEmpty)
    }
}
