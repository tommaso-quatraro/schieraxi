import Foundation
import Testing
@testable import Schieraxi

/// I testi degli avvisi dell'app che l'utente legge: l'avviso della versione nuova dal catalogo, senza la sigla della release
/// («build-37») e con la versione che Informazioni mostra; la riga del certificato in Gestione con il testo vero del promemoria
/// (diceva «Rinnovala con SideStore») e con quando arriva nelle ore tranquille.
struct AvvisiDalCatalogoTests {
    @Test("L'avviso della versione nuova viene dal catalogo, con la versione leggibile e senza sigle")
    func versioneNuova() {
        let avviso = NuovaVersione.avviso(per: NuovaVersione.Esito(build: 38, nome: "build-38"))
        #expect(avviso.titolo == Catalogo.Avv.versioneNuovaTitolo)
        #expect(avviso.testo == Catalogo.Avv.versioneNuovaTesto(versione: "1.0.38"))
        #expect(!avviso.titolo.contains("build") && !avviso.testo.contains("build"), "«\(avviso.titolo)» «\(avviso.testo)»")
    }

    @Test("La versione leggibile è quella che la compilazione dà alla build («1.0.N», come «Versione dell'app» in Informazioni)")
    func versioneLeggibile() {
        #expect(NuovaVersione.versione(build: 38) == "1.0.38")
        #expect(NuovaVersione.versione(build: 216) == "1.0.216")
    }

    @Test("La riga del certificato cita il promemoria com'è davvero (`avv.certificato_ore`) e dice delle ore tranquille")
    func rigaCertificato() {
        let riga = CertificatoSezione.aiuto
        #expect(riga.contains(Catalogo.Avv.certificatoOre(6)), "«\(riga)»")
        #expect(!riga.contains("SideStore"), "il promemoria non nomina SideStore: «\(riga)»")
        #expect(riga.contains("ore tranquille"), "nelle ore tranquille arriva prima che comincino: «\(riga)»")
    }
}
