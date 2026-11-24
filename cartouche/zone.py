"""Icône dans la zone de notification (Shell_NotifyIcon par ctypes, rien à installer).
Zone(titre, entrees, ouvrir) : `entrees()` renvoie [(id, libellé, rappel)] à chaque ouverture du menu ; double-clic = `ouvrir`."""
import ctypes
import ctypes.wintypes as w
import logging
import threading

log = logging.getLogger("cartouche.zone")
u32 = ctypes.WinDLL("user32", use_last_error=True)
sh = ctypes.WinDLL("shell32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

WM_CLOSE, WM_DESTROY, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_CONTEXTMENU, WM_NULL, WM_APP = 0x10, 0x2, 0x203, 0x205, 0x7B, 0, 0x8000
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
NIIF_WARNING = 2
HWND_MESSAGE = -3
RETOUR = WM_APP + 1


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", w.UINT), ("proc", WNDPROC), ("cls", ctypes.c_int), ("wnd", ctypes.c_int), ("inst", w.HINSTANCE),
                ("icon", w.HICON), ("cursor", w.HANDLE), ("fond", w.HBRUSH), ("menu", w.LPCWSTR), ("nom", w.LPCWSTR)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("hwnd", w.HWND), ("id", w.UINT), ("flags", w.UINT), ("retour", w.UINT), ("icon", w.HICON),
                ("tip", w.WCHAR * 128), ("etat", w.DWORD), ("masque", w.DWORD), ("info", w.WCHAR * 256), ("version", w.UINT),
                ("titre", w.WCHAR * 64), ("info_flags", w.DWORD), ("guid", ctypes.c_ubyte * 16), ("icone_info", w.HICON)]


u32.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u32.DefWindowProcW.restype = LRESULT
u32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
u32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
u32.CreateWindowExW.restype = w.HWND
u32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u32.LoadIconW.argtypes = [w.HINSTANCE, ctypes.c_void_p]
u32.LoadIconW.restype = w.HICON
u32.CreatePopupMenu.restype = w.HMENU
u32.AppendMenuW.argtypes = [w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR]
u32.TrackPopupMenu.argtypes = [w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, ctypes.c_void_p]
u32.DestroyMenu.argtypes = [w.HMENU]
u32.SetForegroundWindow.argtypes = [w.HWND]
u32.DestroyWindow.argtypes = [w.HWND]
u32.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
sh.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.POINTER(NOTIFYICONDATA)]
k32.GetModuleHandleW.argtypes = [w.LPCWSTR]
k32.GetModuleHandleW.restype = w.HMODULE


class Zone:
    def __init__(self, titre, entrees, ouvrir):
        self.titre, self.entrees, self.ouvrir = titre[:127], entrees, ouvrir
        self.hwnd, self.fil, self.pret, self.ok = None, None, threading.Event(), False
        self._proc = WNDPROC(self._wndproc)  # garder en vie

    def demarrer(self, delai=5.0):
        """Pose l'icône ; renvoie False si Windows la refuse (l'application continue sans)."""
        self.fil = threading.Thread(target=self._boucle, name="zone", daemon=True)
        self.fil.start()
        self.pret.wait(delai)
        return self.ok

    def arreter(self):
        if self.hwnd and self.fil and self.fil.is_alive():
            u32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            self.fil.join(3)

    def notifier(self, titre, texte):
        """Bulle de notification (alerte de batterie)."""
        if not self.ok:
            return
        d = self._donnees(NIF_INFO)
        d.info, d.titre, d.info_flags = texte[:255], titre[:63], NIIF_WARNING
        sh.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d))

    def _donnees(self, flags):
        d = NOTIFYICONDATA()
        d.cb, d.hwnd, d.id, d.flags = ctypes.sizeof(d), self.hwnd, 1, flags
        return d

    def _boucle(self):
        try:
            inst = k32.GetModuleHandleW(None)
            c = WNDCLASS()
            c.proc, c.inst, c.nom = self._proc, inst, "CartoucheZone"
            u32.RegisterClassW(ctypes.byref(c))  # déjà enregistrée : sans importance, la classe existante sert
            self.hwnd = u32.CreateWindowExW(0, "CartoucheZone", "Cartouche", 0, 0, 0, 0, 0, HWND_MESSAGE, None, inst, None)
            if not self.hwnd:
                raise OSError(f"CreateWindowExW : {ctypes.get_last_error()}")
            d = self._donnees(NIF_MESSAGE | NIF_ICON | NIF_TIP)
            d.retour, d.icon, d.tip = RETOUR, u32.LoadIconW(None, 32512), self.titre  # IDI_APPLICATION
            self.ok = bool(sh.Shell_NotifyIconW(NIM_ADD, ctypes.byref(d)))
            if not self.ok:
                log.warning("Shell_NotifyIcon a refusé l'icône (%s)", ctypes.get_last_error())
        except Exception:
            log.exception("icône de la zone de notification")
            self.ok = False
        finally:
            self.pret.set()
        if not self.ok:
            return
        msg = w.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))

    def _wndproc(self, hwnd, m, wp, lp):
        try:
            if m == RETOUR and lp in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._menu(hwnd)
            elif m == RETOUR and lp == WM_LBUTTONDBLCLK:
                threading.Thread(target=self.ouvrir, daemon=True).start()
            elif m == WM_CLOSE:
                u32.DestroyWindow(hwnd)
                return 0
            elif m == WM_DESTROY:
                sh.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._donnees(0)))
                u32.PostQuitMessage(0)
                return 0
        except Exception:
            log.exception("message de la zone de notification")
        return u32.DefWindowProcW(hwnd, m, wp, lp)

    def _menu(self, hwnd):
        entrees = self.entrees()
        menu = u32.CreatePopupMenu()
        for i, (_, libelle, _) in enumerate(entrees, 1):
            u32.AppendMenuW(menu, 0, i, libelle)
        pt = w.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        u32.SetForegroundWindow(hwnd)  # sans cela le menu ne se ferme pas quand on clique ailleurs
        choix = u32.TrackPopupMenu(menu, 0x100 | 0x2, pt.x, pt.y, 0, hwnd, None)  # TPM_RETURNCMD | TPM_RIGHTBUTTON
        u32.PostMessageW(hwnd, WM_NULL, 0, 0)
        u32.DestroyMenu(menu)
        if choix:
            threading.Thread(target=entrees[choix - 1][2], daemon=True).start()
