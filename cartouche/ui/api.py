"""L'API JSON de l'interface, au-dessus du cœur. Une section de plus = une fonction `@route(...)` de plus ici
et une entrée dans `C.sections` côté page (static/app.js)."""
import contextlib
import json
import re
import tempfile
import threading
from pathlib import Path

from .. import clavier as K, donnees, profil, souris as S, transport
from .. import touches as T
from ..transport import Erreur
from ..moteur.logique import compiler
from ..moteur.service import charger_config
from . import maquette

MACROS_VERIFIEES = False  # le cœur le dit : `Clavier.ecrire_macro` = « format non vérifié sur matériel »
MSG_MACROS = "format non vérifié sur le matériel : l'écriture des macros est désactivée"
SOURIS_BOUTONS = range(6)
NON_PRIS = ["Paliers DPI (écriture)", "Fréquence de scrutation", "Distance de décollage", "Molette"]  # NonPris dans souris.py
NOMS_FR = {"superb": "bouton B", "supera": "bouton A", **{f"k{i}": f"Super Button K{i}" for i in range(1, 9)}}
SAUVEGARDE = re.compile(r"sauvegarde-[0-9]{8}-[0-9]{6}(-[0-9]+)?\.json")


class Invalide(Exception):
    """Entrée refusée (400)."""


class Bloque(Exception):
    """Refusé en l'état (409)."""


ROUTES = {}


def _service(cfg):
    from ..moteur import Service
    return Service(cfg)


def route(methode, chemin):
    def poser(f):
        ROUTES[(methode, chemin)] = f
        return f
    return poser


class App:
    def __init__(self, demo=False, dossier=None, donnees_dir=None, moteur=None):
        """`donnees_dir` : dossier du fichier de l'utilisateur (défaut `%APPDATA%/Cartouche`, un dossier temporaire en démo)."""
        self.demo, self.lock = demo, threading.RLock()  # un seul accès HID à la fois
        self.dossier = Path(dossier or (tempfile.mkdtemp(prefix="cartouche-demo-") if demo else profil.DOSSIER_SAUVEGARDES))
        self.donnees = Path(donnees_dir or (tempfile.mkdtemp(prefix="cartouche-donnees-") if demo else donnees.dossier()))
        self.maquettes = {"clavier": maquette.Clavier(), "souris": maquette.Souris()}
        self.auto = False  # démarrage automatique simulé (démo)
        self.erreur_config = None
        try:
            cfg = donnees.lire(self.donnees).get("logiciel", {})
        except Erreur as e:
            cfg, self.erreur_config = {}, str(e)
        if moteur is None:
            try:
                moteur = (maquette.Moteur if demo else _service)(cfg)
            except ValueError as e:  # configuration enregistrée invalide : on démarre à vide
                moteur, self.erreur_config = (maquette.Moteur if demo else _service)({}), f"configuration du logiciel refusée : {e}"
        self.moteur = moteur

    def memoriser(self, **etats):
        """Garde dans le fichier de l'utilisateur l'état relu du matériel (sans la batterie, qui change)."""
        try:
            donnees.mettre(self.donnees, **{z: {k: v for k, v in e.items() if k != "batterie"} for z, e in etats.items()})
        except (OSError, Erreur):  # le matériel est déjà écrit et relu : un fichier illisible ne doit pas tout faire échouer
            pass

    def batterie(self):
        """Batterie de la souris, ou None si elle n'est pas joignable. Un seul accès HID à la fois."""
        with self.lock:
            if self.demo:
                return self.maquettes["souris"].etat()["batterie"]
            if not any(d["pid"] == transport.PID_SOURIS and d["page"] == transport.PAGE_SOURIS for d in transport.lister()):
                return None
            with self.ouvrir("souris") as s:
                return s.batterie()

    @contextlib.contextmanager
    def ouvrir(self, quoi):
        if self.demo:
            yield self.maquettes[quoi]
            return
        h = (transport.ouvrir_clavier if quoi == "clavier" else transport.ouvrir_souris)()
        try:
            yield K.Clavier(h) if quoi == "clavier" else S.Souris(h)
        finally:
            h.fermer()


# ---- état des périphériques ------------------------------------------------------------------------------

