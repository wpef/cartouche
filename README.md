# Cartouche

Unofficial configurator for the **8BitDo Retro Mechanical Keyboard** and the **Retro R8 mouse**: key and button remapping, profiles ("cartridges"), and software-side features the hardware cannot do (per-application profiles, layers, tap/hold keys, macros). Not affiliated with 8BitDo. **It never flashes firmware** and never touches the firmware-update HID report (`0xB2`).

Pure Python (3.13) plus `ctypes`: no compiled code, no admin rights, no registry changes. The only dependency is `hidapi`. Windows 11 only.

One command starts everything in a single process: a local web interface, the software engine, and a notification-area icon.

```
cartouche.cmd                      (or: .venv\Scripts\python -m cartouche app)
```

## What works, honestly

| Function | State |
|---|---|
| Keyboard: read profile name, key assignments, macros | tried on hardware |
| Keyboard: create/delete profile, assign a key, restore factory state | tried on hardware (write, then read-back check) |
| Keyboard: macro writing | implemented, **not tried** (format unverified, disabled in the UI) |
| Mouse: read buttons, DPI stages, battery; reassign buttons | implemented, **not tried** (no mouse adapter on the test machine) |
| Mouse: DPI writing, polling rate, lift-off distance, wheel | not possible yet (protocol unknown) |
| Backups before every write, read-back after, import/export of the whole cartridge | tried (simulated devices and keyboard) |
| Software engine: hooks, remaps, chords, layers, tap/long/double, per-app profiles, emergency stop | hooks tried on Windows with a harmless rule (F24 only); logic covered by unit tests |
| Engine rules that send keys or actions (text, run, URL, macros) | implemented and unit-tested, **not tried** live |
| "Logiciel" screen (engine state, forms, JSON editor, hot reload, pause list) | tried in a browser in demo mode and against the real engine |
| Notification-area icon (open / pause-resume / quit, double-click opens) | tried (menu clicks not exercised by hand) |
| Low-battery balloon (mouse below 20 %) | implemented and unit-tested, **not tried** (needs the mouse) |
| Start with Windows (a `.cmd` in your Startup folder, only when you tick the box) | implemented, **not tried** |
| "Menu" key | the keyboard has none: both reference projects make `menu` an alias of the **A** button (hardware code `0x6D`); implemented that way, **not tried** |

## Install and run

```
py -3.13 -m venv .venv
.venv\Scripts\pip install -e .
cartouche.cmd                        # opens http://127.0.0.1:8737/
cartouche.cmd --demo                 # simulated devices and engine: nothing is written or intercepted
```

Options of `python -m cartouche app`: `--demo`, `--port N`, `--donnees <folder>` (where `cartouche.json` lives; default `%APPDATA%\Cartouche`), `--dir <folder>` (backups; default `<donnees>\sauvegardes`), `--duree <seconds>` (auto-quit, for tests), `--sans-navigateur` (no browser), `--sans-icone` (no tray icon). The command-line tools remain: `python -m cartouche list|dump|map|unmap|profile|macro|mouse|apply|restore` (`--dry-run` sends nothing).

Your single cartridge is `%APPDATA%\Cartouche\cartouche.json` (`clavier`, `souris`, `logiciel`). The app updates it after each hardware write and each engine save; import/export in the "Cartouche" screen carry all three parts.

**Hardware limits.** The keyboard must be connected **by cable with the side switch OFF** (the 2.4 GHz receiver and Bluetooth do not expose the configuration channel). The mouse needs its **2.4 GHz adapter**. The window says what it can see and tells you when a device appears or disappears.

**Engine.** It hooks keyboard and mouse input and applies your rules. **Emergency stop: Ctrl+Alt+Pause** toggles the engine at any time (hard-coded; no rule can remap it). Events it injects are never reprocessed. Rule format: [docs/moteur.md](docs/moteur.md). It cannot see elevated (administrator) windows.

## Security

The server listens on `127.0.0.1` only; the `Host` header is checked; every `POST` needs a random per-launch token; inputs are validated server-side (the engine configuration is compiled before it is saved or reloaded); the port is bound exclusively. Engine rules can launch programs and open URLs (http/https/mailto only, never through a shell), so treat `cartouche.json` like a script. Nothing is sent over the network.

## Limits

Windows only; Python 3.13; keyboard by cable (switch OFF) only; mouse through the 2.4 GHz adapter only; no firmware access, ever; macros stay read-only until their format is confirmed on hardware; the tray icon is the stock Windows application icon.

Protocol knowledge builds on [goncalor/8bitdo-kbd-mapper](https://github.com/goncalor/8bitdo-kbd-mapper), [Aryaman73/8db-retro-config](https://github.com/Aryaman73/8db-retro-config), [KilnerJhow/retro87-configurator](https://github.com/KilnerJhow/retro87-configurator) and [mbs1337/r8-rs](https://github.com/mbs1337/r8-rs). See [NOTICE.md](NOTICE.md).

License: GPL-3.0-or-later.
