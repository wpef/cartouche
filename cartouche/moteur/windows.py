"""Colle Windows (ctypes, rien à installer) : crochets bas niveau, SendInput, application au premier plan.

Règle d'or : un rappel ne lève jamais et ne bloque jamais ; en cas de doute l'événement passe."""
import ctypes
import ctypes.wintypes as w
import logging
import os
import subprocess
import time

from .touches import MOUSE, nom_vk, vk_nom

log = logging.getLogger("cartouche.moteur")
u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, w.WPARAM, w.LPARAM)
ULONG_PTR = ctypes.c_size_t


class KBD(ctypes.Structure):
    _fields_ = [("vk", w.DWORD), ("scan", w.DWORD), ("flags", w.DWORD), ("time", w.DWORD), ("extra", ULONG_PTR)]


class MSL(ctypes.Structure):
    _fields_ = [("pt", w.POINT), ("data", w.DWORD), ("flags", w.DWORD), ("time", w.DWORD), ("extra", ULONG_PTR)]


class _KI(ctypes.Structure):
    _fields_ = [("vk", w.WORD), ("scan", w.WORD), ("flags", w.DWORD), ("time", w.DWORD), ("extra", ULONG_PTR)]


class _MI(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("data", w.DWORD), ("flags", w.DWORD), ("time", w.DWORD),
                ("extra", ULONG_PTR)]


class _HI(ctypes.Structure):
    _fields_ = [("msg", w.DWORD), ("lo", w.WORD), ("hi", w.WORD)]


class _U(ctypes.Union):
    _fields_ = [("ki", _KI), ("mi", _MI), ("hi", _HI)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", w.DWORD), ("u", _U)]


u32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, w.HINSTANCE, w.DWORD]
u32.SetWindowsHookExW.restype = w.HHOOK
u32.CallNextHookEx.argtypes = [w.HHOOK, ctypes.c_int, w.WPARAM, w.LPARAM]
u32.CallNextHookEx.restype = LRESULT
u32.UnhookWindowsHookEx.argtypes = [w.HHOOK]
u32.SendInput.argtypes = [w.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
u32.GetForegroundWindow.restype = w.HWND
u32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
u32.PeekMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
u32.MsgWaitForMultipleObjects.argtypes = [w.DWORD, ctypes.c_void_p, w.BOOL, w.DWORD, w.DWORD]
k32.GetModuleHandleW.argtypes = [w.LPCWSTR]
k32.GetModuleHandleW.restype = w.HMODULE
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.OpenProcess.restype = w.HANDLE
k32.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
k32.CloseHandle.argtypes = [w.HANDLE]

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
TOUCHE_BAS, TOUCHE_HAUT = (0x100, 0x104), (0x101, 0x105)
ETENDUES = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D, 0x6F, 0x90, 0xA3, 0xA5}
# message souris -> (numéro de bouton, appui ?)
BOUTONS = {0x201: (1, True), 0x202: (1, False), 0x204: (2, True), 0x205: (2, False), 0x207: (3, True), 0x208: (3, False)}
MOUSEEVENTF = {1: (0x2, 0x4), 2: (0x8, 0x10), 3: (0x20, 0x40)}  # X1/X2 : 0x80 / 0x100 avec donnée 1 ou 2


def _signe16(n):
    n = (n >> 16) & 0xFFFF
    return n - 0x10000 if n & 0x8000 else n


