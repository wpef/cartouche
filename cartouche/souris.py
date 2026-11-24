"""Souris Retro R8 via l'adaptateur 2,4 G, interface de configuration (page d'usage 0xFF00).
Rapports de 64 octets sans identifiant (sous hidapi : un `00` devant à l'envoi). Chaque commande reçoit deux
paquets : un écho qui commence par `21` (ignoré), puis la vraie réponse `01 06 <cmd> 11 …`."""
import time

from . import touches as T
from .transport import Erreur, NonPris

BOUTONS = 6  # 0 gauche, 1 droit, 2 milieu, 3 latéral, 4 supplémentaire, 5 (DPI ? non confirmé)


def paquet(corps):
    return bytes([0]) + bytes(corps) + bytes(64 - len(corps))


class Souris:
    def __init__(self, transport, dry=False):
        self.t, self.dry = transport, dry

    def _vider(self):
        while self.t.lire(0):
            pass

    def _requete(self, corps):
        self._vider()
        self.t.ecrire(paquet(corps))
        fin = time.monotonic() + 0.5
        while time.monotonic() < fin:
            r = self.t.lire(50)
            if len(r) >= 8 and r[:3] == bytes(corps[:3]):  # l'écho commence par 21
                return r
        raise Erreur("souris : pas de réponse à " + " ".join(f"{x:02x}" for x in corps[:4]))

    def dpi(self):
        r = self._requete([1, 6, 0x12, 1])
        n = r[4]
        if len(r) < 8 + 2 * n:
            raise Erreur("réponse DPI trop courte")
        le = lambda i: r[i] | r[i + 1] << 8
        return {"index": r[5], "current": le(6), "stages": [le(8 + 2 * i) for i in range(n)]}

    def bouton(self, n):
        """Valeur du micrologiciel pour un bouton (voir touches.BOUTONS_SOURIS)."""
        r = self._requete([1, 6, 0x10, 1, 0, n])
        if r[5] != n:
            raise Erreur(f"réponse pour le bouton {r[5]}, attendu {n}")
        return r[6] | r[7] << 8

    def batterie(self):
        """Sur le matériel testé la réponse est vide (known False) ; le sens des octets vient de r8-rs."""
        r = self._requete([1, 6, 0x1A, 1])
        return {"percent": min(r[4], 100), "charging": bool(r[5] & 1), "known": bool(r[4] or r[5])}

    def etat(self):
        return {"dpi": self.dpi(),
                "boutons": {str(n): T.nom_valeur_souris(self.bouton(n)) for n in range(BOUTONS)},
                "batterie": self.batterie()}

    def affecter_bouton(self, n, valeur):
        """Écrit puis relit ; un second essai est permis (r8-rs)."""
        if not 0 <= n < BOUTONS:
            raise Erreur(f"bouton {n} : 0 à {BOUTONS - 1}")
        corps = [1, 6, 0x10, 4, 0, n, valeur & 255, valeur >> 8]
        if self.dry:
            print("[simulation] envoi", " ".join(f"{x:02x}" for x in paquet(corps)))
            return
        for _ in range(2):
            self._vider()
            self.t.ecrire(paquet(corps))
            time.sleep(0.06)
            if self.bouton(n) == valeur:
                return
        raise Erreur(f"vérification échouée : bouton {n}, la relecture ne donne pas {valeur}")

    # Aucune de ces commandes n'est documentée : on ne les invente pas.
    def ecrire_dpi(self, *_):
        raise NonPris("écriture des DPI")

    def frequence_scrutation(self, *_):
        raise NonPris("fréquence de scrutation")

    def distance_decollage(self, *_):
        raise NonPris("distance de décollage")

    def molette(self, *_):
        raise NonPris("réglage de la molette")
