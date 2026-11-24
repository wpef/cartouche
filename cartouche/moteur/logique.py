"""Logique pure du moteur : événements en entrée, décisions en sortie. Aucun appel Windows.

Étapes (ce que le fil de sortie exécute) : ("down", nom) ("up", nom) ("wait", ms) ("text", s)
("run", argv) ("url", s) ("wheel", dx, dy). Les étapes ("profil", nom) sont traitées ici."""
import threading
from urllib.parse import urlparse

from .touches import GENERIC, MODGEN, MOLETTE, valide


class ErreurConfig(ValueError):
    pass


# ---------------------------------------------------------------- compilation de la configuration
def combo(s):
    """'ctrl+shift+x' -> ['lctrl', 'lshift', 'x'] (noms validés)."""
    noms = [GENERIC.get(p.strip(), p.strip()) for p in str(s).lower().split("+")]
    for n in noms:
        if not valide(n):
            raise ErreurConfig(f"touche inconnue : {n!r} (dans {s!r})")
    return noms


def appui(noms):
    return [("down", n) for n in noms] + [("up", n) for n in reversed(noms)]


def action(a):
    if isinstance(a, str):
        return appui(combo(a))
    if isinstance(a, list):
        return [e for x in a for e in action(x)]
    if not isinstance(a, dict):
        raise ErreurConfig(f"action illisible : {a!r}")
    out = []
    for k, v in a.items():
        if k in ("envoyer", "media"):
            out += action(v)
        elif k == "macro":
            out += action(list(v))
        elif k == "lancer":
            argv = [v] if isinstance(v, str) else [str(x) for x in v]
            if not argv:
                raise ErreurConfig("lancer : commande vide")
            out.append(("run", tuple(argv)))
        elif k == "url":
            if urlparse(str(v)).scheme not in ("http", "https", "mailto"):
                raise ErreurConfig(f"url refusée (http, https ou mailto seulement) : {v!r}")
            out.append(("url", str(v)))
        elif k == "texte":
            out.append(("text", str(v)))
        elif k == "attendre":
            out.append(("wait", int(v)))
        elif k in ("bas", "haut"):
            (n,) = combo(v)
            out.append(("down" if k == "bas" else "up", n))
        elif k == "profil":
            out.append(("profil", str(v)))
        elif k == "molette":  # [dx, dy], dy > 0 vers le haut, dx > 0 vers la droite, 120 = un cran
            out.append(("wheel", int(v[0]), int(v[1])))
        else:
            raise ErreurConfig(f"action inconnue : {k!r}")
    return out


def regle(v, cfg):
    if isinstance(v, str):
        return ("remap", combo(v))
    if isinstance(v, dict) and {"couche", "court", "long", "double"} & v.keys():
        f = lambda k: action(v[k]) if k in v else None
        return ("tap", {"couche": v.get("couche"), "court": f("court"), "long": f("long"), "double": f("double"),
                        "seuil": v.get("seuil", cfg.get("seuil_long", 400)) / 1000,
                        "delai": v.get("delai", cfg.get("delai_double", 300)) / 1000})
    return ("action", action(v))


def table(touches, cfg):
    """{'ctrl+alt+p': règle} -> {code: [(modificateurs, règle)]}."""
    t = {}
    for spec, v in (touches or {}).items():
        *mods, cle = [p.strip() for p in str(spec).lower().split("+")]
        mods = frozenset(MODGEN.get(GENERIC.get(m, m), m) for m in mods)
        if not mods <= set(MODGEN.values()):
            raise ErreurConfig(f"modificateur inconnu dans {spec!r}")
        codes = [c for c, g in MODGEN.items() if g == cle] or [cle]
        for c in codes:
            if not valide(c):
                raise ErreurConfig(f"touche inconnue : {c!r}")
            t.setdefault(c, []).append((mods, regle(v, cfg)))
    return t


def compiler(cfg):
    cfg = cfg.get("logiciel", cfg)

    def profil(p):
        return {"apps": {a.lower() for a in p.get("apps", [])}, "touches": table(p.get("touches"), cfg),
                "couches": {n: table(c, cfg) for n, c in p.get("couches", {}).items()}}

    profils = {n: profil(p) for n, p in cfg.get("profils", {}).items()}
    defaut = cfg.get("profil_defaut", "defaut")
    profils.setdefault(defaut, profil({}))
    commun = profil(cfg.get("commun", {}))
    for p in [commun, *profils.values()]:
        for rs in p["touches"].values():
            for _, r in rs:
                if r[0] == "tap" and r[1]["couche"] and not any(r[1]["couche"] in q["couches"] for q in (p, commun)):
                    raise ErreurConfig(f"couche inconnue : {r[1]['couche']!r}")
                for e in r[1] if r[0] == "action" else []:
                    if e[0] == "profil" and e[1] not in (*profils, "auto", "suivant"):
                        raise ErreurConfig(f"profil inconnu : {e[1]!r}")
    return {"profils": profils, "defaut": defaut, "commun": commun,
            "pause": {a.lower() for a in cfg.get("pause_apps", [])}}


