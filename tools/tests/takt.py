# Sensor-Takt: neue Beschriftung und aufgeklappte Erklaerung
settings.setdefault("fw_last", {})["tracker"] = {"source": "main", "board": "ProMicro",
                                                  "options": ["StackedSmol", "SPI", "Mag", "NoSleep", "SW0"]}
at(1500, open_multiflash_window)
at(10000, lambda: click("Nächster Schritt"))
at(11500, lambda: click("?", 4))
at(12500, lambda: (scroll(0.25), shot("takt")))
at(13000, done)
