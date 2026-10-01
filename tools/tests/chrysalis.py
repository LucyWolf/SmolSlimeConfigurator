# Von Stacked Smol + I2C + Takt aus auf Chrysalis wechseln: SPI, Takt, Taster stellen sich ein und sperren
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro",
                                   "options": ["StackedSmol", "I2C", "SW0", "Sleep"]}}

def pick(label):
    radios = [c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkRadioButton) and c.winfo_ismapped()]
    next(r for r in radios if r.cget("text") == label).invoke()

at(1500, open_multiflash_window)
at(9000, lambda: click("Nächster Schritt"))
at(10500, lambda: (scroll(0.2), shot("1_stacked")))
at(11000, lambda: pick("Chrysalis"))
at(12000, lambda: (scroll(0.2), shot("2_chrysalis")))
at(12500, lambda: pick("Normal (Non-Stacked)"))
at(13500, lambda: (scroll(0.2), shot("3_normal")))
at(14000, done)
