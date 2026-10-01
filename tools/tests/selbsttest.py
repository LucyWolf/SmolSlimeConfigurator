# Wie der Selbsttest im Build: Fenster + Firmware-Tool oeffnen, Bild, beenden
at(2000, open_multiflash_window)
at(9000, lambda: shot("selbsttest"))
at(9500, done)
