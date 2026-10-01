# DIY Firmware-Tool: Schritt 1 und 2, eine Erklaerung aufgeklappt, Einstellungen offen
settings.setdefault("fw_last", {})["tracker"] = {"source": "all"}
at(1500, open_multiflash_window)
at(10000, lambda: shot("1_firmware"))
at(10500, lambda: click("Nächster Schritt"))
at(12000, lambda: click("?", 1))
at(13000, lambda: shot("2_bauweise"))
at(13500, lambda: click("▸ Firmware-Einstellungen (optional)"))
at(14500, lambda: scroll(0.5))
at(15500, lambda: shot("3_einstellungen"))
at(16000, done)
