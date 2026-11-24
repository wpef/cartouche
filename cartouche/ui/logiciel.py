"""Écran « Logiciel » : le moteur (cartouche/moteur) piloté depuis l'interface. Mêmes garde-fous que le reste (jeton, Host)."""
import os

from .. import donnees
from ..moteur import service
from ..moteur.touches import MOLETTE, MOUSE, VK
from ..transport import Erreur
from . import api
from .api import Invalide, route

ACTIONS = ("demarrer", "pause", "reprendre", "arreter")
APPS_DEMO = ["chrome.exe", "code.exe", "explorer.exe", "notepad.exe"]


def _statut(e):
    return "arrete" if not e["tourne"] else "actif" if e["actif"] else "pause"


def _etat(app):
    e = app.moteur.etat()
    auto = app.auto if app.demo else service.demarrage_auto_actif()
    return {**{k: e.get(k) for k in ("profil", "app", "evenements", "erreur")}, "statut": _statut(e), "auto": auto}


@route("GET", "/api/logiciel")
def r_logiciel(app, q, b):
    try:
        cfg = donnees.lire(app.donnees).get("logiciel", {})
    except Erreur as e:
        raise api.Bloque(str(e))
    return {"config": cfg, "moteur": _etat(app), "touches": [*VK, *MOUSE, *MOLETTE], "arret_urgence": "Ctrl+Alt+Pause",
            "alerte": app.erreur_config, "demo": app.demo}


@route("GET", "/api/logiciel/etat")
def r_etat_moteur(app, q, b):
    return _etat(app)


@route("GET", "/api/applications")
def r_applications(app, q, b):
    if app.demo:
        return {"applications": APPS_DEMO}
    from ..moteur.windows import applications_ouvertes
    return {"applications": applications_ouvertes()}


@route("POST", "/api/logiciel/valider")
def r_valider(app, q, b):
    api.valider_logiciel(b.get("config"))
    return {"valide": True}


@route("POST", "/api/logiciel/enregistrer")
def r_enregistrer(app, q, b):
    """Valide, enregistre dans le fichier de l'utilisateur, recharge à chaud. Une configuration invalide ne change rien."""
    cfg = api.valider_logiciel(b.get("config"))
    with app.lock:
        try:
            donnees.mettre(app.donnees, logiciel=cfg)
        except (OSError, Erreur) as e:
            raise api.Bloque(f"enregistrement impossible : {e}")
        app.moteur.recharger(cfg)
        app.erreur_config = None
    return {"config": cfg, "moteur": _etat(app)}


@route("POST", "/api/logiciel/moteur")
def r_moteur(app, q, b):
    a = b.get("action")
    if a not in ACTIONS:
        raise Invalide("action inconnue")
    try:
        if a == "demarrer":
            app.moteur.demarrer()
        elif a == "arreter":
            app.moteur.arreter()
        else:
            app.moteur.pause(a == "pause")
    except OSError as e:
        raise api.Bloque(f"moteur : {e}")
    return _etat(app)


@route("POST", "/api/logiciel/auto")
def r_auto(app, q, b):
    """Seul appel à `demarrage_auto` : sur un clic de l'utilisateur dans l'écran Logiciel."""
    if not isinstance(b.get("activer"), bool):
        raise Invalide("activer : vrai ou faux")
    if app.demo:
        app.auto = b["activer"]
    else:
        try:
            service.demarrage_auto(b["activer"], args=["-m", "cartouche", "app", "--sans-navigateur"]
                                   + (["--donnees", os.fspath(app.donnees)] if app.donnees != donnees.dossier() else []))
        except OSError as e:
            raise api.Bloque(f"lanceur : {e}")
    return _etat(app)
