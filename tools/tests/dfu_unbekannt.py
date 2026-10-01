# Firmware ohne dfu-Befehl: App muss "bitte zweimal Reset druecken" anzeigen
exec(open("/src/tools/tests/fake_devices.py").read())
serial.tools.list_ports.comports = lambda: [FAKE_TRACKER]
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": ["StackedSmol", "SPI", "SW0", "CLK", "Sleep"]}}

def status():
    return [c.cget("text") for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkLabel)
            and ("Reset" in c.cget("text") or "Bootloader" in c.cget("text") or "UF2" in c.cget("text"))]

at(1500, open_multiflash_window)
at(20000, lambda: click("Nächster Schritt"))
at(21000, lambda: click("Nächster Schritt"))
at(22000, lambda: click("Alle verbinden"))
at(23000, lambda: click("Nächster Schritt"))
at(24000, lambda: click("Weiter zum Flashen"))
at(25000, lambda: click("⬇ Flashen starten"))
at(30000, lambda: print("STATUS:", status(), flush=True))
at(30500, done)
