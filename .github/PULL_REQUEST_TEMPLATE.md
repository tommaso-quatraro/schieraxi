Closes #

Aree: <!-- cartelle o file toccati, separati da virgole (es. «fanta/web, tests, docs»). Il job «ambito» controlla che i file cambiati stiano qui dentro. -->

## Cosa cambia

## Perché

## Come l'ho provato
<!-- comandi e risultati; per le schermate, quali hai guardato e a che larghezza -->

## «Fatto» (docs/METODO.md)
- [ ] Test visto fallire prima della correzione e poi passare; suite intera verde (`python -m pytest -q`).
- [ ] Revisione del ramo fatta (`/code-review`) e rilievi chiusi prima di togliere la bozza.
- [ ] Schermate cambiate guardate davvero (web a 390, 768, 1024 e 1440 px, chiaro e scuro; iPhone: «Foto da fare: …»).
- [ ] `docs/GUIDA-UTENTE.md` o `docs/API.md` aggiornati se cambia una schermata o una rotta.
- [ ] Web e iPhone uguali (`docs/COERENZA-WEB-IPHONE.md`), oppure issue «coerenza: …» aperta.
- [ ] Se tocco `fanta/`, `script/server/` o `requirements.txt`: c'è `fanta/novita.d/<nome>.json` senza numero di versione.

## Controlli prima di inviare
- [ ] Niente dati personali: ho guardato `git diff` e non ci sono nomi di persone, indirizzi, IP, email, password o token.
- [ ] Non ho copiato dati di altri siti (nemmeno nei test) e non ho tolto l'interruttore delle fonti.
