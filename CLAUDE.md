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

## Build et tests (Rust)
- Chaîne retenue : `stable-x86_64-pc-windows-gnu` (rustup, profil utilisateur). Aucun outil MSVC sur ce PC (`vswhere` et `link.exe` absents), et son installation demanderait les droits administrateur.
- Espace de travail Cargo à la racine : `crates/cartouche-core` (protocole), `crates/cartouche-cli` (binaire `cartouche`), `crates/cartouche-remap` (vide, remappage logiciel).
- `hidapi` est épinglé à `=2.6.4` avec `windows-native` : les versions 2.6.5 et suivantes passent par `windows-sys 0.61` en `raw-dylib`, qui exige `dlltool` et `as` (binutils, absents avec la chaîne GNU).
- PATH : `~/.cargo/bin`. Commandes : `cargo test`, `cargo build -p cartouche-cli`, `cargo run -p cartouche-cli -- list`.
- Le transport refuse tout rapport `0xB2` (firmware) ; les tests le vérifient.
- Blocage connu : le contrôle d'application de Windows peut bloquer le script de build d'une dépendance (`quote`, erreur 4551). Ne pas le contourner : le débloquer côté Windows.
