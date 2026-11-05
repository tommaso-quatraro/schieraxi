# Provare l'app per iPhone nel browser (Appetize.io)

Il workflow `.github/workflows/ios-simulatore.yml` compila l'app per il **simulatore** di iPhone e la carica su
[Appetize.io](https://appetize.io), un servizio che fa girare il simulatore in una pagina web: si tocca, si scorre e si naviga
come su un telefono vero, anche con Claude in Chrome. L'app gira in **modalità demo**: dati finti, nessuna rete, nessun dato vero.

Cose da sapere:

- Appetize accetta solo app per il simulatore (cartella `.app` compressa in `.zip`), non il file IPA di SideStore.
- Piano gratuito (pagina dei prezzi, 5/11/2026): **30 minuti al mese**, sessioni di **3 minuti** al massimo, 2 dispositivi
  attivi. Bastano per prove mirate, non per giocarci a lungo.
- L'app si apre solo a chi ha fatto l'accesso ad Appetize con l'account che l'ha caricata: i log di GitHub del repository sono
  pubblici e il link da solo non basta a consumare i minuti.
- Senza il segreto `APPETIZE_TOKEN` il workflow fa solo lo `.zip` (artifact «schieraxi-simulatore», 7 giorni) e finisce verde.

## 1. Account e token (una volta sola)

1. Crea l'account gratuito: <https://appetize.io> → **Sign Up**.
2. Crea il token per le API: <https://appetize.io/organization/api-tokens> → **Generate API Token**.
   - Label: `github-schieraxi`
   - Role: **Developer** (il ruolo con meno permessi)
   - Copia il token subito: Appetize lo mostra una volta sola.
3. Salva il token come segreto del repository. Apri il terminale nella cartella del repository (quella
   con `MAPPA.md`) e scrivi:

   ```
   gh secret set APPETIZE_TOKEN
   ```

   `gh` chiede il valore: incolla il token e premi Invio. Il token non finisce nella cronologia del terminale né nei log.

## 2. Prima corsa: crea l'app su Appetize

```
gh workflow run ios-simulatore.yml --ref main
gh run watch
```

Dura circa 10-15 minuti. Alla fine il riepilogo della corsa (pagina della corsa su GitHub, in fondo) mostra:

- il **link** per aprire l'app con la demo;
- il comando per salvare la chiave dell'app, così le corse dopo aggiornano la stessa app e il link non cambia:

  ```
  gh variable set APPETIZE_APP --body <chiave>
  ```

  Al posto di `<chiave>` metti la chiave scritta nel riepilogo (la stessa che sta nel link dopo `/app/`).

## 3. Le corse dopo: aggiorna la stessa app

```
gh workflow run ios-simulatore.yml --ref main
```

Per provare un ramo prima dell'unione: `--ref <nome-del-ramo>`. Ogni corsa sostituisce l'app su Appetize con quella del ramo
scelto.

## 4. Aprire l'app

Apri il link del riepilogo dopo aver fatto l'accesso ad Appetize nello stesso browser. Il link è fatto così:

```
https://appetize.io/app/<chiave>?device=iphone16pro&launchArgs=%5B%22-DEMO%22%2C%22-AppleLanguages%22%2C%22%28it%29%22%2C%22-AppleLocale%22%2C%22it_IT%22%5D
```

- `launchArgs` accende la demo (`-DEMO`) e la lingua italiana. Senza, l'app parte normale e chiede il server.
- `device` sceglie l'iPhone (elenco: <https://appetize.io/available-devices>).

## Se qualcosa non va

- **Appetize ha risposto 401**: il token è sbagliato o revocato. Rifallo (punto 1) e risalvalo con `gh secret set APPETIZE_TOKEN`.
- **Appetize ha risposto 404**: la chiave in `APPETIZE_APP` non esiste più (app cancellata su Appetize). Svuota la variabile
  con `gh variable delete APPETIZE_APP` e rilancia: il workflow crea un'app nuova.
- **La variabile APPETIZE_APP non sembra una chiave**: rimettila copiando solo la chiave, senza il link intorno.
- **Minuti finiti**: si ricaricano all'inizio del mese.
