import Foundation

extension Giocatore {
    /// Da fare (#283, #284): per ora la pedina dice sempre «gioca N%».
    var esitoPedina: String? { nil }

    /// La frase di VoiceOver della pedina.
    var vocePedina: String {
        LetturaPedina.voce(nome: nome, ruolo: nomeRuolo(ruolo), fvAtteso: fvAtteso, pVoto: pVoto, avversario: avversario, inCasa: inCasa)
    }
}