def statut(interfaces):
    """Pure : liste d'interfaces (`transport.lister()`) -> statut et message utile de chaque périphérique."""
    ifs = {(d["pid"], d["page"]) for d in interfaces}
    pids = {p for p, _ in ifs}
    if any((p, transport.PAGE_CLAVIER) in ifs for p in transport.PIDS_CLAVIER):
        k = ("cable", "Clavier en câble : prêt.")
    elif 0x5201 in pids:
        k = ("recepteur", "Seul le récepteur 2,4 G est visible : il ne permet pas la configuration. "
             "Branche le clavier en câble, interrupteur sur OFF.")
    else:
        k = ("absent", "Clavier absent. Branche-le en câble USB, interrupteur sur OFF.")
    if (transport.PID_SOURIS, transport.PAGE_SOURIS) in ifs:
        s = ("adaptateur", "Souris par l'adaptateur 2,4 G : prête.")
    elif 0x5205 in pids:
        s = ("bluetooth", "Souris en Bluetooth seulement : sa configuration demande l'adaptateur 2,4 G.")
    else:
        s = ("absente", "Souris absente. Branche l'adaptateur 2,4 G.")
    return {"clavier": {"statut": k[0], "message": k[1], "pret": k[0] == "cable"},
            "souris": {"statut": s[0], "message": s[1], "pret": s[0] == "adaptateur"}}


@route("GET", "/api/etat")
def r_etat(app, q, b):
    if app.demo:
        ifs = [{"pid": transport.PIDS_CLAVIER[0], "page": transport.PAGE_CLAVIER},
               {"pid": transport.PID_SOURIS, "page": transport.PAGE_SOURIS}]
    else:
        try:
            with app.lock:
                ifs = transport.lister()
        except Exception as e:  # hidapi absent ou en échec
            raise Erreur(f"énumération HID impossible : {e}")
    return {"demo": app.demo, "peripheriques": statut(ifs), "macros_ecriture": MACROS_VERIFIEES,
            "macros_message": MSG_MACROS, "non_pris": NON_PRIS}


@route("GET", "/api/clavier")
def r_clavier(app, q, b):
    with app.lock, app.ouvrir("clavier") as k:
        return k.etat()


@route("GET", "/api/souris")
def r_souris(app, q, b):
    with app.lock, app.ouvrir("souris") as s:
        return s.etat()


@route("GET", "/api/catalogue")
def r_catalogue(app, q, b):
    noms = [chr(97 + i) for i in range(26)] + [str(i) for i in range(10)] + [f"f{i}" for i in range(1, 25)] + list(T.NOMMEES)
    return {"touches": noms, "mods": list(T.MODS), "media": list(T.MEDIA), "souris": list(T.SOURIS),
            "hw": list(T.HW_SEUL), "noms_fr": NOMS_FR}


@route("GET", "/api/cible")
def r_cible(app, q, b):
    try:
        return {"texte": T.cible_texte(T.cible(q.get("texte", [""])[0]))}
    except (Erreur, ValueError) as e:
        raise Invalide(str(e))


# ---- brouillon : validation et différences ---------------------------------------------------------------

def _macro(m):
    hw = T.hw_code(m["key"])
    nom, cycles, ms, pas = m["name"], m.get("cycles"), m.get("interval_ms", 0), m["steps"]
    if not (isinstance(nom, str) and 1 <= len(nom) <= 28 and isinstance(pas, list) and 0 < len(pas) <= 100
            and all(isinstance(p, str) for p in pas) and type(ms) is int and 0 <= ms <= 65535
            and (cycles is None or (type(cycles) is int and 0 <= cycles <= 255))):
        raise Invalide("macro invalide")
    out = {"key": T.hw_nom(hw), "name": nom, "cycles": cycles, "interval_ms": ms, "steps": pas}
    K.corps_macro(out)  # lève Erreur si un pas est faux
    return out


