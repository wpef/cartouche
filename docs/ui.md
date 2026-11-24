# Interface web locale (`cartouche/ui/`)

Lancement : `.venv\Scripts\python -m cartouche.ui [--demo] [--port 8737] [--dir <sauvegardes>] [--sans-navigateur]`. Sans dépendance nouvelle ; la page (`static/`) n'a ni build ni CDN. `--demo` : clavier et souris simulés en mémoire (`maquette.py`), rien n'est écrit dans le matériel, sauvegardes dans un dossier temporaire.

## Sécurité
Écoute `127.0.0.1` seulement ; `Host` doit être `127.0.0.1:<port>` ou `localhost:<port>` (sinon 403) ; toute requête `POST` exige l'en-tête `X-Jeton` (jeton aléatoire au lancement, remis dans la page) ; entrées validées côté serveur (`api.valider`) ; chemins statiques limités à `static/` ; un seul accès matériel à la fois (verrou), périphérique refermé après chaque requête.

## Flux
Le brouillon vit dans la page. `POST /api/diff` relit le matériel et liste les différences ; `POST /api/appliquer` sauvegarde, écrit (`profil.appliquer_*`) et relit. Les macros ne sont jamais écrites tant que `api.MACROS_VERIFIEES` vaut `False` (format non vérifié sur le matériel).

## Routes
`GET /api/etat | clavier | souris | catalogue | cible?texte= | sauvegardes` ; `POST /api/diff | appliquer | importer | restaurer | usine`. Voir `api.py`.

## Ajouter une section (ex. « Logiciel »)
Côté API : une fonction `@route("GET", "/api/<nom>")` dans `api.py` (ou un nouveau module qui l'importe). Côté page : `C.sections.push({id, titre, rendre(main)})` dans un script chargé par `index.html` avant `divers.js` ; la section « Logiciel » existe déjà, vide, dans `divers.js`.

## À savoir
`static/` doit être livré avec le paquet : `pyproject.toml` n'a pas de `package-data` (l'installation éditable suffit pour l'instant).
