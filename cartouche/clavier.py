"""Clavier, interface de configuration (page d'usage 0x8C). Trames de 33 octets : rapport 0x52 (envoi) ou
0x54 (réponse) puis 32 octets. Toute écriture est acquittée par `54 e4 08` (`54 e4 09` = refus)."""
import time

from . import touches as T
from .transport import Erreur

SORTIE, ENTREE, TAILLE = 0x52, 0x54, 33
CODEC_NOM = "utf-16-be"  # hypothèse issue des sources, à confirmer au matériel


def hexa(b):
    return " ".join(f"{x:02x}" for x in b)


def trame(charge):
    return bytes([SORTIE]) + bytes(charge) + bytes(TAILLE - 1 - len(charge))


def encode_nom(s):
    return s.encode(CODEC_NOM)


def decode_nom(b):
    paires = [b[i:i + 2] for i in range(0, len(b) - 1, 2)]
    fin = next((i for i, p in enumerate(paires) if p == b"\0\0"), len(paires))
    return b"".join(paires[:fin]).decode(CODEC_NOM, "replace")


# ---- macros : un pas est "down:<touche>", "up:<touche>" ou "wait:<ms>" ----------------------------------

def _pas(s):
    op, _, arg = s.partition(":")
    if op in ("down", "up") and arg:
        u = T.usage_macro(arg)
        mod = T.est_modificateur_macro(u)
        return bytes([(0x83 if mod else 0x81) if op == "down" else (3 if mod else 1), u, 0])
    if op == "wait" and arg.isdigit():
        ms = int(arg)
        return bytes([0x0F, ms & 255, ms >> 8])
    raise Erreur(f"pas de macro invalide : {s} (down:<touche>, up:<touche>, wait:<ms>)")


def corps_macro(m):
    d = b"".join(_pas(s) for s in m["steps"])
    ms = m.get("interval_ms", 0)
    if ms > 0 or len(m["steps"]) > 1:
        d += bytes([0x0F, ms & 255, ms >> 8, 0])  # le 4e octet gonfle la longueur, comme l'application d'origine
    return d


def trames_macro(hw, m):
    """Commande 0x76 : première trame (en-tête + 21 octets), puis morceaux de 24 octets avec leur décalage."""
    d = corps_macro(m)
    if len(d) > 1000:
        raise Erreur("macro trop longue")
    n = len(d)
    p = bytearray(32)
    p[0], p[1], p[6] = 0x76, hw, 1
    if m.get("cycles") is None:
        p[8] = 0x20
    else:
        p[7] = m["cycles"]
    p[9] = n // 3
    if n < 0x16:
        p[5] = 0x1A
        p[10:10 + n] = d
        return [bytes(p)]
    p[2], p[5] = 1, 0x19
    p[10:31] = d[:21]
    out, cur = [bytes(p)], 21
    while cur < n:
        k = min(n - cur, 0x18)
        c = bytearray(32)
        c[0], c[1], c[2], c[5] = 0x76, hw, int(n - cur > 0x18), k
        c[3], c[4] = (cur + 4) & 255, (cur + 4) >> 8
        c[6:6 + k] = d[cur:cur + k]
        out.append(bytes(c))
        cur += k
    return out


def trames_nom_macro(hw, nom):
    b = encode_nom(nom)
    if not b or len(b) > 56:
        raise Erreur("nom de macro : 1 à 28 caractères")
    morceaux = [b[i:i + 28] for i in range(0, len(b), 28)]
    out = []
    for i, c in enumerate(morceaux):
        p = bytearray(32)
        p[0], p[1], p[2], p[3] = 0x74, hw, len(c), int(i + 1 < len(morceaux))
        p[4:4 + len(c)] = c
        out.append(bytes(p))
    return out


def decode_macro(hw, nom, rec):
    if len(rec) < 4:
        raise Erreur("enregistrement de macro trop court")
    count, steps, interval = rec[3], [], 0
    for i in range(count):
        e = rec[4 + 3 * i:7 + 3 * i]
        if len(e) < 3:
            raise Erreur("enregistrement de macro trop court")
        if e[0] == 0x0F and i + 1 == count:
            interval = e[1] | e[2] << 8
        elif e[0] == 0x0F:
            steps.append(f"wait:{e[1] | e[2] << 8}")
        elif e[0] in (0x81, 0x83):
            steps.append("down:" + T.nom_usage_macro(e[1]))
        elif e[0] in (1, 3):
            steps.append("up:" + T.nom_usage_macro(e[1]))
    return {"key": T.hw_nom(hw), "name": nom, "cycles": None if rec[2] == 0x20 else rec[1],
            "interval_ms": interval, "steps": steps}


