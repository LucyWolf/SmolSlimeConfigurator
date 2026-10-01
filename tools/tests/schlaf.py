# Schlafmodus (WOM) als an/aus: gespeichert ist "aus" -> Kaestchen leer, Datei mit NoSleep
settings.setdefault("fw_last", {})["tracker"] = {"source": "main", "board": "ProMicro",
                                                  "options": ["StackedSmol", "SPI", "Mag", "SW0", "CLK"]}
at(1500, open_multiflash_window)
at(10000, lambda: click("Nächster Schritt"))
at(11500, lambda: click("?", 4))
at(12500, lambda: (scroll(0.25), shot("schlaf")))
at(13000, done)
