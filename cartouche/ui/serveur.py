"""Serveur local : 127.0.0.1 seulement, en-tête Host vérifié, jeton exigé pour toute requête qui modifie."""
import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ..transport import Erreur, NonPris
from . import api, logiciel  # noqa: F401  (enregistre les routes de l'écran Logiciel)

STATIC = Path(__file__).parent / "static"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".svg": "image/svg+xml"}
MAX_CORPS = 1_000_000
CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class Serveur(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # sous Windows, SO_REUSEADDR laisserait deux instances (ou un intrus) se lier au même port

    def __init__(self, app, port=0):
        super().__init__(("127.0.0.1", port), Handler)
        self.app, self.jeton = app, secrets.token_urlsafe(24)
        p = self.server_address[1]
        self.hotes = {f"127.0.0.1:{p}", f"localhost:{p}"}


class Handler(BaseHTTPRequestHandler):
    server_version = "Cartouche"

    def log_message(self, *a):
        pass

    def _envoyer(self, code, corps, type_="application/json; charset=utf-8"):
        if not isinstance(corps, bytes):
            corps = json.dumps(corps, ensure_ascii=False).encode()
        self.send_response(code)
        for k, v in (("Content-Type", type_), ("Content-Length", len(corps)), ("Cache-Control", "no-store"),
                     ("X-Content-Type-Options", "nosniff"), ("Content-Security-Policy", CSP), ("Referrer-Policy", "no-referrer")):
            self.send_header(k, str(v))
        self.end_headers()
        self.wfile.write(corps)

    def _erreur(self, code, msg):
        self._envoyer(code, {"erreur": msg})

    def _traiter(self, methode):
        if self.headers.get("Host") not in self.server.hotes:
            return self._erreur(403, "hôte refusé")
        u = urlsplit(self.path)
        if methode == "GET" and not u.path.startswith("/api/"):
            return self._statique(u.path)
        f = api.ROUTES.get((methode, u.path))
        if f is None:
            return self._erreur(404, "route inconnue")
        body = {}
        if methode == "POST":
            if not hmac.compare_digest(self.headers.get("X-Jeton", ""), self.server.jeton):
                return self._erreur(403, "jeton manquant ou faux")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if not 0 <= n <= MAX_CORPS:
                    return self._erreur(413, "corps trop gros")
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._erreur(400, "JSON attendu : un objet")
        try:
            self._envoyer(200, f(self.server.app, parse_qs(u.query), body))
        except api.Invalide as e:
            self._erreur(400, str(e))
        except api.Bloque as e:
            self._erreur(409, str(e))
        except NonPris as e:
            self._erreur(501, f"protocole pas encore connu : {e}")
        except Erreur as e:
            self._erreur(502, str(e))

    def _statique(self, chemin):
        nom = "index.html" if chemin == "/" else chemin.removeprefix("/static/") if chemin.startswith("/static/") else None
        p = STATIC / nom if nom and "/" not in nom and "\\" not in nom else None
        if p is None or not p.is_file() or p.suffix not in TYPES:
            return self._erreur(404, "introuvable")
        corps = p.read_bytes()
        if nom == "index.html":
            corps = corps.replace(b"__JETON__", self.server.jeton.encode())
        self._envoyer(200, corps, TYPES[p.suffix])

    def do_GET(self):
        self._traiter("GET")

    def do_POST(self):
        self._traiter("POST")
