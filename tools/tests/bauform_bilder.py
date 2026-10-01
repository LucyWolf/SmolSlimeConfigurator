# "?" bei der Bauform zeigt die Bilder der Bauformen
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro", "options": ["StackedSmol", "SPI", "SW0", "CLK", "Sleep"]}}
at(1500, open_multiflash_window)
at(20000, lambda: click("Nächster Schritt"))
at(21500, lambda: click("?", 0))
at(22500, lambda: (scroll(0.2), shot("bilder")))


# Bild anklicken -> grosses Fenster
def click_first_image():
    pics = [c for win in _windows() for c in _walk(win) if isinstance(c, tk.Label) and getattr(c, "image", None)]
    pics[0].event_generate("<Button-1>")
at(23200, click_first_image)
at(25000, lambda: shot("gross"))
at(25500, done)
