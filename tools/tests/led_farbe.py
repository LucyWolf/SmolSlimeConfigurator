# LED-Farbe: im Firmware-Tool nur bei Farb-LED (Chrysalis ja, Stacked nein); in der Geraeteverwaltung
# meldet sich der nachgebaute Tracker als Stacked Smol -> keine LED-Farbe
exec(open("/src/tools/tests/fake_devices.py").read())
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": ["StackedSmol", "SPI", "SW0", "CLK", "Sleep"]}}

def pick(label):
    radios = [c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkRadioButton) and c.winfo_ismapped()]
    next(r for r in radios if r.cget("text") == label).invoke()

def led_visible():
    return any(isinstance(c, ctk.CTkLabel) and c.cget("text") == "Farbe im Normalbetrieb" and c.winfo_ismapped()
               for win in _windows() for c in _walk(win))

at(1500, open_multiflash_window)
at(20000, lambda: click("Nächster Schritt"))
at(21000, lambda: click("▸ Firmware-Einstellungen (optional)"))
at(22000, lambda: print("Stacked Smol -> LED-Farbe sichtbar:", led_visible(), flush=True))
at(22500, lambda: pick("Chrysalis"))
at(23500, lambda: print("Chrysalis -> LED-Farbe sichtbar:", led_visible(), flush=True))
at(24000, lambda: multi_win.destroy())

def devsettings():
    dev = get_or_add_device(FAKE_TRACKER)
    connect_device(dev, ask=False)
    open_device_settings(dev, app)
at(25000, devsettings)
at(30000, lambda: print("Geraeteverwaltung (Stacked) -> LED-Farbe sichtbar:", led_visible(), flush=True))
at(30500, done)