class Clavier:
    def __init__(self, transport, dry=False):
        self.t, self.dry = transport, dry  # dry : les écritures sont affichées, jamais envoyées

    def _vider(self):
        while self.t.lire(0):
            pass

    def _jusqua(self, prefixe, delai_ms):
        """Lit jusqu'à une trame qui commence par `prefixe` ; les autres (`54 8a …`) sont ignorées."""
        fin = time.monotonic() + delai_ms / 1000
        while time.monotonic() < fin:
            r = self.t.lire(50)
            if r.startswith(bytes(prefixe)):
                return r.ljust(TAILLE, b"\0")
        raise Erreur(f"pas de réponse {hexa(prefixe)}")

    def _lire(self, charge):
        self._vider()
        self.t.ecrire(trame(charge))
        return self._jusqua([ENTREE, charge[0]], 600)

    def _accuse(self, delai_ms):
        fin = time.monotonic() + delai_ms / 1000
        while time.monotonic() < fin:
            r = self.t.lire(50)
            if r.startswith(bytes([ENTREE, 0xE4, 0x08])):
                return
            if r.startswith(bytes([ENTREE, 0xE4])):
                raise Erreur(f"écriture refusée par le clavier : {hexa(r[:4])}")
        raise Erreur("pas d'accusé de réception")

    def _ecrire(self, charges, delai_ms=1500):
        if self.dry:
            for c in charges:
                print("[simulation] envoi", hexa(trame(c)))
            return
        self._vider()
        for c in charges:
            self.t.ecrire(trame(c))
            time.sleep(0.005)
        self._accuse(delai_ms)

    def _attention(self):
        if self.dry:
            print("[simulation] envoi", hexa(trame([0x76, 0xFF])))
            return
        self._vider()
        self.t.ecrire(trame([0x76, 0xFF]))
        try:
            self._jusqua([ENTREE], 300)
        except Erreur:
            pass

    # ---- lectures ----------------------------------------------------------------------------------

    def nom_profil(self):
        r = self._lire([0x80])
        if r[2] == 0:
            return None
        octets = r[4:]  # r[2] : longueur du morceau, r[3] : un autre morceau suit
        for _ in range(2):
            if r[3] == 0:
                break
            r = self._lire([0x80])
            octets += r[4:]
        return decode_nom(octets)

    def touches_mappees(self):
        """Codes matériels des touches réaffectées."""
        r, out = self._lire([0x81, 0x00]), []
        while True:
            for i in range(2, TAILLE - 1, 2):  # paires (touche, 07) ; 0 termine
                if r[i] == 0:
                    return out
                out.append(r[i])
            if r[TAILLE - 1] != 1:
                return out
            r = self._jusqua([ENTREE, 0x81], 600)

    def lire_touche(self, hw):
        r = self._lire([0x83, hw])
        if r[2] != hw:
            raise Erreur(f"réponse pour la touche {r[2]:#04x}, attendu {hw:#04x}")
        return bytes(r[3:9])

    def macros(self):
        r = self._lire([0x82])
        liste = r[2:30]
        if r[30]:
            liste += self._lire([0x82])[2:6]
        return [self._macro(liste[i]) for i in range(0, len(liste) - 3, 4)[:8] if liste[i]]

    def _macro(self, hw):
        nom = b""
        for _ in range(3):
            r = self._lire([0x84, hw])
            nom += r[5:33]
            if r[4] == 0:
                break
        rec = b""
        while len(rec) < 609:
            r = self._lire([0x86, hw])
            rec += r[4:30]
            if r[3] == 0:
                break
        return decode_macro(hw, decode_nom(nom), rec)

    def etat(self):
        """État lisible : {'profil', 'touches': {nom: cible}, 'macros': [...]}."""
        return {"profil": self.nom_profil(),
                "touches": {T.hw_nom(h): T.cible_texte(self.lire_touche(h)) for h in self.touches_mappees()},
                "macros": self.macros()}

    # ---- écritures ---------------------------------------------------------------------------------

    def affecter(self, hw, cible):
        self._attention()
        self._ecrire([[0xFA, 0x03, 0x0C, 0x00, 0xAA, 0x09, 0x71, hw, *cible]])
        self._ecrire([[0x76, 0xA5]])

    def creer_profil(self, nom):
        """Nomme le profil courant : c'est ce qui l'enregistre dans le clavier."""
        n = encode_nom(nom)
        if not n or len(n) > 28:
            raise Erreur("nom de profil : 1 à 14 caractères")
        self._attention()
        self._ecrire([[0x70, len(n), 0, *n]])

    def supprimer_profil(self):
        """Supprime le profil courant et ses affectations."""
        self._ecrire([[0x70]])

    def ecrire_macro(self, m):
        hw = T.hw_code(m["key"])
        self._ecrire(trames_nom_macro(hw, m["name"]), 4000)
        self._ecrire(trames_macro(hw, m), 4000)
