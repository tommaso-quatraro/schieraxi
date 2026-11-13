import Foundation
import Testing
@testable import Schieraxi

/// La riga dello stato sotto il campo, come `rigaStato` di `mostraFormazione` della web (#616, #673): cinque stati (consigliata,
/// cambiata, superata, non più valida, chiusa con le sue tre frasi) e la scelta che non si legge. Frasi dal catalogo comune, plurali
/// e punti con il segno come la web (`Formato.conSegno`). Più il modulo dai ruoli e la validità della scelta salvata. Dati inventati.
@Suite("Riga dello stato della scelta, come la web")
struct StatoSceltaTests {
    /// Gli 11 della consigliata.
    static let consigliati = Array(1...11)
    /// Due titolari diversi dalla consigliata.
    static let dueDiversi = Array(1...9) + [20, 21]
    /// Un titolare diverso dalla consigliata.
    static let unoDiverso = Array(1...10) + [20]

    /// Lo stato con i valori di una formazione aperta, letta, con gli 11 della consigliata: ogni prova cambia solo ciò che le serve.
    /// Punti esatti in binario (70 e 70,5), così la differenza è proprio −0,5.
    static func stato(mia: Bool = true, letta: Bool = true, copia: Bool = false, chiusa: Bool = false, salvata: SceltaSalvata? = nil,
                      nonValida: Bool = false, titolari: [Int] = consigliati, punti: Double? = 70,
                      puntiConsigliata: Double? = 70.5) -> StatoScelta {
        StatoScelta.calcola(mia: mia, letta: letta, copia: copia, chiusa: chiusa, salvata: salvata, nonValida: nonValida,
                            titolari: titolari, consigliati: consigliati, punti: punti, puntiConsigliata: puntiConsigliata)
    }

    // MARK: cinque stati

    @Test("Gli 11 della consigliata, anche salvati e in un altro ordine: «È la consigliata.», senza «Torna alla consigliata»")
    func consigliata() {
        #expect(Self.stato() == .consigliata)
        let rovescia = Array(Self.consigliati.reversed())
        #expect(Self.stato(salvata: SceltaSalvata(titolari: rovescia), titolari: rovescia) == .consigliata)
        #expect(StatoScelta.consigliata.frase == Catalogo.Formazione.statoEConsigliata)
        #expect(StatoScelta.consigliata.frase == "È la consigliata.")
        #expect(!StatoScelta.consigliata.conTorna)
        #expect(StatoScelta.consigliata.tono == .neutro)
    }

    @Test("Cambiata da te: quanti titolari diversi, con il plurale giusto, e i punti con il segno della web")
    func cambiata() {
        let due = Self.stato(salvata: SceltaSalvata(titolari: Self.dueDiversi), titolari: Self.dueDiversi)
        #expect(due == .cambiata(diversi: 2, punti: -0.5))
        #expect(due.frase == "L'hai cambiata tu: 2 titolari diversi dalla consigliata (\u{2212}0,5 punti attesi).")
        #expect(due.frase == Catalogo.Formazione.statoCambiata(2, d: " (" + Catalogo.Formazione.statoPunti(d: "\u{2212}0,5") + ")"))
        let uno = Self.stato(salvata: SceltaSalvata(titolari: Self.unoDiverso), titolari: Self.unoDiverso, punti: 71)
        #expect(uno.frase == "L'hai cambiata tu: 1 titolare diverso dalla consigliata (+0,5 punti attesi).")
        #expect(due.conTorna && uno.conTorna)
        #expect(due.tono == .neutro)
    }

    @Test("Senza uno dei due numeri la frase resta, senza i punti; a pari punti «0,0» senza segno")
    func cambiataSenzaPunti() {
        let senza = Self.stato(salvata: SceltaSalvata(titolari: Self.dueDiversi), titolari: Self.dueDiversi, punti: nil)
        #expect(senza == .cambiata(diversi: 2, punti: nil))
        #expect(senza.frase == "L'hai cambiata tu: 2 titolari diversi dalla consigliata.")
        let pari = Self.stato(salvata: SceltaSalvata(titolari: Self.dueDiversi), titolari: Self.dueDiversi, punti: 70.5)
        #expect(pari.frase == "L'hai cambiata tu: 2 titolari diversi dalla consigliata (0,0 punti attesi).")
        let strano = Self.stato(salvata: SceltaSalvata(titolari: Self.dueDiversi), titolari: Self.dueDiversi, punti: .nan)
        #expect(strano == .cambiata(diversi: 2, punti: nil), "un numero non finito vale come mancante")
    }

    @Test("Avevi salvato la consigliata ed è cambiata lei: la frase «superata», arancio, con «Torna alla consigliata»")
    func superata() {
        let salvata = SceltaSalvata(titolari: Self.unoDiverso, eraConsigliata: true)
        let s = Self.stato(salvata: salvata, titolari: Self.unoDiverso, punti: 70)
        #expect(s == .superata(diversi: 1, punti: -0.5))
        #expect(s.frase == "La consigliata è cambiata da quando l'hai salvata: 1 titolare diverso (\u{2212}0,5 punti attesi).")
        let due = Self.stato(salvata: SceltaSalvata(titolari: Self.dueDiversi, eraConsigliata: true), titolari: Self.dueDiversi, punti: nil)
        #expect(due.frase == Catalogo.Formazione.statoSuperata(2, d: ""))
        #expect(s.conTorna)
        #expect(s.tono == .attenzione)
    }

