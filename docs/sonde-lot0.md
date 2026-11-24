# Sonde lot 0 : lecture seule

Outil : `sonde/sonde.py` (hidapi 0.15, Windows). Sortie brute dans `captures/` (hors git). Seules les trames de la liste blanche du lot sont émises ; aucune écriture de configuration, aucun rapport `0xB2`.

## Interfaces `2DC8`

| PID | Interface | Usage page / usage | Rôle | Ouvert |
|---|---|---|---|---|
| 5201 | 0 | `0x01` / `0x02` | souris standard | non |
| 5201 | 1 | `0x8C` / `0x01` | **configuration clavier** | oui |
| 5201 | 2 | `0x01`/`0x06` (x3), `0x01`/`0x80`, `0x0C`/`0x01` (x2) | clavier, contrôle système, consommateur | non |
| 5206 | 0 | `0x01` / `0x02` | souris standard | non |
| 5206 | 1 | `0x01`/`0x06`, `0x01`/`0x80`, `0x0C`/`0x01` | clavier / système / consommateur | non |
| 5206 | 2 | `0xFF00` / `0x01` | **configuration souris** | oui |
| 5206 | 3 | `0xFF02` / `0x01` et `0xFF0B` / `0x104` | fournisseur, usage inconnu (descripteur lu seulement, rien envoyé) | descripteur seul |

Descripteurs lus :
- Clavier `0x8C` : entrées `0xB1` et `0x54`, sorties `0xB2`, `0x51`, `0x52`, toutes de 32 octets. Identique à `protocol.txt` de la référence.
- Souris `0xFF00` : un rapport d'entrée et un de sortie de 64 octets, **sans identifiant**. Sous hidapi, écriture = `00` + 64 octets.
- `0xFF02` : un rapport de fonction `0x14` de 20 octets. `0xFF0B` : rapports `0x2A`, `0x2B`, `0x2C`, `0x2D` (60 octets, ou 4 x 32 bits). Non explorés.

## Clavier (récepteur 5201)

Trame : `52` + 32 octets (33 avec l'identifiant), zéros de complément.

| Envoyé | Réponse | Interprétation |
|---|---|---|
| `52 80` | aucune (350 ms) | |
| `52 81 00` | aucune | |
| `52 83 04 <hwkey>`, hwkey `01`, `02`, `04`, `0C` | aucune | |

Les écritures ont réussi côté système (pas d'erreur), mais le clavier n'a rien répondu. Hypothèse, non vérifiée : le clavier n'est pas actuellement connecté au récepteur (autre mode, éteint), le récepteur seul n'ayant pas de configuration à renvoyer. À retester clavier allumé en mode 2,4 G, puis en câble (`5200`).

## Souris (adaptateur 5206, `0xFF00`)

Chaque commande reçoit deux paquets : d'abord un paquet `21 06 <cmd> ...` qui répète la commande, avec un octet `14` en position 40 (sens inconnu, constant, probablement un accusé), puis la vraie réponse `01 06 <cmd> 11 ...`. L'octet 3 passe de `01` à `11` dans la réponse.

| Envoyé | Réponse (utile) | Interprétation |
|---|---|---|
| `01 06 12 01` | `01 06 12 11 06 03 60 09 20 03 b0 04 40 06 60 09 80 0c 00 19` | 6 paliers, index courant 3 (4e palier), DPI courant 2400 ; paliers 800, 1200, 1600, 2400, 3200, 6400 |
| `01 06 10 01 00 00` | `... 10 11 00 00 01` | bouton 0 : code `01` |
| `... 00 01` | `... 11 00 01 02` | bouton 1 : `02` |
| `... 00 02` | `... 11 00 02 03` | bouton 2 : `03` |
| `... 00 03` | `... 11 00 03 05` | bouton 3 : `05` |
| `... 00 04` | `... 11 01 04 04` | bouton 4 : `04`, octet 4 = `01` (signification inconnue) |
| `... 00 05` | `... 11 00 05 00` | bouton 5 : `00` (non affecté) |
| `01 06 1A 01` | `01 06 1a 11 00 00 ...` | charge à zéro : pas de valeur connue (charge ou veille ; non résolu) |

Les paliers correspondent exactement aux valeurs par défaut de `r8-rs`. La réponse batterie est vide, comme le prévoit `r8-rs` quand la valeur est inconnue.

## Ce qui ne répond pas
- Toutes les lectures du clavier.
- Batterie souris : réponse présente mais sans donnée.
