# Umschalter Dongle: Holyiot wird erkannt, Schritt 4 zeigt die nRF-Connect-Anleitung
exec(open("/src/tools/tests/fake_devices.py").read())
serial.tools.list_ports.comports = lambda: [FAKE_DONGLE]
settings["fw_last"] = {"tracker": {"source": "main"}}

def to_dongle():
    seg = next(c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkSegmentedButton) and c.winfo_ismapped())
    seg.set("Dongle")
    seg._command("Dongle")

at(1500, open_multiflash_window)
at(20000, to_dongle)
at(21000, lambda: shot("1_dongle"))
at(21500, lambda: click("Nächster Schritt"))
at(22500, lambda: click("Nächster Schritt"))
at(23500, lambda: click("Alle verbinden"))
at(24500, lambda: click("Nächster Schritt"))
at(26000, lambda: (scroll(1.0), shot("2_anleitung")))
at(26500, done)
