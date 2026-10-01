# Offizielle Quelle, Version "latest (stabil)": Stacked Smol + I2C + Schlafmodus aus wie in Lucys Link
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro",
                                   "options": ["StackedSmol", "I2C", "SW0", "CLK"]}}
at(1500, open_multiflash_window)
at(12000, lambda: shot("1_version"))
at(12500, lambda: click("Nächster Schritt"))
at(14000, lambda: (scroll(0.2), shot("2_bauweise")))
at(14500, done)
