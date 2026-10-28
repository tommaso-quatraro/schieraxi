# SchieraXI per iOS

App **nativa** (SwiftUI) per iPhone e iPad. Parla con il server di SchieraXI sul server (API JSON, rete privata acceso) e usa le funzioni di iOS.
Il server e la logica (modello, formazioni, scambi) stanno nell'altro repository (`schieraxi`): qui c'è solo l'app.

## Cosa c'è
- **Oggi, Formazione, Lega:** nativi (SwiftUI, materiali di vetro di iOS, pull-to-refresh, feedback aptico, condivisione della formazione con ShareLink).
- **Promemoria locali** (UserNotifications): un'ora e un quarto d'ora prima della prima partita, anche con l'app chiusa. Non servono push né account a pagamento.
- **Mercato, Scambi:** da portare in nativo (per ora rimandano alla web app).

## Come si compila (nessun Mac)
- GitHub Actions su un Mac (`macos-15`), senza firma: produce `Schieraxi.ipa` (artifact e release `build-N`). Gratis anche nel repository privato.
- Indirizzo del server: variabili del repository `FANTA_HOST` e `FANTA_PORT`; si può cambiare anche dalla schermata Lega.
- **Installazione:** SideStore sull'iPhone firma l'IPA con l'Apple ID gratuito e lo rinnova da solo (ogni 7 giorni, in background, con LocalDevVPN attiva).

## Limiti noti (Apple ID gratuito)
- Niente notifiche push (APNs): per gli avvisi del server resta la web app installata dalla Home; l'app nativa usa promemoria locali.
- Certificato di 7 giorni, massimo 3 app: serve il rinnovo di SideStore.
- Mai in git: firme, certificati, profili, password, Apple ID.
