"""Logique pure du moteur : aucun appel Windows."""
import unittest

from cartouche.moteur.logique import ErreurConfig, Moteur, appui

CFG = {
    "pause_apps": ["Game.exe"],
    "commun": {"touches": {"mouse4": {"couche": "souris", "court": "alt+left"}},
               "couches": {"souris": {"wheelup": {"media": "volup"}, "wheeldown": {"media": "voldown"},
                                      "ctrl+wheelup": {"molette": [-120, 0]}}}},
    "profils": {
        "defaut": {"touches": {
            "capslock": {"couche": "nav", "court": "esc"},
            "f13": "ctrl+shift+x",
            "f14": {"court": {"texte": "salut"}, "long": {"lancer": ["notepad.exe"]},
                    "double": {"url": "https://example.org"}},
            "f15": {"macro": ["a", {"attendre": 50}, {"bas": "b"}, {"haut": "b"}]},
            "ctrl+alt+1": {"profil": "code"},
            "f16": {"profil": "suivant"},
            "ctrl+f20": "a",
        }, "couches": {"nav": {"h": "left", "j": "down"}}},
        "code": {"apps": ["Code.exe"], "touches": {"f13": "f1", "f17": {"profil": "auto"}}},
    },
}


def moteur():
    return Moteur(CFG)


class Dec:
    def __init__(self, m, app=""):
        self.m, self.app, self.t = m, app, 0.0

    def __call__(self, code, down, dt=0.0, app=None):
        self.t += dt
        return self.m.traiter(code, down, self.t, self.app if app is None else app)

    def tape(self, code, dt=0.05):
        a = self(code, True)
        return a, self(code, False, dt)


class Regles(unittest.TestCase):
    def test_touche_sans_regle_passe(self):
        d = Dec(moteur())
        self.assertEqual(d("z", True), (True, []))
        self.assertEqual(d("z", False), (True, []))

    def test_accord_et_relachement_inverse(self):
        d = Dec(moteur())
        self.assertEqual(d("f13", True), (False, [("down", "lctrl"), ("down", "lshift"), ("down", "x")]))
        self.assertEqual(d("f13", True), (False, [("down", "x")]))  # répétition automatique
        self.assertEqual(d("f13", False), (False, [("up", "x"), ("up", "lshift"), ("up", "lctrl")]))

    def test_profil_par_application(self):
        d = Dec(moteur())
        self.assertEqual(d("f13", True, app="Code.exe")[1], [("down", "f1")])
        d("f13", False, app="Code.exe")
        self.assertEqual(d("f13", True, app="autre.exe")[1][0], ("down", "lctrl"))

    def test_changement_application_en_plein_appui(self):
        d = Dec(moteur())
        d("f13", True, app="autre.exe")
        self.assertEqual(d("f13", False, app="Code.exe")[1], [("up", "x"), ("up", "lshift"), ("up", "lctrl")])
        self.assertEqual(d.m.tenues, {})

    def test_appui_court_et_long(self):
        d = Dec(moteur())
        d("f14", True)
        self.assertEqual(d("f14", False, 0.1)[1], [])  # court : attend un éventuel double appui
        self.assertEqual(d.m.tick(d.t + 1), [("text", "salut")])
        d("f14", True)
        self.assertEqual(d("f14", False, 0.6)[1], [("run", ("notepad.exe",))])

    def test_appui_long_interrompu_donne_court(self):
        d = Dec(moteur())
        d("f14", True)
        d("z", True, 0.1)
        self.assertEqual(d("f14", False, 0.6)[1], [])
        self.assertEqual(d.m.tick(d.t + 1), [("text", "salut")])
        d("z", False)
        self.assertEqual(d.m.tenues, {})

    def test_double_appui(self):
        d = Dec(moteur())
        d.tape("f14")
        self.assertEqual(d("f14", True, 0.1), (False, [("url", "https://example.org")]))
        self.assertEqual(d("f14", False, 0.05), (False, []))
        self.assertEqual(d.m.tick(d.t + 5), [])

    def test_double_appui_expire_donne_court(self):
        d = Dec(moteur())
        d.tape("f14")
        self.assertEqual(d.m.tick(d.t + 0.1), [])
        self.assertEqual(d.m.tick(d.t + 0.5), [("text", "salut")])
        self.assertEqual(d.m.tick(d.t + 9), [])

    def test_autre_touche_vide_le_court_en_attente(self):
        d = Dec(moteur())
        d.tape("f14")
        self.assertEqual(d("z", True, 0.05), (True, [("text", "salut")]))

    def test_macro(self):
        d = Dec(moteur())
        self.assertEqual(d("f15", True)[1], appui(["a"]) + [("wait", 50), ("down", "b"), ("up", "b")])
        self.assertEqual(d("f15", False), (False, []))

    def test_url_refusee_et_touche_inconnue(self):
        for mauvais in ({"f1": {"url": "file:///c:/x"}}, {"f1": "nimportequoi"}, {"f1": {"couche": "nope"}},
                        {"f1": {"profil": "absent"}}):
            with self.assertRaises(ErreurConfig):
                Moteur({"profils": {"defaut": {"touches": mauvais}}})

    def test_modificateurs_requis(self):
        d = Dec(moteur())
        d("lctrl", True)
        self.assertEqual(d("f20", True)[1], [("down", "a")])
        d("f20", False)
        d("lctrl", False)
        self.assertEqual(d("f20", True), (True, []))


