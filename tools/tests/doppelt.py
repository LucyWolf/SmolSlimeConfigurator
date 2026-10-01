# Firmware-Tool: Magnetometer und Sensor-Takt nicht doppelt in den optionalen Einstellungen
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": ["StackedSmol", "SPI", "SW0", "CLK", "Sleep"]}}

def count(text):
    return sum(1 for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkLabel) and c.cget("text") == text)

at(1500, open_multiflash_window)
at(20000, lambda: click("Nächster Schritt"))
at(21000, lambda: click("▸ Firmware-Einstellungen (optional)"))
at(22000, lambda: print("Takt oben:", count("Sensor-Takt (CLK_CTL)"), "| Magnetometer oben:", count("Magnetometer"), "| unten:", count("Magnetometer benutzen"),
                         "| Takt unten:", count("Sensor-Takt (CLK_CTL) benutzen"), flush=True))
at(22500, done)
