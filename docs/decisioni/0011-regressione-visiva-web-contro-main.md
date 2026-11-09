# 0011. L'aspetto della web si confronta con `main` nella stessa corsa, per ora solo come avviso

Data: 9/11/2026. Stato: accettata (scelta della spec dell'ondata 2, §6; messa in opera con la PR #522, issue #503).

## Contesto e problema
Una modifica alla web può cambiare l'aspetto di una schermata che nessuno ha guardato: lo si scopriva tardi, dal telefono. Serve un
controllo automatico che dica, in ogni PR che tocca `fanta/web/`, quali schermate cambiano. Spec:
`docs/superpowers/specs/2026-11-08-ondata-2-design.md`, (d); piano `docs/superpowers/plans/2026-11-08-ondata-2.md`, D1.

## Fattori della decisione
- Niente file pesanti in git e nessun passo a mano per aggiornare un riferimento.
- Nessun falso allarme quando cambia il Chrome dei computer di GitHub.
- Dati con nomi inventati (repository pubblico) e senza un server vero.
- Un controllo nuovo non deve fermare le unioni finché non si sa quanto è affidabile.

## Opzioni considerate
- Foto di riferimento salvate nel repository, aggiornate a mano.
- Foto di `main` (la base della PR) scattate nella stessa corsa, con lo stesso Chrome.
- Dati: un archivio di calcio inventato, oppure le risposte registrate di `ios/fotografie/vero-prima.json` servite da un server finto.
- Subito bloccante, oppure prima solo avviso.

## Decisione
Scelta: foto della PR e di `main` nella stessa corsa (`script/ci/aspetto_web.py`, workflow `.github/workflows/aspetto-web.yml`), con
un server finto che risponde con le risposte registrate. Il riferimento si aggiorna da solo quando la PR si unisce e i due lati usano
lo stesso Chrome. La PR scrive le scene che cambiano nella riga `Aspetto:`; il controllo avvisa solo per quelle non scritte. Per ora
è solo avviso: la corsa resta verde. L'archivio inventato è scartato perché è un progetto a sé.

## Conseguenze
- Bene: ogni cambio di aspetto della web si vede nella PR, con le immagini (`main`, PR, differenza) nell'artifact `aspetto-web`.
- Male (il prezzo): due giri di foto per corsa; le scene che le registrazioni non coprono non si controllano; finché è un avviso,
  chi rivede deve guardarlo.
- Una scena che cambia da sola va nell'elenco `INSTABILI` con il motivo. Diventa bloccante dopo una decina di corse senza falsi
  allarmi (D2, rimandato a dopo #168). Test: `tests/test_aspetto_web.py`.
