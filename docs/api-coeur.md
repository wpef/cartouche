# API du cœur (`cartouche/`)

Noms de touches, cibles et pas de macro : textes (`touches.py`). Tout ce qui écrit lève `Erreur` si la relecture ou l'accusé échoue ; `dry=True` affiche les trames sans rien envoyer. Le rapport `0xB2` est refusé (`Refuse`), le non documenté lève `NonPris` ; les deux héritent de `Erreur` (`transport.py`).

## transport
- `lister() -> list[dict]` : `pid, interface, page, usage, produit, configurable`. Lecture.
- `ouvrir_clavier() / ouvrir_souris() -> Hid` : `Erreur` si absent (clavier : câble, interrupteur OFF ; souris : adaptateur 2,4 G).
- `Transport` (`ecrire(trame)`, `lire(delai_ms)`), `Faux(reponses)` pour simuler.

## Clavier (`clavier.Clavier(transport, dry=False)`)
- Lecture : `nom_profil() -> str|None`, `touches_mappees() -> list[int]`, `lire_touche(hw) -> bytes(6)`, `macros() -> list[dict]`, `etat() -> dict` (`profil`, `touches` {nom: cible}, `macros`).
- ÉCRIT : `affecter(hw, cible: bytes)`, `creer_profil(nom)` (1 à 14 car.), `supprimer_profil()` (efface aussi les affectations), `ecrire_macro(dict)` (format non vérifié sur matériel).
- Une affectation n'est conservée que si le profil est nommé.

## Souris (`souris.Souris(transport, dry=False)`)
- Lecture : `dpi() -> {index, current, stages}`, `bouton(n) -> int`, `batterie() -> {percent, charging, known}`, `etat() -> dict`.
- ÉCRIT : `affecter_bouton(n, valeur)` (relit, `Erreur` si différent).
- `NonPris` : `ecrire_dpi`, `frequence_scrutation`, `distance_decollage`, `molette`.

## touches
- `hw_code(nom) -> int`, `hw_nom(code) -> str` (`superb`, `supera`, `k1..k8`, `capslock`, `0x6c`). `menu`, `compose`, `app` = `supera` (0x6D) ; 0x65 est Maj gauche.
- `cible(texte) -> bytes(6)`, `cible_texte(bytes) -> str` : `f13`, `lctrl+c`, `media:playpause`, `mouse:left`, `none`, `default`, `raw:<12 hex>`.
- `valeur_souris(texte) -> int`, `nom_valeur_souris(int) -> str` : `left right middle forward back disabled code:N`.

## profil (la « cartouche » JSON)
- `lire_tout(clavier=None, souris=None) -> dict` ; `exporter(c, chemin)` ; `importer(chemin) -> dict`. Lecture.
- `sauvegarder(c, dossier=None) -> Path` : écrit dans `captures/sauvegardes/`. À appeler AVANT toute écriture.
- ÉCRIT : `appliquer_clavier(clavier, voulu) -> list[str]` (supprime et recrée le profil si une affectation disparaît, relit pour vérifier), `appliquer_souris(souris, voulu) -> list[str]`.

## Ligne de commande
`python -m cartouche [--dry-run] list|dump|map|unmap|profile|macro|mouse|apply|restore`. Ne pas lancer deux accès HID en même temps sur le même périphérique.
