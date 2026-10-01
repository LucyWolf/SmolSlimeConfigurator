# "?" bei der Bauform zeigt die Bilder der Bauformen
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": ["StackedSmol", "SPI", "SW0", "CLK", "Sleep"]}}
at(1500, open_multiflash_window)
at(20000, lambda: click("Nächster Schritt"))
at(21500, lambda: click("?", 0))
at(22500, lambda: (scroll(0.2), shot("bilder")))
at(23000, done)
