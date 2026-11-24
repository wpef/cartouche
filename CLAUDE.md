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

## Pile et commandes (Python)
- Python 3.13 dans `.venv` ; seule dépendance : `hidapi`. Pas de Rust : Smart App Control est actif sur ce PC et bloque tout exécutable compilé ici (erreur 4551 sur le script de build de `quote`) ; on ne le désactive pas.
- Installation : `.venv\Scripts\pip install -e .` (Windows) ; lancement : `.venv\Scripts\python -m cartouche list|dump|map|unmap|profile|macro|mouse|apply|restore` ; `--dry-run` n'envoie rien.
- Tests : `.venv\Scripts\python -m unittest` (sans matériel, sur trames réelles).
- Le transport refuse tout rapport `0xB2` (firmware). Sauvegarde automatique dans `captures/sauvegardes/` avant toute écriture, relecture de contrôle après.
- API du cœur : `docs/api-coeur.md`. `cartouche/ui/` et `cartouche/moteur/` : réservés à d'autres chantiers.
