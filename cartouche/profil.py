"""Une « cartouche » : l'état lisible du clavier et de la souris, en JSON. Sert de profil, d'export et de sauvegarde.
{"cartouche": 1, "clavier": {"profil", "touches", "macros"}, "souris": {"dpi", "boutons", "batterie"}}"""
import json
import time
from pathlib import Path

from . import touches as T
from .transport import Erreur

DOSSIER_SAUVEGARDES = Path("captures/sauvegardes")


def lire_tout(clavier=None, souris=None):
    c = {"cartouche": 1}
    if clavier:
        c["clavier"] = clavier.etat()
    if souris:
        c["souris"] = souris.etat()
    return c


def exporter(c, chemin):
    Path(chemin).write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")


def importer(chemin):
    c = json.loads(Path(chemin).read_text(encoding="utf-8"))
    if c.get("cartouche") != 1:
        raise Erreur(f"version de cartouche inconnue : {c.get('cartouche')}")
    return c


def sauvegarder(c, dossier=None):
    """Écrit la cartouche sous un nom daté ; le dossier est créé au besoin. Renvoie le chemin."""
    d = Path(dossier or DOSSIER_SAUVEGARDES)
    d.mkdir(parents=True, exist_ok=True)
    base, n = time.strftime("sauvegarde-%Y%m%d-%H%M%S"), 0
    while (p := d / (base + (f"-{n}" if n else "") + ".json")).exists():
        n += 1
    exporter(c, p)
    return p


def _touches(d):
    return {T.hw_code(k): T.cible(v) for k, v in d.items()}


def appliquer_clavier(clavier, voulu):
    """Amène le clavier à l'état voulu, puis relit pour vérifier. Renvoie des remarques."""
    notes, veut = [], _touches(voulu.get("touches", {}))
    if voulu.get("profil") is None and veut:
        raise Erreur("des affectations sans nom de profil : un profil non nommé ne reste pas dans le clavier")
    cur = clavier.etat()
    a = _touches(cur["touches"])
    # Retirer une affectation = supprimer le profil, il n'existe pas d'autre commande documentée.
    if cur["profil"] is not None and (voulu.get("profil") is None or any(h not in veut for h in a)):
        clavier.supprimer_profil()
        cur["profil"], a = None, {}
    if voulu.get("profil") is not None and cur["profil"] != voulu["profil"]:
        clavier.creer_profil(voulu["profil"])
    for h, t in veut.items():
        if a.get(h) != t:
            clavier.affecter(h, t)
    for m in voulu.get("macros", []):
        if m not in cur["macros"]:
            clavier.ecrire_macro(m)
    if any(m not in voulu.get("macros", []) for m in cur["macros"]):
        notes.append("des macros du clavier ne sont pas dans la cartouche : aucune commande documentée pour les retirer")
    if not clavier.dry:
        apres = clavier.etat()
        if apres["profil"] != voulu.get("profil") or _touches(apres["touches"]) != veut:
            raise Erreur(f"vérification échouée : clavier relu {apres['profil']!r} {apres['touches']}")
    return notes


def appliquer_souris(souris, voulu):
    notes, cur = [], souris.etat()
    if cur["dpi"]["stages"] != voulu["dpi"]["stages"]:
        notes.append("paliers DPI différents : écriture non documentée, ignorée")
    for n, v in voulu.get("boutons", {}).items():
        if cur["boutons"].get(n) is None or T.valeur_souris(cur["boutons"][n]) != T.valeur_souris(v):
            souris.affecter_bouton(int(n), T.valeur_souris(v))
    return notes
