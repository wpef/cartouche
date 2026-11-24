"""Noms de touches du moteur <-> codes virtuels Windows (VK). Noms en minuscules."""
import re

VK = {"backspace": 8, "tab": 9, "enter": 13, "pause": 0x13, "capslock": 0x14, "esc": 27, "space": 32,
      "pageup": 33, "pagedown": 34, "end": 35, "home": 36, "left": 37, "up": 38, "right": 39, "down": 40,
      "printscreen": 0x2C, "insert": 0x2D, "delete": 0x2E, "lwin": 0x5B, "rwin": 0x5C, "app": 0x5D,
      "kpmultiply": 0x6A, "kpplus": 0x6B, "kpminus": 0x6D, "kpdot": 0x6E, "kpdivide": 0x6F,
      "numlock": 0x90, "scrolllock": 0x91, "lshift": 0xA0, "rshift": 0xA1, "lctrl": 0xA2, "rctrl": 0xA3,
      "lalt": 0xA4, "ralt": 0xA5, "mute": 0xAD, "voldown": 0xAE, "volup": 0xAF, "next": 0xB0,
      "prev": 0xB1, "stop": 0xB2, "playpause": 0xB3, "semicolon": 0xBA, "equal": 0xBB, "comma": 0xBC,
      "minus": 0xBD, "dot": 0xBE, "slash": 0xBF, "grave": 0xC0, "lbracket": 0xDB, "backslash": 0xDC,
      "rbracket": 0xDD, "apostrophe": 0xDE}
VK.update({chr(97 + i): 0x41 + i for i in range(26)})
VK.update({str(i): 0x30 + i for i in range(10)})
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
VK.update({f"kp{i}": 0x60 + i for i in range(10)})
NOM = {v: k for k, v in VK.items()}
NOM.update({0x10: "lshift", 0x11: "lctrl", 0x12: "lalt"})
# noms génériques -> touche gauche (pour émettre) ; touche physique -> modificateur générique
GENERIC = {"ctrl": "lctrl", "shift": "lshift", "alt": "lalt", "win": "lwin"}
MODGEN = {"lctrl": "ctrl", "rctrl": "ctrl", "lshift": "shift", "rshift": "shift",
          "lalt": "alt", "ralt": "alt", "lwin": "win", "rwin": "win"}
MOUSE = {f"mouse{i}": i for i in range(1, 6)}  # 1 gauche, 2 droit, 3 milieu, 4 précédent, 5 suivant
MOLETTE = ("wheelup", "wheeldown", "wheelleft", "wheelright")
_VKN = re.compile(r"vk\d+$")


def valide(n):
    return n in VK or n in MOUSE or n in MOLETTE or bool(_VKN.match(n))


def nom_vk(vk):
    return NOM.get(vk, f"vk{vk}")


def vk_nom(n):
    return VK[n] if n in VK else int(n[2:])
