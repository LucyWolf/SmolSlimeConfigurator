# Echter Flash-Test auf Lucys PC (kein Xvfb): Firmware-Art aus "info" lesen, dieselbe Bauart flashen.
import builtins
def log(*a):
    print(*a, flush=True)

def shot(name):   # auf dem PC keine Bildschirmfotos
    pass

state = {}

def read_info():
    trackers = [d for d in devices if not d.is_receiver and d.connected]
    if not trackers:
        log("KEIN TRACKER VERBUNDEN"); done(); return
    dev = trackers[0]
    state["dev"] = dev
    def work():
        lines = query_device(dev, ["info"], wait=2.0)
        target = next((l[8:] for l in lines if l.startswith("Target: ")), "")
        fw = next((l for l in lines if l.startswith("SlimeVR-")), "")
        log("Tracker:", dev.serial_number, "| Firmware vorher:", fw, "| Target:", target)
        t = target.lower()
        if "stackedspi" in t:
            opts = ["StackedSmol", "SPI", "SW0", "CLK", "Sleep"]
        elif "stackedi2c" in t:
            opts = ["StackedSmol", "I2C", "SW0", "CLK", "Sleep"]
        elif t.endswith("/spi"):
            opts = ["SPI", "Sleep"]
        else:
            opts = ["I2C", "Sleep"]
        settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": opts}}
        log("Gewaehlt:", opts)
        app.after(0, open_multiflash_window)
    threading.Thread(target=work, daemon=True).start()

def result_text():
    return [c.cget("text") for win in _windows() for c in _walk(win)
            if isinstance(c, ctk.CTkLabel) and (c.cget("text").startswith("✅") or c.cget("text").startswith("❌"))]

def report():
    texts = [c.cget("text") for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkLabel)
             and any(k in c.cget("text") for k in ("fertig", "Bootloader", "geschrieben", "kein UF2", "fehlgeschlagen",
                                                     "von ", "Fehler", "nicht zur"))]
    log("STATUS:", texts)

at(6000, read_info)                                    # Geraete verbinden sich selbst
at(26000, lambda: (log("Datei:", result_text()), click("Nächster Schritt")))
at(28000, lambda: (log("Schritt2:", result_text()), click("Nächster Schritt")))
at(29500, lambda: click("Alle verbinden"))
at(31000, lambda: click("Nächster Schritt"))
at(32500, lambda: click("Weiter zum Flashen"))
at(34000, lambda: (report(), click("⬇ Flashen starten")))
for t in range(44000, 140000, 10000):
    at(t, report)
at(141000, lambda: (report(), done()))
