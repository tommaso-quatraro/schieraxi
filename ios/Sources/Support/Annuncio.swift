import Accessibility
import SwiftUI

/// Una frase che VoiceOver legge da solo, senza che si sposti il dito: l'esito di un'azione che compare lontano dal pulsante toccato
/// (un errore, una formazione salvata), come una regione `role="status"` della web. Priorità alta: la frase non si perde quando il
/// pulsante toccato cambia scritta («Un attimo…») o sparisce («Torna alla consigliata»), e VoiceOver la legge intera.
enum Annuncio {
    /// La frase con la priorità alta di VoiceOver.
    static func testo(_ frase: String) -> AttributedString {
        var testo = AttributedString(frase)
        testo.accessibilitySpeechAnnouncementPriority = .high
        return testo
    }

    /// Fa leggere la frase a VoiceOver (senza VoiceOver non succede niente).
    @MainActor static func leggi(_ frase: String) {
        AccessibilityNotification.Announcement(testo(frase)).post()
    }
}
