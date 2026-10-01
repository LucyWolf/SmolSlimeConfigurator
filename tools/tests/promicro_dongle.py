# ProMicro mit Tracker-Firmware soll Dongle werden: auswaehlbar, markiert, Sicherung fragt nach
exec(open("/src/tools/tests/fake_devices.py").read())
serial.tools.list_ports.comports = lambda: [FAKE_TRACKER]
settings["fw_last"] = {"tracker": {"source": "main"}}
import tkinter.messagebox as _mb
asked = []
_mb.askyesno = lambda title, msg, **k: (asked.append(msg), False)[1]   # Sicherung: "Nein"

def to_dongle():
    seg = next(c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkSegmentedButton) and c.winfo_ismapped())
    seg.set("Dongle"); seg._command("Dongle")

def pick_board(name):
    menu = next(c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkOptionMenu) and c.winfo_ismapped()
                and name in c.cget("values"))
    menu.set(name); menu._command(name)

def status():
    return [c.cget("text") for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkLabel)
            and ("umgeflasht" in c.cget("text") or "Abgebrochen" in c.cget("text"))]

def add_tracker_row():
    click("+ Gerät")
    menus = [c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkOptionMenu) and c.winfo_ismapped()]
    m = next(x for x in menus if any("Tracker" in v for v in x.cget("values")))
    v = next(v for v in m.cget("values") if "Tracker" in v)
    m.set(v)

at(1500, open_multiflash_window)
at(20000, to_dongle)
at(20500, lambda: pick_board("ProMicro"))
at(21500, lambda: click("Nächster Schritt"))
at(22500, lambda: click("Nächster Schritt"))
at(23000, add_tracker_row)
at(23500, lambda: click("Alle verbinden"))
at(24500, lambda: print("Schritt 3:", status(), flush=True))
at(25000, lambda: click("Nächster Schritt"))
at(25500, lambda: click("Weiter zum Flashen"))
at(26500, lambda: click("⬇ Flashen starten"))
at(29500, lambda: print("Sicherung gefragt:", bool(asked), "|", status(), flush=True))
at(30000, done)