class Crochets:
    """Pose les deux crochets ; on_event(code, appui) -> True pour bloquer l'événement.
    Les événements injectés (SendInput, donc ceux du moteur) ne sont jamais transmis à on_event."""

    def __init__(self, on_event):
        self.on_event, self.hooks = on_event, []
        self._kb_ref, self._ms_ref = HOOKPROC(self._kb), HOOKPROC(self._ms)  # garder en vie

    def poser(self):
        h = k32.GetModuleHandleW(None)
        for id_, ref in ((WH_KEYBOARD_LL, self._kb_ref), (WH_MOUSE_LL, self._ms_ref)):
            hk = u32.SetWindowsHookExW(id_, ref, h, 0)
            if not hk:
                self.retirer()
                raise OSError(f"SetWindowsHookExW({id_}) a échoué : {ctypes.get_last_error()}")
            self.hooks.append(hk)

    def retirer(self):
        while self.hooks:
            u32.UnhookWindowsHookEx(self.hooks.pop())

    def pomper(self, ms=50):
        """Traite les messages (c'est là que les rappels s'exécutent) ; à appeler dans le fil qui a posé les crochets."""
        u32.MsgWaitForMultipleObjects(0, None, False, ms, 0x4FF)  # QS_ALLINPUT
        msg = w.MSG()
        while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))

    def _kb(self, n, wp, lp):
        try:
            if n == 0 and wp in TOUCHE_BAS + TOUCHE_HAUT:
                s = ctypes.cast(lp, ctypes.POINTER(KBD)).contents
                if not s.flags & 0x10 and self.on_event(nom_vk(s.vk), wp in TOUCHE_BAS):
                    return 1
        except Exception:
            log.exception("rappel clavier")
        return u32.CallNextHookEx(None, n, wp, lp)

    def _ms(self, n, wp, lp):
        try:
            if n == 0 and wp != 0x200:  # 0x200 = déplacement : le chemin le plus chaud, on le laisse passer tout de suite
                s = ctypes.cast(lp, ctypes.POINTER(MSL)).contents
                code = None
                if s.flags & 1:  # injecté
                    pass
                elif wp in BOUTONS:
                    code, bas = f"mouse{BOUTONS[wp][0]}", BOUTONS[wp][1]
                elif wp in (0x20B, 0x20C):
                    code, bas = f"mouse{3 + _signe16(s.data)}", wp == 0x20B
                elif wp == 0x20A:
                    code, bas = "wheelup" if _signe16(s.data) > 0 else "wheeldown", True
                elif wp == 0x20E:
                    code, bas = "wheelright" if _signe16(s.data) > 0 else "wheelleft", True
                if code and self.on_event(code, bas):
                    return 1
        except Exception:
            log.exception("rappel souris")
        return u32.CallNextHookEx(None, n, wp, lp)


_cache = {"hwnd": None, "t": 0.0, "nom": ""}


def application_premier_plan():
    """Nom du processus de la fenêtre au premier plan, en minuscules ('' si illisible). Mis en cache 2 s par fenêtre."""
    try:
        hwnd, now = u32.GetForegroundWindow(), time.monotonic()
        if hwnd == _cache["hwnd"] and now - _cache["t"] < 2:
            return _cache["nom"]
        pid, nom = w.DWORD(), ""
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if h:
            buf, n = ctypes.create_unicode_buffer(520), w.DWORD(520)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                nom = os.path.basename(buf.value).lower()
            k32.CloseHandle(h)
        _cache.update(hwnd=hwnd, t=now, nom=nom)
        return nom
    except Exception:
        log.exception("application au premier plan")
        return ""


def _envoyer(*entrees):
    arr = (INPUT * len(entrees))(*entrees)
    if u32.SendInput(len(entrees), arr, ctypes.sizeof(INPUT)) != len(entrees):
        log.warning("SendInput incomplet : %s", ctypes.get_last_error())


def _clavier(vk=0, scan=0, flags=0):
    i = INPUT(type=1)
    i.ki = _KI(vk, scan, flags, 0, 0)
    return i


def _souris(flags, data=0):
    i = INPUT(type=0)
    i.mi = _MI(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
    return i


class Sortie:
    """Exécute les étapes ; suit ce qu'elle a enfoncé pour pouvoir tout relâcher à l'arrêt."""

    def __init__(self, arret):
        self.arret, self.enfoncees = arret, []

    def liberer(self):
        for n in reversed(self.enfoncees[:]):
            self._touche(n, False)

    def executer(self, steps):
        for s in steps:
            if self.arret.is_set():
                break
            try:
                getattr(self, "_" + s[0])(*s[1:])
            except Exception:
                log.exception("étape %r", s[0])

    def _touche(self, nom, bas):
        if bas:
            self.enfoncees.append(nom)
        elif nom in self.enfoncees:
            self.enfoncees.remove(nom)
        if nom in MOUSE:
            k = MOUSE[nom]
            if k <= 3:
                _envoyer(_souris(MOUSEEVENTF[k][0 if bas else 1]))
            else:
                _envoyer(_souris(0x80 if bas else 0x100, k - 3))
            return
        vk = vk_nom(nom)
        _envoyer(_clavier(vk, u32.MapVirtualKeyW(vk, 0), (0 if bas else 2) | (1 if vk in ETENDUES else 0)))

    def _down(self, nom):
        self._touche(nom, True)

    def _up(self, nom):
        self._touche(nom, False)

    def _wait(self, ms):
        self.arret.wait(ms / 1000)

    def _text(self, texte):
        for c in texte:
            if c in "\r\n":
                self._down("enter"), self._up("enter")
                continue
            for f in (4, 6):  # UNICODE, UNICODE | KEYUP
                _envoyer(_clavier(0, ord(c), f))

    def _wheel(self, dx, dy):
        if dy:
            _envoyer(_souris(0x800, dy))
        if dx:
            _envoyer(_souris(0x1000, dx))

    def _run(self, argv):
        # le texte vient de la configuration de l'utilisateur ; jamais de shell
        subprocess.Popen(list(argv), shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=0x8 | 0x200)

    def _url(self, url):
        os.startfile(url)
