# Schritt 5, aber das Geraet ist abgezogen: es muss ein Fehler dastehen
exec(open("/src/tools/tests/fake_devices.py").read())
plugged = [FAKE_TRACKER]
serial.tools.list_ports.comports = lambda: list(plugged)
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": ["StackedSmol", "SPI", "SW0", "CLK", "Sleep"]}}

at(1500, open_multiflash_window)
at(20000, lambda: click("Nächster Schritt"))
at(21000, lambda: click("Nächster Schritt"))          # -> Schritt 3
at(22000, lambda: click("Alle verbinden"))
at(23000, lambda: click("Nächster Schritt"))          # -> Schritt 4
at(23500, lambda: (scroll(0.6), shot("schritt4")))
at(24000, lambda: click("Weiter zum Flashen"))         # -> Schritt 5
def unplug():
    plugged.clear()
    for d in devices:
        device_lost(d, "abgezogen\n")
at(25000, unplug)
at(27000, lambda: (multi_win.lift(), scroll(1.0), shot("schritt5")))
at(27500, done)
