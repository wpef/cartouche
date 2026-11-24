# Interface web locale (`cartouche/ui/`)

Lancement : `.venv\Scripts\python -m cartouche.ui [--demo] [--port 8737] [--dir <sauvegardes>] [--sans-navigateur]`. Sans dépendance nouvelle ; la page (`static/`) n'a ni build ni CDN. `--demo` : clavier et souris simulés en mémoire (`maquette.py`), rien n'est écrit dans le matériel, sauvegardes dans un dossier temporaire.

## Sécurité
Écoute `127.0.0.1` seulement ; `Host` doit être `127.0.0.1:<port>` ou `localhost:<port>` (sinon 403) ; toute requête `POST` exige l'en-tête `X-Jeton` (jeton aléatoire au lancement, remis dans la page) ; entrées validées côté serveur (`api.valider`) ; chemins statiques limités à `static/` ; un seul accès matériel à la fois (verrou), périphérique refermé après chaque requête.

## Flux
Le brouillon vit dans la page. `POST /api/diff` relit le matériel et liste les différences ; `POST /api/appliquer` sauvegarde, écrit (`profil.appliquer_*`) et relit. Les macros ne sont jamais écrites tant que `api.MACROS_VERIFIEES` vaut `False` (format non vérifié sur le matériel).

## Routes
`GET /api/etat | clavier | souris | catalogue | cible?texte= | sauvegardes` ; `POST /api/diff | appliquer | importer | restaurer | usine`. Voir `api.py`.

## Écran « Logiciel » (`logiciel.py`, `static/logiciel.js`)
`GET /api/logiciel | /api/logiciel/etat | /api/applications` ; `POST /api/logiciel/valider | enregistrer | moteur {action: demarrer|pause|reprendre|arreter} | auto {activer}`. Une configuration est compilée par le moteur (`moteur.logique.compiler`) avant d'être enregistrée dans `cartouche.json` et rechargée à chaud ; invalide, elle ne change rien. `auto` est le seul appel à `demarrage_auto` (sur clic ; simulé en démo). La page garde la configuration en brouillon (formulaires et éditeur JSON) jusqu'à « Enregistrer et recharger ». Applications ouvertes : `moteur.windows.applications_ouvertes`.

## Fichier de l'utilisateur
`App(demo, dossier, donnees_dir, moteur)` : `donnees_dir` (défaut `%APPDATA%/Cartouche`) contient `cartouche.json`. Après chaque écriture matériel réussie, l'état relu y est mémorisé (`App.memoriser`). Import / export de l'écran Cartouche : clavier, souris et logiciel. Lancement groupé (interface + moteur + icône) : `python -m cartouche app`, voir `README.md`.

## Veille des périphériques
La page interroge `/api/etat` toutes les 5 s (énumération HID, aucune ouverture) et affiche un message quand un périphérique apparaît ou disparaît ; elle relit le matériel sauf si un brouillon est en cours.

## Ajouter une section
Côté API : une fonction `@route("GET", "/api/<nom>")` dans un module importé par `serveur.py`. Côté page : `C.sections.push({id, titre, rendre(main)})` dans un script chargé par `index.html` avant `divers.js`.

## À savoir
`static/` et `exemple.json` sont livrés avec le paquet (`package-data` de `pyproject.toml`).
