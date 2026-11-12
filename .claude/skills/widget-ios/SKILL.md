---
name: widget-ios
description: Come funzionano e si modificano i widget iOS di SchieraXI con Apple ID gratuito e SideStore - collegamento automatico (App Group letto dal profilo della firma, Keychain condiviso), «Tocca per collegare» come ultimo ripiego, token fw_ a scopo limitato, /api/widget con ETag, aggiornamento e tocchi. Usala prima di toccare l'estensione widget o la rotta /api/widget.
---

# Widget iOS di SchieraXI

Riferimenti nel repo `schieraxi`: `ios/docs/WIDGET.md` (quali widget, misure, dati) e `docs/RIFERIMENTO.md`, «Contratti delle API» (token del widget).

**Come firma SideStore (letto nel codice, ramo `develop`, 1/11/2026)**
- [verificato] App Group `group.X` → registrato come `group.X.<TEAMID>`, uguale per app ed estensioni (`FetchProvisioningProfilesOperation.adjustedGroupIdentifier`); bundle id → `it.schieraxi.app.<TEAMID>` (widget `...<TEAMID>.widget`). Se un gruppo non si registra l'installazione FALLISCE (non lo salta).
- [verificato] Dal commit 7866508 (15/9/2026) SideStore NON scrive più `ALTAppGroups` in Info.plist (AltStore e le SideStore vecchie sì; Sideloadly mai). Il nome vero si legge da `embedded.mobileprovision` del PROPRIO pacchetto (`ProfiloFirma` in `Condiviso.swift`), poi si prova con `containerURL(forSecurityApplicationGroupIdentifier:)`.
- [verificato] Firma con i permessi del profilo ma SOLO le chiavi che l'app dichiara (ldid in `ipa.yml`); per `keychain-access-groups` tiene i gruppi dell'app cambiando il prefisso prima del primo punto con il TEAMID (`ALTSigner.swift` di SideStore/AltSign). Quindi un Keychain condiviso app↔widget si ottiene dichiarando `<prefisso>.it.schieraxi.app.condiviso`.
- [da verificare sul telefono] che il profilo gratuito contenga gruppo e `keychain-access-groups` e che widget e app vedano gli stessi dati (Impostazioni > Avanzate > Diagnostica widget: «gruppo sì/no · portachiavi sì/no»). AltStore vecchio: il prefisso del Keychain [da verificare].
- Con `keychain-access-groups` nei permessi il gruppo PREDEFINITO del Keychain diventa quello condiviso: gli elementi privati (token di sessione) vanno scritti con il gruppo esplicito `application-identifier` (`KeychainToken.gruppoPrivato`).

**Vincoli che non cambiano**
- Collegamento AUTOMATICO (dal 1/11/2026, PR #13): l'utente non compila niente. L'app (`Accesso.sincronizzaConIlWidget`) scrive indirizzo + token `fw_` nel file dell'App Group e nel Keychain condiviso (`PortachiaviCondiviso`); il widget legge in quest'ordine: gruppo con token > Keychain con token > codice incollato > indirizzo senza token > server pubblico (`ServerPubblico.indirizzo`). Il widget NON chiede l'indirizzo del server.
- Ultimo ripiego: il widget non collegato dice «Tocca per collegare» e apre `schieraxi://widget/collega`. Quell'indirizzo lo può aprire qualsiasi app o pagina: `CollegaWidgetView` si apre SENZA fare niente e aspetta il tocco su «Collega» (#482; logica in `CollegaWidgetModello`, appunti dietro `AppuntiCodice`/`AppuntiDiSistema`). Solo dopo il tocco chiede il token `fw_` se manca, riprova l'automatico e, solo se non va, copia il codice (`CodiceWidget`, `schieraxi1.`) negli appunti SOLO locali per 2 minuti; «Annulla» (o chiudere il foglio) ferma il lavoro in corso e non copia niente. L'utente lo incolla in «Modifica widget» > «Collegamento manuale» (interruttore) > «Codice di collegamento» (campo nascosto con `parameterSummary` + `When`). Stato per l'utente: Impostazioni > App, «Widget collegato automaticamente» / «Widget: tocca per collegare».
- Idea non fatta (serve il server): abbinamento senza campi via server (il widget mostra un codice casuale nell'URL del tocco, l'app lo registra, il widget ritira il token). Da proporre solo se gruppo e Keychain falliscono sul telefono.
- Il token apre SOLO le letture del widget; tutto il resto risponde 403. Il server ne tiene UNO per utente: rinnovo (l'app lo rinnova a 7 giorni dalla scadenza) o uscita invalidano il codice incollato → 401.
- Ogni estensione consuma un App ID: in SideStore va attivato «Register App ID for Each Extension». Non cambiare bundle id dell'app né dell'estensione.
- Repo pubblico: nessun indirizzo o token nel codice, nei test, negli screenshot o nell'IPA (il workflow IPA fallisce se ne trova).

**Dati e aggiornamento**
- Una sola chiamata: `GET /api/widget` con `If-None-Match`. 304 = dati uguali; 202 = il server calcola, tieni i dati di prima dello stesso collegamento; 401 = token scaduto, rinnovato o revocato → il widget cancella tutte le sue copie (cartella condivisa, sue UserDefaults e riassunto: `MemoriaWidget.applica`/`accessoNegato`) e dice «Tocca per collegare», senza dati vecchi; mai dati di un altro utente.
- Ogni copia del widget porta l'impronta del collegamento (`MemoriaWidget.impronta`: SHA-256 di indirizzo e token del widget) e si mostra solo con lo stesso collegamento, anche senza App Group; le copie senza impronta (di prima della #486) non si mostrano. Il precaricamento dell'app usa l'impronta del token del WIDGET.
- Uscita dall'account: prima il server revoca il token del widget, poi l'app toglie token e riassunto dal file condiviso (se non riesce a riscriverlo lo cancella), svuota il Keychain condiviso e le copie, e ricarica i widget. Limite noto: con il collegamento manuale, uscendo senza rete il token non viene revocato e il widget mostra quell'account finché il token non scade o non si toglie il codice.
- Il server con quel token non calcola mai (solo cache): parti mancanti arrivano in `mancano`, mostrale come «in arrivo», non come errore.
- Timeline: aggiornamenti ragionevoli (iOS limita il numero), conto alla rovescia con le date di sistema invece di ricaricare spesso.
- Tocchi: `widgetURL`/`Link` verso schermate precise con lo schema URL esistente (non cambiarlo).
- Niente capitano né classifica di lega.

**Lavoro in parallelo:** il widget è un'area separata dall'app (un agente per area). Se serve un campo nuovo dal server, chiedilo all'agente web nel rapporto: campi nuovi sempre facoltativi.
**Prova:** la CI dice solo «compila»; elenca all'utente cosa controllare sul telefono (aggiunta del widget, collegamento, tocchi, iPad).
