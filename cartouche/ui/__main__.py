"""python -m cartouche.ui [--demo] [--port N] [--dir <sauvegardes>] [--sans-navigateur]"""
import argparse
import sys
import webbrowser

from .api import App
from .serveur import Serveur

p = argparse.ArgumentParser(prog="python -m cartouche.ui", description="Interface web locale de Cartouche (127.0.0.1).")
p.add_argument("--demo", action="store_true", help="périphériques simulés en mémoire, rien n'est écrit dans le matériel")
p.add_argument("--port", type=int, default=8737)
p.add_argument("--dir", help="dossier des sauvegardes (défaut : captures/sauvegardes)")
p.add_argument("--sans-navigateur", action="store_true")
a = p.parse_args()
try:
    s = Serveur(App(a.demo, a.dir), a.port)
except OSError as e:
    sys.exit(f"erreur : port {a.port} indisponible ({e})")
url = f"http://127.0.0.1:{s.server_address[1]}/"
print(f"Cartouche{' (démonstration)' if a.demo else ''} : {url}  (Ctrl+C pour arrêter)")
if not a.sans_navigateur:
    webbrowser.open(url)
try:
    s.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    s.server_close()