    @Test("La scelta salvata non vale più: in campo la consigliata, la frase della web in rosso, con «Torna alla consigliata»")
    func nonValida() {
        let s = Self.stato(salvata: SceltaSalvata(titolari: Self.dueDiversi), nonValida: true)
        #expect(s == .nonValida)
        #expect(s.frase == Catalogo.Formazione.statoNonValidaOra)
        #expect(s.conTorna)
        #expect(s.tono == .malus)
    }

    /// A giornata chiusa: se c'è una scelta salvata, se non vale più, quale frase e la frase del catalogo.
    static let chiusure: [(Bool, Bool, StatoScelta.Chiusura, String)] = [
        (false, false, .senzaScelta, Catalogo.Formazione.statoChiusa),
        (true, false, .tua, Catalogo.Formazione.statoChiusaTua),
        (true, true, .nonValida, Catalogo.Formazione.statoChiusaNonValida),
    ]

    @Test("Giornata chiusa: le tre frasi della web, prima di tutto il resto, senza «Torna alla consigliata»",
          arguments: StatoSceltaTests.chiusure)
    func chiusa(conScelta: Bool, nonValida: Bool, chiusura: StatoScelta.Chiusura, frase: String) {
        let salvata = conScelta ? SceltaSalvata(titolari: Self.dueDiversi) : nil
        let s = Self.stato(chiusa: true, salvata: salvata, nonValida: nonValida, titolari: Self.dueDiversi)
        #expect(s == .chiusa(chiusura))
        #expect(s.frase == frase)
        #expect(!s.conTorna)
        #expect(s.simbolo == "lock.fill")
        #expect(s.tono == .neutro)
    }

    // MARK: quando non si dice niente

    @Test("Scelta non letta: l'errore della web; sulla copia del telefono e a giornata chiusa niente")
    func nonLetta() {
        let s = Self.stato(letta: false)
        #expect(s == .nonLetta)
        #expect(s.frase == Catalogo.Formazione.sceltaNonLetta)
        #expect(!s.conTorna)
        #expect(s.tono == .malus)
        #expect(Self.stato(letta: false, copia: true) == .nessuno, "i dati nuovi stanno arrivando")
        #expect(Self.stato(letta: false, chiusa: true) == .nessuno)
    }

    @Test("La formazione di un'altra squadra non ha la riga dello stato")
    func altraSquadra() {
        #expect(Self.stato(mia: false, titolari: Self.dueDiversi) == .nessuno)
        #expect(StatoScelta.nessuno.frase.isEmpty)
        #expect(StatoScelta.nessuno.simbolo.isEmpty)
    }

    @Test("VoiceOver: il «·» delle frasi chiuse diventa una virgola")
    func voce() {
        #expect(StatoScelta.chiusa(.tua).voce == "Giornata iniziata: la formazione è chiusa, vale quella che hai salvato")
        #expect(!StatoScelta.chiusa(.nonValida).voce.contains("·"))
    }

    // MARK: modulo e validità

    @Test("Il modulo si conta dai ruoli dei titolari")
    func moduloDaiRuoli() {
        #expect(ModuloTitolari.modulo(ruoli: ["P", "D", "D", "D", "C", "C", "C", "C", "A", "A", "A"]) == "3-4-3")
        #expect(ModuloTitolari.modulo(ruoli: []) == "0-0-0")
    }

    @Test("La scelta salvata si giudica solo con la rosa: senza rosa non si dice che non vale")
    func validita() throws {
        let rosa: [String: Giocatore] = try Dictionary(uniqueKeysWithValues: (1...12).map { id in
            (String(id), try Decodifica.decodifica(Data("{\"id\": \(id), \"nome\": \"Prova \(id)\", \"ruolo\": \"C\"}".utf8)) as Giocatore)
        })
        #expect(ValiditaScelta.controlla(titolari: Self.consigliati, rosa: rosa) == .valida)
        #expect(ValiditaScelta.controlla(titolari: Array(1...10), rosa: rosa) == .nonValida)
        #expect(ValiditaScelta.controlla(titolari: Array(1...10) + [1], rosa: rosa) == .nonValida, "doppioni")
        #expect(ValiditaScelta.controlla(titolari: Array(2...12), rosa: [:]) == .nonSiSa, "rosa vuota: non si giudica")
        #expect(ValiditaScelta.controlla(titolari: Array(1...10), rosa: nil) == .nonSiSa, "senza rosa: non si giudica")
        #expect(ValiditaScelta.controlla(titolari: Array(1...10) + [77], rosa: rosa) == .nonValida, "uno fuori rosa")
    }
}
