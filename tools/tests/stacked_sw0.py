# Stacked Smol gewaehlt: SW0 ist automatisch an und gesperrt, Datei wird gefunden
settings.setdefault("fw_last", {})["tracker"] = {"source": "main", "board": "ProMicro",
                                                  "options": ["StackedSmol", "SPI", "Mag", "NoSleep", "SW0"]}
at(1500, open_multiflash_window)
at(10000, lambda: click("Nächster Schritt"))
at(12000, lambda: (scroll(0.25), shot("stacked")))
at(12500, done)