class Couches(unittest.TestCase):
    def test_couche_transforme_les_autres(self):
        d = Dec(moteur())
        self.assertEqual(d("capslock", True), (False, []))
        self.assertEqual(d("h", True)[1], [("down", "left")])
        self.assertEqual(d("capslock", False), (False, []))  # a servi de couche : pas de tap
        self.assertEqual(d("h", False)[1], [("up", "left")])  # relâché après la couche : suit son appui
        self.assertEqual(d("h", True), (True, []))  # couche partie

    def test_couche_seule_donne_court(self):
        d = Dec(moteur())
        d("capslock", True)
        self.assertEqual(d("capslock", False, 0.1)[1], appui(["esc"]))

    def test_touche_normale_pendant_couche_hors_table(self):
        d = Dec(moteur())
        d("capslock", True)
        self.assertEqual(d("z", True), (True, []))
        self.assertEqual(d("z", False), (True, []))

    def test_pas_de_touche_collee(self):
        d = Dec(moteur())
        d("capslock", True)
        d("h", True)
        d("capslock", False)
        self.assertEqual(d.m.tenues["h"], ("chord", ["left"]))
        d("h", False)
        self.assertEqual(d.m.tenues, {})
        self.assertEqual(d.m.liberer(), [])


class Souris(unittest.TestCase):
    def test_bouton_modificateur_molette_volume(self):
        d = Dec(moteur())
        self.assertEqual(d("mouse4", True), (False, []))
        self.assertEqual(d("wheelup", True), (False, appui(["volup"])))
        self.assertEqual(d("wheeldown", True), (False, appui(["voldown"])))
        self.assertEqual(d("mouse4", False), (False, []))
        self.assertEqual(d("wheelup", True), (True, []))

    def test_bouton_modificateur_defilement_horizontal(self):
        d = Dec(moteur())
        d("mouse4", True)
        d("lctrl", True)
        self.assertEqual(d("wheelup", True), (False, [("wheel", -120, 0)]))

    def test_clic_court_du_bouton(self):
        d = Dec(moteur())
        d("mouse4", True)
        self.assertEqual(d("mouse4", False, 0.1)[1], appui(["lalt", "left"]))


class Securite(unittest.TestCase):
    def test_arret_urgence_et_reprise(self):
        d = Dec(moteur())
        d("f13", True)
        d("lctrl", True)
        d("lalt", True)
        pas, steps = d("pause", True)
        self.assertTrue(pas)
        self.assertEqual(steps, [("up", "x"), ("up", "lshift"), ("up", "lctrl")])
        self.assertFalse(d.m.actif)
        self.assertEqual(d("f13", True), (True, []))
        d("pause", True)
        self.assertTrue(d.m.actif)

    def test_arret_urgence_non_reaffectable(self):
        cfg = {"profils": {"defaut": {"touches": {"pause": "a", "ctrl+alt+pause": "b"}}}}
        d = Dec(Moteur(cfg))
        d("lctrl", True)
        d("lalt", True)
        self.assertEqual(d("pause", True), (True, []))
        self.assertFalse(d.m.actif)

    def test_application_en_pause(self):
        d = Dec(moteur())
        self.assertEqual(d("f13", True, app="GAME.EXE"), (True, []))
        self.assertEqual(d("f13", False, app="GAME.EXE"), (True, []))
        self.assertEqual(d("capslock", True, app="game.exe"), (True, []))

    def test_pause_pendant_appui_relache_proprement(self):
        d = Dec(moteur())
        d("f13", True)
        self.assertEqual(d("f13", False, app="game.exe")[1][0], ("up", "x"))

    def test_bascule_de_profil(self):
        d = Dec(moteur())
        d("lctrl", True)
        d("lalt", True)
        self.assertEqual(d("1", True), (False, []))
        self.assertEqual(d.m.etat()["profil"], "code")
        d("f13", True, app="autre.exe")
        self.assertEqual(d.m.tenues["f13"], ("chord", ["f1"]))
        d("f13", False)
        d("f17", True)
        self.assertEqual(d.m.etat()["profil"], "defaut")
        d("f16", True)
        self.assertEqual(d.m.etat()["profil"], "code")

    def test_rechargement_garde_les_appuis(self):
        d = Dec(moteur())
        d("f13", True)
        d.m.charger({"profils": {"defaut": {}}})
        self.assertEqual(d("f13", False)[1][0], ("up", "x"))
        with self.assertRaises(ErreurConfig):
            d.m.charger({"profils": {"defaut": {"touches": {"f1": "zzz"}}}})
        self.assertEqual(d("f13", True), (True, []))


if __name__ == "__main__":
    unittest.main()
