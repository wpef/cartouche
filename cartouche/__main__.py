"""python -m cartouche [--dry-run] [--dir <sauvegardes>] <commande>. Toute écriture est précédée d'une sauvegarde."""
import json
import sys

from . import profil, transport
from . import touches as T
from .clavier import Clavier
from .souris import Souris
from .transport import Erreur

AIDE = """python -m cartouche [--dry-run] [--dir <sauvegardes>] <commande>
  list                          périphériques détectés
  dump                          tout lire, en JSON
  map <touche> <cible>          affecter (f13, lctrl+c, media:playpause, mouse:left, none)
  unmap <touche>                rendre à la touche sa fonction d'origine
  profile show|create <nom>|delete
  macro list|set <fichier.json>
  mouse show|button <n> <action>|dpi|rate|liftoff|wheel
  apply <fichier.json>          amener le matériel à l'état de la cartouche
  restore <sauvegarde.json>     idem, depuis une sauvegarde"""


def clavier(dry):
    return Clavier(transport.ouvrir_clavier(), dry)


def souris(dry):
    return Souris(transport.ouvrir_souris(), dry)


def sauvegarde(dossier, dry, k=None, m=None):
    if not dry:
        print("sauvegarde :", profil.sauvegarder(profil.lire_tout(k, m), dossier), file=sys.stderr)


def main(argv):
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    dossier = None
    if "--dir" in argv:
        i = argv.index("--dir")
        dossier = argv[i + 1]
        del argv[i:i + 2]
    cmd = argv[:1]
    arg = argv[1:]
    if cmd == ["list"]:
        for d in transport.lister():
            print(f"{d['pid']:04X} if{d['interface']:<2} page {d['page']:#06x} usage {d['usage']:#04x}  {d['produit']}"
                  + ("  [configurable]" if d["configurable"] else ""))
    elif cmd == ["dump"]:
        k = clavier(False) if _present(transport.PIDS_CLAVIER, transport.PAGE_CLAVIER) else None
        m = souris(False) if _present((transport.PID_SOURIS,), transport.PAGE_SOURIS) else None
        if not (k or m):
            raise Erreur("ni clavier ni souris configurable")
        print(json.dumps(profil.lire_tout(k, m), indent=2, ensure_ascii=False))
    elif cmd == ["map"] and len(arg) == 2:
        k = clavier(dry)
        sauvegarde(dossier, dry, k)
        k.affecter(T.hw_code(arg[0]), T.cible(arg[1]))
    elif cmd == ["unmap"] and len(arg) == 1:
        hw = T.hw_code(arg[0])
        t = T.cible_defaut(hw)
        if t is None:
            raise transport.NonPris("fonction d'origine inconnue : supprimer le profil")
        k = clavier(dry)
        sauvegarde(dossier, dry, k)
        k.affecter(hw, t)
    elif cmd == ["profile"] and arg[:1] == ["show"]:
        print(clavier(False).nom_profil() or "(aucun profil)")
    elif cmd == ["profile"] and arg[:1] == ["create"] and len(arg) == 2:
        k = clavier(dry)
        sauvegarde(dossier, dry, k)
        k.creer_profil(arg[1])
    elif cmd == ["profile"] and arg == ["delete"]:
        k = clavier(dry)
        sauvegarde(dossier, dry, k)
        k.supprimer_profil()
    elif cmd == ["macro"] and arg == ["list"]:
        print(json.dumps(clavier(False).macros(), indent=2, ensure_ascii=False))
    elif cmd == ["macro"] and arg[:1] == ["set"] and len(arg) == 2:
        k = clavier(dry)
        sauvegarde(dossier, dry, k)
        k.ecrire_macro(json.load(open(arg[1], encoding="utf-8")))
    elif cmd == ["mouse"] and arg == ["show"]:
        print(json.dumps(souris(False).etat(), indent=2))
    elif cmd == ["mouse"] and arg[:1] == ["button"] and len(arg) == 3:
        m = souris(dry)
        sauvegarde(dossier, dry, None, m)
        m.affecter_bouton(int(arg[1]), T.valeur_souris(arg[2]))
    elif cmd == ["mouse"] and arg[:1] in (["dpi"], ["rate"], ["liftoff"], ["wheel"]):
        getattr(souris(dry), {"dpi": "ecrire_dpi", "rate": "frequence_scrutation",
                              "liftoff": "distance_decollage", "wheel": "molette"}[arg[0]])()
    elif cmd in (["apply"], ["restore"]) and len(arg) == 1:
        voulu = profil.importer(arg[0])
        notes = []
        if "clavier" in voulu:
            k = clavier(dry)
            sauvegarde(dossier, dry, k)
            notes += profil.appliquer_clavier(k, voulu["clavier"])
        if "souris" in voulu:
            m = souris(dry)
            sauvegarde(dossier, dry, None, m)
            notes += profil.appliquer_souris(m, voulu["souris"])
        for n in notes:
            print("note :", n, file=sys.stderr)
    else:
        print(AIDE)


def _present(pids, page):
    return any(d["pid"] in pids and d["page"] == page for d in transport.lister())


try:
    main(sys.argv[1:])
except Erreur as e:
    sys.exit(f"erreur : {e}")
