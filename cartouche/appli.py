"""python -m cartouche app : interface web, moteur logiciel et icône de la zone de notification dans un seul processus."""
import argparse
import logging
import os
import sys
import threading
import webbrowser

from . import donnees
from .transport import Erreur
from .ui.api import App
from .ui.serveur import Serveur

log = logging.getLogger("cartouche")
SEUIL_BATTERIE = 20      # alerte en dessous (hors charge)
RETOUR_BATTERIE = 30     # l'alerte se réarme au-dessus
INTERVALLE_BATTERIE = 300  # secondes entre deux lectures de la batterie de la souris


def alerte_batterie(b, deja):
    """(message ou None, `deja`) : prévient une fois quand la batterie connue passe sous le seuil, se réarme en remontant."""
    if not b or not b.get("known"):
        return None, deja
    if b.get("charging") or b["percent"] >= RETOUR_BATTERIE:
        return None, False
    if b["percent"] < SEUIL_BATTERIE and not deja:
        return f"Batterie de la souris faible : {b['percent']} %.", True
    return None, deja


class Appli:
    def __init__(self, demo=False, donnees_dir=None, dossier=None, port=8737, navigateur=True, icone=True):
        self.app = App(demo, dossier or (os.path.join(donnees.dossier(donnees_dir), "sauvegardes") if not demo else None), donnees_dir)
        self.serveur = Serveur(self.app, port)  # OSError si le port est pris
        self.url = f"http://127.0.0.1:{self.serveur.server_address[1]}/"
        self.navigateur, self.icone, self.zone = navigateur, icone, None
        self.fin, self.arrete, self.deja = threading.Event(), threading.Event(), False

    # -- cycle de vie
    def demarrer(self):
        threading.Thread(target=self.serveur.serve_forever, name="http", daemon=True).start()
        try:
            self.app.moteur.demarrer()
        except OSError as e:  # l'interface reste utilisable : l'écran Logiciel affiche l'état
            log.error("moteur non démarré : %s", e)
        if self.icone:
            from .zone import Zone
            self.zone = Zone("Cartouche", self._entrees, self.ouvrir)
            if not self.zone.demarrer():
                log.warning("pas d'icône dans la zone de notification : l'application continue sans")
                self.zone = None
        threading.Thread(target=self._veille, name="batterie", daemon=True).start()
        if self.navigateur:
            self.ouvrir()

    def arreter(self):
        if self.arrete.is_set():
            return
        self.arrete.set()
        if self.zone:
            self.zone.arreter()
        self.app.moteur.arreter()
        self.serveur.shutdown()
        self.serveur.server_close()

    def attendre(self, duree=None):
        try:
            self.fin.wait(duree)
        except KeyboardInterrupt:
            pass

    # -- actions
    def ouvrir(self):
        webbrowser.open(self.url)

    def _pause_ou_reprise(self):
        e = self.app.moteur.etat()
        if not e["tourne"]:
            self.app.moteur.demarrer()
        else:
            self.app.moteur.pause(e["actif"])

    def _entrees(self):
        e = self.app.moteur.etat()
        libelle = "Démarrer le moteur" if not e["tourne"] else "Mettre le moteur en pause" if e["actif"] else "Reprendre le moteur"
        return [("ouvrir", "Ouvrir", self.ouvrir), ("pause", libelle, self._pause_ou_reprise), ("quitter", "Quitter", self.fin.set)]

    def _veille(self):
        """Lit la batterie de la souris de temps en temps (un accès HID à la fois, sous le verrou de l'application)."""
        attente = 10
        while not self.arrete.wait(attente):
            attente = INTERVALLE_BATTERIE
            try:
                msg, self.deja = alerte_batterie(self.app.batterie(), self.deja)
            except Exception as e:  # périphérique absent ou occupé : on réessaiera
                log.info("batterie illisible : %s", e)
                continue
            if msg:
                log.warning(msg)
                if self.zone:
                    self.zone.notifier("Cartouche", msg)


def main(argv):
    p = argparse.ArgumentParser(prog="python -m cartouche app", description="Cartouche : interface, moteur logiciel et icône de notification.")
    p.add_argument("--demo", action="store_true", help="périphériques et moteur simulés, rien n'est écrit ni intercepté")
    p.add_argument("--port", type=int, default=8737)
    p.add_argument("--donnees", help="dossier du fichier de l'utilisateur (défaut : %%APPDATA%%\\Cartouche)")
    p.add_argument("--dir", help="dossier des sauvegardes (défaut : <donnees>\\sauvegardes)")
    p.add_argument("--duree", type=float, help="arrêt automatique après N secondes (essais)")
    p.add_argument("--sans-navigateur", action="store_true")
    p.add_argument("--sans-icone", action="store_true")
    a = p.parse_args(argv)
    if sys.stdout is None:  # pythonw : pas de console
        sys.stdout = sys.stderr = open(os.devnull, "w")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        x = Appli(a.demo, a.donnees, a.dir, a.port, not a.sans_navigateur, not a.sans_icone)
    except OSError as e:
        print(f"erreur : port {a.port} indisponible ({e})", file=sys.stderr)
        return 1
    except Erreur as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 1
    print(f"Cartouche{' (démonstration)' if a.demo else ''} : {x.url}  (Ctrl+C ou « Quitter » de l'icône pour arrêter ; arrêt d'urgence du moteur : Ctrl+Alt+Pause)")
    x.demarrer()
    x.attendre(a.duree)
    x.arreter()
    return 0
