# Quellen mit Link-Knopf; Sensor-Anschluss nur SPI/I2C, smSPI als eigenes Kaestchen (Alle Quellen, ProMicro)
settings.setdefault("fw_last", {})["tracker"] = {"source": "all"}
opened = []
webbrowser.open = lambda url: opened.append(url) or print("Browser:", url, flush=True)
at(1500, open_multiflash_window)
at(11000, lambda: shot("1_quellen"))
at(11500, lambda: click("↗"))
at(12000, lambda: click("Nächster Schritt"))
at(13500, lambda: (scroll(0.2), shot("2_anschluss")))
at(14000, done)