# ---------------------------------------------------------------- machine à états
class Moteur:
    def __init__(self, cfg):
        self.verrou = threading.RLock()
        self.c = compiler(cfg)
        self.actif = True
        self.force = None       # profil imposé par une bascule (None = automatique)
        self.physiques = set()  # modificateurs physiquement tenus
        self.tenues = {}        # code -> décision prise à l'appui (le relâchement la suit, même si le profil change)
        self.attente = {}       # code -> (échéance, étapes de l'appui court, étapes du double appui)
        self.app = ""

    def charger(self, cfg):
        c = compiler(cfg)  # lève avant de toucher à l'état
        with self.verrou:
            self.c = c
            if self.force not in c["profils"]:
                self.force = None

    def etat(self):
        with self.verrou:
            return {"actif": self.actif, "profil": self.profil_nom(self.app), "app": self.app,
                    "tenues": len(self.tenues), "en_attente": len(self.attente)}

    def profil_nom(self, app):
        if self.force:
            return self.force
        for n, p in self.c["profils"].items():
            if app in p["apps"]:
                return n
        return self.c["defaut"]

    # -- sorties
    def liberer(self):
        """Relâche tout ce que le moteur tient enfoncé ; à l'arrêt ou à la désactivation."""
        with self.verrou:
            steps = []
            for r in self.tenues.values():
                if r[0] == "chord":
                    steps += [("up", n) for n in reversed(r[1])]
            self.tenues.clear()
            self.attente.clear()
            return steps

    def tick(self, now):
        """Appuis courts dont le délai de double appui est écoulé."""
        with self.verrou:
            out = []
            for code, (fin, court, _) in list(self.attente.items()):
                if now >= fin:
                    del self.attente[code]
                    out += court
            return self._finir(out)

    def _finir(self, steps):
        out = []
        for e in steps:
            if e[0] != "profil":
                out.append(e)
            elif e[1] == "auto":
                self.force = None
            elif e[1] == "suivant":
                noms = list(self.c["profils"])
                self.force = noms[(noms.index(self.profil_nom(self.app)) + 1) % len(noms)]
            else:
                self.force = e[1]
        return out

    def _flush(self, sauf=None):
        out = []
        for code, (_, court, _) in list(self.attente.items()):
            if code != sauf:
                del self.attente[code]
                out += court
        return out

    # -- recherche d'une règle
    def _trouver(self, code, couches):
        if self.app in self.c["pause"]:
            return None
        mods = {MODGEN[c] for c in self.physiques if c != code}
        p = self.c["profils"][self.profil_nom(self.app)]
        for tb in [*couches, p["touches"], self.c["commun"]["touches"]]:
            meilleur = None
            for m, r in tb.get(code, ()):
                if m <= mods and (meilleur is None or len(m) > len(meilleur[0])):
                    meilleur = (m, r)
            if meilleur:
                return meilleur[1]

    def _couche(self, nom):
        p = self.c["profils"][self.profil_nom(self.app)]
        return p["couches"].get(nom) or self.c["commun"]["couches"].get(nom) or {}

    def _couches(self):
        return [r[1]["map"] for r in reversed(list(self.tenues.values())) if r[0] == "tap" and r[1]["map"] is not None]

    def _marquer(self):
        for r in self.tenues.values():
            if r[0] == "tap":
                r[1]["interrompu"] = True

    # -- entrée principale : (laisser passer ?, étapes à exécuter)
    def traiter(self, code, down, t, app=""):
        with self.verrou:
            self.app = app.lower()
            if code in MODGEN:
                (self.physiques.add if down else self.physiques.discard)(code)
            if down and code == "pause" and {"ctrl", "alt"} <= {MODGEN[c] for c in self.physiques}:
                self.actif = not self.actif  # arrêt d'urgence : codé en dur, aucune règle ne passe avant
                return True, self.liberer()
            if not self.actif:
                return True, []
            if code in MOLETTE:
                return self._molette(code)
            return self._appui(code, t) if down else self._relache(code, t)

    def _molette(self, code):
        steps = self._flush()
        self._marquer()
        r = self._trouver(code, self._couches())
        if r is None or r[0] == "tap":
            return True, steps
        return False, self._finir(steps + (appui(r[1]) if r[0] == "remap" else r[1]))

    def _appui(self, code, t):
        rec = self.tenues.get(code)
        if rec:  # répétition automatique
            if rec[0] == "pass":
                return True, []
            return False, [("down", rec[1][-1])] if rec[0] == "chord" else []
        att = self.attente.pop(code, None)
        steps = self._flush(sauf=code)
        if att and t <= att[0]:
            self.tenues[code] = ("swallow",)
            return False, self._finir(steps + att[2])
        if att:
            steps += att[1]
        self._marquer()
        r = self._trouver(code, self._couches())
        if r is None:
            self.tenues[code] = ("pass",)
            return True, self._finir(steps)
        if r[0] == "remap":
            self.tenues[code] = ("chord", r[1])
            return False, steps + [("down", n) for n in r[1]]
        if r[0] == "action":
            self.tenues[code] = ("swallow",)
            return False, self._finir(steps + r[1])
        d = dict(r[1], t0=t, interrompu=False)
        d["map"] = self._couche(d["couche"]) if d["couche"] else None
        self.tenues[code] = ("tap", d)
        return False, self._finir(steps)

    def _relache(self, code, t):
        rec = self.tenues.pop(code, None)
        if rec is None or rec[0] == "pass":
            return True, []
        if rec[0] == "chord":
            return False, [("up", n) for n in reversed(rec[1])]
        if rec[0] == "swallow":
            return False, []
        d = rec[1]
        if d["map"] is not None and d["interrompu"]:
            return False, []  # la touche a servi de couche
        if d["long"] and not d["interrompu"] and t - d["t0"] >= d["seuil"]:
            return False, self._finir(d["long"])
        court = d["court"] if d["court"] is not None else appui([code])
        if d["double"]:
            self.attente[code] = (t + d["delai"], court, d["double"])
            return False, []
        return False, self._finir(court)
