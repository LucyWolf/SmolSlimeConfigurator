# Offizielle Quelle, Stacked Smol + I2C waehlen -> fehlt -> "In allen Quellen suchen" -> Datei von kounocom
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": ["SPI", "Sleep"]}}

def choose():
    radios = [c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkRadioButton) and c.winfo_ismapped()]
    next(r for r in radios if r.cget("text") == "Stacked Smol").invoke()
    next(r for r in radios if r.cget("text") == "I2C").invoke()

at(1500, open_multiflash_window)
at(9000, lambda: click("Nächster Schritt"))
at(10500, choose)
at(11500, lambda: (scroll(0.25), shot("1_fehlt")))
at(12000, lambda: click("🔍 In allen Quellen suchen"))
at(24000, lambda: (scroll(0.2), shot("2_gefunden")))
at(24500, done)
