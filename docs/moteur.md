# Moteur logiciel

Programme en fond qui intercepte clavier et souris (crochets Windows `WH_KEYBOARD_LL` / `WH_MOUSE_LL`, `ctypes`, aucune dépendance) et applique des règles que le matériel ne sait pas faire.

```
python -m cartouche.moteur --config cartouche/moteur/exemple.json [--duree 10] [--verifier]
```

- `--duree N` : arrêt automatique ; `--verifier` : valide le fichier sans poser de crochet.
- **Arrêt d'urgence : Ctrl+Alt+Pause** (bascule actif / inactif ; codé en dur, aucune règle ne peut le réaffecter).
- Les événements injectés (dont ceux du moteur) ne sont jamais retraités. Toute erreur dans un rappel laisse passer l'événement.

## Format (section `logiciel` d'une cartouche, ou fichier seul)

| Clé | Rôle |
|---|---|
| `profils` | `{nom: {apps, touches, couches}}` ; `apps` = noms de processus (`code.exe`). Pas d'héritage : ce qui vaut partout va dans `commun`. |
| `profil_defaut` | profil sans `apps` utilisé si aucune application ne correspond (défaut `defaut`) |
| `commun` | `{touches, couches}` consultés après le profil actif |
| `pause_apps` | processus où le moteur laisse tout passer (jeux avec anti-triche) |
| `seuil_long` / `delai_double` | millisecondes (400 / 300), modifiables par règle (`seuil`, `delai`) |

**Touches** : noms en minuscules (`a`, `f13`, `enter`, `capslock`, `lctrl`, `volup`, `playpause`… voir `cartouche/moteur/touches.py`), `vkNNN` pour un code virtuel brut, souris `mouse1`..`mouse5` (gauche, droit, milieu, précédent, suivant) et `wheelup/wheeldown/wheelleft/wheelright`. `ctrl`, `shift`, `alt`, `win` désignent gauche ou droite. Une clé de règle peut exiger des modificateurs : `"ctrl+alt+1"`.

**Règle** (valeur d'une touche) :
- une chaîne : réaffectation ou accord, tenu tant que la touche l'est (`"f13": "ctrl+shift+x"`) ;
- une action (ci-dessous), déclenchée à l'appui ;
- `{couche, court, long, double}` : décidé au relâchement. `couche` = nom d'une couche active tant que la touche est tenue (si une autre touche est pressée, pas d'appui court). `court` (défaut : la touche elle-même), `long` (si tenue au moins `seuil` sans interruption), `double` (deuxième appui dans `delai` ; le `court` attend alors ce délai). Un appui long interrompu par une autre touche donne le `court`.

**Actions** : `"ctrl+c"` (raccourci) · `{"media": "volup"}` / `{"envoyer": "..."}` · `{"texte": "..."}` · `{"lancer": ["prog.exe", "arg"]}` (sans shell) · `{"url": "https://..."}` (http, https, mailto) · `{"macro": [actions...]}` ou une simple liste, avec `{"attendre": ms}`, `{"bas": "a"}`, `{"haut": "a"}` · `{"profil": "nom"}` (ou `"suivant"`, `"auto"`) · `{"molette": [dx, dy]}` (120 = un cran, dy > 0 vers le haut).

Un bouton de souris peut servir de couche : `"mouse4": {"couche": "souris", "court": "alt+left"}` puis, dans la couche, `"wheelup": {"media": "volup"}` ou `"ctrl+wheelup": {"molette": [-120, 0]}`.

## Exemple complet

`cartouche/moteur/exemple.json` (testé par `tests/test_moteur_config.py`) : couche souris (volume, défilement horizontal), couche de navigation sur Verr. Maj, accord, appui court/long/double, macro, profil par application, bascule `ctrl+alt+p`, liste de pause.

## Limites connues

- Une touche à règle `court/long/double` est avalée à l'appui et décidée au relâchement.
- Les modificateurs physiquement tenus s'ajoutent à un accord émis.
- Le moteur ne voit pas les fenêtres d'administrateur (Windows ne livre pas leurs touches à un processus normal) ; le nom d'application y est vide.
- `cartouche.moteur.demarrage_auto(True, config)` écrit un `.cmd` dans le dossier Démarrage ; rien ne l'appelle.
