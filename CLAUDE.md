Projet `cartouche` de Foulqui (FDP). Tout ce qui n'est pas du code (état, plan, décisions, passations, règles de travail) vit dans son vault Obsidian, dépôt privé `wpef/obsidian-vault`, dossier `01-Projects/cartouche/`.
Avant d'écrire autre chose que du code, lis le `CLAUDE.md` du vault et suis-le.
Si le vault n'est pas accessible dans cette session, dis-le en une ligne et demande-le avant de continuer.

## Technique
- Dépôt public, GPL-3.0-or-later. Travail sous Windows (accès HID au matériel), pas sous WSL.
- Matériel : clavier 8BitDo Retro Mechanical Keyboard (récepteur `2DC8:5201`), souris Retro R8 (adaptateur `2DC8:5206`).
- Jamais d'écriture de firmware, jamais rien sur le rapport HID `0xB2` (canal de mise à jour).
- Toute écriture de configuration est précédée d'une lecture sauvegardée dans `captures/` (hors git).
- `captures/` : sorties brutes et captures USB, hors git (numéros de série, adresses Bluetooth).
- Commits libres, un par intention, avec la ligne `Co-Authored-By` de Claude.
