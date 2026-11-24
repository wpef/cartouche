"""Accès HID. Une trame commence par l'identifiant de rapport, comme sur le fil."""
import time

VID = 0x2DC8
PIDS_CLAVIER = (0x5200, 0x5209)  # câble ; le récepteur 2,4 G (5201) reste muet
PAGE_CLAVIER = 0x8C
PID_SOURIS = 0x5206              # adaptateur 2,4 G
PAGE_SOURIS = 0xFF00


class Erreur(Exception):
    """Périphérique absent, réponse absente ou inattendue, relecture qui ne correspond pas."""


class Refuse(Erreur):
    """Trame refusée par le garde-fou."""


class NonPris(Erreur):
    """Fonction non documentée : on ne l'invente pas."""


def garde(trame):
    # Le rapport 0xB2 est le canal de mise à jour du firmware. Jamais.
    if trame and trame[0] == 0xB2:
        raise Refuse("rapport 0xB2 (firmware)")


class Transport:
    """Interface : ecrire(trame) et lire(delai_ms) -> bytes (vide si rien n'arrive)."""

    def ecrire(self, trame):
        raise NotImplementedError

    def lire(self, delai_ms):
        raise NotImplementedError


class Hid(Transport):
    def __init__(self, chemin):
        import hid
        self.d = hid.device()
        self.d.open_path(chemin)
        self.d.set_nonblocking(True)

    def ecrire(self, trame):
        garde(trame)
        if self.d.write(bytes(trame)) < 0:
            raise Erreur("écriture HID impossible")

    def lire(self, delai_ms):
        fin = time.monotonic() + delai_ms / 1000
        while True:
            r = self.d.read(65)
            if r:
                return bytes(r)
            if time.monotonic() >= fin:
                return b""
            time.sleep(0.002)

    def fermer(self):
        self.d.close()


class Faux(Transport):
    """Pour les tests : rejoue des réponses, garde ce qui a été envoyé."""

    def __init__(self, reponses=()):
        self.envoye = []
        self.reponses = list(reponses)

    def ecrire(self, trame):
        garde(trame)
        self.envoye.append(bytes(trame))

    def lire(self, delai_ms):
        # un délai nul sert à vider le tampon : rien d'ancien dans le jeu d'essai
        return b"" if delai_ms == 0 or not self.reponses else self.reponses.pop(0)


def lister():
    """Interfaces 2DC8 sans numéro de série ni adresse Bluetooth."""
    import hid
    out = [dict(pid=d["product_id"], interface=d["interface_number"], page=d["usage_page"],
                usage=d["usage"], produit=d["product_string"],
                configurable=(d["product_id"] in PIDS_CLAVIER and d["usage_page"] == PAGE_CLAVIER)
                or (d["product_id"] == PID_SOURIS and d["usage_page"] == PAGE_SOURIS))
           for d in hid.enumerate(VID)]
    return sorted(out, key=lambda d: (d["pid"], d["interface"], d["page"]))


def _ouvrir(pids, page, quoi):
    import hid
    for d in hid.enumerate(VID):
        if d["product_id"] in pids and d["usage_page"] == page:
            return Hid(d["path"])
    raise Erreur(f"{quoi} introuvable (clavier : câble USB, interrupteur sur OFF ; souris : adaptateur 2,4 G)")


def ouvrir_clavier():
    return _ouvrir(PIDS_CLAVIER, PAGE_CLAVIER, "clavier")


def ouvrir_souris():
    return _ouvrir((PID_SOURIS,), PAGE_SOURIS, "souris")
