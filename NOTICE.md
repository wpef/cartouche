# Sources du protocole

Cartouche est sous GPL-3.0-or-later. Le protocole vient de ces projets (tous GPL-3.0) et de nos propres lectures sur le matériel (`docs/sonde-lot0.md`). Quand une source et le matériel se contredisent, le matériel a raison.

- [goncalor/8bitdo-kbd-mapper](https://github.com/goncalor/8bitdo-kbd-mapper) : `protocol.txt`, trames clavier (profil, affectation, accusé `54 e4 08`), table des touches physiques.
- [Aryaman73/8db-retro-config](https://github.com/Aryaman73/8db-retro-config) : accords modificateur + touche (`07 <mod> <touche>`), codes F13-F24 selon la norme HID, Super Buttons externes (touches physiques `0x74`/`0x75`), séquence « profil nommé puis affectation ».
- [KilnerJhow/retro87-configurator](https://github.com/KilnerJhow/retro87-configurator) : `docs/PROTOCOL.md` et famille « JP » (macros `0x74`/`0x76`/`0x82`/`0x84`/`0x86`, 8 emplacements, valeurs multimédia et souris du clavier).
- [mbs1337/r8-rs](https://github.com/mbs1337/r8-rs) : `crates/r8-core/src/hid.rs`, souris R8 (DPI `01 06 12 01`, boutons `01 06 10 …`, valeurs des boutons).
