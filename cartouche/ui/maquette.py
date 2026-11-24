"""Mode démonstration : un clavier et une souris en mémoire, avec la même interface que `Clavier` et `Souris`.
Rien ne touche au matériel. (Un `Faux` rejoue des réponses figées : il ne se prête pas à des écritures suivies de relectures.)"""
from .. import touches as T
from ..transport import NonPris
from ..clavier import corps_macro
from ..moteur.logique import Moteur as LogiqueMoteur


class Clavier:
    dry = False

    def __init__(self):
        self.profil, self.touches, self.liste = None, {}, []

    def nom_profil(self):
        return self.profil

    def etat(self):
        return {"profil": self.profil, "touches": dict(self.touches), "macros": [dict(m) for m in self.liste]}

    def affecter(self, hw, cible):
        if self.profil is None:
            return  # comme le clavier : sans profil nommé, rien n'est conservé
        t = T.cible_texte(cible)
        n = T.hw_nom(hw)
        if t == "default":
            self.touches.pop(n, None)
        else:
            self.touches[n] = t

    def creer_profil(self, nom):
        self.profil = nom

    def supprimer_profil(self):
        self.profil, self.touches = None, {}

    def ecrire_macro(self, m):
        corps_macro(m)
        self.liste = [x for x in self.liste if x["key"] != m["key"]] + [dict(m)]


class Moteur:
    """Moteur simulé : mêmes méthodes que `moteur.Service`, aucun crochet posé."""

    def __init__(self, config):
        self.moteur, self.tourne = LogiqueMoteur(config), False

    def demarrer(self):
        self.tourne = True

    def arreter(self):
        self.tourne = False

    def pause(self, pause=True):
        self.moteur.actif = not pause

    def recharger(self, config):
        self.moteur.charger(config)

    def etat(self):
        return dict(self.moteur.etat(), tourne=self.tourne, crochets=self.tourne, evenements=0, erreur=None)


class Souris:
    dry = False

    def __init__(self):
        self.boutons = {"0": "left", "1": "right", "2": "middle", "3": "back", "4": "forward", "5": "code:0"}

    def etat(self):
        return {"dpi": {"index": 3, "current": 2400, "stages": [800, 1200, 1600, 2400, 3200, 6400]},
                "boutons": dict(self.boutons), "batterie": {"percent": 80, "charging": False, "known": True}}

    def affecter_bouton(self, n, valeur):
        self.boutons[str(n)] = T.nom_valeur_souris(valeur)

    def ecrire_dpi(self, *_):
        raise NonPris("écriture des DPI")
