# Nicht vorhandene Kombination (Stacked Smol + SPI + Mag + NoSleep + SW0): Vorschlaege anzeigen, ersten anklicken
settings.setdefault("fw_last", {})["tracker"] = {"source": "main", "board": "ProMicro",
                                                  "options": ["StackedSmol", "SPI", "Mag", "NoSleep"]}

def pick_sw0():
    boxes = [c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkCheckBox) and c.winfo_ismapped()]
    for b in boxes:
        if b.cget("variable") and str(b.cget("variable")):
            pass
    # SW0-Kaestchen ist das vierte Kontrollkaestchen (Magnetometer, Schlafmodus, SW0, TDMA)
    sw0 = [b for b in boxes if b.cget("text") == "An"][2]
    sw0.toggle()

at(1500, open_multiflash_window)
at(10000, lambda: click("Nächster Schritt"))
at(11500, pick_sw0)
at(12500, lambda: (scroll(0.25), shot("1_vorschlaege")))
at(13000, lambda: click("Taster an SW0 aus"))
at(14000, lambda: shot("2_angewendet"))
at(14500, done)