def valider(b):
    """Brouillon {clavier:{profil,touches,macros}, souris:{boutons}} -> forme normalisée, ou Invalide."""
    try:
        out = {}
        if b.get("clavier") is not None:
            k = b["clavier"]
            nom = k.get("profil")
            if nom is not None and not (isinstance(nom, str) and 1 <= len(nom) <= 14):
                raise Invalide("nom de profil : 1 à 14 caractères")
            touches = {}
            for n, t in k.get("touches", {}).items():
                texte = T.cible_texte(T.cible(t))
                if texte != "default":
                    touches[T.hw_nom(T.hw_code(n))] = texte
            macros = {m["key"]: m for m in (_macro(m) for m in k.get("macros", []))}
            out["clavier"] = {"profil": nom, "touches": touches, "macros": list(macros.values())}
        if b.get("souris") is not None:
            bt = {}
            for n, v in b["souris"].get("boutons", {}).items():
                if int(n) not in SOURIS_BOUTONS:
                    raise Invalide(f"bouton {n} inconnu")
                x = T.valeur_souris(v)
                if not 0 <= x <= 0xFFFF:
                    raise Invalide("code de bouton hors limites")
                bt[str(int(n))] = T.nom_valeur_souris(x)
            out["souris"] = {"boutons": bt}
        return out
    except Invalide:
        raise
    except (Erreur, ValueError, TypeError, KeyError, AttributeError) as e:
        raise Invalide(f"brouillon invalide : {e}")


def valider_logiciel(cfg):
    """Section « logiciel » -> elle-même si le moteur l'accepte, sinon Invalide (même contrôle que `Service.recharger`)."""
    if not isinstance(cfg, dict):
        raise Invalide("la configuration du logiciel doit être un objet JSON")
    try:
        compiler(charger_config(cfg))
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as e:
        raise Invalide(f"configuration du logiciel refusée : {e}")
    return cfg.get("logiciel", cfg)  # une cartouche entière collée à la place de la section est acceptée


def _fr(h):
    return NOMS_FR.get(h, h)


def _ou_defaut(t):
    return "d'origine" if t is None or t == "default" else t


def comparer(cur, voulu):
    """Différences entre l'état relu et le brouillon validé. {lignes, avertissements, bloque, a_ecrire}."""
    lignes, avert, bloque = [], [], []
    if "clavier" in voulu:
        c, v = cur["clavier"], voulu["clavier"]
        if c["profil"] != v["profil"]:
            lignes.append({"zone": "clavier", "texte": f"Profil : {c['profil'] or 'aucun'} → {v['profil'] or 'aucun'}"})
        for h in sorted(set(c["touches"]) | set(v["touches"])):
            a, n = c["touches"].get(h), v["touches"].get(h)
            if a != n:
                lignes.append({"zone": "clavier", "texte": f"{_fr(h)} : {_ou_defaut(a)} → {_ou_defaut(n)}"})
        if v["touches"] and v["profil"] is None:
            bloque.append("Des touches sont affectées sans nom de profil : un profil non nommé ne reste pas dans le clavier.")
        if lignes and ((v["profil"] is None and c["profil"] is not None) or any(h not in v["touches"] for h in c["touches"])):
            avert.append("Retirer une affectation ou le profil supprime le profil du clavier, puis le recrée avec ce qui reste.")
        cm = {m["key"]: m for m in c["macros"]}
        for m in v["macros"]:
            if cm.get(m["key"]) != m:
                lignes.append({"zone": "clavier", "ignore": True,
                               "texte": f"Macro « {m['name']} » sur {_fr(m['key'])} : non écrite ({MSG_MACROS})"})
        if any(m["key"] not in {x["key"] for x in v["macros"]} for m in c["macros"]):
            avert.append("Des macros du clavier ne sont pas dans le brouillon : aucune commande documentée pour les retirer.")
    if "souris" in voulu:
        for n, x in voulu["souris"]["boutons"].items():
            a = cur["souris"]["boutons"].get(n)
            if a is not None and T.valeur_souris(a) != T.valeur_souris(x):
                lignes.append({"zone": "souris", "texte": f"Bouton {n} : {a} → {x}"})
    return {"lignes": lignes, "avertissements": avert, "bloque": bloque,
            "a_ecrire": any(not l.get("ignore") for l in lignes)}


def _lire(app, pile, voulu):
    """Ouvre les périphériques du brouillon ; renvoie (clavier, souris, état courant)."""
    k = pile.enter_context(app.ouvrir("clavier")) if "clavier" in voulu else None
    s = pile.enter_context(app.ouvrir("souris")) if "souris" in voulu else None
    return k, s, {z: o.etat() for z, o in (("clavier", k), ("souris", s)) if o}


