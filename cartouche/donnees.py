"""Le fichier de l'utilisateur : une seule cartouche (clavier, souris, logiciel) dans `%APPDATA%/Cartouche/cartouche.json`."""
import json
import os
from pathlib import Path

from .transport import Erreur

NOM = "cartouche.json"


def dossier(d=None):
    return Path(d) if d else Path(os.environ.get("APPDATA") or Path.home()) / "Cartouche"


def lire(d=None):
    """La cartouche enregistrée ; `{"cartouche": 1}` si le fichier n'existe pas encore."""
    p = dossier(d) / NOM
    if not p.exists():
        return {"cartouche": 1}
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Erreur(f"{p} illisible : {e}")
    if not isinstance(c, dict) or c.get("cartouche") != 1:
        raise Erreur(f"{p} : pas une cartouche (version 1 attendue)")
    return c


def ecrire(c, d=None):
    """Écriture atomique (fichier temporaire puis remplacement)."""
    p = dossier(d)
    p.mkdir(parents=True, exist_ok=True)
    tmp = p / (NOM + ".tmp")
    tmp.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p / NOM)


def mettre(d=None, **sections):
    """Remplace des sections (clavier, souris, logiciel) sans toucher aux autres."""
    c = lire(d)
    c.update(sections)
    ecrire(c, d)
    return c
