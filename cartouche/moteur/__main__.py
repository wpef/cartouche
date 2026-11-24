"""python -m cartouche.moteur --config fichier.json [--duree secondes] [--verifier]"""
import argparse
import logging
import sys

from .logique import ErreurConfig, Moteur
from .service import Service, charger_config


def main(argv=None):
    p = argparse.ArgumentParser(prog="cartouche.moteur", description="Moteur logiciel : règles que le matériel ne sait pas faire.")
    p.add_argument("--config", required=True, help="fichier JSON (section « logiciel » d'une cartouche)")
    p.add_argument("--duree", type=float, help="arrêt automatique après N secondes")
    p.add_argument("--verifier", action="store_true", help="valide la configuration puis quitte, sans poser de crochet")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        cfg = charger_config(a.config)
        Moteur(cfg)
    except (OSError, ValueError) as e:
        print(f"configuration refusée : {e}", file=sys.stderr)
        return 2
    if a.verifier:
        print("configuration valide")
        return 0
    s = Service(cfg)
    s.demarrer()
    logging.getLogger("cartouche.moteur").info("démarré ; arrêt d'urgence : Ctrl+Alt+Pause ; état %s", s.etat())
    try:
        s.arret.wait(a.duree)
    except KeyboardInterrupt:
        pass
    finally:
        s.arreter()
    logging.getLogger("cartouche.moteur").info("arrêté ; état %s", s.etat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
