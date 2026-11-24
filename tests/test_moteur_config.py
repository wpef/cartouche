"""Exemple fourni, cartouche entière, et détails de la colle qui ne touchent pas Windows."""
import json
import unittest
from pathlib import Path

from cartouche.moteur import Moteur, charger_config
from cartouche.moteur.touches import nom_vk, vk_nom

EXEMPLE = Path(__file__).parent.parent / "cartouche" / "moteur" / "exemple.json"


class Config(unittest.TestCase):
    def test_exemple_se_compile_et_fonctionne(self):
        m = Moteur(charger_config(EXEMPLE))
        self.assertEqual(m.traiter("f13", True, 0, "code.exe")[1], [("down", "lctrl"), ("down", "lshift"), ("down", "p")])
        m.traiter("f13", False, 0.1, "code.exe")
        self.assertEqual(m.traiter("f13", True, 1, "chrome.exe")[1][-1], ("down", "x"))
        m.traiter("f13", False, 1.1, "chrome.exe")
        self.assertEqual(m.traiter("f13", True, 2, "valorant.exe"), (True, []))

    def test_section_logiciel_d_une_cartouche(self):
        cart = {"nom": "x", "clavier": {}, "logiciel": json.loads(EXEMPLE.read_text(encoding="utf-8"))}
        self.assertEqual(Moteur(cart).traiter("f16", True, 0, "")[1][0], ("down", "playpause"))

    def test_codes_virtuels(self):
        self.assertEqual(nom_vk(0xA2), "lctrl")
        self.assertEqual(nom_vk(0xE8), "vk232")
        self.assertEqual((vk_nom("f24"), vk_nom("vk232"), vk_nom("a")), (0x87, 232, 0x41))


if __name__ == "__main__":
    unittest.main()
