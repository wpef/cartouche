"""Le moteur en fond : crochets + fil de sortie. API pour l'intégration : Service."""
import json
import logging
import os
import queue
import sys
import threading
import time

from .logique import Moteur

log = logging.getLogger("cartouche.moteur")


def charger_config(source):
    """Chemin d'un fichier JSON, ou dict déjà lu. Accepte une cartouche entière (section « logiciel ») ou la section seule."""
    if isinstance(source, (str, os.PathLike)):
        with open(source, encoding="utf-8") as f:
            source = json.load(f)
    return source


class Service:
    """Service(config).demarrer() / .arreter() / .recharger(config) / .etat()."""

    def __init__(self, config):
        self.moteur = Moteur(charger_config(config))
        self.arret = threading.Event()
        self.file = queue.Queue()
        self.fils = []
        self.erreur = None
        self.crochets_ok = threading.Event()
        self.evenements = 0

    # -- API publique
    def demarrer(self, delai=5.0):
        """Pose les crochets (dans un fil dédié) ; lève OSError si impossible."""
        if self.fils:
            return
        self.arret.clear()
        self.erreur = None
        self.crochets_ok.clear()
        self.fils = [threading.Thread(target=f, name=f.__name__, daemon=True) for f in (self._crochets, self._sortie)]
        for f in self.fils:
            f.start()
        if not self.crochets_ok.wait(delai) or self.erreur:
            self.arreter()
            raise OSError(f"crochets non posés : {self.erreur}")

    def arreter(self):
        """Arrête, retire les crochets et relâche toute touche tenue. Idempotent."""
        self.arret.set()
        for f in self.fils:
            f.join(5)
        self.fils = []
        from .windows import Sortie
        s = Sortie(threading.Event())
        s.executer(self.moteur.liberer())

    def recharger(self, config):
        """Nouvelle configuration à chaud ; si elle est invalide, lève ErreurConfig et garde l'ancienne."""
        self.moteur.charger(charger_config(config))

    def etat(self):
        return dict(self.moteur.etat(), tourne=bool(self.fils) and not self.arret.is_set(),
                    crochets=self.crochets_ok.is_set(), evenements=self.evenements, erreur=self.erreur)

    # -- fils
    def _evt(self, code, bas):
        from .windows import application_premier_plan
        self.evenements += 1
        passer, steps = self.moteur.traiter(code, bas, time.monotonic(), application_premier_plan())
        if steps:
            self.file.put(steps)
        return not passer

    def _crochets(self):
        from .windows import Crochets
        c = Crochets(self._evt)
        try:
            c.poser()
            self.crochets_ok.set()
            while not self.arret.is_set():
                c.pomper(50)
        except Exception as e:
            self.erreur = repr(e)
            log.exception("fil des crochets")
            self.crochets_ok.set()
        finally:
            c.retirer()

    def _sortie(self):
        # ponytail: un seul fil pour la sortie et les délais ; une macro longue retarde les doubles appuis en attente
        from .windows import Sortie
        s = Sortie(self.arret)
        while not self.arret.is_set():
            try:
                steps = self.file.get(timeout=0.02)
            except queue.Empty:
                steps = self.moteur.tick(time.monotonic())
            s.executer(steps)
        s.liberer()


def demarrage_auto(activer, config=None):
    """Pose ou retire un lanceur dans le dossier Démarrage de l'utilisateur (jamais appelé par le moteur lui-même).
    ponytail: un .cmd plutôt qu'un .lnk (qui demande COM) ; même effet à l'ouverture de session."""
    dossier = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    lanceur = os.path.join(dossier, "cartouche-moteur.cmd")
    if not activer:
        if os.path.exists(lanceur):
            os.remove(lanceur)
        return lanceur
    py = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    py = py if os.path.exists(py) else sys.executable
    cmd = f'"{py}" -m cartouche.moteur' + (f' --config "{os.path.abspath(config)}"' if config else "")
    with open(lanceur, "w", encoding="utf-8") as f:
        f.write(f'@echo off\r\nstart "" /min {cmd}\r\n')
    return lanceur
