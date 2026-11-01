"""Crea `sorgente.json`: il "sorgente" di SideStore/AltStore che dice qual è l'ultima versione dell'app e dove scaricare l'IPA.
Aggiungendo una volta l'indirizzo del sorgente in SideStore, gli aggiornamenti compaiono da soli nella scheda "Sorgenti" (basta un tocco su Aggiorna).
Uso (nel workflow, dopo aver creato l'IPA):  python3 scripts/genera_sorgente.py <repo> <numero-build> <file.ipa>"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

repo, build, ipa = sys.argv[1], sys.argv[2], sys.argv[3]
base = f"https://github.com/{repo}"

sorgente = {
    "name": "SchieraXI",
    "identifier": "it.schieraxi.app.sorgente",
    "subtitle": "SchieraXI per iPhone e iPad",
    "description": "Le versioni di SchieraXI compilate da GitHub.",
    "iconURL": f"https://raw.githubusercontent.com/{repo}/main/Sources/Assets.xcassets/AppIcon.appiconset/icon-1024.png",
    "tintColor": "3DDC97",
    "apps": [
        {
            "name": "SchieraXI",
            "bundleIdentifier": "it.schieraxi.app",
            "developerName": "SchieraXI",
            "subtitle": "Formazioni e scambi per il fantacalcio",
            "localizedDescription": "App nativa per scegliere la formazione e analizzare gli scambi, con widget, Siri e Comandi.",
            "iconURL": f"https://raw.githubusercontent.com/{repo}/main/Sources/Assets.xcassets/AppIcon.appiconset/icon-1024.png",
            "tintColor": "3DDC97",
            "version": f"1.0.{build}",
            "versionDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "versionDescription": f"Build {build}",
            "downloadURL": f"{base}/releases/download/build-{build}/Schieraxi.ipa",
            "size": os.path.getsize(ipa),
            "minOSVersion": "18.0",
        }
    ],
    "news": [],
}

with open("sorgente.json", "w", encoding="utf-8") as f:
    json.dump(sorgente, f, ensure_ascii=False, indent=2)
print("sorgente.json scritto:", sorgente["apps"][0]["version"], sorgente["apps"][0]["downloadURL"])
