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

    @Test("Gestione, versione nuova: la riga di chi gestisce dice le versioni come il banner, senza «build-38»")
    func rigaVersioneDiChiGestisce() {
        let riga = NuovaVersioneSezione.disponibile(NuovaVersione.Esito(build: 38, nome: "build-38"), installata: 37)
        #expect(riga.contains(NuovaVersione.versione(build: 38)) && riga.contains(NuovaVersione.versione(build: 37)), "«\(riga)»")
        #expect(!riga.contains("build"), "«\(riga)»")
    }

    @Test("La riga del certificato viene dal catalogo, cita il promemoria com'è davvero e dice cosa fa con le ore tranquille")
    func rigaCertificato() {
        let riga = CertificatoSezione.aiuto
        #expect(riga == Catalogo.Avv.certificatoAiuto(promemoria: Catalogo.Avv.certificatoOre(6)))
        #expect(riga.contains(Catalogo.Avv.certificatoOre(6)), "«\(riga)»")
        #expect(!riga.contains("SideStore"), "il promemoria non nomina SideStore: «\(riga)»")
        // come `Notifiche.promemoriaCertificato` (provato in `PromemoriaTestiDelServerTests`): prima che comincino, oppure alla loro
        // fine se sono già cominciate e manca almeno un'ora
        #expect(riga.contains("un minuto prima che comincino") && riga.contains("già cominciate") && riga.contains("almeno un'ora"),
                "«\(riga)»")
    }
}