@route("POST", "/api/diff")
def r_diff(app, q, b):
    voulu = valider(b)
    with app.lock, contextlib.ExitStack() as pile:
        return comparer(_lire(app, pile, voulu)[2], voulu)


def _appliquer(app, voulu):
    with app.lock, contextlib.ExitStack() as pile:
        k, s, cur = _lire(app, pile, voulu)
        d = comparer(cur, voulu)
        if d["bloque"]:
            raise Bloque(" ".join(d["bloque"]))
        if not d["a_ecrire"]:
            return {"ecrit": False, "notes": [], "sauvegarde": None, **d}
        chemin = profil.sauvegarder(profil.lire_tout(k, s), app.dossier)  # AVANT toute écriture
        notes = []
        if k:  # les macros ne sont jamais écrites tant que le format n'est pas vérifié : on les laisse telles quelles
            notes += profil.appliquer_clavier(k, {**voulu["clavier"], "macros": cur["clavier"]["macros"]})
        if s:
            notes += profil.appliquer_souris(s, {"dpi": cur["souris"]["dpi"], "boutons": voulu["souris"]["boutons"]})
        etat = {z: o.etat() for z, o in (("clavier", k), ("souris", s)) if o}
        app.memoriser(**etat)
        return {"ecrit": True, "notes": notes, "sauvegarde": chemin.name, "etat": etat, **d}


@route("POST", "/api/appliquer")
def r_appliquer(app, q, b):
    return _appliquer(app, valider(b))


# ---- cartouche : import, sauvegardes, état d'usine -------------------------------------------------------

def _brouillon(c):
    out = {}
    if "clavier" in c:
        out["clavier"] = {"profil": c["clavier"].get("profil"), "touches": c["clavier"].get("touches", {}),
                          "macros": c["clavier"].get("macros", [])}
    if "souris" in c:
        out["souris"] = {"boutons": c["souris"].get("boutons", {})}
    return out


@route("POST", "/api/importer")
def r_importer(app, q, b):
    c = b.get("cartouche")
    if not isinstance(c, dict) or c.get("cartouche") != 1:
        raise Invalide("ce n'est pas une cartouche (version 1 attendue)")
    try:
        out = valider(_brouillon(c))
    except AttributeError:
        raise Invalide("cartouche mal formée")
    if "logiciel" in c:
        out["logiciel"] = valider_logiciel(c["logiciel"])
    return out


@route("GET", "/api/sauvegardes")
def r_sauvegardes(app, q, b):
    out = []
    for p in sorted(app.dossier.glob("sauvegarde-*.json"), key=lambda f: f.stat().st_mtime_ns, reverse=True):
        if not SAUVEGARDE.fullmatch(p.name):
            continue
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
            k = c.get("clavier") or {}
            resume = {"profil": k.get("profil"), "touches": len(k.get("touches", {})), "clavier": "clavier" in c, "souris": "souris" in c}
        except (OSError, ValueError, AttributeError):
            resume = {}
        out.append({"nom": p.name, "taille": p.stat().st_size, **resume})
    return {"sauvegardes": out}


@route("POST", "/api/restaurer")
def r_restaurer(app, q, b):
    nom = b.get("nom")
    if not (isinstance(nom, str) and SAUVEGARDE.fullmatch(nom) and (app.dossier / nom).is_file()):
        raise Invalide("sauvegarde inconnue")
    try:
        voulu = valider(_brouillon(profil.importer(app.dossier / nom)))
    except (ValueError, OSError, AttributeError) as e:
        raise Invalide(f"sauvegarde illisible : {e}")
    return _appliquer(app, voulu)


@route("POST", "/api/usine")
def r_usine(app, q, b):
    if b.get("confirmer") is not True:
        raise Invalide("confirmation requise")
    with app.lock, app.ouvrir("clavier") as k:
        chemin = profil.sauvegarder(profil.lire_tout(k), app.dossier)
        k.supprimer_profil()
        app.memoriser(clavier=k.etat())
        return {"sauvegarde": chemin.name, "etat": k.etat()}
