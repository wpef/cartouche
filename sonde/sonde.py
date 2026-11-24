"""Sonde lot 0 : lecture seule. Liste blanche stricte, rien d'autre ne part vers le materiel."""
import hid, time, datetime, sys

VID = 0x2DC8
out = []
def log(s=""):
    print(s); out.append(s)
hx = lambda b: " ".join(f"{x:02x}" for x in b)

# --- liste blanche -------------------------------------------------------
KBD = [("profil", [0x80]), ("touches reaffectees", [0x81, 0x00])] + \
      [(f"affectation hwkey {k:#04x}", [0x83, 0x04, k]) for k in (0x01, 0x02, 0x04, 0x0C)]
MOUSE = [("DPI", [0x01, 0x06, 0x12, 0x01])] + \
        [(f"bouton {b}", [0x01, 0x06, 0x10, 0x01, 0x00, b]) for b in range(6)] + \
        [("batterie", [0x01, 0x06, 0x1A, 0x01])]
# -------------------------------------------------------------------------

def drain(d):
    while d.read(64): pass

def kbd_xfer(d, body):
    drain(d)
    d.write(bytes([0x52] + body + [0] * (32 - len(body))))  # 33 octets
    time.sleep(0.001)
    r = []
    end = time.time() + 0.35
    while time.time() < end:
        x = d.read(64)
        if x: r.append(bytes(x))
        elif r: break
        else: time.sleep(0.005)
    return r

def mouse_xfer(d, body):
    drain(d)
    d.write(bytes([0x00] + body + [0] * (64 - len(body))))  # id 0 (pas d'id) + 64
    time.sleep(0.05)
    r = []
    end = time.time() + 0.35
    while time.time() < end:
        x = d.read(64)
        if x: r.append(bytes(x))
        else: time.sleep(0.005)
    return r

log(f"# sonde {datetime.datetime.now().isoformat(timespec='seconds')} hidapi {hid.version_str()}")
devs = sorted(hid.enumerate(VID), key=lambda d: (d["product_id"], d["interface_number"], d["usage_page"], d["usage"]))
log("\n## Interfaces")
for d in devs:
    log(f"{d['product_id']:04X} if{d['interface_number']} up={d['usage_page']:#06x} u={d['usage']:#04x} "
        f"'{d['product_string']}' {d['path'].decode(errors='replace')}")

def vendor(d):  # seules collections ouvertes : fournisseur
    return d["usage_page"] == 0x8C or d["usage_page"] >= 0xFF00

for d in devs:
    if not vendor(d): continue
    h = hid.device()
    try:
        h.open_path(d["path"]); h.set_nonblocking(True)
    except Exception as e:
        log(f"\n## {d['product_id']:04X} up={d['usage_page']:#x} ouverture impossible : {e}"); continue
    log(f"\n## {d['product_id']:04X} if{d['interface_number']} up={d['usage_page']:#x} u={d['usage']:#x}")
    try:
        log("descripteur : " + hx(h.get_report_descriptor()))
    except Exception as e:
        log(f"descripteur indisponible : {e}")
    plan = KBD if d["product_id"] in (0x5200, 0x5201) and d["usage_page"] == 0x8C else \
           MOUSE if d["product_id"] == 0x5206 and d["usage_page"] == 0xFF00 else []
    xfer = kbd_xfer if plan is KBD else mouse_xfer
    for name, body in plan:
        try:
            r = xfer(h, body)
        except Exception as e:
            log(f"[{name}] envoi {hx(body)} -> ERREUR {e}"); continue
        log(f"[{name}] envoi {hx(body)} -> " + (" | ".join(hx(x) for x in r) if r else "aucune reponse"))
        time.sleep(0.001)
    h.close()

open(f"captures/sonde-{datetime.datetime.now():%Y%m%d-%H%M%S}.txt", "w", encoding="utf-8").write("\n".join(out))
